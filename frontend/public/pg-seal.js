/* PROVING GROUND — shared Struck Seal renderer.
   Classic script: registers window.PGSeal. Load via <script src="/pg-seal.js">.
   The seal is the persistent signature across all four surfaces. Color is supplied by the caller:
   in the live cockpit it is earned (gold once proven); on a static deck it rests in steel.
   Source of truth — ported verbatim from the Claude Design "pg-seal.js" (PROVING GROUND round 1). */
(function () {
  function rgb(hex) {
    if (typeof hex !== 'string' || hex[0] !== '#') return [110, 140, 168];
    var n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgba(c, a) {
    var x = Array.isArray(c) ? c : rgb(c);
    return 'rgba(' + x[0] + ',' + x[1] + ',' + x[2] + ',' + a + ')';
  }
  function mulberry(seed) {
    var a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function seedInt(devId) {
    var h = (devId || '').replace(/[^0-9a-f]/gi, '');
    return (parseInt(h.slice(0, 8) || '9f3c2ba3', 16) >>> 0) || 0x9f3c2ba3;
  }
  // o: {cx,cy,R,color,now,motion,intensity,bloom,seed}
  function drawStruckSeal(ctx, o) {
    var cx = o.cx, cy = o.cy, R = o.R, col = o.color || '#6E8CA8', now = o.now || 0;
    var motion = !!o.motion, intensity = (o.intensity == null ? 1 : o.intensity), bloom = o.bloom || 0;
    var rand = mulberry(o.seed != null ? o.seed : 0x9f3c2ba3);
    var breath = motion ? (0.84 + 0.16 * (0.5 + 0.5 * Math.sin(now * 0.0016))) : 1;
    var flick = motion ? (0.85 + 0.15 * Math.abs(Math.sin(now * 0.013))) : 1;
    var I = intensity * breath;
    ctx.save();
    ctx.translate(cx, cy);
    // halo (glows through a translucent twin in the cockpit; ambient here)
    var halo = ctx.createRadialGradient(0, 0, R * 0.2, 0, 0, R * 1.9);
    halo.addColorStop(0, rgba(col, (0.12 + 0.18 * bloom) * I));
    halo.addColorStop(0.5, rgba(col, (0.05 + 0.07 * bloom) * I));
    halo.addColorStop(1, rgba(col, 0));
    ctx.beginPath(); ctx.arc(0, 0, R * 1.9, 0, Math.PI * 2); ctx.fillStyle = halo; ctx.fill();
    var spokes = 10 + Math.floor(rand() * 7);
    ctx.rotate(motion ? now * 0.00006 : 0);
    for (var i = 0; i < 3; i++) {
      var rr = R * (0.5 + i * 0.2);
      ctx.beginPath(); ctx.arc(0, 0, rr, 0, Math.PI * 2);
      ctx.strokeStyle = rgba(col, (0.10 + 0.05 * i) * I); ctx.lineWidth = 1; ctx.stroke();
    }
    for (var j = 0; j < spokes; j++) {
      var ang = (j / spokes) * Math.PI * 2, len = R * (0.42 + rand() * 0.5);
      var x = Math.cos(ang) * len, y = Math.sin(ang) * len;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(x, y);
      ctx.strokeStyle = rgba(col, 0.22 * I * flick); ctx.lineWidth = 1; ctx.stroke();
      var p = 0.5 + 0.5 * Math.sin(now * 0.002 + j);
      ctx.beginPath(); ctx.arc(x, y, 1.5 + p * 1.4, 0, Math.PI * 2);
      ctx.fillStyle = rgba(col, (0.5 + 0.4 * bloom) * I); ctx.fill();
    }
    ctx.beginPath();
    for (var k = 0; k <= spokes; k++) {
      var a2 = (k / spokes) * Math.PI * 2;
      var r2 = R * (0.2 + 0.08 * Math.sin(a2 * 3 + (motion ? now * 0.0011 : 0)));
      var px = Math.cos(a2) * r2, py = Math.sin(a2) * r2;
      k === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.closePath(); ctx.strokeStyle = rgba(col, 0.6 * I); ctx.lineWidth = 1.5; ctx.stroke();
    var g = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 0.34);
    g.addColorStop(0, rgba(col, (0.5 + 0.4 * bloom) * I)); g.addColorStop(1, rgba(col, 0));
    ctx.beginPath(); ctx.arc(0, 0, R * 0.34, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
    ctx.restore();
  }
  window.PGSeal = { drawStruckSeal: drawStruckSeal, mulberry: mulberry, seedInt: seedInt, rgb: rgb, rgba: rgba };
})();
