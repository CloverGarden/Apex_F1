"""The 60fps browser-side replay component (whole race, one driver).

Performance design (this is what makes it smooth, not ticking):
  - The STATIC layers (track outline, telemetry line charts) are rendered
    ONCE to offscreen canvases. Every animation frame only blits those
    cached layers and draws the few MOVING things (car dot, trail, cursor).
    So a frame is cheap no matter how many data points there are.
  - Animation runs on requestAnimationFrame; Python never reruns during play.

Features: whole-race timeline with live lap readout, a smoothed circuit map
with a gliding car dot that leaves a short fading trail, live gauges, and
telemetry charts with a working hover tooltip (rendered outside any clipped
container).

Theme tokens (ACCENT, ACCENT2, PANEL, BORDER, DIM) are substituted here.
"""

from __future__ import annotations


def replay_html(payload_json: str, theme: dict, height: int = 880) -> str:
    html = _TEMPLATE.replace("__PAYLOAD__", payload_json)
    html = (html
            .replace("ACCENT2", theme["accent2"])
            .replace("ACCENT", theme["accent"])
            .replace("PANEL", theme["panel"])
            .replace("BORDER", theme["border"])
            .replace("DIM", theme["dim"]))
    return html


_TEMPLATE = r"""
<div id="apex-root">
  <style>
    #apex-root{font-family:Inter,system-ui,Arial,sans-serif;color:#F3F6FF;}
    .ax-ctrls{display:flex;align-items:center;gap:14px;margin-bottom:14px;}
    .ax-btn{background:ACCENT;color:#fff;border:none;border-radius:10px;padding:11px 20px;
      font-size:1rem;font-weight:800;cursor:pointer;transition:filter .15s,transform .08s;
      box-shadow:0 2px 14px color-mix(in srgb,ACCENT 45%,transparent);}
    .ax-btn:hover{filter:brightness(1.12);}.ax-btn:active{transform:scale(.96);}
    .ax-time{font-variant-numeric:tabular-nums;font-size:.92rem;color:DIM;margin-left:14px;}
    .ax-laptime{display:flex;flex-direction:column;align-items:flex-start;margin-left:18px;}
    .ax-lt-label{font-size:.58rem;letter-spacing:.2em;color:DIM;}
    .ax-lt-val{font-size:1.9rem;font-weight:800;line-height:1;color:#F3F6FF;
      font-variant-numeric:tabular-nums;text-shadow:0 0 16px color-mix(in srgb,ACCENT 50%,transparent);}
    .pulse{animation:axpulse .35s ease;}
    @keyframes axpulse{0%{color:ACCENT2;transform:scale(1.18);}100%{transform:scale(1);}}
    .ax-lap{font-weight:800;color:#F3F6FF;font-size:1.05rem;min-width:84px;}
    .ax-speedrow{display:flex;align-items:center;gap:10px;margin:-6px 0 16px;}
    .ax-speedlabel{font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:DIM;}
    .ax-sp button{background:transparent;color:DIM;border:1px solid BORDER;border-radius:8px;
      padding:7px 14px;margin-left:6px;cursor:pointer;font-size:.85rem;font-weight:700;transition:all .15s;}
    .ax-sp button:hover{border-color:ACCENT;color:#F3F6FF;}
    .ax-sp button.on{background:ACCENT;color:#fff;border-color:ACCENT;box-shadow:0 0 12px color-mix(in srgb,ACCENT 50%,transparent);}
    .ax-timeline{margin:2px 0 16px;}
    .ax-scrub{-webkit-appearance:none;appearance:none;width:100%;height:10px;border-radius:7px;
      background:BORDER;outline:none;cursor:pointer;}
    .ax-scrub::-webkit-slider-thumb{-webkit-appearance:none;width:20px;height:20px;border-radius:50%;
      background:#fff;border:3px solid ACCENT;cursor:pointer;box-shadow:0 0 12px ACCENT;}
    .ax-scrub::-moz-range-thumb{width:20px;height:20px;border-radius:50%;background:#fff;border:3px solid ACCENT;}
    .ax-grid3{display:grid;grid-template-columns:0.8fr 1.5fr 0.8fr;gap:14px;align-items:start;}
    .ax-lb{width:100%;border-collapse:collapse;font-size:.78rem;}
    .ax-lb td{padding:5px 6px;border-bottom:1px solid color-mix(in srgb,BORDER 55%,transparent);
      transition:transform .4s cubic-bezier(.22,.61,.36,1);}
    .ax-lb .p{font-weight:800;width:26px;color:#F3F6FF;font-variant-numeric:tabular-nums;}
    .ax-lb .nm{font-weight:700;}
    .ax-lb .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle;}
    .ax-lb tr.sel{background:color-mix(in srgb,ACCENT 24%,transparent);box-shadow:inset 3px 0 0 ACCENT;}
    .ax-lb tr.fl .nm::after{content:" ⚡";color:#c678ff;}
    .ax-lb .gap{color:DIM;font-variant-numeric:tabular-nums;text-align:right;}
    .ax-card{background:PANEL;border:1px solid BORDER;border-top:2px solid ACCENT;border-radius:14px;
      padding:16px;position:relative;
      box-shadow:inset 0 1px 0 color-mix(in srgb,ACCENT 30%,transparent),0 2px 16px rgba(0,0,0,.35);}
    .ax-edge{position:absolute;left:0;top:0;bottom:0;width:3px;background:ACCENT2;opacity:.85;border-radius:14px 0 0 14px;}
    .ax-h{font-size:.7rem;letter-spacing:.17em;text-transform:uppercase;color:DIM;margin:0 0 12px;}
    .ax-circuit-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}
    .ax-circuit-name{font-size:1.05rem;font-weight:800;letter-spacing:.02em;color:#F3F6FF;}
    .ax-legend{display:flex;gap:10px;}
    .ax-legend .lg{font-size:.66rem;color:DIM;display:flex;align-items:center;gap:4px;}
    .ax-legend .lg i{width:12px;height:4px;border-radius:2px;display:inline-block;}
    canvas{width:100%;display:block;}
    .ax-g{margin:12px 0;}
    .ax-grow{display:flex;justify-content:space-between;font-size:.68rem;text-transform:uppercase;
      letter-spacing:.1em;color:DIM;margin-bottom:6px;}
    .ax-val{color:#F3F6FF;font-weight:800;font-size:1.05rem;font-variant-numeric:tabular-nums;}
    .ax-trk{height:12px;border-radius:7px;background:#0007;border:1px solid BORDER;overflow:hidden;position:relative;}
    .ax-fill{height:100%;border-radius:7px;background:linear-gradient(90deg,ACCENT,ACCENT2);width:0%;
      transition:width .09s linear;}   /* glide between updates, no stepping */
    .ax-fill.red{box-shadow:0 0 10px ACCENT2;}
    .ax-chip{display:inline-flex;gap:16px;margin-top:12px;}
    #tip{position:fixed;pointer-events:none;background:#000d;border:1px solid ACCENT;border-radius:8px;
      padding:7px 10px;font-size:.78rem;color:#fff;opacity:0;transform:translate(-50%,-115%);
      transition:opacity .08s;white-space:nowrap;z-index:9999;box-shadow:0 4px 18px #000a;}
  </style>

  <div class="ax-ctrls">
    <button class="ax-btn" id="play">▶ Play</button>
    <span class="ax-lap" id="lapLbl">Lap 1</span>
    <div class="ax-laptime"><span class="ax-lt-label">LAP TIME</span>
      <span class="ax-lt-val" id="lapTime">0:00.0</span></div>
    <span class="ax-time" id="time">Race 0:00 / 0:00</span>
  </div>
  <div class="ax-timeline"><input type="range" class="ax-scrub" id="scrub" min="0" max="10000" value="0"/></div>
  <div class="ax-speedrow"><span class="ax-speedlabel">Playback speed</span>
    <span class="ax-sp" id="sp"></span></div>

  <div class="ax-grid3">
    <div class="ax-card"><div class="ax-edge"></div>
      <div class="ax-h">Live Leaderboard</div>
      <div id="board"></div></div>
    <div class="ax-card"><div class="ax-edge"></div>
      <div class="ax-circuit-head">
        <span class="ax-circuit-name" id="circuitName">Circuit</span>
        <span class="ax-legend">
          <span class="lg"><i style="background:#e10600"></i>S1</span>
          <span class="lg"><i style="background:#1e88ff"></i>S2</span>
          <span class="lg"><i style="background:#ffd400"></i>S3</span>
        </span>
      </div>
      <canvas id="track" height="460"></canvas></div>
    <div class="ax-card"><div class="ax-edge"></div>
      <div class="ax-h">Gauges</div><div id="gauges"></div></div>
  </div>

  <div class="ax-card" style="margin-top:14px"><div class="ax-edge"></div>
    <div class="ax-h">Telemetry · hover for values</div>
    <canvas id="chart" height="200"></canvas></div>
</div>
<div id="tip"></div>

<script>
const DATA = __PAYLOAD__;
(function(){
  const T=DATA.theme, N=DATA.t.length, dur=DATA.duration||1;
  const TRAIL_MS=1400;                     // how long the glowing trail lingers
  let playing=false, frac=0, speed=1, last=null, hoverFrac=null, raf=null;
  const trail=[];                          // recent {x,y,age} for the fading trail

  const $=id=>document.getElementById(id);
  if(DATA.circuit){const cn=document.getElementById("circuitName");if(cn)cn.textContent=DATA.circuit;}
  const play=$("play"), scrub=$("scrub"), timeEl=$("time"), lapEl=$("lapLbl");
  const trackCv=$("track"), chartCv=$("chart"), gauges=$("gauges"), tip=$("tip"), spEl=$("sp");

  function mm(a){let lo=Infinity,hi=-Infinity;for(let i=0;i<a.length;i++){const v=a[i];if(v==null)continue;if(v<lo)lo=v;if(v>hi)hi=v;}return[lo,hi];}
  // Bounds must cover BOTH the track line and the dot path, with the SAME
  // scale, or the dot drifts off the drawn track. Combine them here.
  function mm2(a,b){const[al,ah]=mm(a),[bl,bh]=mm(b);return[Math.min(al,bl),Math.max(ah,bh)];}
  const [minX,maxX]=mm2(DATA.track.x,DATA.path.x), [minY,maxY]=mm2(DATA.track.y,DATA.path.y);
  const idxAt=f=>Math.min(N-1,Math.max(0,Math.round(f*(N-1))));
  // Seconds -> "M:SS" (or "H:MM:SS" for a long race) for the time readout.
  function fmtMMSS(sec){sec=Math.max(0,Math.round(sec));const h=Math.floor(sec/3600);
    const m=Math.floor((sec%3600)/60),s=sec%60;const ss=String(s).padStart(2,"0");
    if(h>0)return h+":"+String(m).padStart(2,"0")+":"+ss;return m+":"+ss;}

  // Speed buttons: 1x = real time. Higher = watch the race faster.
  [1,2,5,10,30,60].forEach(s=>{const b=document.createElement("button");b.textContent=s+"×";
    if(s===1)b.className="on";b.onclick=()=>{speed=s;[...spEl.children].forEach(c=>c.className="");b.className="on";};
    spEl.appendChild(b);});

  const GDEFS=[["Speed","speed",0,360,"km/h",null],["RPM","rpm",0,12500,"",0.92],
               ["Throttle","throttle",0,100,"%",null],["Brake","brake",0,100,"%",null]];
  const gEls=GDEFS.map(([label])=>{const w=document.createElement("div");w.className="ax-g";
    w.innerHTML=`<div class="ax-grow"><span>${label}</span><span class="ax-val"></span></div>
                 <div class="ax-trk"><div class="ax-fill"></div></div>`;
    gauges.appendChild(w);return{v:w.querySelector(".ax-val"),f:w.querySelector(".ax-fill")};});
  const chip=document.createElement("div");chip.className="ax-chip";
  chip.innerHTML=`<span class="ax-val" id="gGear">Gear --</span><span class="ax-val" id="gDrs">DRS --</span>`;
  gauges.appendChild(chip);

  // --- Live leaderboard ---
  const boardEl=$("board");
  const EV=(DATA.pos_events||[]).slice().sort((a,b)=>a.t-b.t);
  const DM=DATA.drivers_meta||{}, SEL=DATA.selected, OFL=DATA.overall_fastest;
  function standingsAt(sec){
    // latest known position per driver at/<=sec
    const cur={};
    for(let k=0;k<EV.length;k++){const e=EV[k];if(e.t>sec)break;cur[e.n]=e.p;}
    // Before the first events (sec < first event time), seed with the opening
    // grid so the board is never blank at the start.
    if(Object.keys(cur).length===0&&EV.length){
      const t0=EV[0].t;for(let k=0;k<EV.length;k++){if(EV[k].t>t0)break;cur[EV[k].n]=EV[k].p;}}
    const arr=Object.keys(cur).map(n=>({n:+n,p:cur[n]}));
    arr.sort((a,b)=>a.p-b.p);return arr;}
  let lastBoardKey="";
  function renderBoard(sec){
    const arr=standingsAt(sec);if(!arr.length){return;}
    const key=arr.map(a=>a.n+":"+a.p).join(",");if(key===lastBoardKey)return;lastBoardKey=key;
    let html='<table class="ax-lb"><tbody>';
    arr.forEach(a=>{const m=DM[a.n]||{};const col=m.colour?("#"+String(m.colour).replace("#",""))
      :T.accent;const sel=a.n===SEL?" sel":"";const fl=(OFL&&OFL.n===a.n)?" fl":"";
      html+=`<tr class="${sel}${fl}"><td class="p">${a.p}</td>`+
        `<td><span class="dot" style="background:${col}"></span>`+
        `<span class="nm">${m.acronym||a.n}</span></td>`+
        `<td class="gap">${m.team||""}</td></tr>`;});
    html+="</tbody></table>";boardEl.innerHTML=html;}

  // --- offscreen static layers (rendered once) ---
  let trackBG=null, chartBG=null, geom={};
  function dpr(){return window.devicePixelRatio||1;}

  const PAD=10;   // inner padding; smaller = map fills more of the panel
  function mapPt(x,y,w,h,pad){pad=pad===undefined?PAD:pad;
    const s=Math.min((w-2*pad)/((maxX-minX)||1),(h-2*pad)/((maxY-minY)||1));
    const ox=(w-(maxX-minX)*s)/2, oy=(h-(maxY-minY)*s)/2;
    return[ox+(x-minX)*s, h-(oy+(y-minY)*s)];}

  // Interpolate the car position along the path for a fractional index, so
  // the dot glides smoothly BETWEEN GPS samples instead of snapping to them.
  function pathPos(f){const px=DATA.path.x,py=DATA.path.y,n=px.length;
    const fi=f*(n-1), i0=Math.floor(fi), i1=Math.min(n-1,i0+1), tt=fi-i0;
    if(px[i0]==null||px[i1]==null)return null;
    return [px[i0]+(px[i1]-px[i0])*tt, py[i0]+(py[i1]-py[i0])*tt];}

  // Interpolate ANY telemetry series at a fractional moment, so gauges move
  // smoothly between samples instead of stepping.
  function valAt(key,f){const a=DATA[key],n=a.length;const fi=f*(n-1);
    const i0=Math.floor(fi),i1=Math.min(n-1,i0+1),tt=fi-i0;
    const v0=a[i0]||0,v1=a[i1]||0;return v0+(v1-v0)*tt;}
  // Elapsed seconds into the CURRENT lap, from the lap boundary table.
  function lapTimeAt(f){const sec=valAt("t",f);const lp=DATA.lap[idxAt(f)];
    const b=DATA.laps.find(L=>L.n===lp);if(!b)return[lp,0];
    return[lp, Math.max(0, sec-b.t0)];}

  // FIXED internal resolution. The canvas is drawn once at this size and CSS
  // scales it to fit the column, so the sidebar resizing the page only scales
  // the picture — it never rebuilds or collapses the canvas.
  const CW=880, TH=parseInt(trackCv.getAttribute("height")), CH2=parseInt(chartCv.getAttribute("height"));
  function buildTrackBG(){const w=CW,h=TH,d=dpr();
    trackCv.style.width="100%";trackCv.style.height="auto";
    trackCv.width=w*d;trackCv.height=h*d;
    const off=document.createElement("canvas");off.width=w*d;off.height=h*d;
    const ctx=off.getContext("2d");ctx.setTransform(d,0,0,d,0,0);
    const tx=DATA.track.x,ty=DATA.track.y;
    // smooth outline with quadratic midpoints
    const pts=[];for(let i=0;i<tx.length;i++){if(tx[i]==null)continue;pts.push(mapPt(tx[i],ty[i],w,h,PAD));}
    function stroke(width,color){ctx.beginPath();ctx.moveTo(pts[0][0],pts[0][1]);
      for(let i=1;i<pts.length;i++){const p0=pts[i],p1=pts[(i+1)%pts.length];
        const mx=(p0[0]+p1[0])/2,my=(p0[1]+p1[1])/2;ctx.quadraticCurveTo(p0[0],p0[1],mx,my);}
      ctx.closePath();   // close the loop: start meets finish
      ctx.lineJoin="round";ctx.lineCap="round";ctx.lineWidth=width;ctx.strokeStyle=color;ctx.stroke();}
    stroke(16, "#05060f");                    // outer casing (dark), like F1 maps
    stroke(11, "#11182f");                     // tarmac
    // Racing line split into 3 SECTORS, each its own colour (like F1 maps).
    const SEC=DATA.sectors||[0];
    const SECCOL=["#e10600","#1e88ff","#ffd400"];   // S1 red, S2 blue, S3 yellow
    function strokeRange(a,b,width,color){ctx.beginPath();
      let first=true;for(let i=a;i<=b&&i<pts.length;i++){const p=pts[i];
        first?ctx.moveTo(p[0],p[1]):ctx.lineTo(p[0],p[1]);first=false;}
      ctx.lineJoin="round";ctx.lineCap="round";ctx.lineWidth=width;ctx.strokeStyle=color;ctx.stroke();}
    if(SEC.length>=3){
      strokeRange(SEC[0],SEC[1],3.4,SECCOL[0]);
      strokeRange(SEC[1],SEC[2],3.4,SECCOL[1]);
      strokeRange(SEC[2],pts.length-1,3.4,SECCOL[2]);
      strokeRange(pts.length-1,pts.length-1,0,SECCOL[2]);
    } else { stroke(3.2, T.accent); }

    // Start/finish marker: a small checkered bar across the track, drawn
    // perpendicular to the track direction at the start/finish point.
    if(DATA.start_finish){const sf=DATA.start_finish;
      const[sx,sy]=mapPt(sf.x,sf.y,w,h,PAD);
      // direction from neighbouring track points -> perpendicular
      const n=DATA.track.x.length, a=(sf.i-2+n)%n, b=(sf.i+2)%n;
      const[ax,ay]=mapPt(DATA.track.x[a],DATA.track.y[a],w,h,PAD);
      const[bx,by]=mapPt(DATA.track.x[b],DATA.track.y[b],w,h,PAD);
      let dx=bx-ax, dy=by-ay; const len=Math.hypot(dx,dy)||1; dx/=len; dy/=len;
      const px=-dy, py=dx;             // perpendicular unit vector
      const half=9, sq=3;              // bar half-length, square size
      ctx.save();ctx.translate(sx,sy);ctx.rotate(Math.atan2(py,px));
      for(let r=0;r<2;r++)for(let cN=-3;cN<3;cN++){
        ctx.fillStyle=((r+cN)&1)?"#fff":"#111";
        ctx.fillRect(cN*sq, (r-1)*sq, sq, sq);}
      ctx.restore();
      // small label
      ctx.fillStyle=T.dim;ctx.font="bold 9px Inter,Arial";
      ctx.fillText("START/FINISH", sx+12, sy-8);}
    trackBG=off;geom.track={w,h};}

  const CH_DEFS=[{label:"SPEED",key:"speed",min:0,max:360,color:T.accent},
                 {label:"THROTTLE",key:"throttle",min:0,max:100,color:T.accent},
                 {label:"BRAKE",key:"brake",min:0,max:100,color:T.accent2},
                 {label:"RPM",key:"rpm",min:0,max:12500,color:T.accent}];

  function buildChartBG(){const w=CW,h=CH2,d=dpr();
    chartCv.style.width="100%";chartCv.style.height="auto";
    chartCv.width=w*d;chartCv.height=h*d;
    const off=document.createElement("canvas");off.width=w*d;off.height=h*d;
    const ctx=off.getContext("2d");ctx.setTransform(d,0,0,d,0,0);
    const padL=34,padR=16,gh=h/CH_DEFS.length,plotW=w-padL-padR;
    CH_DEFS.forEach((dd,row)=>{const arr=DATA[dd.key],y0=row*gh+10,y1=(row+1)*gh-10;
      ctx.beginPath();for(let i=0;i<arr.length;i++){const x=padL+plotW*(i/(arr.length-1));
        const yv=y1-(y1-y0)*((arr[i]-dd.min)/((dd.max-dd.min)||1));i?ctx.lineTo(x,yv):ctx.moveTo(x,yv);}
      ctx.strokeStyle=dd.color;ctx.lineWidth=1.8;ctx.stroke();
      ctx.fillStyle=T.dim;ctx.font="10px Inter,Arial";ctx.fillText(dd.label,padL,y0);});
    chartBG=off;geom.chart={w,h,padL,padR,plotW};}

  function rebuild(){buildTrackBG();buildChartBG();}

  let lastGear=null,lastDrs=null;
  function updateGauges(f){const i=idxAt(f);
    GDEFS.forEach(([l,key,mn,mx,unit,red],k)=>{const v=valAt(key,f);   // interpolated -> smooth
      gEls[k].v.textContent=(key==="rpm"?Math.round(v).toLocaleString():Math.round(v))+(unit?(" "+unit):"");
      const pct=100*(v-mn)/((mx-mn)||1);gEls[k].f.style.width=Math.max(0,Math.min(100,pct)).toFixed(1)+"%";
      gEls[k].f.classList.toggle("red",red!=null&&pct>=red*100);});
    // Gear & DRS are discrete; flash them on change so a shift reads smoothly.
    const g=DATA.gear[i]||0, dr=DATA.drs[i]?1:0;
    const gEl=$("gGear"),dEl=$("gDrs");
    if(g!==lastGear){gEl.textContent="Gear "+g;gEl.classList.remove("pulse");void gEl.offsetWidth;gEl.classList.add("pulse");lastGear=g;}
    if(dr!==lastDrs){dEl.textContent="DRS "+(dr?"OPEN":"closed");dEl.style.color=dr?T.accent:"";dEl.classList.remove("pulse");void dEl.offsetWidth;dEl.classList.add("pulse");lastDrs=dr;}}

  function frame(){
    if(!trackBG||!chartBG||!geom.track||!geom.chart)return;  // layers not ready yet
    // TRACK: blit cached bg, draw trail + dot
    const d=dpr(),{w,h}=geom.track,ctx=trackCv.getContext("2d");
    ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,trackCv.width,trackCv.height);
    ctx.drawImage(trackBG,0,0);ctx.setTransform(d,0,0,d,0,0);
    // trail (fades over TRAIL_MS; longer, drawn as a fading glowing ribbon)
    for(let k=0;k<trail.length;k++){const tr=trail[k];const a=Math.max(0,1-tr.age/TRAIL_MS);
      if(a<=0)continue;const rad=3+5*a;
      ctx.beginPath();ctx.arc(tr.x,tr.y,rad,0,7);
      ctx.fillStyle=T.accent2;ctx.globalAlpha=a*0.45;
      ctx.shadowColor=T.accent2;ctx.shadowBlur=10*a;ctx.fill();ctx.shadowBlur=0;ctx.globalAlpha=1;}
    const pp=pathPos(frac);
    if(pp){const[cx,cy]=mapPt(pp[0],pp[1],w,h,PAD);
      ctx.beginPath();ctx.arc(cx,cy,9,0,7);ctx.fillStyle=T.accent2;ctx.shadowColor=T.accent2;
      ctx.shadowBlur=20;ctx.fill();ctx.shadowBlur=0;ctx.lineWidth=2.5;ctx.strokeStyle="#fff";ctx.stroke();}
    // CHART: blit cached bg, draw cursor + hover
    const g=geom.chart,cc=chartCv.getContext("2d");
    cc.setTransform(1,0,0,1,0,0);cc.clearRect(0,0,chartCv.width,chartCv.height);
    cc.drawImage(chartBG,0,0);cc.setTransform(d,0,0,d,0,0);
    const cx=g.padL+g.plotW*frac;cc.beginPath();cc.moveTo(cx,0);cc.lineTo(cx,g.h);
    cc.strokeStyle=T.accent2;cc.lineWidth=2;cc.globalAlpha=.85;cc.stroke();cc.globalAlpha=1;
    if(hoverFrac!=null){const hx=g.padL+g.plotW*hoverFrac;cc.beginPath();cc.moveTo(hx,0);cc.lineTo(hx,g.h);
      cc.strokeStyle=T.dim;cc.setLineDash([3,3]);cc.stroke();cc.setLineDash([]);}
    // labels
    const i=idxAt(frac);scrub.value=Math.round(frac*10000);
    const pct=(frac*100).toFixed(1);
    scrub.style.background=`linear-gradient(90deg,${T.accent} ${pct}%,${T.border} ${pct}%)`;
    const[lp,lt]=lapTimeAt(frac);
    const lm=Math.floor(lt/60), ls=(lt-lm*60);
    $("lapTime").textContent=lm+":"+ls.toFixed(1).padStart(4,"0");   // M:SS.s
    timeEl.textContent="Race "+fmtMMSS(DATA.t[i]||0)+" / "+fmtMMSS(dur);
    lapEl.textContent="Lap "+(lp||1);updateGauges(frac);
    renderBoard(DATA.t[i]||0);}   // live leaderboard at the current race second

  function loop(ts){
    if(last==null)last=ts;const dt=ts-last;last=ts;
    if(playing){frac+=((dt/1000)*speed)/Math.max(dur,0.001);  // 1x = REAL TIME
      if(frac>=1){frac=1;playing=false;play.textContent="▶ Play";}
      // push current (interpolated) pos to trail
      const pp=pathPos(frac);
      if(pp){const{w,h}=geom.track;const[cx,cy]=mapPt(pp[0],pp[1],w,h,PAD);trail.push({x:cx,y:cy,age:0});}
    }
    for(let k=0;k<trail.length;k++)trail[k].age+=dt;
    while(trail.length&&trail[0].age>TRAIL_MS)trail.shift();
    frame();raf=requestAnimationFrame(loop);}

  play.onclick=()=>{if(frac>=1){frac=0;trail.length=0;}playing=!playing;last=null;
    play.textContent=playing?"⏸ Pause":"▶ Play";};
  scrub.oninput=()=>{frac=scrub.value/10000;playing=false;trail.length=0;play.textContent="▶ Play";};

  // hover tooltip (tip is fixed-position, outside any clipped card)
  chartCv.addEventListener("mousemove",e=>{const r=chartCv.getBoundingClientRect(),g=geom.chart;
    // mouse is in rendered px; scale into the fixed internal canvas space.
    const scale=g.w/(r.width||g.w);
    const x=(e.clientX-r.left)*scale;hoverFrac=Math.min(1,Math.max(0,(x-g.padL)/g.plotW));
    const i=idxAt(hoverFrac);
    tip.innerHTML=`<b>Lap ${DATA.lap[i]}</b> · ${(DATA.t[i]||0).toFixed(1)}s<br>`+
      `${Math.round(DATA.speed[i])} km/h · ${Math.round(DATA.throttle[i])}% thr · `+
      `${Math.round(DATA.brake[i])}% brk · ${Math.round(DATA.rpm[i]).toLocaleString()} rpm · g${DATA.gear[i]}`;
    tip.style.left=e.clientX+"px";tip.style.top=r.top+"px";tip.style.opacity=1;});
  chartCv.addEventListener("mouseleave",()=>{hoverFrac=null;tip.style.opacity=0;});

  // The canvas has a FIXED internal resolution (CW x TH) and is scaled to the
  // column by CSS (width:100%). So when the sidebar resizes the page, the
  // browser just scales the already-drawn picture — we NEVER rebuild on
  // resize, which is what used to make the map collapse and vanish.
  // Build the static layers exactly once, then run the animation loop forever.
  rebuild();
  raf=requestAnimationFrame(loop);
})();
</script>
"""
