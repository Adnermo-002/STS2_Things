"""Continuous body, planted four-leg IK, and a seven-joint current tail."""
import math
import numpy as np
NAME='reverse_salamander'
ORIGIN=(745,982)
VIEW=dict(scale=.48,W=880,H=610,ox=425,oy=576)
ORDER=['leg_hind_far','leg_front_far','tail','body','gill_0','gill_1','gill_2','leg_hind_near','leg_front_near','eye_far','eye_near']
SPACING={n:15 for n in ORDER};SPACING.update(body=13,tail=16,eye_far=7,eye_near=7,gill_0=9,gill_1=9,gill_2=9)
CHAINS={}
BONES=[('root',None,ORIGIN),('pelvis','root',(886,779)),('body','pelvis',(628,714)),
 ('neck','body',(481,640)),('head','neck',(328,567)),('muzzle','head',(128,596)),('jaw','head',(234,681)),
 ('belly','body',(620,849)),('eye_far','head',(103,491)),('eye_near','head',(295,530)),
 ('chest','body',(504,765)),('back','body',(805,657)),('haunch','pelvis',(988,803))]
LEGS={
 'front_far':((267,741),(193,839),(196,924),(122,944),'body'),
 'front_near':((650,709),(724,823),(674,945),(587,964),'body'),
 'hind_far':((953,746),(881,838),(868,931),(823,937),'pelvis'),
 'hind_near':((1069,760),(1161,841),(1164,933),(1222,954),'pelvis'),
}
for name,(hip,knee,ankle,toe,parent) in LEGS.items():
 BONES += [(name+'_hip',parent,hip),(name+'_knee',name+'_hip',knee),(name+'_ankle',name+'_knee',ankle),(name+'_toe',name+'_ankle',toe)]
TAIL=[(1029,748),(1204,763),(1361,664),(1436,490),(1380,335),(1231,209),(1035,159)]
for i,pos in enumerate(TAIL):BONES.append((f'tail_{i}','pelvis' if i==0 else f'tail_{i-1}',pos))
FINS={'fin_a':(955,86),'fin_b':(964,217),'fin_c':(1036,311)}
FIN_ROOTS={'fin_a':(1068,102),'fin_b':(1084,209),'fin_c':(1120,290)}
for n,p in FINS.items():
 BONES.append((n,'tail_6',FIN_ROOTS[n]));BONES.append((n+'_tip',n,p))
GILLS=[((522,524),(558,446)),((535,569),(615,529)),((529,610),(604,619))]
for i,(a,b) in enumerate(GILLS):BONES += [(f'gill_{i}','neck',a),(f'gill_{i}_tip',f'gill_{i}',b)]
BONES += [('mouth_vfx','muzzle',(96,612)),('flow_tip','tail_6',(926,99))]
SKIN={n:[('body',(0,0),(0,0))] for n in ORDER}

def segment_weights(points,bones,anchors,radius=65):
 p=np.asarray(points);anchors=np.array(anchors,float)
 # A normalized smooth field avoids discontinuities around the curved tail.
 distances=np.linalg.norm(p[:,None,:]-anchors[None,:,:],axis=2)
 weights=np.exp(-((distances-distances.min(axis=1,keepdims=True))/radius)**2)
 weights/=weights.sum(axis=1,keepdims=True)
 return [[(bone,float(v)) for bone,v in zip(bones,row) if v>.0001] for row in weights]

