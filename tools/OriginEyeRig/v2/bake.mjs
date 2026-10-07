// Bake a vanilla Spine 4.2 binary skeleton into a constraint-free Spine 4.2 JSON:
// setup pose (bones/slots/mesh+region attachments) + every animation sampled at FPS from the
// runtime (applied local transforms after path/transform constraints, slot colour, attachment, deform).
// usage: node bake.mjs <in.skel> <in.atlas> <out.json> <extra.json>
import * as S from '@esotericsoftware/spine-core';
import fs from 'fs';
const [,, skelPath, atlasPath, outPath, extraPath] = process.argv;
const FPS = 30;
const atlas = new S.TextureAtlas(fs.readFileSync(atlasPath, 'utf8'));
for (const p of atlas.pages) p.setTexture({ setFilters() {}, setWraps() {}, dispose() {}, getImage() { return { width: p.width, height: p.height }; } });
const sd = new S.SkeletonBinary(new S.AtlasAttachmentLoader(atlas)).readSkeletonData(new Uint8Array(fs.readFileSync(skelPath)));
const extra = extraPath ? JSON.parse(fs.readFileSync(extraPath, 'utf8')) : {};
const r = (v, d = 3) => Math.round(v * 10 ** d) / 10 ** d;
const hex = c => [c.r, c.g, c.b, c.a].map(v => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, '0')).join('');
const BLEND = ['normal', 'additive', 'multiply', 'screen'];
const RC = extra.recolor || null; const RCS = new Set(RC ? RC.slots : []);
function rgb2hsv(r,g,b){const mx=Math.max(r,g,b),mn=Math.min(r,g,b),d=mx-mn;let h=0;if(d){if(mx===r)h=((g-b)/d)%6;else if(mx===g)h=(b-r)/d+2;else h=(r-g)/d+4;h*=60;if(h<0)h+=360;}return[h,mx?d/mx:0,mx];}
function hsv2rgb(h,s,v){const c=v*s,x=c*(1-Math.abs((h/60)%2-1)),m=v-c;let r,g,b;[r,g,b]=h<60?[c,x,0]:h<120?[x,c,0]:h<180?[0,c,x]:h<240?[0,x,c]:h<300?[x,0,c]:[c,0,x];return[r+m,g+m,b+m];}
function remapHex(hx){ if(!RC) return hx; const v=[0,2,4,6].map(o=>parseInt(hx.substr(o,2),16)/255); let [h,sa,va]=rgb2hsv(v[0],v[1],v[2]);
  if (sa < 0.05) return hx; h = ((RC.hueTo + (h - RC.hueFrom) * RC.k) % 360 + 360) % 360; sa = Math.min(1, sa * (RC.sat||1)); va = va * (RC.val||1);
  const o=hsv2rgb(h,sa,va); return [...o, v[3]].map(x=>Math.round(Math.max(0,Math.min(1,x))*255).toString(16).padStart(2,'0')).join(''); }
const OV = extra.overlays || {};

