"""A continuous 17-bone leech mesh with a flexible neck, rim, eyes and curled tail."""
import numpy as np
import cv2

NAME = 'sanguine_leech'
ORIGIN = (820, 909)
VIEW = dict(scale=.5, W=960, H=620, ox=470, oy=548)
ORDER = ['skin']
SPACING = {'skin': 14}
CHAINS = {}
FRONT = [(941,738),(801,626),(649,507),(495,399),(327,352)]
TAIL = [(1002,775),(1151,799),(1329,752),(1426,647)]
BONES = [('root',None,ORIGIN),('body','root',FRONT[0])]
for i, point in enumerate(FRONT[1:]):
    BONES.append((['neck_0','neck_1','neck_2','head'][i], 'body' if i == 0 else ['neck_0','neck_1','neck_2'][i-1], point))
BONES += [('mouth','head',(212,348)),('lip_upper','mouth',(177,222)),('lip_lower','mouth',(170,466)),
          ('eye_far','head',(407,198)),('eye_near','head',(498,284))]
for i, point in enumerate(TAIL):
    BONES.append((f'tail_{i}', 'body' if i == 0 else f'tail_{i-1}', point))
BONES += [('sucker','body',(1098,871)),('belly','body',(781,743))]
SKIN = {'skin': [('body',(0,0),(0,0))]}

def smooth(value):
    value = np.clip(value, 0, 1)
    return value*value*(3-2*value)

def curve_weights(points, pivots, names):
    distances, amounts = [], []
    for a,b in zip(pivots[:-1], pivots[1:]):
        a,b = np.array(a),np.array(b)
        direction = b-a
        t = np.clip((points-a)@direction/(direction@direction),0,1)
        distances.append(np.linalg.norm(points-a-t[:,None]*direction,axis=1))
        amounts.append(t)
    result = []
    for i,k in enumerate(np.array(distances).argmin(axis=0)):
        t = float(smooth(amounts[k][i]))
        result.append({names[k]:1-t,names[k+1]:t})
    return result

def field(poly, sigma=24):
    mask = np.zeros((1024,1536), np.float32)
    cv2.fillPoly(mask,[np.array(poly,np.int32)],1)
    return cv2.GaussianBlur(mask,(0,0),sigma)

FIELDS = {
 'head':field([(30,180),(310,100),(520,160),(621,312),(587,453),(458,584),(220,573),(37,419)],30),
 'mouth':field([(40,199),(252,135),(346,193),(368,393),(281,532),(104,528),(39,400)],20),
 'lip_upper':field([(107,205),(163,167),(253,179),(293,226),(230,251),(117,259)],18),
 'lip_lower':field([(95,401),(172,438),(271,399),(297,464),(231,517),(109,490)],20),
 'eye_far':field([(362,161),(425,145),(463,177),(456,225),(416,248),(365,226)],12),
 'eye_near':field([(449,248),(517,224),(552,262),(545,308),(503,335),(458,309)],12),
 'sucker':field([(861,854),(1120,824),(1282,846),(1250,915),(884,926)],35),
 'belly':field([(647,663),(818,674),(943,779),(897,877),(700,845),(577,762)],60)
}

def weights(name, points):
    points = np.asarray(points)
    x = np.clip(points[:,0].astype(int),0,1535)
    y = np.clip(points[:,1].astype(int),0,1023)
    front = curve_weights(points, FRONT, ['body','neck_0','neck_1','neck_2','head'])
    tail = curve_weights(points, TAIL, ['tail_0','tail_1','tail_2','tail_3'])
    blend = smooth((points[:,0]-925)/210)
    result=[]
    for i in range(len(points)):
        acc = {b:w*(1-blend[i]) for b,w in front[i].items()}
        for b,w in tail[i].items():
            acc[b] = acc.get(b,0)+w*blend[i]
        for region, mask in FIELDS.items():
            strength = float(mask[y[i],x[i]])
            if region == 'belly':
                strength *= .55
            acc = {b:w*(1-strength) for b,w in acc.items()}
            acc[region] = acc.get(region,0)+strength
        acc = {b:w for b,w in acc.items() if w>.002}
        total = sum(acc.values())
        result.append([(b,w/total) for b,w in acc.items()])
    return result
