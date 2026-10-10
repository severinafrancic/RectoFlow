// Ausschliesslich lokal: keine Netzwerkzugriffe, URLs, Cookies oder Textinhalte.
(() => {
  'use strict';
  const token = '__SESSION_TOKEN__';
  const created = __SESSION_STARTED__;
  if (Date.now() < created || Date.now()-created > 180000) throw new Error('Picker-Sitzung abgelaufen.');
  const key = '__edgeCaptureLocalPicker';
  if (window !== window.top) throw new Error('DOM_PICKER_FAILED: Top-Frame der Seite auswaehlen.');
  if (window[key]) window[key].cleanup();
  const abort = new AbortController();
  const names = ['PAGES', 'NEXT', 'PROGRESS'];
  const colors = [[239,17,131], [17,239,131], [131,17,239], [239,131,17]];
  const chosen = {};
  const candidates = [];
  let step = 0, ready = false, hovered = null, timeout;
  const host = document.createElement('div');
  host.style.cssText = 'all:initial!important;position:fixed!important;inset:0!important;pointer-events:none!important;z-index:2147483647!important;';
  const shadow = host.attachShadow({mode:'closed'});
  const panel = document.createElement('div');
  panel.style.cssText = 'position:fixed;right:12px;top:12px;max-width:440px;background:#132030;color:white;padding:12px;font:15px Arial;border:2px solid white;pointer-events:auto;';
  const line = document.createElement('div');
  const skip = document.createElement('button');
  skip.textContent = 'Seiten fertig / weiter (ESC)';
  const cancel = document.createElement('button');
  cancel.textContent = 'Abbrechen / entfernen';
  const copyButton = document.createElement('button');
  copyButton.textContent = 'Ergebnisdatei speichern';
  copyButton.hidden = true;
  const textarea = document.createElement('textarea');
  textarea.hidden = true;
  textarea.readOnly = true;
  textarea.style.cssText = 'width:400px;height:80px;';
  panel.append(line, skip, cancel, copyButton, textarea);
  const highlight = document.createElement('div');
  highlight.style.cssText = 'position:fixed;pointer-events:none;border:3px solid #ffd530;box-sizing:border-box;background:rgba(255,213,48,.12);';
  // Eine durchgehende Flaeche faengt auch spaeter eingefuegte, bewegte und
  // Shadow-DOM-Frames ab. Auswahl hit-testet synchron durch diese Flaeche.
  const shield = document.createElement('div');
  shield.style.cssText = 'position:fixed;inset:0;pointer-events:auto;background:transparent;z-index:1;';
  shadow.append(shield, panel, highlight);
  const beacon = document.createElement('div');
  beacon.style.cssText = 'position:fixed;left:12px;top:12px;width:16px;height:16px;background:rgb(217,227,37);pointer-events:none;';
  shadow.append(beacon);
  document.documentElement.append(host);
  const starting = {w:innerWidth,h:innerHeight,dpr:devicePixelRatio,x:scrollX,y:scrollY};
  const markers = [];
  function cleanup() {
    abort.abort(); clearTimeout(timeout); host.remove();
    if (window[key]?.token === token) delete window[key];
  }
  window[key] = {token, cleanup};
  const on = (node, event, fn) => node.addEventListener(event, fn, {capture:true,passive:false,signal:abort.signal});
  function elementAt(x,y) {
    shield.style.pointerEvents = 'none';
    try {
      let el = document.elementFromPoint(x,y);
      while (el?.shadowRoot) {
        const inner = el.shadowRoot.elementFromPoint(x,y);
        if (!inner || inner === el) break;
        el = inner;
      }
      return el && el !== host && el !== document.documentElement ? el : null;
    } finally {shield.style.pointerEvents = 'auto';}
  }
  function hover(el) {
    hovered = el;
    highlight.hidden = !el;
    if (el) {
      const r = el.getBoundingClientRect();
      Object.assign(highlight.style,{left:r.left+'px',top:r.top+'px',width:r.width+'px',height:r.height+'px'});
    }
  }
  function pageElement(el) {
    return el?.closest?.('[data-page-wrapper]') || el;
  }
  function visibleRect(el) {
    if (!el || el === host) return null;
    const r=el.getBoundingClientRect();
    let l=Math.max(0,r.left),t=Math.max(0,r.top),b=Math.min(innerHeight,r.bottom),right=Math.min(innerWidth,r.right);
    for(let node=el;node;node=node.parentElement || node.getRootNode?.().host) {
      const s=getComputedStyle(node);
      if(s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0||s.contentVisibility==='hidden'||node.hidden) return null;
      if(node!==el && /(hidden|clip|scroll|auto)/.test(s.overflowX+' '+s.overflowY)) {
        const clip=node.getBoundingClientRect();
        if(/(hidden|clip|scroll|auto)/.test(s.overflowX)){l=Math.max(l,clip.left);right=Math.min(right,clip.right);}
        if(/(hidden|clip|scroll|auto)/.test(s.overflowY)){t=Math.max(t,clip.top);b=Math.min(b,clip.bottom);}
      }
    }
    if(right<=l || b<=t) return null;
    // Check actual paint hit-test as well as styles. The own transparent shield
    // is temporarily excluded; page overlays inside a wrapper count as the page.
    const positions=[[.5,.5],[.25,.25],[.75,.25],[.25,.75],[.75,.75]];
    if(!positions.some(([x,y])=>{const hit=elementAt(l+(right-l)*x,t+(b-t)*y);return hit && (hit===el||el.contains(hit));}))return null;
    return {left:l,top:t,right,bottom:b,width:right-l,height:b-t};
  }
  function roots() {
    const found=[document];
    for(let i=0;i<found.length;i++) for(const el of found[i].querySelectorAll('*'))
      if(el!==host && el.shadowRoot)found.push(el.shadowRoot);
    return found;
  }
  function detectPages() {
    let pages=[];
    for(const root of roots()) {
      const wrappers=[...root.querySelectorAll('[data-page-wrapper]')];
      const elements=wrappers.length?wrappers:[...root.querySelectorAll('img[alt]')].filter(el=>/^Seite\b/i.test(el.alt));
      for(const el of elements) {const r=visibleRect(el);if(r && !pages.some(p=>JSON.stringify(p)===JSON.stringify(r)))pages.push(r);}
    }
    // Only an unambiguous horizontal row is sorted. Overlapping layouts retain
    // DOM order and are explicitly editable proposals, not LEFT/RIGHT truth.
    if(pages.every((a,i)=>pages.slice(i+1).every(b=>a.right<=b.left || b.right<=a.left)))pages.sort((a,b)=>a.left-b.left);
    return pages.slice(0,64);
  }
  function detectNext() {
    for(const root of roots()) {
      const buttons=[...root.querySelectorAll('button,[role="button"]')];
      const matches=buttons.filter(el=>el.getAttribute('data-testid')==='dua-navi-vor' || /^(Nächste Seite|Naechste Seite|Next(?: page)?|Weiter)$/i.test(el.getAttribute('aria-label')||''));
      const visible=matches.map(visibleRect).filter(Boolean);
      if(visible.length===1)return visible[0];
    }
    return null;
  }
  function choose(el) {
    if (!el || ready) return;
    const rect=visibleRect(step===0?pageElement(el):el.closest?.('button,[role="button"]')||el);
    if(!rect)return;
    if (step === 0) {
      if (candidates.length >= 64) return;
      // Multiple clicked pages remain in explicit selection order, never x/y sort.
      if (!candidates.some(p=>JSON.stringify(p)===JSON.stringify(rect))) candidates.push(rect);
      update();
    } else {chosen[names[step]] = rect; next();}
  }
  function update() {
    hovered = null; highlight.hidden = true;
    skip.textContent = step === 0 ? 'Seiten fertig / weiter (ESC)' : 'Schritt ueberspringen (ESC)';
    line.textContent = step === 0 ? `${candidates.length} Seiten gewaehlt. Jede sichtbare Seite anklicken, dann Seiten fertig. Eine Seite ist gueltig. Nicht scrollen/zoomen.` : `${names[step]} ungefaehr auswaehlen. Klick waehlt; ESC ueberspringt.`;
  }
  function next() {
    if (++step < 3) update(); else finish();
  }
  function invalidate() {
    cleanup();
    // Kein neuer Datensatz: alte Daten werden durch fehlende Sitzungsmarker abgewiesen.
  }
  function finish() {
    ready = true; hovered = null; highlight.hidden = true; skip.hidden = true; copyButton.hidden = false;
    const positions = [[24,72],[innerWidth-56,72],[24,innerHeight-56],[innerWidth-56,innerHeight-56]];
    if (innerWidth < 180 || innerHeight < 180 || (visualViewport && visualViewport.scale !== 1)) return invalidate();
    positions.forEach((p,i) => {
      const marker = document.createElement('div');
      marker.style.cssText = `all:initial;position:fixed;left:${p[0]}px;top:${p[1]}px;width:32px;height:32px;background:rgb(${colors[i].join(',')});pointer-events:none;z-index:5!important;`;
      // A colored 8x8-cell perimeter plus 36 interior bits. Four 32-bit pieces
      // encode the complete session token; the fixed prefix binds orientation.
      const word=parseInt(token.slice(i*8,i*8+8),16)>>>0;
      const bits=[1,0,0,1,...Array.from({length:32},(_,j)=>(word>>>(31-j))&1)];
      bits.forEach((bit,j)=>{const cell=document.createElement('span');cell.style.cssText=`all:initial;position:absolute;left:${4+(j%6)*4}px;top:${4+Math.floor(j/6)*4}px;width:4px;height:4px;background:${bit?'white':'black'};`;marker.append(cell);});
      shadow.append(marker); markers.push(marker);
    });
    const result = {schema:3,token,created_ms:created,dpr:devicePixelRatio,candidates,
      viewport:[innerWidth,innerHeight],scroll:[scrollX,scrollY],visual_scale:visualViewport?.scale || 1,
      markers:positions.map((p,i)=>({css_center:[p[0]+16,p[1]+16],color:colors[i]})),rects:chosen};
    textarea.value = JSON.stringify(result); textarea.hidden = false;
    line.textContent = 'Ergebnisdatei speichern und in RectoFlow importieren. F8 entfernt jetzt alles.';
  }
  on(skip,'click', e => {e.stopImmediatePropagation(); next();});
  on(cancel,'click', e => {e.stopImmediatePropagation(); cleanup();});
  on(copyButton,'click', e => {
    e.stopImmediatePropagation();
    const url=URL.createObjectURL(new Blob([textarea.value],{type:'application/json'}));
    const link=document.createElement('a'); link.href=url;link.download=`result.${token}.json`;
    link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    copyButton.textContent='Datei gespeichert / erneut speichern';
  });
  on(document,'keydown', e => {
    if (e.key === 'F8') {e.preventDefault();e.stopImmediatePropagation();cleanup();return;}
    if (e.key === 'Escape') {e.preventDefault();e.stopImmediatePropagation(); if (ready) cleanup(); else next();}
  });
  on(document,'pointermove', e => {
    if (ready || e.composedPath().includes(host)) return;
    let el = e.composedPath().find(n => n instanceof Element);
    // Offene Shadow Roots liefern echte innere Elemente; geschlossene liefern den Host.
    if (!el || el === host || el === document.documentElement) return;
    hover(el);
  });
  // Unterliegende Seite nicht navigieren/bedienen. Cross-origin iframes koennen
  // nicht innen abgefangen werden: iframe-Host ueberspringen/manuell auswaehlen.
  for (const name of ['pointerdown','pointerup','mousedown','mouseup']) {
    on(document,name,e=>{if(!ready&&!e.composedPath().includes(host)){e.preventDefault();e.stopImmediatePropagation();}});
  }
  on(document,'click', e => {
    if (ready || e.composedPath().includes(host)) return;
    e.preventDefault();e.stopImmediatePropagation();
    choose(hovered);
  });
  on(window,'resize', invalidate);
  on(document,'scroll', invalidate);
  on(window,'pagehide', cleanup);
  on(shield,'pointermove',e=>{e.stopImmediatePropagation();if(!ready)hover(elementAt(e.clientX,e.clientY));});
  for (const name of ['pointerdown','pointerup','mousedown','mouseup','contextmenu']) {
    on(shield,name,e=>{e.preventDefault();e.stopImmediatePropagation();});
  }
  on(shield,'click',e=>{
    e.preventDefault();e.stopImmediatePropagation();choose(elementAt(e.clientX,e.clientY));
  });
  on(shield,'wheel',e=>{e.preventDefault();e.stopImmediatePropagation();invalidate();});
  // Panel ueber der Auswahlflaeche lassen, Marker erhalten keine Klicks.
  panel.style.zIndex='3';
  highlight.style.zIndex='2';
  beacon.style.zIndex='4';
  timeout = setTimeout(cleanup, Math.max(0,180000-(Date.now()-created)));
  candidates.push(...detectPages());
  const autoNext=detectNext();if(autoNext)chosen.NEXT=autoNext;
  update();
})();
