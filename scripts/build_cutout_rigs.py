#!/usr/bin/env python3
"""Build rigid 2D cutout parts for the STS2_Things monster rigs.

The editable monster art is intentionally kept as one lossless RGBA source per
monster.  This build step partitions those canvases into overlapping rigid
pieces, crops each piece, and emits the C# placement table consumed at runtime.
No color operation is performed here: every visible pixel is copied verbatim
from the exact original RGBA shipping texture.
"""

from __future__ import annotations

import argparse
import colorsys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
MONSTERS = ROOT / "images" / "monsters"
PARTS_ROOT = MONSTERS / "rig_parts"
GENERATED_CS = ROOT / "STS2_Things" / "Visuals" / "GeneratedCutoutRigData.cs"
GENERATED_MANIFEST = ROOT / "source_assets" / "monsters" / "cutout_rigs.generated.json"
DEFAULT_AUDIT_ROOT = ROOT / "build" / "rig_segmentation_audit"


Point = tuple[int, int]
Shape = tuple[str, tuple]


def polygon(*points: Point) -> Shape:
    return ("polygon", tuple(points))


def ellipse(left: int, top: int, right: int, bottom: int) -> Shape:
    return ("ellipse", (left, top, right, bottom))


def rectangle(left: int, top: int, right: int, bottom: int) -> Shape:
    return ("rectangle", (left, top, right, bottom))


def voronoi_cell(index: int, centers: tuple[Point, ...]) -> Shape:
    """Partition a flattened multi-subject texture by nearest authored center."""

    return ("voronoi", (index, centers))


@dataclass(frozen=True)
class Piece:
    name: str
    bone: str
    pivot: Point
    shapes: tuple[Shape, ...]
    z: int
    pad: int = 8
    pixel_family: str | None = None
    underlay: bool = False
    atlas_bleed: int = 2
    semantic: str = "rigid"


@dataclass(frozen=True)
class ExternalPiece:
    name: str
    bone: str
    texture: str
    center: Point
    pivot: Point
    z: int


@dataclass(frozen=True)
class VirtualBone:
    """A transform-only hierarchy node with no dedicated sprite part."""

    name: str
    pivot: Point


@dataclass(frozen=True)
class Rig:
    key: str
    source: str
    base_bone: str
    base_pivot: Point
    pieces: tuple[Piece, ...]
    external: tuple[ExternalPiece, ...] = ()
    parents: tuple[tuple[str, str], ...] = ()
    virtual_bones: tuple[VirtualBone, ...] = ()


SOUL_ROES_CENTERS: tuple[Point, ...] = (
    (260, 226), (178, 221), (104, 214), (323, 183),
    (310, 175), (115, 138), (38, 145), (183, 125),
    (270, 115), (80, 72), (145, 48), (220, 55),
)


