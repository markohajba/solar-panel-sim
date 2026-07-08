"""Self-contained canvas animation of heat leaving a single panel.

Python computes the fluxes; this module serialises them to JSON, injects them
into a standalone HTML + vanilla-JS ``<canvas>`` scene, and (in the app) hands it
to ``streamlit.components.v1.html``. The animation loop runs on
``requestAnimationFrame`` independently of Streamlit reruns. Arrow lengths,
particle emission rates, colours and the panel tint are all driven by the
injected values, so changing the conditions and recomputing refreshes the scene.
"""

from __future__ import annotations

import json

from panelsim.models import SimResult

# Tokens replaced at build time (kept out of str.format because the JS body is
# full of literal braces).
_HTML_TEMPLATE = r"""
<div id="hf-wrap" style="width:100%;font-family:system-ui,Segoe UI,Roboto,sans-serif;">
  <canvas id="hf-canvas" style="width:100%;height:__HEIGHT__px;display:block;
    border-radius:12px;border:1px solid rgba(0,0,0,0.15);"></canvas>
</div>
<script>
(function(){
  const DATA = __DATA__;
  const L = __LABELS__;
  const WARMUP = __WARMUP__;

  const canvas = document.getElementById("hf-canvas");
  const ctx = canvas.getContext("2d");
  let W = 0, H = 0, dpr = 1;

  function resize(){
    dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    W = Math.max(320, rect.width);
    H = __HEIGHT__;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  const clamp = (x,a,b) => Math.max(a, Math.min(b, x));
  const lerp = (a,b,t) => a + (b-a)*t;
  const gRef = Math.max(DATA.g, 1);
  const frac = (x) => clamp(x / gRef, 0, 1);
  const pct  = (x) => (100 * x / Math.max(DATA.g, 1e-9));
  const fmt  = (x) => (Math.abs(x) >= 100 ? x.toFixed(0) : x.toFixed(1));

  // Thermal colour ramp for the panel tint (blue -> light blue -> yellow ->
  // orange -> red), interpolated in RGB so it avoids the green midtone that a
  // raw HSL hue sweep from blue to red would pass through.
  const TEMP_STOPS = [
    [15, [49, 112, 214]], [28, [120, 190, 235]], [42, [250, 205, 70]],
    [56, [240, 130, 45]], [72, [205, 45, 45]]
  ];
  function tempColor(t){
    const s = TEMP_STOPS;
    if(t <= s[0][0]) return "rgb(" + s[0][1].join(",") + ")";
    if(t >= s[s.length-1][0]) return "rgb(" + s[s.length-1][1].join(",") + ")";
    for(let i=0;i<s.length-1;i++){
      const t0 = s[i][0], c0 = s[i][1], t1 = s[i+1][0], c1 = s[i+1][1];
      if(t >= t0 && t <= t1){
        const f = (t - t0) / (t1 - t0);
        const r = Math.round(lerp(c0[0], c1[0], f));
        const gg = Math.round(lerp(c0[1], c1[1], f));
        const b = Math.round(lerp(c0[2], c1[2], f));
        return "rgb(" + r + "," + gg + "," + b + ")";
      }
    }
    return "rgb(" + s[0][1].join(",") + ")";
  }

  // --- Panel geometry (recomputed each frame so it tracks resize) ----------
  function geom(){
    const cx = W * 0.5, cy = H * 0.56;
    const len = Math.min(W * 0.42, 320);
    const a = 25 * Math.PI / 180;          // tilt angle
    const dir = {x: Math.cos(a), y: -Math.sin(a)};   // along face, up to the right
    const nF  = {x: -Math.sin(a), y: -Math.cos(a)};  // front normal (to sky)
    const nB  = {x:  Math.sin(a), y:  Math.cos(a)};  // back normal (to ground)
    const p1 = {x: cx - dir.x*len/2, y: cy - dir.y*len/2};
    const p2 = {x: cx + dir.x*len/2, y: cy + dir.y*len/2};
    return {cx, cy, len, a, dir, nF, nB, p1, p2};
  }

  // --- Convection particles ------------------------------------------------
  const MAX_PARTICLES = 260;
  let particles = [];
  function spawnParticle(g){
    const along = clamp(g.len*0.5, 0, 240);
    const s = (Math.random()*2 - 1);       // position along the face
    const base = {x: g.cx + g.dir.x*s*along, y: g.cy + g.dir.y*s*along};
    const off = 8 + Math.random()*22;      // ride just above the front face
    return {
      x: base.x + g.nF.x*off,
      y: base.y + g.nF.y*off,
      life: 0,
      ttl: 60 + Math.random()*60,
      wob: Math.random()*Math.PI*2
    };
  }

  // --- Main draw loop ------------------------------------------------------
  let t0 = null;
  function draw(now){
    if(t0 === null) t0 = now;
    const time = (now - t0) / 1000;

    // Warm-up envelope: intensity ramps 0->1 over ~5 s, then holds; panel
    // temperature interpolates from ambient to steady over the same window.
    let inten = 1, tShown = DATA.t_cell;
    if(WARMUP){
      const ramp = clamp(time / 5.0, 0, 1);
      inten = 0.15 + 0.85*ramp;
      tShown = lerp(DATA.t_air, DATA.t_cell, ramp);
    }

    const g = geom();
    ctx.clearRect(0,0,W,H);

    // Sky and ground.
    const sky = ctx.createLinearGradient(0,0,0,H);
    sky.addColorStop(0, "#bfe3ff");
    sky.addColorStop(0.7, "#e9f4ff");
    ctx.fillStyle = sky; ctx.fillRect(0,0,W,H*0.72);
    const gnd = ctx.createLinearGradient(0,H*0.72,0,H);
    gnd.addColorStop(0, "#cdb892");
    gnd.addColorStop(1, "#b09a72");
    ctx.fillStyle = gnd; ctx.fillRect(0,H*0.72,W,H*0.28);

    // Sun (top-left) with incident rays onto the panel.
    const sun = {x: W*0.13, y: H*0.16};
    const sunR = 22;
    const halo = ctx.createRadialGradient(sun.x,sun.y,2,sun.x,sun.y,sunR*2.4);
    halo.addColorStop(0,"rgba(255,214,90,0.95)");
    halo.addColorStop(1,"rgba(255,214,90,0)");
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(sun.x,sun.y,sunR*2.4,0,Math.PI*2); ctx.fill();
    ctx.fillStyle = "#ffcf3f";
    ctx.beginPath(); ctx.arc(sun.x,sun.y,sunR,0,Math.PI*2); ctx.fill();

    ctx.strokeStyle = "rgba(255,190,40,0.85)"; ctx.lineWidth = 2;
    const nRays = 5;
    for(let i=0;i<nRays;i++){
      const s = (i/(nRays-1) - 0.5)*0.9;
      const target = {x: g.cx + g.dir.x*s*g.len, y: g.cy + g.dir.y*s*g.len};
      const dash = (time*60) % 16;
      ctx.setLineDash([9,7]); ctx.lineDashOffset = -dash;
      ctx.beginPath(); ctx.moveTo(sun.x,sun.y); ctx.lineTo(target.x,target.y); ctx.stroke();
    }
    ctx.setLineDash([]);

    // Reflection rays (a few, bouncing up-right; optical, not heat).
    const rN = Math.round(1 + 3*frac(DATA.reflected)*3);
    ctx.strokeStyle = "rgba(120,170,255,"+(0.35+0.5*frac(DATA.reflected))+")";
    ctx.lineWidth = 1.5;
    for(let i=0;i<rN;i++){
      const s = (i/Math.max(rN-1,1) - 0.5)*0.7;
      const o = {x: g.cx + g.dir.x*s*g.len, y: g.cy + g.dir.y*s*g.len};
      const rlen = 40 + 60*frac(DATA.reflected);
      const rd = {x: g.nF.x*0.6 + 0.8, y: g.nF.y*0.6 - 0.3};
      ctx.beginPath(); ctx.moveTo(o.x,o.y); ctx.lineTo(o.x+rd.x*rlen, o.y+rd.y*rlen); ctx.stroke();
    }

    // The panel itself (thick tinted bar with a frame).
    ctx.save();
    ctx.translate(g.cx, g.cy);
    ctx.rotate(-g.a);
    const th = 12;
    ctx.fillStyle = tempColor(tShown);
    ctx.strokeStyle = "rgba(30,30,40,0.85)"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.rect(-g.len/2, -th/2, g.len, th); ctx.fill(); ctx.stroke();
    // cell grid lines
    ctx.strokeStyle = "rgba(255,255,255,0.35)"; ctx.lineWidth = 1;
    for(let i=1;i<8;i++){ const x=-g.len/2 + i*g.len/8; ctx.beginPath(); ctx.moveTo(x,-th/2); ctx.lineTo(x,th/2); ctx.stroke(); }
    ctx.restore();

    // Support strut.
    ctx.strokeStyle = "rgba(70,70,80,0.9)"; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(g.cx+8, g.cy+4); ctx.lineTo(g.cx+8, H*0.72); ctx.stroke();

    // --- Radiation: wavy arrows to sky (front) and ground (back) -----------
    function radArrows(origin, normal, count, color){
      ctx.strokeStyle = color;
      for(let i=0;i<count;i++){
        const spread = (i/Math.max(count-1,1) - 0.5) * g.len * 0.6;
        const ox = origin.x + g.dir.x*spread;
        const oy = origin.y + g.dir.y*spread;
        const len = (28 + 70*frac(DATA.q_rad)) * inten;
        ctx.lineWidth = 2;
        ctx.beginPath();
        const steps = 14;
        for(let k=0;k<=steps;k++){
          const tt = k/steps;
          const px = ox + normal.x*len*tt + Math.sin(tt*Math.PI*3 + time*6 + i)*4*normal.y;
          const py = oy + normal.y*len*tt + Math.sin(tt*Math.PI*3 + time*6 + i)*4* -normal.x;
          if(k===0) ctx.moveTo(px,py); else ctx.lineTo(px,py);
        }
        ctx.stroke();
        // arrow head
        const hx = ox + normal.x*len, hy = oy + normal.y*len;
        ctx.beginPath();
        ctx.moveTo(hx,hy);
        ctx.lineTo(hx - normal.x*8 - normal.y*5, hy - normal.y*8 + normal.x*5);
        ctx.moveTo(hx,hy);
        ctx.lineTo(hx - normal.x*8 + normal.y*5, hy - normal.y*8 - normal.x*5);
        ctx.stroke();
      }
    }
    const radN = Math.round(2 + 4*frac(DATA.q_rad));
    const radOpacity = 0.45 + 0.5*frac(DATA.q_rad);
    const frontOrigin = {x: g.cx + g.nF.x*10, y: g.cy + g.nF.y*10};
    const backOrigin  = {x: g.cx + g.nB.x*10, y: g.cy + g.nB.y*10};
    radArrows(frontOrigin, g.nF, radN, "rgba(255,110,60,"+radOpacity+")");
    radArrows(backOrigin,  g.nB, Math.max(1,Math.round(radN*0.6)), "rgba(255,140,80,"+(radOpacity*0.8)+")");

    // --- Convection particles (blue in from the wind side, red out) --------
    const emit = Math.round(frac(DATA.q_conv) * 3 * inten);
    for(let i=0;i<emit;i++){ if(particles.length < MAX_PARTICLES) particles.push(spawnParticle(g)); }
    const windPush = 0.5 + DATA.wind*0.35;
    const next = [];
    for(const p of particles){
      p.life += 1;
      p.x += (g.dir.x*windPush*2.0) + 0.4;
      p.y += (g.dir.y*windPush*2.0) - 0.25 + Math.sin(p.wob + p.life*0.15)*0.4;
      if(p.life < p.ttl && p.x < W+20 && p.y > -20){
        const u = clamp(p.life/p.ttl, 0, 1);
        const hue = lerp(210, 8, u);       // cold blue -> warm red
        const alpha = 0.85 * (1 - u*0.5);
        ctx.fillStyle = "hsla("+hue.toFixed(0)+",90%,55%,"+alpha.toFixed(2)+")";
        ctx.beginPath(); ctx.arc(p.x, p.y, 2.6, 0, Math.PI*2); ctx.fill();
        next.push(p);
      }
    }
    particles = next;

    // --- Conduction: arrow down the strut, width ~ Q_cond ------------------
    const condW = clamp(1 + 10*frac(DATA.q_cond)*4, 1, 9);
    ctx.strokeStyle = "rgba(150,90,60,0.85)"; ctx.lineWidth = condW;
    const c0 = {x: g.cx+8, y: g.cy+6};
    const c1 = {x: g.cx+8, y: g.cy+6 + 40*inten};
    ctx.beginPath(); ctx.moveTo(c0.x,c0.y); ctx.lineTo(c1.x,c1.y); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(c1.x, c1.y);
    ctx.lineTo(c1.x-5, c1.y-7); ctx.moveTo(c1.x, c1.y); ctx.lineTo(c1.x+5, c1.y-7);
    ctx.stroke();

    // --- Electricity: cable + bolt from the low end of the panel -----------
    const elx = g.p1.x - 6, ely = g.p1.y + 6;
    ctx.strokeStyle = "rgba(40,40,40,0.8)"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(g.p1.x, g.p1.y); ctx.lineTo(elx, ely+18); ctx.lineTo(elx-24, ely+18); ctx.stroke();
    const boltPulse = 0.6 + 0.4*Math.sin(time*8);
    ctx.fillStyle = "rgba(255,206,0,"+boltPulse.toFixed(2)+")";
    ctx.strokeStyle = "rgba(180,140,0,0.9)"; ctx.lineWidth = 1;
    const bx = elx-30, by = ely+10, bs = 8 + 8*frac(DATA.p_el);
    ctx.beginPath();
    ctx.moveTo(bx, by-bs); ctx.lineTo(bx-bs*0.5, by); ctx.lineTo(bx, by);
    ctx.lineTo(bx-bs*0.4, by+bs); ctx.lineTo(bx+bs*0.6, by-bs*0.2); ctx.lineTo(bx, by-bs*0.2);
    ctx.closePath(); ctx.fill(); ctx.stroke();

    // --- Labels --------------------------------------------------------------
    drawLabels(g, tShown);

    requestAnimationFrame(draw);
  }

  function chip(x, y, color, text){
    ctx.font = "600 12px system-ui,Segoe UI,sans-serif";
    const w = ctx.measureText(text).width + 24;
    ctx.fillStyle = "rgba(255,255,255,0.82)";
    ctx.strokeStyle = "rgba(0,0,0,0.12)"; ctx.lineWidth = 1;
    roundRect(x, y, w, 20, 6); ctx.fill(); ctx.stroke();
    ctx.fillStyle = color;
    ctx.beginPath(); ctx.arc(x+11, y+10, 5, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = "#1a1a1a";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x+20, y+11);
  }
  function roundRect(x,y,w,h,r){
    ctx.beginPath();
    ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r);
    ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath();
  }
  function line(v){ return fmt(v) + " " + L.wm2 + " (" + pct(v).toFixed(0) + "%)"; }

  function drawLabels(g, tShown){
    let y = 10;
    const x = 10;
    chip(x, y, "#ff6e3c", L.radiation + ": " + line(DATA.q_rad));      y += 25;
    chip(x, y, "#2f8fff", L.convection + ": " + line(DATA.q_conv));    y += 25;
    chip(x, y, "#96593c", L.conduction + ": " + line(DATA.q_cond));    y += 25;
    chip(x, y, "#ffce00", L.electricity + ": " + line(DATA.p_el));     y += 25;
    chip(x, y, "#78aaff", L.reflection + ": " + line(DATA.reflected)); y += 25;
    // panel temperature chip near the panel
    ctx.font = "700 13px system-ui,Segoe UI,sans-serif";
    const tt = L.panel_temp + ": " + tShown.toFixed(1) + " °C";
    const w = ctx.measureText(tt).width + 18;
    ctx.fillStyle = "rgba(20,20,30,0.78)";
    roundRect(g.cx - w/2, g.cy - 44, w, 22, 7); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.textBaseline = "middle";
    ctx.fillText(tt, g.cx - w/2 + 9, g.cy - 33);

    if(WARMUP && L.transient_note){
      ctx.font = "500 11px system-ui,Segoe UI,sans-serif";
      ctx.fillStyle = "rgba(30,30,40,0.7)";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(L.transient_note, 10, H - 10);
    }
  }

  requestAnimationFrame(draw);
})();
</script>
"""


def heatflow_html(
    result: SimResult,
    labels: dict[str, str],
    wind: float = 2.0,
    height: int = 460,
    warmup: bool = False,
) -> str:
    """Build the standalone HTML/JS string for the heat-flow animation."""
    data = result.flux_json()
    data["wind"] = float(wind)
    html = _HTML_TEMPLATE
    html = html.replace("__DATA__", json.dumps(data))
    html = html.replace("__LABELS__", json.dumps(labels, ensure_ascii=True))
    html = html.replace("__HEIGHT__", str(int(height)))
    html = html.replace("__WARMUP__", "true" if warmup else "false")
    return html


def render_heatflow(
    result: SimResult,
    labels: dict[str, str],
    wind: float,
    height: int = 460,
    warmup: bool = False,
) -> None:
    """Render the animation inside a Streamlit app via components.v1.html."""
    import streamlit.components.v1 as components

    html = heatflow_html(result, labels, wind=wind, height=height, warmup=warmup)
    components.html(html, height=height + 12, scrolling=False)


__all__ = ["heatflow_html", "render_heatflow"]