def weights(name,points):
 p=np.asarray(points)
 if name in ['eye_far','eye_near']:return [[(name,1.)] for _ in p]
 if name.startswith('gill_'):
  i=int(name[-1]);a,b=np.array(GILLS[i][0]),np.array(GILLS[i][1]);u=np.clip(((p-a)@(b-a))/np.dot(b-a,b-a),0,1)
  return [[(name,float(1-t*t)),(name+'_tip',float(t*t))] for t in u]
 if name=='tail':
  result=segment_weights(p,[f'tail_{i}' for i in range(len(TAIL))],TAIL,95)
  for point,row in zip(p,result):
   acc=dict(row)
   for bone,center in FINS.items():
    v=.65*math.exp(-np.sum(((point-center)/(116,81))**2)*1.6)
    root=np.array(FIN_ROOTS[bone]);tip=np.array(center);u=float(np.clip(((point-root)@(tip-root))/np.dot(tip-root,tip-root),0,1))
    acc={k:w*(1-v) for k,w in acc.items()};acc[bone]=v*(1-u*.65);acc[bone+'_tip']=v*u*.65
   total=sum(acc.values());row[:]=[(k,w/total) for k,w in acc.items() if w>.0001]
  return result
 if name.startswith('leg_'):
  key=name[4:];hip,knee,ankle,toe,_=LEGS[key]
  result=segment_weights(p,[key+'_hip',key+'_knee',key+'_ankle',key+'_toe'],[hip,knee,ankle,toe],60)
  # Keep the painted shoulder/haunch seam on the same surface as the body.
  # Only the free portion of each limb follows the IK chain completely.
  axis=np.array(knee)-hip
  u=((p-hip)@axis)/np.dot(axis,axis)
  root=np.clip((.45-u)/.55,0,1);root=root*root*(3-2*root)
  for row,host,v in zip(result,weights('body',p),root):
   acc={b:w*(1-v) for b,w in row}
   for b,w in host:acc[b]=acc.get(b,0)+w*v
   total=sum(acc.values());row[:]=[(b,w/total) for b,w in acc.items() if w>.0001]
  return result
 fields=[('body',(660,700),(280,230),.98),('back',(805,657),(166,91),.40),
  ('haunch',(988,803),(130,133),.36),('belly',(645,866),(242,123),.58),
  ('chest',(504,765),(158,107),.30),('neck',(483,641),(154,143),.93),
  ('head',(323,539),(260,170),.99),('muzzle',(113,585),(100,68),.70),('jaw',(236,691),(173,87),.65)]
 result=[]
 for point in p:
  acc={'pelvis':1.}
  for bone,center,radius,strength in fields:
   w=float(strength*np.exp(-np.sum(((point-center)/radius)**2)*1.4))
   if bone=='head':w=max(w,float(np.clip((520-point[0])/120,0,1)*np.clip((745-point[1])/110,0,1)))
   acc={k:v*(1-w) for k,v in acc.items()};acc[bone]=acc.get(bone,0)+w
  total=sum(acc.values());result.append([(k,v/total) for k,v in acc.items() if v>.0001])
 return result

def s(p):return np.array([p[0]-ORIGIN[0],ORIGIN[1]-p[1]],float)
def angle(v):return math.atan2(v[1],v[0])
def wrap(v):return (v+180)%360-180
def matrix(p,r):
 a=math.radians(r);m=np.eye(3);m[:2,:2]=[[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]];m[:2,2]=p;return m
def post(pose,world,frame,sk):
 for name,(hip,knee,ankle,toe,parent) in LEGS.items():
  host=world[parent];hb,kb,ab=name+'_hip',name+'_knee',name+'_ankle'
  h=(host@np.r_[sk.local[hb],1])[:2];a,k,hr=s(ankle),s(knee),s(hip)
  offset=frame.extra.get('feet',{}).get(name,(0,0,0));target=a+np.array(offset[:2])
  l1,l2=np.linalg.norm(k-hr),np.linalg.norm(a-k);delta=target-h;distance=np.linalg.norm(delta)
  reach=np.clip(distance,abs(l1-l2)+.02,l1+l2-.02)
  if abs(reach-distance)>1e-5:
   dy=np.clip(delta[1],-reach+.001,reach-.001);side=1 if ankle[0]>=hip[0] else -1
   target=h+[side*math.sqrt(max(0,reach*reach-dy*dy)),dy]
  local=(np.linalg.inv(host)@np.r_[target,1])[:2]-sk.local[hb];d=max(.001,np.linalg.norm(local))
  va,vb=k-hr,a-hr;sign=1 if va[0]*vb[1]-va[1]*vb[0]>=0 else -1
  alpha=math.acos(np.clip((l1*l1+d*d-l2*l2)/(2*l1*d),-1,1))
  r1=wrap(math.degrees(angle(local)-sign*alpha-angle(sk.local[kb])));upper=host@matrix(sk.local[hb],r1)
  q=(upper@np.r_[sk.local[kb],1])[:2];r2=wrap(math.degrees(angle(target-q)-angle(upper[:2,:2]@sk.local[ab])))
  lower=upper@matrix(sk.local[kb],r2);fv=s(toe)-s(ankle);r3=wrap(math.degrees(angle(fv)-angle(lower[:2,:2]@fv))+offset[2])
  pose[hb]=(r1,0,0,1,1);pose[kb]=(r2,0,0,1,1);pose[ab]=(r3,0,0,1,1)
