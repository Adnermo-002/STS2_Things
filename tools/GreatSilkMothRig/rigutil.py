"""rigutil — helpers importable from rigdef.py / anims.py (no rig dependency)."""
import math
from functools import lru_cache


def chain_skin(bones, pos, tail):
    """SKIN entries for a bone chain: segment i = pos[i] -> pos[i+1] (last -> tail)."""
    pts = [pos[b] for b in bones] + [tail]
    return [(b, pts[i], pts[i + 1]) for i, b in enumerate(bones)]


# ---------------------------------------------------------------- animation helpers
TAU = 2 * math.pi
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_in(x): x = clamp(x); return x ** 3
def seg(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def bump(t, t0, t1, t2): return ease(seg(t, t0, t1)) * (1 - ease(seg(t, t1, t2)))
def kick(t, t0, freq=3.0, damp=4.0):
    if t < t0: return 0.0
    x = t - t0; return math.exp(-damp * x) * math.sin(TAU * freq * x)
def hold(t, t0, t1, t2, t3):
    """0 -> 1 over t0..t1, stays, 1 -> 0 over t2..t3"""
    return ease(seg(t, t0, t1)) * (1 - ease(seg(t, t2, t3)))


@lru_cache(maxsize=None)
def _curve(points):
    slopes = [0.0] * len(points)
    for i in range(1, len(points)-1):
        h0, h1 = points[i][0]-points[i-1][0], points[i+1][0]-points[i][0]
        a, b = (points[i][1]-points[i-1][1])/h0, (points[i+1][1]-points[i][1])/h1
        if a*b > 0:
            w0, w1 = 2*h1+h0, h1+2*h0
            slopes[i] = (w0+w1)/(w0/a+w1/b)
    return slopes


def key(t, *points):
    """Shape-preserving Hermite curve with continuous passing-pose velocity."""
    if t <= points[0][0]: return points[0][1]
    slopes = _curve(points)
    for i in range(len(points)-1):
        if t <= points[i+1][0]:
            h = points[i+1][0]-points[i][0]
            u = (t-points[i][0])/h
            return ((2*u**3-3*u*u+1)*points[i][1] + (u**3-2*u*u+u)*h*slopes[i]
                    + (-2*u**3+3*u*u)*points[i+1][1] + (u**3-u*u)*h*slopes[i+1])
    return points[-1][1]


class Pose(dict):
    def add(self, b, r=0, x=0, y=0, sx=0, sy=0, s=0):
        Rr, X, Y, SX, SY = self.get(b, (0, 0, 0, 1, 1))
        self[b] = (Rr + r, X + x, Y + y, SX * (1 + sx + s), SY * (1 + sy + s))


class Frame:
    def __init__(self):
        self.P = Pose(); self.glow = {}
        self.tint = (1.0, 1.0, 1.0, 1.0)
        self.bias = {}          # spring chain bone -> target angle (deg)
        self.extra = {}         # free data for rigdef.post
