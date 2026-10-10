// Standard browser-test instrumentation, limited to a fresh owned headless Edge.
// No production DevTools workflow, security-policy flags, or user profile access.
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const [browser,profile,fixture,dpr,output]=process.argv.slice(2);
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let child,socket,seq=0;const pending=new Map();
async function call(method,params={}) {
  const id=++seq;
  return await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{pending.delete(id);reject(Error('Browser test command timeout: '+method));},10000);
    pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value);},reject:err=>{clearTimeout(timer);reject(err);}});
    socket.send(JSON.stringify({id,method,params}));
  });
}
async function main() {
  child=spawn(browser,['--headless=new','--no-first-run','--no-default-browser-check','--disable-background-networking',
    '--user-data-dir='+profile,'--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--force-device-scale-factor='+dpr,'--window-size=1320,1060','about:blank'],{stdio:'ignore',windowsHide:true});
  const active=path.join(profile,'DevToolsActivePort');
  for(let i=0;i<80&&!fs.existsSync(active);i++)await delay(125);
  if(!fs.existsSync(active))throw Error('Own Edge test endpoint unavailable');
  const port=Number(fs.readFileSync(active,'utf8').split('\n')[0]);
  if(!Number.isInteger(port)||port<1||port>65535)throw Error('Invalid local test port');
  const pages=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page=pages.find(p=>p.type==='page'&&p.url==='about:blank');
  if(!page || !page.webSocketDebuggerUrl.startsWith(`ws://127.0.0.1:${port}/`))throw Error('Own blank fixture target missing');
  socket=new WebSocket(page.webSocketDebuggerUrl);
  socket.addEventListener('message',event=>{
    const message=JSON.parse(event.data),p=pending.get(message.id);
    if(p){pending.delete(message.id);message.error?p.reject(Error(JSON.stringify(message.error))):p.resolve(message.result);}
  });
  await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
  await call('Page.enable');
  await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:path.dirname(output)});
  await call('Page.navigate',{url:fixture});
  let text='';
  for(let i=0;i<80&&!text;i++) {
    const r=await call('Runtime.evaluate',{expression:"document.getElementById('fixture-payload')?.textContent || ''",returnByValue:true});
    text=r.result?.value||'';if(!text)await delay(125);
  }
  if(!text)throw Error('Bookmarklet fixture did not produce a payload');
  const payload=JSON.parse(text);
  await call('Runtime.evaluate',{expression:"window.fixturePicker.querySelectorAll('button')[2].click()"});
  const downloaded=path.join(path.dirname(output),`result.${payload.token}.json`);
  for(let i=0;i<80&&!fs.existsSync(downloaded);i++)await delay(125);
  if(!fs.existsSync(downloaded)||fs.readFileSync(downloaded,'utf8')!==text)throw Error('Actual JSON download did not match exported payload');
  const actual=await call('Runtime.evaluate',{expression:'JSON.stringify([innerWidth,innerHeight,devicePixelRatio])',returnByValue:true});
  const current=JSON.parse(actual.result.value);
  if(current[0]!==payload.viewport[0]||current[1]!==payload.viewport[1]||current[2]!==payload.dpr)throw Error('Viewport changed between export and screenshot');
  const raster=await call('Page.captureScreenshot',{format:'png',fromSurface:true});
  fs.writeFileSync(output,Buffer.from(raster.data,'base64'));
  process.stdout.write(text);
}
main().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;}).finally(async()=>{
  try {if(socket?.readyState===WebSocket.OPEN)await call('Browser.close');}catch(_){}
  socket?.close();
  if(child && child.exitCode===null) {
    for(let i=0;i<40 && child.exitCode===null;i++)await delay(125);
    if(child.exitCode===null)child.kill();
  }
});
