"""Weighted matriarch: a heavy torso, sagging pouches, low hooded face and anchored rear pad."""
import numpy as np
import cv2
NAME='leech_mother'
ORIGIN=(1040,934)
VIEW=dict(scale=.48,W=1000,H=660,ox=575,oy=572)
ORDER=['skin','lid_far','lid_near']
GLOW_OF={'lid_far':'lid_far','lid_near':'lid_near'}
ALPHA_ONLY=['lid_far','lid_near']
GLOW_ALPHA=1.
SPACING={'skin':16,'lid_far':6,'lid_near':6}
CHAINS={}
FRONT=[(910,724),(692,542),(503,440),(345,443),(191,542)]
TAIL=[(1140,806),(1280,796),(1403,759),(1441,635),(1330,502)]
BONES=[('root',None,ORIGIN),('body','root',FRONT[0]),
       ('neck_0','body',FRONT[1]),('neck_1','neck_0',FRONT[2]),
       ('head','neck_1',FRONT[3]),('mouth','head',FRONT[4]),
       ('lip_upper','mouth',(183,446)),('lip_lower','mouth',(205,639)),
       ('eye_far','head',(247,425)),('eye_near','head',(332,466)),
       ('belly','body',(721,722)),('pouch_front','belly',(383,809)),
       ('pouch_mid','belly',(654,855)),('sucker','body',(1112,914))]
for i,point in enumerate(TAIL):BONES.append((f'tail_{i}','body' if i==0 else f'tail_{i-1}',point))
SKIN={name:[('body',(0,0),(0,0))] for name in ORDER}
def smooth(t):
    t=np.clip(t,0,1);return t*t*(3-2*t)
def field(poly,sigma):
    a=np.zeros((1024,1536),np.float32)
    cv2.fillPoly(a,[np.array(poly,np.int32)],1)
    return cv2.GaussianBlur(a,(0,0),sigma)
FRONT_FIELD=field([(22,480),(186,338),(422,284),(598,321),(686,527),(586,636),(348,725),(77,669)],42)
BELLY_FIELD=field([(333,634),(539,506),(752,516),(999,641),(1101,851),(962,934),(305,932),(239,793)],80)
FIELDS={
 'mouth':field([(54,449),(185,396),(312,436),(348,567),(261,680),(77,684),(43,560)],28),
 'lip_upper':field([(82,427),(172,401),(266,427),(300,482),(261,503),(135,465)],16),
 'lip_lower':field([(99,605),(178,617),(277,594),(294,640),(235,678),(96,662)],16),
 'eye_far':field([(205,387),(280,390),(289,443),(219,447)],15),
 'eye_near':field([(292,425),(359,427),(371,479),(302,489)],15),
 'pouch_front':field([(242,746),(365,707),(482,808),(431,907),(282,888)],36),
 'pouch_mid':field([(551,778),(646,730),(783,800),(780,911),(628,951),(539,911)],38),
 'sucker':field([(1007,876),(1190,875),(1268,917),(1107,951),(963,934)],38)}
def chain(points,pivots,names):
    distance=[];amount=[]
    for a,b in zip(pivots[:-1],pivots[1:]):
        a,b=np.array(a),np.array(b);d=b-a;t=np.clip((points-a)@d/(d@d),0,1)
        distance.append(np.linalg.norm(points-a-t[:,None]*d,axis=1));amount.append(t)
    influence=np.exp(-(np.array(distance)/75)**2)+1e-12
    influence/=influence.sum(axis=0)
    output=[]
    for i in range(len(points)):
        acc={}
        for k in range(len(distance)):
            w=float(influence[k,i]);t=float(smooth(amount[k][i]))
            acc[names[k]]=acc.get(names[k],0)+w*(1-t)
            acc[names[k+1]]=acc.get(names[k+1],0)+w*t
        output.append(acc)
    return output
def weights(name,points):
    points=np.asarray(points);x=np.clip(points[:,0].astype(int),0,1535);y=np.clip(points[:,1].astype(int),0,1023)
    front=chain(points,FRONT,['body','neck_0','neck_1','head','mouth'])
    tail=chain(points,TAIL,[f'tail_{i}' for i in range(5)])
    output=[]
    for i in range(len(points)):
        nf=float(FRONT_FIELD[y[i],x[i]]);nt=float(smooth((points[i,0]-1130)/200))
        acc={'body':1-nf}
        for b,w in front[i].items():acc[b]=acc.get(b,0)+nf*w
        acc={b:w*(1-nt) for b,w in acc.items()}
        for b,w in tail[i].items():acc[b]=acc.get(b,0)+nt*w
        nb=.42*float(BELLY_FIELD[y[i],x[i]])
        acc={b:w*(1-nb) for b,w in acc.items()};acc['belly']=acc.get('belly',0)+nb
        for b,mask in FIELDS.items():
            n=float(mask[y[i],x[i]])
            if b.startswith('pouch'):n*=.5
            acc={key:w*(1-n) for key,w in acc.items()};acc[b]=acc.get(b,0)+n
        acc={key:w for key,w in acc.items() if w>.002};total=sum(acc.values())
        output.append([(key,w/total) for key,w in acc.items()])
    return output
