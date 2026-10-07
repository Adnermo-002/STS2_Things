import json, math, numpy as np
import anims as A
from fk import Skel
from rigdef import S
rig=json.load(open('out/rig_static.json'))
sk=Skel(rig)
chains=rig['chains']
GLOWS=['atrium_glow','bulb_glow']
FPS=30
def chain_setup_dir(c):
    b=np.array(S(c['base'])); t=np.array(S(c['tip'])); d=t-b; return d/np.linalg.norm(d), np.linalg.norm(d)
CX=S((679,420))[0]
def base_pose(name,t):
    """non-chain pose, glows, tint, collapse factor"""
    tint=(1,1,1); c=0.0
    if name=='idle_loop': P,g=A.idle_base(t)
    elif name in ('die','revive'): P,g,tint,c=getattr(A,name)(t)
    else: P,g=getattr(A,name)(t)
    return P,g,tint,c
def chain_targets(name,cn,i,t,c,P_extra):
    ch=chains[cn]; bx=ch['base'][0]
    th=A.weed_target_idle(cn,i,t,bx) * (0.55 if cn.startswith('coral') else 1.0)
    side=1.0 if bx<679 else -1.0          # + = lean outward/left for left-side weeds
    d,_=chain_setup_dir(ch)
    horiz=abs(d[0])>0.7                    # ground fronds
    if name=='die' or name=='revive':
        droop=(7 if cn.startswith('coral') else (5 if horiz else 16))*c
        th+= side*droop*(1 if i==0 else 0.6)
    if name in ('cast','power_up'):
        big=1.35 if name=='power_up' else 1.0
        hold=A.ease(A.seg(t,0,0.4))*(1-A.ease(A.seg(t,0.55,1.4)))
        th+= side*(6+3*i)*hold*big + side*9*A.kick(t,0.42+0.03*i,1.7,3.5)*big
    if name=='summon':
        th+= side*6*A.pulse(t-0.3-0.05*i,0.05,0.25)
    return th
def simulate(name,dur,loop,init=None):
    n=int(round(dur*FPS)); sub=8; dt=1/(FPS*sub)
    warm=2 if loop else 0
    frames=[]
    # precompute non-chain poses at substep resolution
    total=(warm+1)*n*sub if loop else n*sub
    state={}
    for cn,ch in chains.items():
        for i,b in enumerate(ch['bones']):
            state[b]=[0.0,0.0] if init is None else list(init[b])
    prevpos={}; prevvel={}
    out=[]
    for k in range(total+1):
        tt=(k*dt)%dur if loop else min(k*dt,dur)
        P,g,tint,c=base_pose(name,tt)
        W=sk.world(P)
        for cn,ch in chains.items():
            d,L=chain_setup_dir(ch)
            par=sk.bones[sk.idx[ch['bones'][0]]]['parent']
            M=W[par]
            base=M@np.array([*sk.local[ch['bones'][0]],1.0])
            # direction rotated by parent's world rotation
            dw=M[:2,:2]@d; dw/=np.linalg.norm(dw)
            key=cn
            if key in prevpos:
                v=(base[:2]-prevpos[key])/dt
                a=(v-prevvel.get(key,v))/dt
            else: v=np.zeros(2); a=np.zeros(2)
            prevpos[key]=base[:2]; prevvel[key]=v
            cross=dw[0]*a[1]-dw[1]*a[0]
            coral=cn.startswith('coral')
            w0=2*math.pi*(1.9 if coral else 1.3); z=0.32 if coral else 0.22
            for i,b in enumerate(ch['bones']):
                tgt=chain_targets(name,cn,i,tt,c,P)
                th,om=state[b]
                gain=(0.0007 if coral else 0.0014)*(1+0.6*i)
                acc=-w0*w0*(th-tgt)-2*z*w0*om - gain*cross*w0*w0/ (w0*w0) * 60
                om+=acc*dt; th+=om*dt
                th=max(-24,min(24,th))
                state[b]=[th,om]
        if k%sub==0 and (not loop or k>=warm*n*sub):
            fr={'t':round(tt if not loop else (k-warm*n*sub)*dt,5),'pose':dict(P),'glow':g,'tint':tint}
            for cn,ch in chains.items():
                for b in ch['bones']: fr['pose'][b]=(state[b][0],0,0,1,1)
            out.append(fr)
    final={b:tuple(state[b]) for b in state}
    return out[:n+1], final
