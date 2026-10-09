"""Three visible wing planes, flexible feelers, heavy abdomen and two cocoons."""
import numpy as np
NAME='great_silk_moth'
ORIGIN=(710,1090)
VIEW=dict(scale=.45,W=850,H=650,ox=400,oy=615)
ORDER=['wing_far','wing_hind','wing_near','tail','silk_a','silk_b','bridge_silk','body']
SPACING={n:13 for n in ORDER}; SPACING.update(body=10,silk_a=7,silk_b=7,tail=7,bridge_silk=6)
# Baked inertia: heavier silk bundles lag behind the faster feeler tips.
CHAINS={
 'cocoon_far':dict(bones=['silk_a_mid','silk_a_tip'],freq=1.8,zeta=.78,clamp=5.0,gain=.0030,rgain=.018),
 'cocoon_near':dict(bones=['silk_b_mid','silk_b_tip'],freq=1.55,zeta=.80,clamp=5.5,gain=.0026,rgain=.020),
 'tail_silk':dict(bones=['tail_mid','tail_tip'],freq=2.25,zeta=.74,clamp=4.5,gain=.0018,rgain=.015),
 'feeler_far':dict(bones=['antenna_far_mid','antenna_far_tip'],freq=3.2,zeta=.88,clamp=1.5,gain=.00035,rgain=.012),
 'feeler_near':dict(bones=['antenna_near_mid','antenna_near_tip'],freq=2.85,zeta=.90,clamp=1.5,gain=.00030,rgain=.010),
}
BONES=[
 ('root',None,ORIGIN),('thorax','root',(584,572)),
 ('neck','thorax',(537,526)),('head','neck',(417,531)),
 ('eye_far','head',(330,548)),('eye_near','head',(433,528)),
 ('abdomen','thorax',(606,699)),('abdomen_mid','abdomen',(676,776)),('abdomen_tip','abdomen_mid',(756,850)),
 ('antenna_far','head',(336,487)),('antenna_far_mid','antenna_far',(257,403)),('antenna_far_tip','antenna_far_mid',(89,409)),
 ('antenna_near','head',(465,479)),('antenna_near_mid','antenna_near',(430,367)),('antenna_near_tip','antenna_near_mid',(345,345)),
 ('leg_far','thorax',(416,607)),('leg_far_mid','leg_far',(329,647)),('leg_far_tip','leg_far_mid',(350,684)),
 ('leg_near','thorax',(524,649)),('leg_near_mid','leg_near',(482,686)),('leg_near_tip','leg_near_mid',(480,730)),
 ('wing_far','thorax',(552,505)),('wing_far_mid','wing_far',(454,318)),('wing_far_tip','wing_far_mid',(277,100)),
 ('wing_near','thorax',(590,551)),('wing_near_mid','wing_near',(961,309)),('wing_near_tip','wing_near_mid',(1319,192)),
 ('wing_hind','thorax',(609,638)),('wing_hind_mid','wing_hind',(839,740)),('wing_hind_tip','wing_hind_mid',(1032,827)),
 ('silk_a','leg_far_tip',(350,684)),('silk_a_mid','silk_a',(363,832)),('silk_a_tip','silk_a_mid',(365,904)),
 ('silk_b','leg_near_tip',(480,730)),('silk_b_mid','silk_b',(495,861)),('silk_b_tip','silk_b_mid',(518,959)),
 ('tail','abdomen_tip',(748,853)),('tail_mid','tail',(858,932)),('tail_tip','tail_mid',(1000,1029)),
]
SKIN={n:[('thorax',(0,0),(0,0))] for n in ORDER}
FIELDS=[
 ('neck',(528,543),(100,95),.65),('head',(393,531),(137,101),.97),
 ('eye_far',(326,548),(30,42),.86),('eye_near',(431,528),(49,61),.91),
 ('abdomen',(615,693),(113,108),.85),('abdomen_mid',(688,781),(87,91),.94),('abdomen_tip',(754,851),(62,60),.97),
 ('antenna_far',(291,443),(110,53),.8),('antenna_far_mid',(195,412),(108,40),.92),('antenna_far_tip',(83,408),(59,36),.95),
 ('antenna_near',(457,445),(48,64),.88),('antenna_near_mid',(413,381),(66,57),.94),('antenna_near_tip',(356,352),(64,41),.93),
 ('leg_far',(365,625),(58,30),.92),('leg_far_mid',(330,650),(33,34),.92),('leg_far_tip',(350,687),(30,27),.98),
 ('leg_near',(514,658),(39,32),.90),('leg_near_mid',(484,690),(36,31),.93),('leg_near_tip',(480,733),(29,32),.98)]
def weights(name,points):
    points=np.asarray(points)
    if name!='body':
        if name=='bridge_silk':
            near=weights('silk_b',points)
            u=np.clip((points[:,1]-687)/(873-687),0,1)
            return [[('leg_far_tip',float(1-t))]+[(bone,float(t*w)) for bone,w in target]
                    for t,target in zip(u,near)]
        spans={'wing_far':((552,505),(277,100)), 'wing_near':((590,551),(1319,192)),
               'wing_hind':((609,638),(1032,827)), 'silk_a':((350,684),(365,904)),
               'silk_b':((480,730),(518,959)), 'tail':((748,853),(1000,1029))}
        a,b=map(np.asarray,spans[name]); u=np.clip(((points-a)@(b-a))/np.dot(b-a,b-a),0,1)
        return [[(name,float((1-t)**2)),(name+'_mid',float(2*t*(1-t))),(name+'_tip',float(t*t))] for t in u]
    fields=[(bone,strength*np.exp(-(((points-np.array(center))/np.array(radius))**2).sum(axis=1)*1.5)) for bone,center,radius,strength in FIELDS]
    result=[]
    for i in range(len(points)):
        x,y=points[i]
        acc={'thorax':1.}
        for bone,values in fields:
            w=float(values[i]);acc={k:v*(1-w) for k,v in acc.items()};acc[bone]=acc.get(bone,0)+w
        gate=float(np.clip((330-x)/60,0,1)*np.clip((y-340)/40,0,1)*np.clip((510-y)/20,0,1))
        if gate>0:
            a=np.array((336,487));b=np.array((89,409))
            u=float(np.clip(np.dot(points[i]-a,b-a)/np.dot(b-a,b-a),0,1))
            acc={k:v*(1-gate) for k,v in acc.items()}
            for bone,w in [('antenna_far',(1-u)**2),('antenna_far_mid',2*u*(1-u)),('antenna_far_tip',u*u)]:
                acc[bone]=acc.get(bone,0)+gate*w
        acc={k:v for k,v in acc.items() if v>.002}; total=sum(acc.values())
        result.append([(k,v/total) for k,v in acc.items()])
    return result
