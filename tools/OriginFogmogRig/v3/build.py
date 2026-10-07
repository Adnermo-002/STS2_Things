"""Repair the recovered v3 skin while preserving its vanilla animation contract.

Run from this directory after snapshot.mjs writes out/bind.json at idle_loop t=0.
All input art/animation is read from source/, never from a previous build.
"""
from copy import deepcopy
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"
OUT = HERE / "out"
KEY = "origin_fogmog"


def smooth(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


class Field:
    """Sample the actual host mesh's skin weights, including its shared edges."""

    def __init__(self, world, triangles, weights):
        self.points = world[np.array(triangles).reshape(-1, 3)]
        self.weights = weights[np.array(triangles).reshape(-1, 3)]
        basis = np.stack([self.points[:, 1] - self.points[:, 0],
                          self.points[:, 2] - self.points[:, 0]], axis=2)
        self.inverse = np.linalg.inv(basis)

    def __call__(self, points):
        result = []
        for point in points:
            bc = np.einsum("tij,tj->ti", self.inverse, point - self.points[:, 0])
            bary = np.c_[1 - bc.sum(axis=1), bc]
            inside = np.flatnonzero((bary >= -1e-6).all(axis=1))
            if len(inside):
                index = inside[0]
                coords = bary[index]
            else:
                # Outside the painted host, extend its boundary weight field.
                clipped = np.maximum(bary, 0)
                clipped /= clipped.sum(axis=1, keepdims=True)
                projected = np.einsum("ti,tij->tj", clipped, self.points)
                index = np.square(projected - point).sum(axis=1).argmin()
                coords = clipped[index]
            result.append(coords @ self.weights[index])
        return np.array(result)


class Builder:
    def __init__(self):
        self.data = json.loads((SOURCE / f"{KEY}.spjson").read_text())
        self.bind = json.loads((OUT / "bind.json").read_text())
        self.art = np.array(Image.open(SOURCE / f"{KEY}.png").convert("RGBA"))
        self.skin = self.data["skins"][0]["attachments"]
        self.original = deepcopy(self.skin)
        self.inverse = np.linalg.inv(np.array([b["matrix"] for b in self.bind["bones"]]))
        self.bone_count = len(self.data["bones"])
        self.regions = {}
        name = None
        for line in (SOURCE / f"{KEY}.atlas").read_text().splitlines()[5:]:
            if line and not line.startswith(" "):
                name = line
                self.regions[name] = {}
            elif ":" in line and name:
                key, value = line.strip().split(":", 1)
                self.regions[name][key] = value.strip()
        self.fields = {}
        self.transforms = {}
        for slot, attachments in self.original.items():
            for name, attachment in attachments.items():
                bind = self.bind["attachments"][slot][name]
                uv = np.array(bind["uvs"]).reshape(-1, 2)
                world = np.array(bind["world"]).reshape(-1, 2)
                self.transforms[name] = np.linalg.lstsq(
                    np.c_[uv, np.ones(len(uv))], world, rcond=None)[0]
                if attachment.get("type") != "mesh":
                    continue
                weights = np.zeros((len(world), self.bone_count))
                stream = iter(attachment["vertices"])
                for row in weights:
                    for _ in range(int(next(stream))):
                        bone, _x, _y, weight = [next(stream) for _ in range(4)]
                        row[int(bone)] += weight
                self.fields[name] = Field(world, attachment["triangles"], weights)

    def texture(self, name):
        region = self.regions[name]
        x, y = map(int, region["xy"].split(","))
        w, h = map(int, region["size"].split(","))
        return self.art[y:y + h, x:x + w]

    def sample_image(self, name, values, points):
        transform = self.transforms[name]
        uv = (points - transform[2]) @ np.linalg.inv(transform[:2])
        xy = uv * np.array([values.shape[1], values.shape[0]])
        return np.concatenate([
            cv2.remap(values.astype(np.float32), chunk[:, 0:1].astype(np.float32),
                      chunk[:, 1:2].astype(np.float32), cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=-1000).ravel()
            for chunk in np.array_split(xy, max(1, (len(xy) + 16383) // 16384))
        ])

    def repair_masks(self):
        # Old occlusion fill retained long triangular scraps of the shoulder and
        # thigh. They emerge from behind the moving arm/leg. Keep a rounded trunk.
        body = self.texture("bod")
        yy, xx = np.indices(body.shape[:2])
        right = np.interp(yy[:, 0],
                          [0, 190, 235, 280, 320, 360, 400, 430, 458, 490, 520, 545, 558, 593],
                          [440, 385, 366, 344, 358, 379, 400, 408, 404, 382, 334, 280, 235, 235])
        left = np.interp(yy[:, 0], [0, 230, 255, 280, 315, 355, 400, 593],
                         [0, 0, 60, 85, 78, 56, 0, 0])
        keep = np.clip(np.minimum(right[:, None] - xx, xx - left[:, None]), 0, 1)
        uv = np.c_[xx.ravel() / body.shape[1], yy.ravel() / body.shape[0], np.ones(xx.size)]
        points = uv @ self.transforms["bod"]
        covered = np.zeros(len(points))
        for part in ("top arm", "bottom arm", "top leg", "bottom leg"):
            covered = np.maximum(covered, self.sample_image(part, self.texture(part)[:, :, 3], points))
        # Preserve all exposed original painting pixels in the idle pose.
        master = np.array(Image.open(HERE.parents[2] / "source_assets/monsters/origin_fogmog.png"))
        source_x = (points[:, 0] / 0.58 + 430).astype(np.float32).reshape(body.shape[:2])
        source_y = (945 - points[:, 1] / 0.58).astype(np.float32).reshape(body.shape[:2])
        source_alpha = cv2.remap(master[:, :, 3], source_x, source_y, cv2.INTER_LINEAR).ravel()
        preserve = ((covered < 128) & (source_alpha > 128)).reshape(body.shape[:2])
        keep[preserve] = 1
        body[:, :, 3] = np.minimum(body[:, :, 3], np.round(keep * 255)).astype(np.uint8)
        for name in ("top arm", "bottom arm"):
            texture = self.texture(name)
            count, labels, stats, _ = cv2.connectedComponentsWithStats(
                (texture[:, :, 3] > 0).astype(np.uint8))
            for component in range(1, count):
                if stats[component, cv2.CC_STAT_AREA] < 100:
                    texture[labels == component, 3] = 0

    def claw_field(self, slot, name, host):
        parent = "arm_f_lower" if slot.startswith("top") else "arm_b_lower"
        parent_index = next(i for i, bone in enumerate(self.data["bones"]) if bone["name"] == parent)
        old_bone = next(s["bone"] for s in self.data["slots"] if s["name"] == slot)
        root = np.array([0.5, 0.07, 1]) @ self.transforms[name]
        local = self.inverse[parent_index] @ np.r_[root, 1]
        bone_name = slot.replace(" ", "_") + "_skin"
        bone_index = len(self.data["bones"])
        self.data["bones"].append({"name": bone_name, "parent": parent,
                                   "x": round(float(local[0]), 6), "y": round(float(local[1]), 6)})
        parent_matrix = np.linalg.inv(self.inverse[parent_index])
        child_matrix = parent_matrix.copy()
        child_matrix[:2, 2] = root
        self.inverse = np.concatenate([self.inverse, np.linalg.inv(child_matrix)[None]])
        idle_keys = self.data["animations"]["idle_loop"].get("bones", {}).get(old_bone, {}).get("rotate", [])
        base_rotation = idle_keys[0].get("value", 0) if idle_keys else 0
        for animation in self.data["animations"].values():
            rotation = animation.get("bones", {}).get(old_bone, {}).get("rotate", [])
            if rotation:
                # Vanilla finger pivots do not match the Origin painting. Replay
                # their curl around the painted root with a soft, anchored base.
                keys = [{"time": key.get("time", 0),
                         "value": round((key.get("value", 0) - base_rotation) * 0.55, 5)}
                        for key in rotation]
                animation["bones"][bone_name] = {"rotate": keys}
        height = self.original[slot][name]["height"]

        def claw(points):
            weights = np.pad(host(points), ((0, 0), (0, bone_index + 1 - self.bone_count)))
            curl = smooth(height * 0.22, height * 0.8, root[1] - points[:, 1])
            own = weights[:, parent_index] * curl
            weights[:, parent_index] -= own
            weights[:, bone_index] = own
            return weights

        return claw

    def mesh(self, slot, name, field, spacing=8):
        texture = self.texture(name)
        h, w = texture.shape[:2]
        occupied = cv2.dilate((texture[:, :, 3] > 0).astype(np.uint8),
                              np.ones((3, 3), np.uint8))
        xs = sorted(set(range(0, w, spacing)) | {w})
        ys = sorted(set(range(0, h, spacing)) | {h})
        vertices, triangles, indices = [], [], {}

        def vertex(i, j):
            if (i, j) not in indices:
                indices[i, j] = len(vertices)
                vertices.append((xs[i] / w, ys[j] / h))
            return indices[i, j]

        for j in range(len(ys) - 1):
            for i in range(len(xs) - 1):
                if occupied[ys[j]:ys[j + 1], xs[i]:xs[i + 1]].any():
                    a, b, c, d = vertex(i, j), vertex(i + 1, j), vertex(i + 1, j + 1), vertex(i, j + 1)
                    triangles.extend([a, b, c, a, c, d])
        uvs = np.array(vertices)
        world = np.c_[uvs, np.ones(len(uvs))] @ self.transforms[name]
        weights = field(world)
        weights[weights < 1e-6] = 0
        weights /= weights.sum(axis=1, keepdims=True)
        stream = []
        for point, row in zip(world, weights):
            bones = np.flatnonzero(row)
            stream.append(len(bones))
            for bone in bones:
                local = self.inverse[bone] @ np.r_[point, 1]
                stream.extend([int(bone), round(float(local[0]), 5),
                               round(float(local[1]), 5), round(float(row[bone]), 7)])
        self.skin[slot][name] = {
            "type": "mesh", "path": name, "uvs": uvs.flatten().round(7).tolist(),
            "triangles": triangles, "vertices": stream, "hull": 0,
            "width": self.original[slot][name]["width"],
            "height": self.original[slot][name]["height"],
        }

    def build(self):
        self.repair_masks()
        body = self.fields["bod"]
        fields = dict(self.fields)
        mask = (self.texture("bod")[:, :, 3] > 128).astype(np.uint8)
        distance = (cv2.distanceTransform(mask, cv2.DIST_L2, 5)
                    - cv2.distanceTransform(1 - mask, cv2.DIST_L2, 5)) * 0.58
        self.mesh("bod", "bod", body)
        self.mesh("face_glow", "face_glow", body)
        for side in ("top", "bottom"):
            original_arm = self.fields[f"{side} arm"]

            def arm(points, original=original_arm):
                edge = self.sample_image("bod", distance, points)
                blend = (smooth(-40, 0, edge) * smooth(185, 235, points[:, 1]))[:, None]
                return original(points) * (1 - blend) + body(points) * blend

            fields[f"{side} arm"] = arm
            self.mesh(f"{side} arm", f"{side} arm", arm)

        # The two textures at an ankle must evaluate the same weight field.
        # Merely overlapping the images cannot hide different skinning at a bend.
        for side in ("top", "bottom"):
            old_leg, old_foot = self.fields[f"{side} leg"], self.fields[f"{side} foot"]

            def leg(points, upper=old_leg, lower=old_foot):
                ankle = smooth(48, 90, points[:, 1])[:, None]
                edge = self.sample_image("bod", distance, points)
                hip = (smooth(-30, 0, edge) * smooth(85, 120, points[:, 1]))[:, None]
                weights = lower(points) * (1 - ankle) + upper(points) * ankle
                return weights * (1 - hip) + body(points) * hip

            for part in (f"{side} leg", f"{side} foot"):
                self.mesh(part, part, leg)

        for slot, attachments in self.original.items():
            if "finger" in slot:
                host = "top arm" if slot.startswith("top") else "bottom arm"
                for name in attachments:
                    self.mesh(slot, name, self.claw_field(slot, name, fields[host]), spacing=5)
        # Face cutouts must share the trunk deformation all the way to their
        # edges. Expression changes still use the vanilla texture switches.
        for slot in ("eyes", "blink 1", "mouth", "moth_dry"):
            for name in self.original[slot]:
                self.mesh(slot, name, body, spacing=5)
        self.data["skeleton"]["hash"] = "originfogmog-seam-repair-v1"
        OUT.mkdir(exist_ok=True)
        (OUT / f"{KEY}.spjson").write_text(json.dumps(self.data, separators=(",", ":")))
        Image.fromarray(self.art).save(OUT / f"{KEY}.png", optimize=True)
        atlas = (SOURCE / f"{KEY}.atlas").read_text()
        (OUT / f"{KEY}.atlas").write_text(atlas, newline="\n")
        (OUT / f"{KEY}.spatlas").write_text(json.dumps({
            "source_path": f"res://STS2_Things/animations/monsters/{KEY}/{KEY}.atlas",
            "atlas_data": atlas, "normal_texture_prefix": "n", "specular_texture_prefix": "s",
        }, separators=(",", ":")), newline="\n")
        print(f"Built {KEY}: {len(self.data['bones'])} bones, {len(self.data['slots'])} slots")


if __name__ == "__main__":
    Builder().build()
