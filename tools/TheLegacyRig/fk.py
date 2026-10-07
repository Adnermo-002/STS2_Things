import math, numpy as np
from rigdef import S
class Skel:
    def __init__(self, rig):
        self.bones=rig['bones']; self.idx={b['name']:i for i,b in enumerate(self.bones)}
        self.setup={b['name']:S(b['pos']) for b in self.bones}
        self.local={}
        for b in self.bones:
            p=b['parent']; sp=self.setup[b['name']]
            if p is None: self.local[b['name']]=sp
            else:
                pp=self.setup[p]; self.local[b['name']]=(sp[0]-pp[0],sp[1]-pp[1])
    def world(self, pose):
        """pose: bone -> (rot,dx,dy,sx,sy). returns bone -> 2x3 matrix"""
        W={}
        for b in self.bones:
            n=b['name']; r,dx,dy,sx,sy=pose.get(n,(0,0,0,1,1))
            lx,ly=self.local[n]; x,y=lx+dx,ly+dy
            c,s=math.cos(math.radians(r)),math.sin(math.radians(r))
            M=np.array([[c*sx,-s*sy,x],[s*sx,c*sy,y],[0,0,1]])
            W[n]=M if b['parent'] is None else W[b['parent']]@M
        return W