RIGS: tuple[Rig, ...] = (
    # Origin Fogmog: articulated limbs with parent-owned opaque socket caps.
    Rig(
        "origin_fogmog", "origin_fogmog.png", "Body", (443, 620),
        (
            Piece("face_features", "Face", (438, 455), (polygon((305, 292), (520, 292), (535, 500), (310, 505)),), 48, 4, semantic="accent"),
            Piece("cap_left", "CapLeft", (260, 286), (polygon((0, 0), (385, 0), (405, 235), (330, 315), (0, 420)),), 45, 12, semantic="cap"),
            Piece("cap_center", "CapCenter", (443, 300), (polygon((285, 0), (610, 0), (620, 315), (500, 335), (330, 320)),), 47, 12, semantic="cap"),
            Piece("cap_right", "CapRight", (650, 280), (polygon((520, 0), (886, 0), (886, 310), (760, 315), (605, 295)),), 44, 12, semantic="cap"),
            Piece("cap_underside", "CapCenter", (443, 300), (polygon((0, 215), (886, 205), (886, 330), (710, 330), (620, 390), (260, 410), (0, 420)),), 43, 8, semantic="cap_underlay"),
            Piece("left_hand", "LeftHand", (137, 700), (polygon((62, 660), (235, 650), (268, 790), (62, 815)),), 34, 14, semantic="hand"),
            Piece("left_forearm", "LeftForearm", (229, 602), (polygon((105, 565), (280, 520), (325, 660), (230, 715), (110, 680)),), 31, 16, semantic="limb"),
            Piece("left_upper_arm", "LeftArm", (322, 487), (polygon((235, 420), (355, 440), (330, 585), (255, 630), (185, 555)),), 30, 20, semantic="limb"),
            Piece("right_hand", "RightHand", (760, 692), (polygon((680, 635), (872, 635), (886, 800), (690, 810)),), 34, 14, semantic="hand"),
            Piece("right_forearm", "RightForearm", (672, 585), (polygon((610, 520), (770, 540), (835, 690), (720, 730), (640, 650)),), 31, 16, semantic="limb"),
            Piece("right_upper_arm", "RightArm", (568, 473), (polygon((535, 390), (655, 400), (690, 560), (620, 610), (550, 525)),), 30, 20, semantic="limb"),
            Piece("left_foot", "LeftFoot", (318, 844), (polygon((150, 825), (430, 810), (465, 954), (150, 954)),), 23, 16, semantic="foot"),
            Piece("left_leg", "LeftLeg", (337, 736), (polygon((260, 690), (430, 690), (445, 860), (245, 865)),), 21, 18, semantic="limb"),
            Piece("right_foot", "RightFoot", (608, 849), (polygon((480, 820), (740, 805), (760, 954), (470, 954)),), 23, 16, semantic="foot"),
            Piece("right_leg", "RightLeg", (571, 736), (polygon((495, 690), (680, 690), (725, 855), (500, 865)),), 21, 18, semantic="limb"),
            Piece("body_core", "Body", (443, 620), (polygon((260, 330), (625, 330), (690, 760), (625, 825), (300, 825), (245, 675)),), 20, 10, semantic="core"),
            Piece("socket_left_shoulder", "Body", (443, 620), (ellipse(285, 445, 355, 525),), 24, 0, underlay=True, semantic="socket"),
            Piece("socket_right_shoulder", "Body", (443, 620), (ellipse(535, 430, 605, 510),), 24, 0, underlay=True, semantic="socket"),
            Piece("socket_left_hip", "Body", (443, 620), (ellipse(305, 705, 380, 780),), 18, 0, underlay=True, semantic="socket"),
            Piece("socket_right_hip", "Body", (443, 620), (ellipse(535, 705, 610, 780),), 18, 0, underlay=True, semantic="socket"),
        ),
        parents=(
            ("Body", "Root"), ("Face", "Body"), ("CapCenter", "Face"),
            ("CapLeft", "CapCenter"), ("CapRight", "CapCenter"),
            ("LeftArm", "Body"), ("LeftForearm", "LeftArm"), ("LeftHand", "LeftForearm"),
            ("RightArm", "Body"), ("RightForearm", "RightArm"), ("RightHand", "RightForearm"),
            ("LeftLeg", "Body"), ("LeftFoot", "LeftLeg"),
            ("RightLeg", "Body"), ("RightFoot", "RightLeg"),
        ),
        virtual_bones=(VirtualBone("Root", (443, 850)),),
    ),

    # Bowlbug Progenitor: five three-link legs plus plate-locked gem accents.
    Rig(
        "bowlbug_progenitor", "bowlbug_progenitor.png", "Root", (745, 520),
        (
            Piece("gem_head_crown", "Crest", (420, 350), (ellipse(220, 165, 300, 250),), 50, 2, semantic="accent"),
            Piece("gem_head_brow", "Head", (420, 510), (ellipse(160, 300, 245, 395),), 50, 2, semantic="accent"),
            Piece("gem_crest_front", "Crest", (420, 350), (ellipse(290, 265, 380, 355),), 50, 2, semantic="accent"),
            Piece("gem_crest_mid", "Crest", (420, 350), (ellipse(575, 140, 675, 230),), 50, 2, semantic="accent"),
            Piece("gem_front_shell_top", "FrontShell", (600, 465), (ellipse(645, 35, 775, 145),), 50, 2, semantic="accent"),
            Piece("gem_front_shell_low", "FrontShell", (600, 465), (ellipse(785, 145, 915, 285),), 50, 2, semantic="accent"),
            Piece("gem_mid_shell", "MidShell", (865, 470), (ellipse(955, 0, 1085, 105),), 50, 2, semantic="accent"),
            Piece("gem_rear_shell", "RearShell", (1260, 500), (ellipse(1110, 20, 1285, 135),), 50, 2, semantic="accent"),
            Piece("gem_tail", "RearShell", (1260, 500), (ellipse(1380, 330, 1437, 430),), 50, 2, semantic="accent"),
            Piece("mandible_upper", "Mandible", (115, 590), (polygon((0, 525), (120, 520), (135, 650), (0, 690)),), 46, 12, semantic="jaw"),
            Piece("mandible_lower", "MandibleLower", (105, 646), (polygon((38, 590), (220, 590), (220, 705), (70, 735), (30, 670)),), 47, 12, semantic="jaw"),
            Piece("front_foot", "FrontFoot", (426, 747), (polygon((365, 715), (470, 705), (505, 782), (360, 782)),), 36, 10, semantic="foot"),
            Piece("front_leg_lower", "FrontLegLower", (480, 660), (polygon((390, 610), (525, 605), (535, 748), (405, 765)),), 35, 14, semantic="limb"),
            Piece("front_leg", "FrontLeg", (575, 592), (polygon((455, 540), (620, 535), (610, 680), (480, 690), (430, 620)),), 34, 20, semantic="limb"),
            Piece("mid_foot_a", "MidFootA", (748, 747), (polygon((695, 715), (785, 705), (800, 782), (705, 782)),), 35, 10, semantic="foot"),
            Piece("mid_leg_a_lower", "MidLegALower", (720, 671), (polygon((675, 620), (760, 615), (785, 745), (710, 758)),), 34, 14, semantic="limb"),
            Piece("mid_leg_a", "MidLegA", (690, 595), (polygon((630, 535), (760, 535), (750, 670), (660, 670)),), 33, 20, semantic="limb"),
            Piece("mid_foot_b", "MidFootB", (1020, 744), (polygon((970, 710), (1070, 705), (1090, 782), (990, 782)),), 35, 10, semantic="foot"),
            Piece("mid_leg_b_lower", "MidLegBLower", (984, 681), (polygon((930, 625), (1030, 620), (1070, 748), (985, 760)),), 34, 14, semantic="limb"),
            Piece("mid_leg_b", "MidLegB", (945, 595), (polygon((850, 535), (1030, 535), (1025, 675), (890, 680)),), 33, 20, semantic="limb"),
            Piece("rear_foot_a", "RearFootA", (1254, 742), (polygon((1190, 700), (1300, 700), (1325, 775), (1230, 782)),), 35, 10, semantic="foot"),
            Piece("rear_leg_a_lower", "RearLegALower", (1182, 676), (polygon((1115, 620), (1220, 615), (1280, 740), (1195, 755)),), 34, 14, semantic="limb"),
            Piece("rear_leg_a", "RearLegA", (1128, 595), (polygon((1040, 530), (1205, 530), (1210, 675), (1080, 680)),), 33, 20, semantic="limb"),
            Piece("rear_foot_b", "RearFootB", (1411, 720), (polygon((1360, 680), (1437, 680), (1437, 770), (1390, 770)),), 35, 10, semantic="foot"),
            Piece("rear_leg_b_lower", "RearLegBLower", (1364, 666), (polygon((1300, 610), (1410, 610), (1437, 735), (1360, 740)),), 34, 14, semantic="limb"),
            Piece("rear_leg_b", "RearLegB", (1320, 595), (polygon((1240, 520), (1385, 520), (1400, 660), (1280, 670)),), 33, 20, semantic="limb"),
            Piece("crest", "Crest", (420, 350), (polygon((180, 40), (540, 100), (565, 455), (405, 530), (185, 405)),), 26, 10, semantic="armor"),
            Piece("head", "Head", (420, 510), (polygon((55, 285), (510, 270), (545, 650), (250, 700), (50, 625)),), 30, 14, semantic="head"),
            Piece("front_shell", "FrontShell", (600, 465), (polygon((455, 75), (830, 0), (850, 520), (610, 565), (460, 440)),), 21, 12, semantic="armor"),
            Piece("mid_shell", "MidShell", (865, 470), (polygon((770, 0), (1125, 0), (1120, 430), (920, 555), (780, 450)),), 22, 12, semantic="armor"),
            Piece("egg_sac", "EggSac", (1060, 475), (polygon((900, 85), (1280, 70), (1330, 545), (1180, 600), (940, 565), (890, 370)),), 20, 10, semantic="core"),
            Piece("rear_shell", "RearShell", (1260, 500), (polygon((1110, 35), (1437, 80), (1437, 650), (1210, 635), (1170, 420)),), 23, 12, semantic="armor"),
            Piece("socket_front_leg", "FrontShell", (600, 465), (ellipse(535, 550, 620, 635),), 31, 0, underlay=True, semantic="socket"),
            Piece("socket_mid_leg_a", "MidShell", (865, 470), (ellipse(645, 550, 730, 635),), 31, 0, underlay=True, semantic="socket"),
            Piece("socket_mid_leg_b", "EggSac", (1060, 475), (ellipse(900, 550, 985, 635),), 31, 0, underlay=True, semantic="socket"),
            Piece("socket_rear_leg_a", "RearShell", (1260, 500), (ellipse(1085, 550, 1170, 635),), 31, 0, underlay=True, semantic="socket"),
            Piece("socket_rear_leg_b", "RearShell", (1260, 500), (ellipse(1280, 545, 1360, 625),), 31, 0, underlay=True, semantic="socket"),
        ),
        parents=(
            ("Head", "FrontShell"), ("Crest", "Head"), ("Mandible", "Head"), ("MandibleLower", "Head"),
            ("FrontShell", "Root"), ("MidShell", "Root"), ("EggSac", "Root"), ("RearShell", "Root"),
            ("FrontLeg", "FrontShell"), ("FrontLegLower", "FrontLeg"), ("FrontFoot", "FrontLegLower"),
            ("MidLegA", "MidShell"), ("MidLegALower", "MidLegA"), ("MidFootA", "MidLegALower"),
            ("MidLegB", "EggSac"), ("MidLegBLower", "MidLegB"), ("MidFootB", "MidLegBLower"),
            ("RearLegA", "RearShell"), ("RearLegALower", "RearLegA"), ("RearFootA", "RearLegALower"),
            ("RearLegB", "RearShell"), ("RearLegBLower", "RearLegB"), ("RearFootB", "RearLegBLower"),
        ),
    ),

    # Scale Beetle: existing antenna ABI plus contour-following limb chains.
    Rig(
        "scale_beetle", "scale_beetle.png", "Root", (610, 650),
        (
            Piece("antenna_front_base", "AntennaFrontBase", (126, 552), (rectangle(100, 485, 152, 582),), 60, 3, "antenna", semantic="antenna"),
            Piece("antenna_front_1", "AntennaFront1", (137, 482), (rectangle(104, 376, 176, 495),), 60, 3, "antenna", semantic="antenna"),
            Piece("antenna_front_2", "AntennaFront2", (166, 374), (rectangle(125, 280, 212, 388),), 60, 3, "antenna", semantic="antenna"),
            Piece("antenna_front_3", "AntennaFront3", (221, 292), (rectangle(172, 203, 282, 306),), 60, 3, "antenna", semantic="antenna"),
            Piece("antenna_front_4", "AntennaFront4", (299, 217), (rectangle(243, 147, 359, 229),), 60, 3, "antenna", semantic="antenna"),
            Piece("antenna_front_5", "AntennaFront5", (392, 163), (rectangle(327, 97, 464, 178),), 60, 3, "antenna", semantic="antenna"),
            Piece("antenna_front_tip", "AntennaFrontTip", (474, 146), (rectangle(419, 88, 562, 160),), 60, 3, "antenna", semantic="antenna"),
            Piece("antenna_back_base", "AntennaBackBase", (101, 549), (rectangle(65, 484, 114, 562),), 59, 3, "antenna", semantic="antenna"),
            Piece("antenna_back_1", "AntennaBack1", (84, 486), (rectangle(49, 383, 104, 495),), 59, 3, "antenna", semantic="antenna"),
            Piece("antenna_back_2", "AntennaBack2", (83, 384), (rectangle(53, 290, 111, 391),), 59, 3, "antenna", semantic="antenna"),
            Piece("antenna_back_3", "AntennaBack3", (120, 286), (rectangle(85, 196, 160, 300),), 59, 3, "antenna", semantic="antenna"),
            Piece("antenna_back_4", "AntennaBack4", (186, 200), (rectangle(136, 116, 239, 212),), 59, 3, "antenna", semantic="antenna"),
            Piece("antenna_back_5", "AntennaBack5", (260, 121), (rectangle(201, 40, 325, 135),), 59, 3, "antenna", semantic="antenna"),
            Piece("antenna_back_tip", "AntennaBackTip", (330, 59), (rectangle(292, 0, 432, 74),), 59, 3, "antenna", semantic="antenna"),
            Piece(
                "eye", "Head", (350, 600),
                (
                    ellipse(135, 545, 270, 675),
                    polygon((20, 565), (275, 565), (285, 740), (45, 775)),
                ),
                42, 0, underlay=True, semantic="jaw_socket_bundle",
            ),
            Piece("jaw_upper", "JawUpper", (165, 660), (polygon((0, 585), (225, 585), (235, 710), (0, 755)),), 44, 10, semantic="jaw"),
            Piece("jaw_lower", "JawLower", (180, 690), (polygon((65, 640), (250, 620), (260, 765), (95, 785)),), 45, 10, semantic="jaw"),
            Piece("fore_claw_tip", "ForeClawLower", (333, 755), (polygon((0, 800), (220, 790), (230, 883), (0, 883)),), 42, 12, semantic="foot"),
            Piece("fore_claw_lower", "ForeClawLower", (333, 755), (polygon((175, 705), (420, 690), (455, 835), (210, 860)),), 41, 16, semantic="limb"),
            Piece("fore_claw", "ForeClaw", (430, 680), (polygon((350, 615), (520, 620), (520, 755), (385, 775), (325, 700)),), 38, 20, semantic="limb"),
            Piece("front_foot", "FrontFoot", (529, 804), (polygon((480, 770), (595, 770), (610, 845), (475, 845)),), 31, 10, semantic="foot"),
            Piece("front_leg_lower", "FrontLegLower", (560, 744), (polygon((500, 690), (625, 685), (625, 805), (510, 815)),), 30, 14, semantic="limb"),
            Piece("front_leg", "FrontLeg", (530, 680), (polygon((455, 625), (610, 620), (630, 725), (500, 735)),), 28, 18, semantic="limb"),
            Piece("mid_foot", "MidFoot", (690, 846), (polygon((625, 815), (755, 815), (780, 883), (635, 883)),), 36, 10, semantic="foot"),
            Piece("mid_leg_lower", "MidLegLower", (656, 744), (polygon((605, 680), (720, 675), (730, 840), (635, 850)),), 35, 14, semantic="limb"),
            Piece("mid_leg", "MidLeg", (620, 650), (polygon((555, 590), (700, 590), (715, 720), (585, 730)),), 33, 18, semantic="limb"),
            Piece("rear_foot", "RearFoot", (958, 842), (polygon((885, 805), (1035, 805), (1060, 883), (900, 883)),), 37, 10, semantic="foot"),
            Piece("rear_leg_lower", "RearLegLower", (911, 735), (polygon((850, 645), (980, 640), (985, 835), (890, 845)),), 36, 14, semantic="limb"),
            Piece("rear_leg", "RearLeg", (866, 625), (polygon((770, 545), (930, 540), (955, 700), (815, 710)),), 34, 18, semantic="limb"),
            Piece("head", "Head", (350, 600), (polygon((20, 320), (500, 280), (525, 700), (250, 760), (15, 715)),), 30, 14, semantic="head"),
            Piece("front_shell", "FrontShell", (505, 555), (polygon((385, 275), (730, 270), (765, 770), (420, 790)),), 20, 10, semantic="armor"),
            Piece("core_shell", "Core", (690, 545), (polygon((490, 280), (930, 295), (975, 765), (605, 795), (465, 595)),), 21, 10, semantic="armor"),
            Piece("rear_shell", "RearShell", (900, 565), (polygon((690, 295), (985, 330), (1127, 490), (1127, 765), (880, 810), (750, 645)),), 19, 10, semantic="armor"),
            Piece(
                "socket_fore_claw", "FrontShell", (505, 555),
                (
                    ellipse(335, 590, 520, 770),
                    polygon((285, 390), (520, 365), (585, 690), (340, 785), (285, 650)),
                ),
                26, 0, underlay=True, semantic="head_foreclaw_socket_bundle",
            ),
            Piece("socket_front_leg", "FrontShell", (505, 555), (ellipse(490, 640, 565, 715),), 26, 0, underlay=True, semantic="socket"),
            Piece("socket_mid_leg", "Core", (690, 545), (ellipse(580, 610, 665, 695),), 26, 0, underlay=True, semantic="socket"),
            Piece("socket_rear_leg", "RearShell", (900, 565), (ellipse(825, 585, 910, 670),), 26, 0, underlay=True, semantic="socket"),
        ),
        parents=(
            ("Core", "Root"), ("FrontShell", "Root"), ("RearShell", "Root"), ("Head", "FrontShell"),
            ("JawUpper", "Head"), ("JawLower", "Head"),
            ("ForeClaw", "FrontShell"), ("ForeClawLower", "ForeClaw"),
            ("FrontLeg", "FrontShell"), ("FrontLegLower", "FrontLeg"), ("FrontFoot", "FrontLegLower"),
            ("MidLeg", "Core"), ("MidLegLower", "MidLeg"), ("MidFoot", "MidLegLower"),
            ("RearLeg", "RearShell"), ("RearLegLower", "RearLeg"), ("RearFoot", "RearLegLower"),
            ("AntennaFrontBase", "Head"), ("AntennaFront1", "AntennaFrontBase"),
            ("AntennaFront2", "AntennaFront1"), ("AntennaFront3", "AntennaFront2"),
            ("AntennaFront4", "AntennaFront3"), ("AntennaFront5", "AntennaFront4"),
            ("AntennaFrontTip", "AntennaFront5"),
            ("AntennaBackBase", "Head"), ("AntennaBack1", "AntennaBackBase"),
            ("AntennaBack2", "AntennaBack1"), ("AntennaBack3", "AntennaBack2"),
            ("AntennaBack4", "AntennaBack3"), ("AntennaBack5", "AntennaBack4"),
            ("AntennaBackTip", "AntennaBack5"),
        ),
    ),

    Rig(
        "soul_roe_1", "soul_roe_1.png", "Root", (52, 52),
        (
            Piece("nucleus", "Nucleus", (52, 56), (ellipse(35, 38, 70, 75),), 3, 0, semantic="nucleus"),
            Piece("inner_halo", "Core", (52, 56), (ellipse(22, 25, 83, 88),), 2, 0, semantic="halo"),
        ),
        parents=(("Core", "Root"), ("Nucleus", "Core")),
    ),
    Rig(
        "soul_roe_2", "soul_roe_2.png", "Root", (52, 52),
        (
            Piece("nucleus", "Nucleus", (52, 56), (ellipse(35, 38, 70, 75),), 3, 0, semantic="nucleus"),
            Piece("inner_halo", "Core", (52, 56), (ellipse(22, 25, 83, 88),), 2, 0, semantic="halo"),
        ),
        parents=(("Core", "Root"), ("Nucleus", "Core")),
    ),
    Rig(
        "soul_roe_3", "soul_roe_3.png", "Root", (52, 52),
        (
            Piece("nucleus", "Nucleus", (52, 56), (ellipse(35, 38, 70, 75),), 3, 0, semantic="nucleus"),
            Piece("inner_halo", "Core", (52, 56), (ellipse(22, 25, 83, 88),), 2, 0, semantic="halo"),
        ),
        parents=(("Core", "Root"), ("Nucleus", "Core")),
    ),

    Rig(
        "soul_roes", "soul_roes.png", "Root", (178, 140),
        (
            # Descending visual depth gives overlap pixels to the foreground
            # orb while preserving a disjoint, exact-alpha source partition.
            Piece("roe_bottom_right", "RoeBottomRight", (260, 226), (voronoi_cell(0, SOUL_ROES_CENTERS),), 10, 0, semantic="orb"),
            Piece("roe_bottom", "RoeBottom", (178, 221), (voronoi_cell(1, SOUL_ROES_CENTERS),), 9, 0, semantic="orb"),
            Piece("roe_bottom_left", "RoeBottomLeft", (104, 214), (voronoi_cell(2, SOUL_ROES_CENTERS),), 8, 0, semantic="orb"),
            Piece("roe_far_right", "RoeFarRight", (323, 183), (voronoi_cell(3, SOUL_ROES_CENTERS),), 7, 0, semantic="orb"),
            Piece("roe_bottom_far_right", "RoeBottomFarRight", (310, 175), (voronoi_cell(4, SOUL_ROES_CENTERS),), 6, 0, semantic="orb"),
            Piece("roe_middle_left", "RoeMiddleLeft", (115, 138), (voronoi_cell(5, SOUL_ROES_CENTERS),), 5, 0, semantic="orb"),
            Piece("roe_middle_far_left", "RoeMiddleFarLeft", (38, 145), (voronoi_cell(6, SOUL_ROES_CENTERS),), 4, 0, semantic="orb"),
            Piece("roe_core", "RoeCore", (183, 125), (voronoi_cell(7, SOUL_ROES_CENTERS),), 4, 0, semantic="orb"),
            Piece("roe_middle_right", "RoeMiddleRight", (270, 115), (voronoi_cell(8, SOUL_ROES_CENTERS),), 3, 0, semantic="orb"),
            Piece("roe_top_left", "RoeTopLeft", (80, 72), (voronoi_cell(9, SOUL_ROES_CENTERS),), 2, 0, semantic="orb"),
            Piece("roe_top", "RoeTop", (145, 48), (voronoi_cell(10, SOUL_ROES_CENTERS),), 1, 0, semantic="orb"),
            Piece("roe_top_right", "RoeTopRight", (220, 55), (voronoi_cell(11, SOUL_ROES_CENTERS),), 1, 0, semantic="orb"),
        ),
        parents=(
            ("ClusterTop", "Root"), ("ClusterMiddle", "Root"), ("ClusterBottom", "Root"),
            ("RoeTopLeft", "ClusterTop"), ("RoeTop", "ClusterTop"), ("RoeTopRight", "ClusterTop"),
            ("RoeMiddleFarLeft", "ClusterMiddle"), ("RoeMiddleLeft", "ClusterMiddle"),
            ("RoeCore", "ClusterMiddle"), ("RoeMiddleRight", "ClusterMiddle"), ("RoeFarRight", "ClusterMiddle"),
            ("RoeBottomLeft", "ClusterBottom"), ("RoeBottom", "ClusterBottom"),
            ("RoeBottomRight", "ClusterBottom"), ("RoeBottomFarRight", "ClusterBottom"),
        ),
        virtual_bones=(
            VirtualBone("ClusterTop", (178, 65)), VirtualBone("ClusterMiddle", (178, 145)),
            VirtualBone("ClusterBottom", (180, 220)),
        ),
    ),

    # The Legacy: zero-pad translucent anatomical regions locked to HeartAnchor.
    Rig(
        "the_legacy", "the_legacy.png", "Root", (680, 560),
        (
            Piece("coral_left", "CoralLeft", (300, 430), (polygon((120, 320), (430, 315), (460, 520), (120, 535)),), 40, 0, "legacy_pink", semantic="coral"),
            Piece("coral_right", "CoralRight", (805, 560), (polygon((700, 450), (1010, 440), (1030, 689), (690, 689)),), 41, 0, "legacy_purple", semantic="coral"),
            Piece("seaweed_left", "SeaweedLeft", (260, 350), (polygon((0, 0), (520, 0), (540, 689), (0, 689)),), 8, 0, "legacy_green", semantic="vegetation"),
            Piece("seaweed_right", "Root", (680, 560), (polygon((480, 0), (1358, 0), (1358, 689), (500, 689)),), 8, 0, "legacy_green", semantic="vegetation"),
            Piece("top_tubes", "TopTubes", (690, 115), (polygon((560, 0), (820, 0), (850, 190), (590, 190)),), 18, 0, semantic="vessel"),
            Piece("top_purple", "TopPurple", (790, 170), (polygon((575, 40), (1040, 40), (1080, 330), (650, 355)),), 10, 0, semantic="organ"),
            Piece("left_tubes", "LeftTubes", (350, 275), (polygon((60, 150), (700, 145), (690, 410), (80, 430)),), 20, 0, semantic="vessel"),
            Piece("left_lobe", "LeftLobe", (340, 430), (polygon((40, 285), (660, 270), (690, 565), (500, 625), (40, 600)),), 21, 0, semantic="organ"),
            Piece("bottom_lobe", "BottomLobe", (420, 565), (polygon((100, 445), (780, 430), (790, 689), (80, 689)),), 22, 0, semantic="organ"),
            Piece("heart_core", "HeartCore", (690, 430), (polygon((500, 190), (930, 180), (1010, 620), (780, 689), (500, 620)),), 25, 0, semantic="organ"),
            Piece("right_lobe", "RightLobe", (930, 440), (polygon((760, 230), (1160, 230), (1210, 620), (875, 689), (740, 530)),), 23, 0, semantic="organ"),
            Piece("right_tubes", "RightTubes", (1120, 410), (polygon((930, 205), (1358, 205), (1358, 555), (1020, 590), (920, 430)),), 26, 0, semantic="vessel"),
            Piece("right_purple_tubes", "RightPurpleTubes", (1230, 520), (polygon((1080, 360), (1358, 345), (1358, 689), (1100, 689)),), 17, 0, semantic="vessel"),
        ),
        parents=(
            ("HeartAnchor", "Root"), ("HeartCore", "HeartAnchor"), ("LeftLobe", "HeartAnchor"),
            ("RightLobe", "HeartAnchor"), ("TopPurple", "HeartAnchor"), ("LeftTubes", "HeartAnchor"),
            ("RightTubes", "HeartAnchor"), ("TopTubes", "TopPurple"), ("BottomLobe", "HeartAnchor"),
            ("RightPurpleTubes", "HeartAnchor"), ("CoralLeft", "HeartAnchor"),
            ("CoralRight", "HeartAnchor"), ("SeaweedLeft", "Root"),
        ),
        virtual_bones=(VirtualBone("HeartAnchor", (690, 430)),),
    ),

    # Thief Raider: real arm/leg chains with small opaque socket underlays.
    Rig(
        "thief_raider", "thief_raider.png", "Torso", (190, 235),
        (
            Piece("dagger", "Dagger", (310, 300), (polygon((285, 270), (353, 265), (353, 420), (300, 382)),), 50, 6, semantic="weapon"),
            Piece("dagger_hand", "DaggerHand", (297, 290), (polygon((265, 255), (325, 250), (330, 320), (275, 325)),), 48, 8, semantic="hand"),
            Piece("dagger_forearm", "DaggerForearm", (282, 235), (polygon((245, 195), (320, 195), (330, 285), (270, 300), (245, 250)),), 46, 10, semantic="limb"),
            Piece("dagger_upper_arm", "DaggerUpperArm", (260, 170), (polygon((215, 120), (300, 125), (315, 225), (255, 255), (225, 215)),), 43, 12, semantic="limb"),
            Piece("guard_hand", "GuardHand", (163, 172), (polygon((140, 135), (195, 135), (205, 195), (155, 210)),), 46, 8, semantic="hand"),
            Piece("guard_forearm", "GuardForearm", (105, 185), (polygon((55, 145), (155, 145), (175, 225), (80, 230)),), 44, 10, semantic="limb"),
            Piece("guard_arm", "GuardArm", (120, 135), (polygon((70, 85), (160, 85), (175, 165), (95, 185), (55, 145)),), 42, 12, semantic="limb"),
            Piece("scarf", "Scarf", (207, 145), (polygon((145, 85), (285, 85), (290, 185), (180, 200), (135, 150)),), 40, 8, semantic="cloth"),
            Piece("face_shadow", "Head", (190, 125), (polygon((135, 35), (245, 35), (250, 125), (130, 130)),), 39, 4, semantic="accent"),
            Piece("head", "Head", (190, 125), (polygon((115, 0), (280, 0), (285, 165), (110, 170)),), 38, 8, semantic="head"),
            Piece("torso", "Torso", (190, 235), (polygon((205, 180), (275, 180), (275, 255), (205, 255)),), 25, 8, semantic="core"),
            Piece("pelvis", "Pelvis", (190, 285), (polygon((95, 210), (280, 205), (290, 350), (90, 355)),), 24, 8, semantic="core"),
            Piece("left_foot", "LeftFoot", (118, 495), (polygon((70, 455), (170, 450), (180, 534), (65, 534)),), 21, 8, semantic="foot"),
            Piece("left_shin", "LeftShin", (135, 410), (polygon((85, 360), (180, 355), (175, 495), (90, 500)),), 19, 10, semantic="limb"),
            Piece("left_leg", "LeftLeg", (145, 320), (polygon((80, 270), (205, 260), (205, 410), (90, 415)),), 17, 12, semantic="limb"),
            Piece("right_foot", "RightFoot", (252, 485), (polygon((190, 445), (305, 440), (315, 515), (200, 520)),), 22, 8, semantic="foot"),
            Piece("right_shin", "RightShin", (225, 405), (polygon((180, 350), (285, 345), (295, 485), (195, 490)),), 20, 10, semantic="limb"),
            Piece("right_leg", "RightLeg", (220, 320), (polygon((165, 255), (305, 250), (310, 405), (180, 410)),), 18, 12, semantic="limb"),
            Piece("bag", "Bag", (126, 145), (polygon((30, 15), (160, 15), (185, 225), (25, 250)),), 5, 8, semantic="prop"),
            Piece("cloak_left_tail", "CloakLeftTail", (69, 300), (polygon((0, 190), (110, 180), (130, 420), (0, 425)),), 9, 10, semantic="cloth"),
            Piece("cloak_right_tail", "CloakRightTail", (150, 315), (polygon((85, 200), (205, 195), (220, 420), (110, 430)),), 10, 10, semantic="cloth"),
            Piece("cloak", "Cloak", (145, 190), (polygon((0, 65), (220, 65), (230, 330), (0, 345)),), 6, 10, semantic="cloth"),
            Piece("socket_guard_shoulder", "Torso", (190, 235), (ellipse(88, 110, 145, 165),), 39, 0, underlay=True, semantic="socket"),
            Piece("socket_dagger_shoulder", "Torso", (190, 235), (ellipse(230, 135, 285, 190),), 39, 0, underlay=True, semantic="socket"),
            Piece("socket_left_hip", "Pelvis", (190, 285), (ellipse(120, 285, 175, 340),), 15, 0, underlay=True, semantic="socket"),
            Piece("socket_right_hip", "Pelvis", (190, 285), (ellipse(190, 285, 250, 345),), 15, 0, underlay=True, semantic="socket"),
        ),
        parents=(
            ("Pelvis", "Root"), ("Torso", "Pelvis"), ("Head", "Torso"), ("Scarf", "Torso"),
            ("Bag", "Torso"), ("Cloak", "Torso"), ("CloakLeftTail", "Cloak"), ("CloakRightTail", "Cloak"),
            ("GuardArm", "Torso"), ("GuardForearm", "GuardArm"), ("GuardHand", "GuardForearm"),
            ("DaggerUpperArm", "Torso"), ("DaggerForearm", "DaggerUpperArm"),
            ("DaggerHand", "DaggerForearm"), ("Dagger", "DaggerHand"),
            ("LeftLeg", "Pelvis"), ("LeftShin", "LeftLeg"), ("LeftFoot", "LeftShin"),
            ("RightLeg", "Pelvis"), ("RightShin", "RightLeg"), ("RightFoot", "RightShin"),
        ),
        virtual_bones=(VirtualBone("Root", (190, 486)),),
    ),
)

