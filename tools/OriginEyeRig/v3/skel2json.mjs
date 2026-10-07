// Faithful Spine 4.2 binary (.skel) -> JSON converter (keeps constraints, weights, path attachments and the exact
// Bezier control points of every key).  usage: node skel2json.mjs <in.skel> <in.atlas> <out.json>
// Only the data kinds used by the STS2 fogmog / eye_with_teeth rigs are supported; anything else throws.
import * as S from '@esotericsoftware/spine-core';
import fs from 'fs';

// ---- record Bezier control points while the binary is read (runtime keeps only the sampled curve)
const BZ = new WeakMap();
function hook(proto) {
  const orig = proto.setBezier;
  proto.setBezier = function (bezier, frame, value, time1, value1, cx1, cy1, cx2, cy2, time2, value2) {
    let m = BZ.get(this); if (!m) { m = new Map(); BZ.set(this, m); }
    m.set(frame * 64 + value, [cx1, cy1, cx2, cy2]);
    return orig.call(this, bezier, frame, value, time1, value1, cx1, cy1, cx2, cy2, time2, value2);
  };
}
hook(S.CurveTimeline.prototype);
if (S.DeformTimeline.prototype.hasOwnProperty('setBezier')) hook(S.DeformTimeline.prototype);

const [, , skelPath, atlasPath, outPath] = process.argv;
const atlas = new S.TextureAtlas(fs.readFileSync(atlasPath, 'utf8'));
for (const p of atlas.pages) p.setTexture({ setFilters() {}, setWraps() {}, dispose() {}, getImage() { return { width: p.width, height: p.height }; } });
const sd = new S.SkeletonBinary(new S.AtlasAttachmentLoader(atlas)).readSkeletonData(new Uint8Array(fs.readFileSync(skelPath)));

const R = (v, d = 5) => { const k = 10 ** d; const r = Math.round(v * k) / k; return Object.is(r, -0) ? 0 : r; };
const T = (t) => R(t, 6);
const hex2 = (v) => Math.max(0, Math.min(255, Math.round(v * 255))).toString(16).padStart(2, '0');
const colHex = (c, alpha = true) => hex2(c.r) + hex2(c.g) + hex2(c.b) + (alpha ? hex2(c.a) : '');
const isWhite = (c) => c.r === 1 && c.g === 1 && c.b === 1 && c.a === 1;
const INHERIT = ['normal', 'onlyTranslation', 'noRotationOrReflection', 'noScale', 'noScaleOrReflection'];
const BLEND = [null, 'additive', 'multiply', 'screen'];
const POSMODE = ['fixed', 'percent'];
const SPACEMODE = ['length', 'fixed', 'percent', 'proportional'];
const ROTMODE = ['tangent', 'chain', 'chainScale'];

const out = {
  skeleton: { hash: sd.hash, spine: sd.version, x: R(sd.x, 3), y: R(sd.y, 3), width: R(sd.width, 3), height: R(sd.height, 3), fps: sd.fps || 30, images: sd.imagesPath || './', audio: sd.audioPath || '' },
  bones: [], slots: [], ik: [], transform: [], path: [], skins: [], animations: {},
};

