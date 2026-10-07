import fs from 'node:fs';
import * as S from '@esotericsoftware/spine-core';

export function load(jsonPath, atlasPath) {
  const json = JSON.parse(fs.readFileSync(jsonPath, 'utf8').replace(/^\uFEFF/, ''));
  const atlas = new S.TextureAtlas(fs.readFileSync(atlasPath, 'utf8'));
  for (const page of atlas.pages) page.setTexture({
    setFilters() {}, setWraps() {}, dispose() {},
    getImage() { return {width: page.width, height: page.height}; },
  });
  return new S.SkeletonJson(new S.AtlasAttachmentLoader(atlas)).readSkeletonData(json);
}

export function pose(data, animation, time = 0) {
  const skeleton = new S.Skeleton(data);
  skeleton.setToSetupPose();
  if (animation) data.findAnimation(animation).apply(
    skeleton, 0, time, false, [], 1, S.MixBlend.setup, S.MixDirection.mixIn);
  skeleton.updateWorldTransform(S.Physics.none);
  return skeleton;
}

export function worldVertices(slot, attachment = slot.attachment) {
  if (attachment instanceof S.RegionAttachment) {
    const vertices = new Float32Array(8);
    attachment.computeWorldVertices(slot, vertices, 0, 2);
    return Array.from(vertices);
  }
  if (attachment instanceof S.MeshAttachment) {
    const vertices = new Float32Array(attachment.worldVerticesLength);
    attachment.computeWorldVertices(slot, 0, vertices.length, vertices, 0, 2);
    return Array.from(vertices);
  }
  return [];
}

export function snapshot(skeleton) {
  const bones = skeleton.bones.map(b => ({name: b.data.name,
    matrix: [[b.a, b.b, b.worldX], [b.c, b.d, b.worldY], [0, 0, 1]]}));
  const attachments = {};
  for (const {slotIndex, name, attachment} of skeleton.data.defaultSkin.getAttachments()) {
    const slot = skeleton.slots[slotIndex];
    (attachments[slot.data.name] ??= {})[name] = {
      world: worldVertices(slot, attachment),
      uvs: Array.from(attachment instanceof S.MeshAttachment ? attachment.regionUVs : [0,1,0,0,1,0,1,1]),
    };
  }
  return {bones, attachments};
}
