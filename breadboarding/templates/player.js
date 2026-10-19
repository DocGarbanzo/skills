(function(){
  // Live replay of simulated LED currents. Data: {key: {dt, n, imax_mA, leds:[{name, b64}]}} (uint8, shared full scale).
  const DATA = JSON.parse(document.getElementById('player-data').textContent);
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const players = [];
  function decode(b64){ const s=atob(b64), a=new Uint8Array(s.length); for(let i=0;i<s.length;i++) a[i]=s.charCodeAt(i); return a; }
  document.querySelectorAll('.player').forEach(el=>{
    const d=DATA[el.dataset.key]; if(!d) return;
    const qs=d.leds.map(l=>decode(l.b64)), n=qs[0].length, dt=d.dt, T=n*dt;
    // flash onsets with hysteresis, for the rate readout
    const on=[]; let st=false;
    const src=(d.rate_led==null)?qs:[qs[d.rate_led]];   // rate from any LED, or from one LED (e.g. a chaser's cycle)
    for(let i=0;i<n;i++){ let v=0; for(const q of src) if(q[i]>v) v=q[i];
      if(!st && v>153){st=true; on.push(i*dt);} else if(st && v<77) st=false; }
    const p={el,qs,n,dt,T,on,imax:d.imax_mA,t:0,playing:false,
      canvas:el.querySelector('canvas'), glows:[...el.querySelectorAll('.glow')],
      rate:el.querySelector('.rate'), curs:[...el.querySelectorAll('.cur')], tpos:el.querySelector('.tpos'),
      btn:el.querySelector('.play')};
    p.btn.addEventListener('click',()=>{ p.playing=!p.playing; sync(p); if(p.playing) kick(); });
    players.push(p); draw(p);
  });
  function sync(p){ p.btn.textContent=p.playing?'Pause':'Play'; p.btn.setAttribute('aria-pressed',p.playing); }
  function sample(p,k,t){ const i=Math.floor(((t%p.T)+p.T)%p.T/p.dt); return p.qs[k][i]/255; }
  function rateAt(p,t){
    const tt=((t%p.T)+p.T)%p.T, on=p.on; if(on.length<2) return null;
    let k=-1; for(let i=0;i<on.length;i++){ if(on[i]<=tt) k=i; else break; }
    let a,b; if(k>=1){a=on[k-1];b=on[k];} else if(k===0){a=on[on.length-1]-p.T;b=on[0];} else {a=on[on.length-2]-p.T;b=on[on.length-1]-p.T;}
    return 1/(b-a);
  }
  function css(v){ return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function draw(p){
    const c=p.canvas, dpr=window.devicePixelRatio||1, w=c.clientWidth, h=c.clientHeight;
    if(!w) return;
    if(c.width!==Math.round(w*dpr)){ c.width=Math.round(w*dpr); c.height=Math.round(h*dpr); }
    const g=c.getContext('2d'); g.setTransform(dpr,0,0,dpr,0,0);
    g.fillStyle=css('--scope-bg'); g.fillRect(0,0,w,h);
    const win=4, top=10, bot=h-18, H=bot-top;
    g.strokeStyle=css('--scope-grid'); g.lineWidth=1; g.font='10px ui-monospace, monospace'; g.fillStyle=css('--scope-text');
    for(let s=0;s<=win;s++){ const x=w*s/win; g.beginPath(); g.moveTo(x+.5,top); g.lineTo(x+.5,bot); g.stroke(); }
    for(let k=0;k<=2;k++){ const y=top+H*k/2; g.beginPath(); g.moveTo(0,y+.5); g.lineTo(w,y+.5); g.stroke(); }
    g.fillText(p.imax.toFixed(1)+' mA',4,top+10); g.fillText('−4 s',2,h-5); g.textAlign='right'; g.fillText('now',w-3,h-5); g.textAlign='left';
    const TRACE={red:'#ff5a4e',blue:'#4f9bff',green:'#4fe07a',yellow:'#ffd84a',white:'#e8eef8'};
    const named=DATA[p.el.dataset.key].leds.map(l=>l.color&&l.color!=='red'?TRACE[l.color]:null);
    const t0=p.t-win, cols=[css('--scope-trace'), css('--scope-trace-2')||'#ffb43a', css('--scope-trace-3')||'#4fb3e8', css('--scope-trace-4')||'#7bd36a'];
    p.qs.forEach((q,k)=>{
      g.strokeStyle=named[k]||cols[k%cols.length]; g.lineWidth=1.6; g.beginPath();
      for(let x=0;x<=w;x++){
        const ta=t0+win*x/w, tb=t0+win*(x+1)/w;
        let mn=1,mx=0; for(let t=ta;t<tb;t+=p.dt){ const v=sample(p,k,t); if(v<mn)mn=v; if(v>mx)mx=v; }
        if(mn>mx){ mn=mx=sample(p,k,ta); }
        const y1=bot-H*mx, y2=bot-H*mn;
        if(x===0) g.moveTo(x,y1); else g.lineTo(x,y1); g.lineTo(x,y2);
      }
      g.stroke();
    });
    p.qs.forEach((q,k)=>{ const v=sample(p,k,p.t);
      if(p.glows[k]) p.glows[k].style.opacity=Math.pow(v,0.6).toFixed(3);
      if(p.curs[k]) p.curs[k].textContent=(v*p.imax).toFixed(1); });
    if(p.rate){ const r=rateAt(p,p.t); p.rate.textContent=r?r.toFixed(r<10?2:1):'–'; }
    p.tpos.textContent='t = '+(((p.t%p.T)+p.T)%p.T).toFixed(1)+' s of '+p.T.toFixed(1)+' s';
  }
  let last=null, running=false;
  function frame(ts){
    const dtr = last===null?0:Math.min((ts-last)/1000,0.1); last=ts;
    let any=false;
    players.forEach(p=>{ if(p.playing){ p.t+=dtr; any=true; } draw(p); });
    if(any) requestAnimationFrame(frame); else { running=false; last=null; }
  }
  function kick(){ if(!running){ running=true; last=null; requestAnimationFrame(frame); } }
  window.addEventListener('resize',()=>players.forEach(draw));
  function autostart(){ players.forEach(p=>{ if(!reduce && !p.started){ p.playing=true; p.started=true; sync(p);} draw(p); }); kick(); }
  if(document.readyState!=='loading') autostart(); else document.addEventListener('DOMContentLoaded',autostart);
})();