for (const b of sd.bones) {
  const e = { name: b.name };
  if (b.parent) e.parent = b.parent.name;
  if (b.length) e.length = R(b.length);
  if (b.x) e.x = R(b.x); if (b.y) e.y = R(b.y);
  if (b.rotation) e.rotation = R(b.rotation);
  if (b.scaleX !== 1) e.scaleX = R(b.scaleX); if (b.scaleY !== 1) e.scaleY = R(b.scaleY);
  if (b.shearX) e.shearX = R(b.shearX); if (b.shearY) e.shearY = R(b.shearY);
  if (b.inherit) e.inherit = INHERIT[b.inherit];
  if (b.skinRequired) throw new Error('skin-required bone ' + b.name);
  out.bones.push(e);
}
for (const s of sd.slots) {
  const e = { name: s.name, bone: s.boneData.name };
  if (!isWhite(s.color)) e.color = colHex(s.color);
  if (s.darkColor) throw new Error('dark colour slot ' + s.name);
  if (s.attachmentName) e.attachment = s.attachmentName;
  if (s.blendMode) e.blend = BLEND[s.blendMode];
  out.slots.push(e);
}
for (const c of sd.ikConstraints) {
  if (c.skinRequired) throw new Error('skin ik');
  out.ik.push({ name: c.name, order: c.order, bones: c.bones.map(b => b.name), target: c.target.name, mix: R(c.mix), softness: R(c.softness), bendPositive: c.bendDirection > 0, compress: c.compress, stretch: c.stretch, uniform: c.uniform });
}
for (const c of sd.transformConstraints) {
  if (c.skinRequired) throw new Error('skin tc');
  out.transform.push({ name: c.name, order: c.order, bones: c.bones.map(b => b.name), target: c.target.name,
    rotation: R(c.offsetRotation), x: R(c.offsetX), y: R(c.offsetY), scaleX: R(c.offsetScaleX), scaleY: R(c.offsetScaleY), shearY: R(c.offsetShearY),
    mixRotate: R(c.mixRotate), mixX: R(c.mixX), mixY: R(c.mixY), mixScaleX: R(c.mixScaleX), mixScaleY: R(c.mixScaleY), mixShearY: R(c.mixShearY),
    local: c.local, relative: c.relative });
}
for (const c of sd.pathConstraints) {
  if (c.skinRequired) throw new Error('skin path');
  out.path.push({ name: c.name, order: c.order, bones: c.bones.map(b => b.name), target: c.target.name,
    positionMode: POSMODE[c.positionMode], spacingMode: SPACEMODE[c.spacingMode], rotateMode: ROTMODE[c.rotateMode],
    rotation: R(c.offsetRotation), position: R(c.position), spacing: R(c.spacing), mixRotate: R(c.mixRotate), mixX: R(c.mixX), mixY: R(c.mixY) });
}
if ((sd.physicsConstraints || []).length) throw new Error('physics constraints not supported');
if (!out.ik.length) delete out.ik; if (!out.transform.length) delete out.transform; if (!out.path.length) delete out.path;

function vertsJson(a) {                  // VertexAttachment -> JSON "vertices" (weighted: [n, bone, x, y, w, ...])
  if (!a.bones) return Array.from(a.vertices, v => R(v, 4));
  const o = []; let b = 0, w = 0;
  while (b < a.bones.length) {
    const n = a.bones[b++]; o.push(n);
    for (let j = 0; j < n; j++, b++, w += 3) o.push(a.bones[b], R(a.vertices[w], 4), R(a.vertices[w + 1], 4), R(a.vertices[w + 2], 6));
  }
  return o;
}
for (const skin of sd.skins) {
  const sj = { name: skin.name, attachments: {} };
  for (const { slotIndex, name, attachment: a } of skin.getAttachments()) {
    const slot = sd.slots[slotIndex].name; let e;
    if (a instanceof S.RegionAttachment) {
      e = {}; if (a.path !== name) e.path = a.path;
      if (a.x) e.x = R(a.x); if (a.y) e.y = R(a.y); if (a.rotation) e.rotation = R(a.rotation);
      if (a.scaleX !== 1) e.scaleX = R(a.scaleX); if (a.scaleY !== 1) e.scaleY = R(a.scaleY);
      e.width = R(a.width); e.height = R(a.height);
      if (a.sequence) throw new Error('sequence');
    } else if (a instanceof S.MeshAttachment) {
      if (a.parentMesh || a.sequence) throw new Error('linked mesh / sequence ' + name);
      e = { type: 'mesh' }; if (a.path !== name) e.path = a.path;
      e.uvs = Array.from(a.regionUVs, v => R(v, 6)); e.triangles = Array.from(a.triangles); e.vertices = vertsJson(a);
      e.hull = a.hullLength / 2; if (a.edges && a.edges.length) e.edges = Array.from(a.edges);
      if (a.width) e.width = R(a.width); if (a.height) e.height = R(a.height);
    } else if (a instanceof S.PathAttachment) {
      e = { type: 'path', closed: a.closed, constantSpeed: a.constantSpeed, lengths: Array.from(a.lengths, v => R(v, 4)), vertexCount: a.worldVerticesLength / 2, vertices: vertsJson(a) };
    } else throw new Error('unsupported attachment ' + a.constructor.name);
    if (a.name !== name) e.name = a.name;
    if (a.color && !isWhite(a.color)) e.color = colHex(a.color);
    (sj.attachments[slot] ||= {})[name] = e;
  }
  out.skins.push(sj);
}

