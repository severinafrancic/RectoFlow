// Ausschliesslich lokal: keine Netzwerkzugriffe, URLs, Cookies oder Textinhalte.
(() => {
  'use strict';
  const token = '__SESSION_TOKEN__';
  const key = '__edgeCaptureLocalPicker';
  if (window !== window.top) throw new Error('DOM_PICKER_FAILED: Top-Frame der Seite auswaehlen.');
  if (window[key]) window[key].cleanup();
  const abort = new AbortController();
  const names = ['LEFT', 'RIGHT', 'NEXT', 'PROGRESS'];
  const colors = [[239,17,131], [17,239,131], [131,17,239]];
  const chosen = {};
  let step = 0, ready = false, hovered = null, timeout;
  const host = document.createElement('div');
  host.style.cssText = 'all:initial!important;position:fixed!important;inset:0!important;pointer-events:none!important;z-index:2147483647!important;';
  const shadow = host.attachShadow({mode:'closed'});
  const panel = document.createElement('div');
  panel.style.cssText = 'position:fixed;right:12px;top:12px;max-width:440px;background:#132030;color:white;padding:12px;font:15px Arial;border:2px solid white;pointer-events:auto;';
  const line = document.createElement('div');
  const skip = document.createElement('button');
  skip.textContent = 'Schritt ueberspringen (ESC)';
  const cancel = document.createElement('button');
  cancel.textContent = 'Abbrechen / entfernen';
  const copyButton = document.createElement('button');
  copyButton.textContent = 'Ergebnis kopieren';
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
  function choose(el) {
    if (!el || ready) return;
    const r = el.getBoundingClientRect();
    chosen[names[step]] = {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height,tag:el.tagName.toLowerCase()};
    next();
  }
  function update() {
    hovered = null; highlight.hidden = true;
    line.textContent = `${step+1}/4 ${names[step]} ungefaehr auswaehlen. Klick waehlt; ESC ueberspringt. Nicht scrollen/zoomen.`;
  }
  function next() {
    if (++step < 4) update(); else finish();
  }
  function invalidate() {
    cleanup();
    // Kein neuer Datensatz: alte Daten werden durch fehlende Sitzungsmarker abgewiesen.
  }
  function finish() {
    ready = true; hovered = null; highlight.hidden = true; skip.hidden = true; copyButton.hidden = false;
    const positions = [[24,72],[innerWidth-48,72],[24,innerHeight-48]];
    if (innerWidth < 180 || innerHeight < 180 || (visualViewport && visualViewport.scale !== 1)) return invalidate();
    positions.forEach((p,i) => {
      const marker = document.createElement('div');
      marker.style.cssText = `position:fixed;left:${p[0]}px;top:${p[1]}px;width:24px;height:24px;border:2px solid black;box-sizing:border-box;background:rgb(${colors[i].join(',')});pointer-events:none;`;
      shadow.append(marker); markers.push(marker);
    });
    const result = {schema:1,token,created_ms:Date.now(),dpr:devicePixelRatio,
      viewport:[innerWidth,innerHeight],scroll:[scrollX,scrollY],visual_scale:visualViewport?.scale || 1,
      markers:positions.map((p,i)=>({css_center:[p[0]+12,p[1]+12],color:colors[i]})),rects:chosen};
    textarea.value = JSON.stringify(result); textarea.hidden = false;
    line.textContent = 'Ergebnis kopieren. DevTools schliessen (ohne Layoutwechsel), danach zur Kalibrierung zurueck. ESC entfernt jetzt alles.';
  }
  on(skip,'click', e => {e.stopImmediatePropagation(); next();});
  on(cancel,'click', e => {e.stopImmediatePropagation(); cleanup();});
  on(copyButton,'click', async e => {
    e.stopImmediatePropagation();
    try {await navigator.clipboard.writeText(textarea.value); copyButton.textContent='Kopiert';}
    catch (_) {textarea.focus();textarea.select();document.execCommand('copy');copyButton.textContent='Auswahl mit Strg+C kopieren';}
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
  timeout = setTimeout(cleanup, 180000);
  update();
})();