function dec(b){ // world matrix -> (rot, x, y, sx, sy, shx, shy) relative to an identity root
  const rot=Math.atan2(b.c,b.a)*180/Math.PI; const sx=Math.hypot(b.a,b.c); const sy=Math.hypot(b.b,b.d);
  let shy=Math.atan2(b.d,b.b)*180/Math.PI-rot-90; while(shy>180)shy-=360; while(shy<-180)shy+=360;
  return [rot,b.worldX,b.worldY,sx,sy,0,shy];
}
const setupSk=new S.Skeleton(sd); setupSk.setToSetupPose(); setupSk.updateWorldTransform(S.Physics.none);
const SETUP=setupSk.bones.map(dec);
// ---------------- setup
const bones = sd.bones.map((b, i) => {
  const e = { name: b.name };
  if (i === 0) return e;
  e.parent = sd.bones[0].name;
  const [rot, x, y, sx, sy, , shy] = SETUP[i];
  if (b.length) e.length = r(b.length);
  if (x) e.x = r(x, 4); if (y) e.y = r(y, 4); if (rot) e.rotation = r(rot, 4);
  if (Math.abs(sx - 1) > 1e-6) e.scaleX = r(sx, 5); if (Math.abs(sy - 1) > 1e-6) e.scaleY = r(sy, 5);
  if (Math.abs(shy) > 1e-5) e.shearY = r(shy, 4);
  return e;
});
const dropSlots = new Set(extra.dropSlots || []);
const slots = sd.slots.filter(s => !dropSlots.has(s.name)).map(s => {
  const e = { name: s.name, bone: s.boneData.name };
  if (s.attachmentName) e.attachment = s.attachmentName;
  if (s.blendMode) e.blend = BLEND[s.blendMode];
  let c = hex(s.color); if (RCS.has(s.name)) c = remapHex(c); if (c !== 'ffffffff') e.color = c;
  return e;
});
for (const [base, ov] of Object.entries(OV)) {
  const i = slots.findIndex(x => x.name === base); const b = slots[i];
  const e = { name: base + ' spots', bone: b.bone, color: ov.color + (b.color ? b.color.substr(6, 2) : 'ff'), blend: 'additive' };
  if (b.attachment) e.attachment = b.attachment + ' spots';
  slots.splice(i + 1, 0, e);
}
const keepSlot = new Set(slots.map(s => s.name));
const skinAtt = {};
const skin = sd.defaultSkin;
for (const { slotIndex, name, attachment: a } of skin.getAttachments()) {
  const slotName = sd.slots[slotIndex].name;
  if (!keepSlot.has(slotName)) continue;
  let e = null;
  if (a instanceof S.RegionAttachment) {
    e = { x: r(a.x), y: r(a.y), width: r(a.width), height: r(a.height) };
    if (a.rotation) e.rotation = r(a.rotation);
    if (a.scaleX !== 1) e.scaleX = r(a.scaleX, 4); if (a.scaleY !== 1) e.scaleY = r(a.scaleY, 4);
    if (a.path !== name) e.path = a.path;
    const c = hex(a.color); if (c !== 'ffffffff') e.color = c;
  } else if (a instanceof S.MeshAttachment) {
    e = { type: 'mesh', uvs: Array.from(a.regionUVs, v => r(v, 5)), triangles: Array.from(a.triangles),
          vertices: Array.from(a.bones ? (() => { const out = []; let vi = 0, bi = 0;
            while (bi < a.bones.length) { const n = a.bones[bi++]; out.push(n);
              for (let k = 0; k < n; k++) { out.push(a.bones[bi++], r(a.vertices[vi]), r(a.vertices[vi + 1]), r(a.vertices[vi + 2], 5)); vi += 3; } }
            return out; })() : a.vertices, v => v), hull: a.hullLength / 2, width: r(a.width), height: r(a.height) };
    if (!a.bones) e.vertices = e.vertices.map(v => r(v));
    if (a.edges && a.edges.length) e.edges = Array.from(a.edges);
    if (a.path !== name) e.path = a.path;
    const c = hex(a.color); if (c !== 'ffffffff') e.color = c;
  } else continue;  // path/bbox/etc not needed after baking
  (skinAtt[slotName] ||= {})[name] = e;
  if (OV[slotName] && (OV[slotName].atts || []).includes(name)) {
    const c2 = JSON.parse(JSON.stringify(e)); c2.path = (e.path || name) + ' spots'; delete c2.color;
    (skinAtt[slotName + ' spots'] ||= {})[name + ' spots'] = c2;
  }
}

// ---------------- sample animations
const skel = new S.Skeleton(sd);
function reduce(times, vals, eps) {
  const keep = [0]; let i = 0; const N = times.length;
  while (i < N - 1) {
    let j = i + 2;
    for (; j < N; j++) {
      let ok = true;
      for (let m = i + 1; m < j && ok; m++) {
        const u = (times[m] - times[i]) / (times[j] - times[i]);
        for (let q = 0; q < vals[0].length; q++)
          if (Math.abs(vals[i][q] + (vals[j][q] - vals[i][q]) * u - vals[m][q]) > eps[q]) { ok = false; break; }
      }
      if (!ok) break;
    }
    i = j - 1; keep.push(i);
  }
  return keep;
}
function unwrap(arr) { for (let k = 1; k < arr.length; k++) { while (arr[k] - arr[k - 1] > 180) arr[k] -= 360; while (arr[k] - arr[k - 1] < -180) arr[k] += 360; } return arr; }

