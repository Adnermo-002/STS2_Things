"""Separate rag wings and a continuously skinned head/body/silk silhouette."""
import numpy as np
NAME = 'silk_moth'
ORIGIN = (700,1120)
VIEW = dict(scale=.44,W=850,H=640,ox=430,oy=610)
ORDER = ['wing_far','wing_near','silk_a','silk_b','silk_c','body']
SPACING = {'wing_far':20,'wing_near':20,'body':12,'silk_a':8,'silk_b':8,'silk_c':8}
CHAINS = {}
BONES = [
 ('root',None,ORIGIN),('thorax','root',(552,560)),
 ('wing_far','thorax',(553,488)),('wing_far_mid','wing_far',(390,299)),('wing_far_tip','wing_far_mid',(232,151)),
 ('wing_near','thorax',(602,522)),('wing_near_mid','wing_near',(897,409)),('wing_near_tip','wing_near_mid',(1170,320)),
 ('abdomen','thorax',(626,675)),('head','thorax',(466,505)),
 ('eye_far','head',(361,527)),('eye_near','head',(443,493)),
 ('antenna_far','head',(292,451)),('antenna_near','head',(365,400)),
 ('leg_far','thorax',(437,622)),('leg_near','thorax',(535,646)),
 ('silk_a','leg_far',(452,715)),('silk_a_tip','silk_a',(470,909)),
 ('silk_b','leg_near',(539,715)),('silk_b_tip','silk_b',(592,1006)),
 ('silk_c','leg_near',(557,715)),('silk_c_tip','silk_c',(673,951)),
]
SKIN = {name:[('thorax',(0,0),(0,0))] for name in ORDER}
FIELDS = [
 ('abdomen',(640,691),(87,99),.96),('head',(450,487),(142,98),.95),
 ('antenna_far',(222,477),(99,65),.95),('antenna_near',(356,395),(99,51),.97),
 ('eye_far',(363,526),(31,41),.8),('eye_near',(443,493),(41,53),.85),
 ('leg_far',(437,633),(40,58),.93),('leg_near',(535,645),(35,53),.93),
 ('silk_a',(451,715),(23,34),.97),
 ('silk_b',(539,715),(17,28),.97),('silk_c',(557,715),(17,28),.97),
]

def weights(name, points):
    points=np.asarray(points)
    if name.startswith('silk_'):
        end={'silk_a':920,'silk_b':1020,'silk_c':959}[name]
        u=np.clip((points[:,1]-715)/(end-715),0,1)
        return [[(name,float(1-t*t)),(name+'_tip',float(t*t))] for t in u]
    if name.startswith('wing_'):
        base=name; a=np.array((553,488) if name=='wing_far' else (602,522))
        end=np.array((232,151) if name=='wing_far' else (1170,320))
        u=np.clip(((points-a)@(end-a))/np.dot(end-a,end-a),0,1)
        # Smooth parent-child weights keep tips pliable while roots stay sealed.
        return [[(base,float((1-t)**2)),(base+'_mid',float(2*t*(1-t))),
                 (base+'_tip',float(t*t))] for t in u]
    fields=[]
    for bone,center,radius,strength in FIELDS:
        d=((points-np.asarray(center))/np.asarray(radius))**2
        fields.append((bone,strength*np.exp(-d.sum(axis=1)*1.5)))
    result=[]
    for i in range(len(points)):
        acc={'thorax':1.}
        for bone,values in fields:
            w=float(values[i]);acc={key:value*(1-w) for key,value in acc.items()}
            acc[bone]=acc.get(bone,0)+w
        acc={key:value for key,value in acc.items() if value>.002}
        total=sum(acc.values());result.append([(key,value/total) for key,value in acc.items()])
    return result