// ---- animations
function curveOf(tl, frame, nValues) {
  if (frame >= tl.getFrameCount() - 1) return undefined;
  const type = tl.curves[frame];
  if (type === 0) return undefined;            // linear
  if (type === 1) return 'stepped';
  const m = BZ.get(tl); const c = [];
  for (let v = 0; v < nValues; v++) {
    const p = m && m.get(frame * 64 + v); if (!p) throw new Error('missing bezier ' + tl.constructor.name + ' frame ' + frame + ' value ' + v);
    c.push(T(p[0]), R(p[1], 6), T(p[2]), R(p[3], 6));
  }
  return c;
}
const BONE1 = { RotateTimeline: 'rotate', TranslateXTimeline: 'translatex', TranslateYTimeline: 'translatey', ScaleXTimeline: 'scalex', ScaleYTimeline: 'scaley', ShearXTimeline: 'shearx', ShearYTimeline: 'sheary' };
const BONE2 = { TranslateTimeline: 'translate', ScaleTimeline: 'scale', ShearTimeline: 'shear' };
for (const anim of sd.animations) {
  const A = {};
  for (const tl of anim.timelines) {
    const kind = tl.constructor.name, F = tl.frames, n = tl.getFrameCount(), E = tl.getFrameEntries();
    const keys = [];
    if (BONE1[kind] || BONE2[kind]) {
      const bone = sd.bones[tl.boneIndex].name;
      for (let i = 0; i < n; i++) {
        const k = { time: T(F[i * E]) };
        if (BONE1[kind]) k.value = R(F[i * E + 1]); else { k.x = R(F[i * E + 1]); k.y = R(F[i * E + 2]); }
        const c = curveOf(tl, i, BONE1[kind] ? 1 : 2); if (c) k.curve = c;
        keys.push(k);
      }
      ((A.bones ||= {})[bone] ||= {})[BONE1[kind] || BONE2[kind]] = keys;
    } else if (kind === 'RGBATimeline' || kind === 'RGBTimeline' || kind === 'AlphaTimeline') {
      const slot = sd.slots[tl.slotIndex].name;
      for (let i = 0; i < n; i++) {
        const k = { time: T(F[i * E]) }; let nv;
        if (kind === 'AlphaTimeline') { k.value = R(F[i * E + 1], 6); nv = 1; }
        else { const c = { r: F[i * E + 1], g: F[i * E + 2], b: F[i * E + 3], a: kind === 'RGBATimeline' ? F[i * E + 4] : 1 }; k.color = colHex(c, kind === 'RGBATimeline'); nv = kind === 'RGBATimeline' ? 4 : 3; }
        const c = curveOf(tl, i, nv); if (c) k.curve = c;
        keys.push(k);
      }
      ((A.slots ||= {})[slot] ||= {})[{ RGBATimeline: 'rgba', RGBTimeline: 'rgb', AlphaTimeline: 'alpha' }[kind]] = keys;
    } else if (kind === 'AttachmentTimeline') {
      const slot = sd.slots[tl.slotIndex].name;
      for (let i = 0; i < n; i++) keys.push({ time: T(F[i]), name: tl.attachmentNames[i] || null });
      ((A.slots ||= {})[slot] ||= {}).attachment = keys;
    } else if (kind === 'DeformTimeline') {
      const slot = sd.slots[tl.slotIndex].name, att = tl.attachment;
      let skinName = null, attName = null;
      for (const skin of sd.skins) for (const e of skin.getAttachments()) if (e.attachment === att && e.slotIndex === tl.slotIndex) { skinName = skin.name; attName = e.name; }
      if (!skinName) throw new Error('deform attachment not in a skin');
      const setup = att.bones ? null : att.vertices;
      for (let i = 0; i < n; i++) {
        const v = Array.from(tl.vertices[i]); if (setup) for (let j = 0; j < v.length; j++) v[j] -= setup[j];
        let s = 0, e = v.length; while (s < e && Math.abs(v[s]) < 1e-9) s++; while (e > s && Math.abs(v[e - 1]) < 1e-9) e--;
        const k = { time: T(F[i]) };
        if (e > s) { if (s) k.offset = s; k.vertices = v.slice(s, e).map(x => R(x, 4)); }
        const c = curveOf(tl, i, 1); if (c) k.curve = c;
        keys.push(k);
      }
      ((((A.attachments ||= {})[skinName] ||= {})[slot] ||= {})[attName] ||= {}).deform = keys;
    } else throw new Error('unsupported timeline ' + kind + ' in ' + anim.name);
  }
  out.animations[anim.name] = A;
}
if (sd.events.length) throw new Error('events not supported');
fs.writeFileSync(outPath, JSON.stringify(out));
console.log('wrote', outPath, 'bones', out.bones.length, 'slots', out.slots.length, 'anims', Object.keys(out.animations).map(a => a + ':' + sd.findAnimation(a).duration.toFixed(3)).join(' '), 'bytes', fs.statSync(outPath).size);