function sample(anim, dur, frameFn) {
  const n = Math.max(1, Math.round(dur * FPS));
  const frames = [];
  for (let k = 0; k <= n; k++) {
    const t = Math.min(dur, k / FPS);
    skel.setToSetupPose();
    frameFn(t);
    skel.updateWorldTransform(S.Physics.none);
        frames.push({
      t,
      bones: skel.bones.map(dec),
      slots: skel.slots.map(s => ({ c: hex(s.color), a: s.attachment ? s.attachment.name : null, d: s.deform.length ? Array.from(s.deform) : null })),
      order: skel.drawOrder.map(s => s.data.name),
    });
  }
  return frames;
}

function toJson(frames) {
  const times = frames.map(f => r(f.t, 4));
  const out = { bones: {}, slots: {}, deform: {} };
  sd.bones.forEach((bd, i) => {
    if (i === 0) return;
    const tl = {}; const SU = SETUP[i];
    const rot = unwrap(frames.map(f => f.bones[i][0] - SU[0])).map(v => [v]);
    const tr = frames.map(f => [f.bones[i][1] - SU[1], f.bones[i][2] - SU[2]]);
    const sc = frames.map(f => [f.bones[i][3] / (SU[3] || 1e-6), f.bones[i][4] / (SU[4] || 1e-6)]);
    const sh = unwrap(frames.map(f => f.bones[i][6] - SU[6])).map(v => [0, v]);
    if (rot.some(v => Math.abs(v[0]) > 1e-3)) tl.rotate = reduce(times, rot, [0.008]).map(k => ({ time: times[k], value: r(rot[k][0]) }));
    if (tr.some(v => Math.abs(v[0]) > 1e-3 || Math.abs(v[1]) > 1e-3)) tl.translate = reduce(times, tr, [0.01, 0.01]).map(k => ({ time: times[k], x: r(tr[k][0], 2), y: r(tr[k][1], 2) }));
    if (sc.some(v => Math.abs(v[0] - 1) > 1e-4 || Math.abs(v[1] - 1) > 1e-4)) tl.scale = reduce(times, sc, [1e-4, 1e-4]).map(k => ({ time: times[k], x: r(sc[k][0], 4), y: r(sc[k][1], 4) }));
    if (sh.some(v => Math.abs(v[0]) > 1e-3 || Math.abs(v[1]) > 1e-3)) tl.shear = reduce(times, sh, [0.05, 0.05]).map(k => ({ time: times[k], x: r(sh[k][0], 2), y: r(sh[k][1], 2) }));
    for (const a of Object.values(tl)) if (a[0].time === 0) delete a[0].time;
    if (Object.keys(tl).length) out.bones[bd.name] = tl;
  });
  sd.slots.forEach((sdat, i) => {
    if (!keepSlot.has(sdat.name)) return;
    const tl = {};
    let cols = frames.map(f => f.slots[i].c);
    if (RCS.has(sdat.name)) cols = cols.map(remapHex);
    const setupC = RCS.has(sdat.name) ? remapHex(hex(sdat.color)) : hex(sdat.color);
    if (cols.some(c => c !== setupC)) {
      const v = cols.map(c => [0, 2, 4, 6].map(o => parseInt(c.substr(o, 2), 16) / 255));
      tl.rgba = reduce(times, v, [0.004, 0.004, 0.004, 0.004]).map(k => ({ time: times[k], color: cols[k] }));
    }
    const atts = frames.map(f => f.slots[i].a);
    if (atts.some(a => a !== sdat.attachmentName)) {
      const keys = [{ time: 0, name: atts[0] }];
      for (let k = 1; k < atts.length; k++) if (atts[k] !== atts[k - 1]) keys.push({ time: times[k], name: atts[k] });
      tl.attachment = keys;
    }
    for (const a of Object.values(tl)) if (a[0].time === 0) delete a[0].time;
    if (Object.keys(tl).length) out.slots[sdat.name] = tl;
    if (OV[sdat.name]) {
      const ov = OV[sdat.name]; const t2 = {}; const atts2 = OV[sdat.name].atts || [];
      const al = frames.map(f => [parseInt(f.slots[i].c.substr(6, 2), 16) / 255]);
      t2.rgba = reduce(times, al, [0.004]).map(k => ({ time: times[k], color: ov.color + frames[k].slots[i].c.substr(6, 2) }));
      if (tl.attachment) t2.attachment = tl.attachment.map(k => ({ ...k, name: k.name && atts2.includes(k.name) ? k.name + ' spots' : null }));
      if (t2.rgba[0].time === 0) delete t2.rgba[0].time;
      out.slots[sdat.name + ' spots'] = t2;
    }
    const defs = frames.map(f => f.slots[i].d);
    if (defs.some(d => d)) {
      const att = frames.find(f => f.slots[i].d).slots[i].a;
      const len = defs.find(d => d).length;
      const v = defs.map(d => d || new Array(len).fill(0));
      // deform arrays hold absolute vertex values; convert to offsets from setup
      const m = skin.getAttachment(i, att);
      const base = m.bones ? null : m.vertices;
      const offs = v.map(d => base ? d.map((x, q) => x - base[q]) : d);
      const ks = reduce(times, offs.map(o => [Math.max(...o.map(Math.abs))]), [0.02]);
      (out.deform[sdat.name] ||= {})[att] = ks.map(k => ({ time: times[k], vertices: offs[k].map(x => r(x, 2)) }));
      for (const key of out.deform[sdat.name][att]) if (key.time === 0) delete key.time;
      if (OV[sdat.name] && (OV[sdat.name].atts || []).includes(att)) (out.deform[sdat.name + ' spots'] ||= {})[att + ' spots'] = out.deform[sdat.name][att];
    }
  });
  const setupOrder = sd.slots.map(s => s.name);
  if (frames.some(f => f.order.join() !== setupOrder.join())) {
    out.drawOrder = [];
    let prev = null;
    frames.forEach((f, k) => {
      const o = f.order.filter(n => keepSlot.has(n)); const js = o.join();
      if (js === prev) return; prev = js;
      const kept = setupOrder.filter(n => keepSlot.has(n));
      const offsets = [];
      o.forEach((n, idx) => { const si = kept.indexOf(n); if (si !== idx) offsets.push({ slot: n, offset: idx - si }); });
      const e = { time: times[k] }; if (offsets.length) e.offsets = offsets; if (e.time === 0) delete e.time;
      out.drawOrder.push(e);
    });
  }
  if (!Object.keys(out.deform).length) delete out.deform;
  return out;
}

