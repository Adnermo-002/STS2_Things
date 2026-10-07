"""Floating fish: continuous skinned body, soft fins, tail chain and eight-link lure."""
import numpy as np
import cv2
NAME='lantern_fish'
ORIGIN=(800,1180)
VIEW=dict(scale=.43,W=880,H=680,ox=470,oy=620)
ORDER=['skin']; GLOW_OF={'lantern_glow':'skin'}; GLOW_SCALE=.5; GLOW_ALPHA=.85
SPACING={'skin':14}; CHAINS={}
LURE=[(620,310),(559,231),(503,159),(404,125),(307,153),(234,207),(190,267),(171,335)]
TAIL=[(1118,572),(1242,578),(1334,568),(1450,568)]
FIN=[(849,657),(916,687),(994,719)]
DORSAL=[(887,356),(933,274),(1045,285),(1120,365)]
BONES=[('root',None,ORIGIN),('body','root',(794,567)),('head','body',(582,552)),('jaw','head',(473,651))]
for name,pts,parent in [('tail',TAIL,'body'),('fin',FIN,'body'),('dorsal',DORSAL,'body'),('lure',LURE,'head')]:
    for i,p in enumerate(pts):BONES.append((f'{name}_{i}',parent if i==0 else f'{name}_{i-1}',p))
BONES.append(('lamp','lure_7',(153,445)))
SKIN={'skin':[('body',(0,0),(0,0))]}
REGIONS={
 'tail':[(1090,411),(1290,458),(1525,352),(1525,810),(1278,743),(1130,751)],
 'dorsal':[(781,150),(1163,136),(1201,452),(1091,490),(848,351)],
 'fin':[(823,604),(952,582),(1064,675),(1068,794),(895,790),(807,700)],
 'jaw':[(286,595),(373,600),(460,618),(502,652),(499,706),(347,719),(281,685)],
 'lure':[(119,53),(580,46),(674,282),(548,367),(492,291),(476,223),(343,167),(239,234),(210,374),(107,362)],
 'lamp':[(32,317),(256,314),(269,592),(28,592)]}
fields={}
for name,poly in REGIONS.items():
    mask=np.zeros((1024,1536),np.float32);cv2.fillPoly(mask,[np.array(poly,np.int32)],1)
    fields[name]=cv2.GaussianBlur(mask,(0,0),45 if name=='fin' else 28 if name=='dorsal' else 9)
xx=np.indices((1024,1536))[1]
tail_blend=np.clip((xx-1070)/210,0,1).astype(np.float32)
fields['tail']=tail_blend*tail_blend*(3-2*tail_blend)

def chain(points,pivots,prefix,width=48):
    ds=[];ts=[];lengths=[]
    for a,b in zip(pivots[:-1],pivots[1:]):
        a,b=np.array(a),np.array(b);v=b-a;length=np.linalg.norm(v)
        t=np.clip((points-a)@v/(length*length),0,1)
        ds.append(np.linalg.norm(points-a-t[:,None]*v,axis=1));ts.append(t);lengths.append(length)
    result=[]
    for i,k in enumerate(np.array(ds).argmin(axis=0)):
        t=ts[k][i];w=min(.49,width/lengths[k]);pair={f'{prefix}_{k}':1.}
        if k>0 and t<w:
            mix=.5*(1-t/w);pair={f'{prefix}_{k-1}':mix,f'{prefix}_{k}':1-mix}
        elif k<len(pivots)-2 and t>1-w:
            mix=.5*(t-(1-w))/w;pair={f'{prefix}_{k}':1-mix,f'{prefix}_{k+1}':mix}
        result.append(pair)
    return result

def weights(name,points):
    points=np.array(points);x=np.clip(points[:,0].astype(int),0,1535);y=np.clip(points[:,1].astype(int),0,1023)
    maps={key:chain(points,pivots,key) for key,pivots in [('tail',TAIL),('fin',FIN),('dorsal',DORSAL),('lure',LURE)]}
    result=[]
    for i,(px,_) in enumerate(points):
        h=float(np.clip((835-px)/260,0,1));acc={'head':h,'body':1-h}
        for reg in REGIONS:
            a=float(fields[reg][y[i],x[i]])
            if a<.002:continue
            incoming=maps[reg][i] if reg in maps else {reg:1.}
            acc={k:v*(1-a) for k,v in acc.items()}
            for k,v in incoming.items():acc[k]=acc.get(k,0)+v*a
        acc={k:v for k,v in acc.items() if v>.005};s=sum(acc.values())
        result.append([(k,v/s) for k,v in acc.items()])
    return result