def reduce_keys(times,vals,eps):
    """vals: list of tuples; keep keys so linear interp error < eps"""
    keep=[0]; i=0; N=len(times)
    while i<N-1:
        j=i+2
        while j<N:
            ok=True
            t0,t1=times[i],times[j]
            for m in range(i+1,j):
                u=(times[m]-t0)/(t1-t0)
                for q in range(len(vals[0])):
                    if abs(vals[i][q]+(vals[j][q]-vals[i][q])*u-vals[m][q])>eps[q]: ok=False;break
                if not ok: break
            if not ok: break
            j+=1
        i=j-1; keep.append(i)
    return keep
def hexcol(r,g,b,a): return ''.join(f'{int(round(max(0,min(1,v))*255)):02x}' for v in (r,g,b,a))
def build_anim(name,frames):
    times=[f['t'] for f in frames]
    bones={}
    for b in sk.idx:
        rot=[(f['pose'].get(b,(0,0,0,1,1))[0],) for f in frames]
        tr=[tuple(f['pose'].get(b,(0,0,0,1,1))[1:3]) for f in frames]
        sc=[tuple(f['pose'].get(b,(0,0,0,1,1))[3:5]) for f in frames]
        tl={}
        if any(abs(v[0])>1e-3 for v in rot):
            ks=reduce_keys(times,rot,(0.04,)); tl['rotate']=[{'time':round(times[k],4),'value':round(rot[k][0],3)} for k in ks]
        if any(abs(v[0])>1e-3 or abs(v[1])>1e-3 for v in tr):
            ks=reduce_keys(times,tr,(0.06,0.06)); tl['translate']=[{'time':round(times[k],4),'x':round(tr[k][0],2),'y':round(tr[k][1],2)} for k in ks]
        if any(abs(v[0]-1)>1e-4 or abs(v[1]-1)>1e-4 for v in sc):
            ks=reduce_keys(times,sc,(0.0006,0.0006)); tl['scale']=[{'time':round(times[k],4),'x':round(sc[k][0],4),'y':round(sc[k][1],4)} for k in ks]
        if tl:
            for arr in tl.values():
                if arr[0]['time']==0: del arr[0]['time']
            bones[b]=tl
    slots={}
    for gname in GLOWS:
        vals=[(0.72*f['glow'].get(gname,0.0),) for f in frames]
        ks=reduce_keys(times,vals,(0.01,))
        slots[gname]={'rgba':[{'time':round(times[k],4),'color':hexcol(1,1,1,vals[k][0])} for k in ks]}
    if any(f['tint']!=(1,1,1) for f in frames):
        vals=[tuple(f['tint']) for f in frames]
        ks=reduce_keys(times,vals,(0.004,0.004,0.004))
        for s in rig['slots']:
            if s['name'] in GLOWS: continue
            slots[s['name']]={'rgba':[{'time':round(times[k],4),'color':hexcol(*vals[k],1)} for k in ks]}
    for sl in slots.values():
        for arr in sl.values():
            if arr and arr[0].get('time')==0: del arr[0]['time']
    return {'bones':bones,'slots':slots}
def main():
    anim_json={}; allframes={}
    idle,idle_state=simulate('idle_loop',*A.ANIMS['idle_loop'])
    # state at idle t=0 (steady state) for one-shots
    init=None
    # re-run to fetch the state at loop start: last state of loop == state at t=dur==t=0
    init=idle_state
    allframes['idle_loop']=idle; anim_json['idle_loop']=build_anim('idle_loop',idle)
    for name,(dur,loop) in A.ANIMS.items():
        if name=='idle_loop': continue
        fr,_=simulate(name,dur,loop,init=init)
        allframes[name]=fr; anim_json[name]=build_anim(name,fr)
    bones=[]
    for b in rig['bones']:
        e={'name':b['name']}
        if b['parent']: e['parent']=b['parent']
        lx,ly=sk.local[b['name']]
        if abs(lx)>1e-6: e['x']=round(lx,2)
        if abs(ly)>1e-6: e['y']=round(ly,2)
        bones.append(e)
    xs=[];ys=[]
    skel={'skeleton':{'hash':'thelegacyrig2','spine':'4.2.0','x':-679.0,'y':-29.0,'width':1358,'height':689,'images':'./','audio':''},
          'bones':bones,'slots':rig['slots'],
          'skins':[{'name':'default','attachments':rig['attachments']}],
          'animations':anim_json}
    json.dump(skel,open('out/the_legacy.json','w'),separators=(',',':'))
    import pickle; pickle.dump(allframes,open('out/frames.pkl','wb'))
    print('ok', {k:len(v) for k,v in allframes.items()})
if __name__=='__main__': main()
