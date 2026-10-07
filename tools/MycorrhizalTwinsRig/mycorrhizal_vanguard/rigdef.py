"""Art-directed joint positions and smooth continuous weights for both silhouettes."""
from pathlib import Path
import json
import numpy as np
NAME=Path.cwd().name
D=json.loads(Path('definition.json').read_text())
A={k:tuple(v) for k,v in D['anchors'].items()}
ORIGIN=tuple(D['origin']);VIEW=dict(scale=.58,W=760,H=650,ox=390,oy=620)
ORDER=['arm_far','foot_far','foot_near','body','cap','arm_near','eye_0','eye_1']
SPACING={n:14 if n not in ['eye_0','eye_1'] else 7 for n in ORDER}
CHAINS={}
BONES=[('root',None,ORIGIN),('body','root',A['body']),('neck','body',A['neck']),
 ('cap_posture','neck',A['cap']),('cap','cap_posture',A['cap']),('cap_l','cap',A['cap_l']),('cap_r','cap',A['cap_r'])]
for side in ['far','near']:
 for bone,parent in [(f'arm_{side}','body'),(f'elbow_{side}',f'arm_{side}'),(f'hand_{side}',f'elbow_{side}')]:BONES.append((bone,parent,A[bone]))
 for bone,parent in [(f'foot_{side}','root')]:BONES.append((bone,parent,A[bone]))
 p=A[f'foot_{side}'];BONES.append((f'toe_{side}',f'foot_{side}',(p[0]-65,p[1]+30)))
BONES += [('eye_0','neck',A['eye_0']),('eye_1','neck',A['eye_1']),('tail','body',A['tail'])]
TALL=NAME.endswith('vanguard')
CAP_TIPS={'cap_l_tip':(65,237) if TALL else (99,480),'cap_r_tip':(786,461) if TALL else (813,608)}
for bone,pos in CAP_TIPS.items():BONES.append((bone,bone.removesuffix('_tip'),pos))
DIGITS={'finger_far_a':(253,690) if TALL else (190,733),'finger_far_b':(322,706) if TALL else (247,744),
 'finger_near_a':(670,697) if TALL else (680,733),'finger_near_b':(775,725) if TALL else (749,765)}
for bone,pos in DIGITS.items():BONES.append((bone,'hand_'+('far' if 'far' in bone else 'near'),pos))
socket_parent='foot_near' if TALL else 'foot_far';p=A[socket_parent]
BONES.append(('root_socket',socket_parent,(p[0]+(65 if TALL else -55),p[1]+25)))
SKIN={n:[('body',(0,0),(0,0))] for n in ORDER}

def weights(name,points):
 p=np.asarray(points)
 if name in ['eye_0','eye_1']:return [[(name,1.)] for _ in p]
 if name.startswith('arm_'):
  side=name[4:];start=np.array(A[name]);end=np.array(A[f'hand_{side}'])
  t=np.clip(((p-start)@(end-start))/np.dot(end-start,end-start),0,1)
  result=[]
  for point,v in zip(p,t):
   acc={name:float((1-v)**2),f'elbow_{side}':float(2*v*(1-v)),f'hand_{side}':float(v*v)}
   for suffix in ['a','b']:
    bone=f'finger_{side}_{suffix}';q=np.asarray(DIGITS[bone]);w=.55*np.exp(-np.sum(((point-q)/(45,83))**2)*1.6)*v*v
    acc={k:value*(1-w) for k,value in acc.items()};acc[bone]=float(w)
   result.append(list(acc.items()))
  return result
 if name.startswith('foot_'):
  side=name[5:];t=np.clip((A[name][0]-p[:,0])/100,0,.6)
  return [[(name,float(1-v)),(f'toe_{side}',float(v))] for v in t]
 if name=='cap':
  center=A['cap'][0];left=CAP_TIPS['cap_l_tip'][0];right=CAP_TIPS['cap_r_tip'][0]
  result=[]
  for x in p[:,0]:
   side='cap_l' if x<center else 'cap_r';v=float(np.clip(abs(x-center)/max(1,abs((left if x<center else right)-center)),0,1))
   result.append([('cap',(1-v)**2),(side,2*v*(1-v)),(side+'_tip',v*v)])
  return result
 fields=[('neck',A['neck'],(130,130),.98),('tail',A['tail'],(90,75),.85),
         ('arm_far',A['arm_far'],(45,60),.75),('arm_near',A['arm_near'],(45,60),.75),
         ('foot_far',A['foot_far'],(85,62),.94),('foot_near',A['foot_near'],(85,62),.94)]
 res=[]
 for point in p:
  acc={'body':1.}
  for bone,center,radius,s in fields:
   v=float(s*np.exp(-np.sum(((point-center)/radius)**2)*1.7));acc={k:w*(1-v) for k,w in acc.items()};acc[bone]=acc.get(bone,0)+v
  acc={k:w for k,w in acc.items() if w>.001};total=sum(acc.values());res.append([(k,w/total) for k,w in acc.items()])
 return res