const animations = {};
const byName = Object.fromEntries(sd.animations.map(a => [a.name, a]));
const plan = extra.animations || Object.fromEntries(sd.animations.map(a => [a.name, { from: a.name }]));
for (const [name, p] of Object.entries(plan)) {
  const src = byName[p.from];
  const dur = p.duration ?? src.duration;
  const frames = sample(src, dur, t => {
    let st = t;
    if (p.reverse) st = src.duration - t * (src.duration / dur);
    else if (p.speed) st = Math.min(src.duration, t * p.speed);
    if (p.hold !== undefined) st = p.hold;
    src.apply(skel, 0, st, !!p.loop, [], 1, S.MixBlend.setup, S.MixDirection.mixIn);
    if (p.overlay) for (const [bn, spec] of Object.entries(p.overlay)) {
      const b = skel.findBone(bn);
      const env = spec.env === 'hurt' ? Math.exp(-7 * t) * Math.sin(Math.PI * Math.min(1, t / 0.06)) : 1;
      if (spec.r) b.rotation += spec.r * env; if (spec.x) b.x += spec.x * env; if (spec.y) b.y += spec.y * env;
      if (spec.sx) b.scaleX *= 1 + spec.sx * env; if (spec.sy) b.scaleY *= 1 + spec.sy * env;
    }
    if (p.tint) for (const s of skel.slots) { const e = Math.exp(-6 * t) * Math.sin(Math.PI * Math.min(1, t / 0.05)); s.color.r = Math.min(1, s.color.r * (1 - p.tint[3] * e) + p.tint[0] * p.tint[3] * e); s.color.g *= (1 - p.tint[3] * e) + p.tint[1] * p.tint[3] * e; s.color.b *= (1 - p.tint[3] * e) + p.tint[2] * p.tint[3] * e; }
  });
  animations[name] = toJson(frames);
}

const xs = []; const ys = [];
const json = {
  skeleton: { hash: (extra.hash || 'baked') + '1', spine: '4.2.0', x: -200, y: -50, width: 400, height: 450, images: './', audio: '' },
  bones, slots, skins: [{ name: 'default', attachments: skinAtt }], animations,
};
fs.writeFileSync(outPath, JSON.stringify(json));
console.log('baked', outPath, 'bones', bones.length, 'slots', slots.length, 'anims', Object.keys(animations).map(k => k + ':' + JSON.stringify(animations[k]).length).join(' '));