def draw_shapes(size: tuple[int, int], shapes: Iterable[Shape]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for kind, data in shapes:
        if kind == "polygon":
            draw.polygon(data, fill=255)
        elif kind == "ellipse":
            draw.ellipse(data, fill=255)
        elif kind == "rectangle":
            draw.rectangle(data, fill=255)
        elif kind == "voronoi":
            target_index, centers = data
            pixels = mask.load()
            for y in range(size[1]):
                for x in range(size[0]):
                    winner = min(
                        range(len(centers)),
                        key=lambda index: (
                            (x - centers[index][0]) ** 2 + (y - centers[index][1]) ** 2,
                            index,
                        ),
                    )
                    if winner == target_index:
                        pixels[x, y] = 255
        else:
            raise ValueError(f"Unknown shape kind: {kind}")
    return mask


def dilate(mask: Image.Image, pixels: int) -> Image.Image:
    if pixels <= 0:
        return mask
    # MaxFilter requires an odd kernel. Split very large pads into legal passes.
    result = mask
    remaining = pixels
    while remaining > 0:
        step = min(remaining, 15)
        result = result.filter(ImageFilter.MaxFilter(step * 2 + 1))
        remaining -= step
    return result


def apply_mask(source: Image.Image, mask: Image.Image) -> Image.Image:
    rgba = source.copy()
    alpha = ImageChops.multiply(source.getchannel("A"), mask)
    rgba.putalpha(alpha)
    return rgba


def crop_piece(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Cutout mask produced an empty part")
    left = max(0, bbox[0] - 2)
    top = max(0, bbox[1] - 2)
    right = min(image.width, bbox[2] + 2)
    bottom = min(image.height, bbox[3] + 2)
    return image.crop((left, top, right, bottom)), (left, top, right, bottom)


def cs_float(value: float) -> str:
    if value == int(value):
        return f"{int(value)}f"
    return f"{value:.4f}f".rstrip("0").rstrip(".") + ("f" if not f"{value:.4f}".rstrip("0").rstrip(".").endswith("f") else "")


def vec(x: float, y: float) -> str:
    return f"new Vector2({x:.3f}f, {y:.3f}f)"


def resolve_resource_path(path: str) -> Path:
    if not path.startswith("res://"):
        raise ValueError(f"Expected a res:// texture path, got {path!r}")
    return ROOT / path.removeprefix("res://")


def place_part_on_canvas(canvas: Image.Image, part: dict, canvas_size: tuple[int, int]) -> Image.Image:
    """Alpha-composite one generated part in its exact bind-pose location."""

    texture = Image.open(resolve_resource_path(part["texture"])).convert("RGBA")
    width, height = canvas_size
    center_x = float(part["pivot"][0]) + float(part["sprite_offset"][0]) + width / 2
    center_y = float(part["pivot"][1]) + float(part["sprite_offset"][1]) + height / 2
    left = round(center_x - texture.width / 2)
    top = round(center_y - texture.height / 2)
    canvas.alpha_composite(texture, (left, top))
    return texture


def visible_pixel_diff(left: Image.Image, right: Image.Image) -> tuple[int, Image.Image]:
    """Return the visible RGBA mismatch count and an opaque red diff image."""

    if left.size != right.size:
        raise ValueError(f"Cannot compare different canvas sizes: {left.size} and {right.size}")
    a = left.convert("RGBA")
    b = right.convert("RGBA")
    a_bytes = a.tobytes()
    b_bytes = b.tobytes()
    diff = Image.new("RGBA", a.size, (0, 0, 0, 0))
    diff_pixels = diff.load()
    mismatches = 0
    for pixel_index, offset in enumerate(range(0, len(a_bytes), 4)):
        source_pixel = a_bytes[offset : offset + 4]
        rebuilt_pixel = b_bytes[offset : offset + 4]
        if source_pixel[3] == 0 and rebuilt_pixel[3] == 0:
            continue
        if source_pixel != rebuilt_pixel:
            mismatches += 1
            x = pixel_index % a.width
            y = pixel_index // a.width
            diff_pixels[x, y] = (255, 32, 32, 255)
    return mismatches, diff


def audit_color(index: int, total: int) -> tuple[int, int, int, int]:
    hue = (index / max(total, 1) + 0.11) % 1.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.68, 1.0)
    return round(red * 255), round(green * 255), round(blue * 255), 104


def write_audit(inspection: dict, audit_root: Path) -> None:
    """Write bind-pose fidelity and segmentation maps outside shipping assets.

    The colored overlays are diagnostics only.  Generated part PNGs remain
    verbatim source RGBA; no recolored image is referenced by the mod.
    """

    audit_root.mkdir(parents=True, exist_ok=True)
    maps_root = audit_root / "part_maps"
    rest_root = audit_root / "rest_rebuilds"
    diff_root = audit_root / "diffs"
    maps_root.mkdir(parents=True, exist_ok=True)
    rest_root.mkdir(parents=True, exist_ok=True)
    diff_root.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict] = {}

    for rig_key, rig in inspection.items():
        width, height = int(rig["canvas"][0]), int(rig["canvas"][1])
        source = Image.open(MONSTERS / rig["source"]).convert("RGBA")
        rebuilt = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay = source.copy()
        ordered_parts = sorted(rig["parts"], key=lambda item: (item["z"], item["name"]))
        for index, part in enumerate(ordered_parts):
            texture = place_part_on_canvas(rebuilt, part, (width, height))
            center_x = float(part["pivot"][0]) + float(part["sprite_offset"][0]) + width / 2
            center_y = float(part["pivot"][1]) + float(part["sprite_offset"][1]) + height / 2
            left = round(center_x - texture.width / 2)
            top = round(center_y - texture.height / 2)
            tint = Image.new("RGBA", texture.size, audit_color(index, len(ordered_parts)))
            tint.putalpha(texture.getchannel("A").point(lambda value: 104 if value else 0))
            overlay.alpha_composite(tint, (left, top))

        draw = ImageDraw.Draw(overlay)
        bone_lookup = {bone["name"]: bone for bone in rig["bones"]}
        for index, part in enumerate(ordered_parts):
            pivot_x = round(float(part["pivot"][0]) + width / 2)
            pivot_y = round(float(part["pivot"][1]) + height / 2)
            color = audit_color(index, len(ordered_parts))[:3] + (255,)
            draw.ellipse((pivot_x - 5, pivot_y - 5, pivot_x + 5, pivot_y + 5), fill=color, outline=(0, 0, 0, 255), width=2)
            draw.text((pivot_x + 7, pivot_y - 7), str(index + 1), fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))

        panel_width = 420
        labelled = Image.new("RGBA", (width + panel_width, max(height, 44 + 22 * len(ordered_parts))), (28, 31, 36, 255))
        labelled.alpha_composite(overlay, (0, 0))
        legend = ImageDraw.Draw(labelled)
        legend.text((width + 18, 14), f"{rig_key}: {len(rig['bones'])} bones / {len(ordered_parts)} parts", fill=(255, 255, 255, 255))
        for index, part in enumerate(ordered_parts):
            y = 42 + index * 22
            color = audit_color(index, len(ordered_parts))[:3] + (255,)
            legend.rectangle((width + 18, y + 2, width + 30, y + 14), fill=color)
            parent = bone_lookup.get(part["bone"], {}).get("parent", "") or "<root>"
            legend.text(
                (width + 38, y),
                f"{index + 1:02} {part['name']}  [{part['bone']} <- {parent}] z={part['z']}",
                fill=(225, 228, 232, 255),
            )

        mismatches, diff = visible_pixel_diff(source, rebuilt)
        labelled.convert("RGB").save(maps_root / f"{rig_key}.jpg", quality=94)
        rebuilt.save(rest_root / f"{rig_key}.png", optimize=True)
        diff.save(diff_root / f"{rig_key}.png", optimize=True)
        external_parts = sum(
            1
            for part in ordered_parts
            if "/rig_parts/" not in str(part["texture"])
        )
        report[rig_key] = {
            "canvas": [width, height],
            "bones": len(rig["bones"]),
            "parts": len(ordered_parts),
            "external_parts": external_parts,
            "visible_bind_pose_rgba_mismatches": mismatches,
            "exact_source_rebuild_expected": external_parts == 0,
        }

    (audit_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build() -> tuple[str, dict]:
    cs_entries: dict[str, list[dict]] = {}
    cs_bones: dict[str, list[dict]] = {}
    inspection: dict[str, dict] = {}

    for rig in RIGS:
        source_path = MONSTERS / rig.source
        source = Image.open(source_path).convert("RGBA")
        width, height = source.size
        alpha = source.getchannel("A")
        alpha_binary = alpha.point(lambda value: 255 if value > 0 else 0)
        # A padded rigid part deliberately borrows a few source pixels from its
        # neighbour so a rotating joint has material underneath the seam.  The
        # overlap is only blend-neutral when that source pixel is fully opaque:
        # drawing the same translucent RGBA pixel twice increases its opacity.
        # Keep every semi-transparent pixel under single ownership and limit
        # joint overlap to the fully opaque interior.  This matters especially
        # for The Legacy and Soul Roe art, whose visible pixels are mostly
        # translucent even well inside the silhouette.
        alpha_opaque = alpha.point(lambda value: 255 if value == 255 else 0)
        hue, saturation, _ = source.convert("HSV").split()
        antenna_low_saturation = saturation.point(
            lambda value: 255 if value <= 78 else 0
        )
        antenna_cyan_hue = hue.point(
            lambda value: 255 if 105 <= value <= 165 else 0
        )
        legacy_colored = saturation.point(lambda value: 255 if value >= 36 else 0)
        legacy_green_hue = hue.point(lambda value: 255 if 34 <= value <= 82 else 0)
        legacy_pink_hue = hue.point(lambda value: 255 if value >= 215 else 0)
        legacy_purple_hue = hue.point(lambda value: 255 if 164 <= value <= 208 else 0)
        pixel_family_masks = {
            "antenna": ImageChops.multiply(
                ImageChops.lighter(antenna_low_saturation, antenna_cyan_hue),
                alpha_binary,
            ),
            "legacy_green": ImageChops.multiply(
                ImageChops.multiply(legacy_green_hue, legacy_colored), alpha_binary
            ),
            "legacy_pink": ImageChops.multiply(
                ImageChops.multiply(legacy_pink_hue, legacy_colored), alpha_binary
            ),
            "legacy_purple": ImageChops.multiply(
                ImageChops.multiply(legacy_purple_hue, legacy_colored), alpha_binary
            ),
        }
        owned = Image.new("L", source.size, 0)
        output_dir = PARTS_ROOT / rig.key
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_texture_names: set[str] = set()
        entries: list[dict] = []

        # Bone pivots are authored in source-canvas pixels.  Parent-relative
        # transforms are calculated at runtime from this absolute bind pose so
        # introducing a hierarchy never shifts a part by even one pixel.
        bone_pivots: dict[str, Point] = {rig.base_bone: rig.base_pivot}

        def register_bone(name: str, pivot: Point) -> None:
            previous = bone_pivots.get(name)
            if previous is not None and previous != pivot:
                raise ValueError(
                    f"{rig.key}/{name} declares conflicting pivots: {previous} and {pivot}"
                )
            bone_pivots[name] = pivot

        for piece in rig.pieces:
            register_bone(piece.bone, piece.pivot)
        for piece in rig.external:
            register_bone(piece.bone, piece.pivot)
        for bone in rig.virtual_bones:
            register_bone(bone.name, bone.pivot)

        parent_by_bone = {name: "" for name in bone_pivots}
        for child, parent in rig.parents:
            if child not in bone_pivots:
                raise ValueError(f"{rig.key} hierarchy child is missing: {child}")
            if parent and parent not in bone_pivots:
                raise ValueError(f"{rig.key}/{child} hierarchy parent is missing: {parent}")
            parent_by_bone[child] = parent

        logical_roots = [name for name, parent in parent_by_bone.items() if not parent]
        if logical_roots != ["Root"]:
            raise ValueError(
                f"{rig.key} must declare exactly one logical Root; got {logical_roots}"
            )

        ordered_bones: list[str] = []
        visit_state: dict[str, int] = {}

        def visit_bone(name: str) -> None:
            state = visit_state.get(name, 0)
            if state == 2:
                return
            if state == 1:
                raise ValueError(f"{rig.key} cutout bone hierarchy contains a cycle at {name}")
            visit_state[name] = 1
            parent = parent_by_bone[name]
            if parent:
                visit_bone(parent)
            visit_state[name] = 2
            ordered_bones.append(name)

        for bone_name in bone_pivots:
            visit_bone(bone_name)

        bone_entries = [
            {
                "name": name,
                "parent": parent_by_bone[name],
                "pivot": [bone_pivots[name][0] - width / 2, bone_pivots[name][1] - height / 2],
            }
            for name in ordered_bones
        ]

        for piece in rig.pieces:
            raw = draw_shapes(source.size, piece.shapes)
            if piece.pixel_family is not None:
                try:
                    raw = ImageChops.multiply(raw, pixel_family_masks[piece.pixel_family])
                except KeyError as exception:
                    raise ValueError(
                        f"{rig.key}/{piece.name} uses unknown pixel family "
                        f"{piece.pixel_family!r}"
                    ) from exception
            # Ownership masks stay binary. A socket underlay is a deliberate
            # duplicate of fully opaque source pixels and therefore never
            # claims pixels away from the anatomical foreground part.
            if piece.underlay:
                core = ImageChops.multiply(raw, alpha_opaque)
            else:
                core = ImageChops.multiply(
                    ImageChops.subtract(raw, owned),
                    alpha_binary,
                )
            if core.getbbox() is None:
                raise ValueError(f"{rig.key}/{piece.name} has no owned pixels")
            if not piece.underlay:
                owned = ImageChops.lighter(owned, core)
            padded = dilate(core, piece.pad)
            opaque_overlap = ImageChops.multiply(padded, alpha_opaque)
            render_mask = ImageChops.lighter(core, opaque_overlap)
            if piece.pixel_family is not None:
                render_mask = ImageChops.multiply(
                    render_mask,
                    pixel_family_masks[piece.pixel_family],
                )
            rendered, bbox = crop_piece(apply_mask(source, render_mask))
            output_path = output_dir / f"{piece.name}.png"
            rendered.save(output_path, optimize=True)
            generated_texture_names.add(output_path.name)
            crop_center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
            entries.append(
                {
                    "name": piece.name,
                    "bone": piece.bone,
                    "texture": f"res://images/monsters/rig_parts/{rig.key}/{piece.name}.png",
                    "pivot": [piece.pivot[0] - width / 2, piece.pivot[1] - height / 2],
                    "sprite_offset": [crop_center[0] - piece.pivot[0], crop_center[1] - piece.pivot[1]],
                    "z": piece.z,
                    "overlap_pixels": piece.pad,
                    "atlas_bleed_pixels": piece.atlas_bleed,
                    "is_underlay": piece.underlay,
                    "semantic": piece.semantic,
                }
            )

        if rig.pieces:
            # The final apply_mask() performs the one and only source-alpha
            # multiplication.  Inverting binary ownership exactly preserves the
            # unowned source pixels, including partially transparent membranes.
            base_mask = ImageChops.invert(owned)
            base_render = apply_mask(source, base_mask)
            if base_render.getchannel("A").getbbox() is not None:
                rendered, bbox = crop_piece(base_render)
                output_path = output_dir / "base.png"
                rendered.save(output_path, optimize=True)
                generated_texture_names.add(output_path.name)
                crop_center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                entries.insert(
                    0,
                    {
                        "name": "base",
                        "bone": rig.base_bone,
                        "texture": f"res://images/monsters/rig_parts/{rig.key}/base.png",
                        "pivot": [rig.base_pivot[0] - width / 2, rig.base_pivot[1] - height / 2],
                        "sprite_offset": [crop_center[0] - rig.base_pivot[0], crop_center[1] - rig.base_pivot[1]],
                        "z": 0,
                        "overlap_pixels": 0,
                        "atlas_bleed_pixels": 2,
                        "is_underlay": False,
                        "semantic": "base",
                    },
                )

        for piece in rig.external:
            entries.append(
                {
                    "name": piece.name,
                    "bone": piece.bone,
                    "texture": piece.texture,
                    "pivot": [piece.pivot[0] - width / 2, piece.pivot[1] - height / 2],
                    "sprite_offset": [piece.center[0] - piece.pivot[0], piece.center[1] - piece.pivot[1]],
                    "z": piece.z,
                    "overlap_pixels": 0,
                    "atlas_bleed_pixels": 0,
                    "is_underlay": False,
                    "semantic": "external",
                }
            )

        # Renamed/resegmented parts must not leak stale PNGs into the exported
        # PCK, where they waste space and make the authored hierarchy ambiguous.
        for stale_path in output_dir.glob("*.png"):
            if stale_path.name not in generated_texture_names:
                stale_path.unlink()
        for stale_sidecar in output_dir.glob("*.png.import"):
            png_name = stale_sidecar.name.removesuffix(".import")
            if png_name not in generated_texture_names:
                stale_sidecar.unlink()

        cs_entries[rig.key] = entries
        cs_bones[rig.key] = bone_entries
        inspection[rig.key] = {
            "source": rig.source,
            "canvas": [width, height],
            "bones": bone_entries,
            "parts": entries,
        }

    lines = [
        "// <auto-generated />",
        "using System.Collections.Generic;",
        "using Godot;",
        "",
        "namespace STS2_Things.Visuals;",
        "",
        "internal readonly record struct CutoutBoneSpec(",
        "    string Name,",
        "    string ParentBoneName,",
        "    Vector2 PivotPosition);",
        "",
        "internal readonly record struct CutoutPartSpec(",
        "    string Name,",
        "    string BoneName,",
        "    string TexturePath,",
        "    Vector2 PivotPosition,",
        "    Vector2 SpriteOffset,",
        "    int ZIndex,",
        "    int JointOverlapPixels,",
        "    int AtlasBleedPixels,",
        "    bool IsUnderlay,",
        "    string SemanticRole);",
        "",
        "internal static class GeneratedCutoutRigData",
        "{",
    ]
    for key, entries in cs_bones.items():
        member = "".join(part.capitalize() for part in key.split("_"))
        lines.append(f"    private static readonly CutoutBoneSpec[] {member}Bones =")
        lines.append("    [")
        for entry in entries:
            lines.append(
                "        new("
                f'"{entry["name"]}", "{entry["parent"]}", {vec(*entry["pivot"])}),'
            )
        lines.append("    ];")
        lines.append("")
    for key, entries in cs_entries.items():
        member = "".join(part.capitalize() for part in key.split("_"))
        lines.append(f"    private static readonly CutoutPartSpec[] {member} =")
        lines.append("    [")
        for entry in entries:
            lines.append(
                "        new("
                f'"{entry["name"]}", "{entry["bone"]}", "{entry["texture"]}", '
                f'{vec(*entry["pivot"])}, {vec(*entry["sprite_offset"])}, {entry["z"]}, '
                f'{entry["overlap_pixels"]}, {entry["atlas_bleed_pixels"]}, '
                f'{str(entry["is_underlay"]).lower()}, "{entry["semantic"]}"),'
            )
        lines.append("    ];")
        lines.append("")
    lines.extend(
        [
            "    internal static IReadOnlyList<CutoutBoneSpec> GetBones(string key)",
            "    {",
            "        return key switch",
            "        {",
        ]
    )
    for key in cs_bones:
        member = "".join(part.capitalize() for part in key.split("_"))
        lines.append(f'            "{key}" => {member}Bones,')
    lines.extend(
        [
            '            _ => throw new KeyNotFoundException($"Unknown cutout rig key: {key}")',
            "        };",
            "    }",
            "",
            "    internal static IReadOnlyList<CutoutPartSpec> Get(string key)",
            "    {",
            "        return key switch",
            "        {",
        ]
    )
    for key in cs_entries:
        member = "".join(part.capitalize() for part in key.split("_"))
        lines.append(f'            "{key}" => {member},')
    lines.extend(
        [
            '            _ => throw new KeyNotFoundException($"Unknown cutout rig key: {key}")',
            "        };",
            "    }",
            "}",
            "",
        ]
    )
    return "\n".join(lines), inspection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify generated metadata without rewriting it")
    parser.add_argument(
        "--audit-dir",
        type=Path,
        nargs="?",
        const=DEFAULT_AUDIT_ROOT,
        help="write bind-pose rebuilds, RGBA diffs and labelled segmentation maps",
    )
    args = parser.parse_args()

    generated_cs, inspection = build()
    manifest_text = json.dumps(inspection, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        errors: list[str] = []
        if not GENERATED_CS.is_file() or GENERATED_CS.read_text(encoding="utf-8") != generated_cs:
            errors.append(str(GENERATED_CS.relative_to(ROOT)))
        if not GENERATED_MANIFEST.is_file() or GENERATED_MANIFEST.read_text(encoding="utf-8") != manifest_text:
            errors.append(str(GENERATED_MANIFEST.relative_to(ROOT)))
        if errors:
            raise SystemExit("stale generated cutout rig files: " + ", ".join(errors))
        print("STS2_Things cutout rigs: PASS")
        return 0

    GENERATED_CS.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_CS.write_text(generated_cs, encoding="utf-8", newline="\n")
    GENERATED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_MANIFEST.write_text(manifest_text, encoding="utf-8", newline="\n")
    if args.audit_dir is not None:
        write_audit(inspection, args.audit_dir)
    print(f"Built {sum(len(value['parts']) for value in inspection.values())} rigid cutout parts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
