// Authored boss motion over the repaired skin. Geometry and bind pose stay intact.
import fs from 'node:fs';
import {load, pose} from './runtime.mjs';

const input = process.argv[2] ?? 'out/origin_fogmog.spjson';
const output = process.argv[3] ?? 'out/origin_fogmog_boss.spjson';
const raw = JSON.parse(fs.readFileSync(input, 'utf8'));
const data = load(input, 'source/origin_fogmog.atlas');
const bind = pose(data, 'idle_loop', 0);
const base = Object.fromEntries(bind.bones.map(b => [b.data.name, {
  x:b.x, y:b.y, r:b.rotation, sx:b.scaleX, sy:b.scaleY, shx:b.shearX, shy:b.shearY,
}]));
const setup = Object.fromEntries(raw.bones.map(b => [b.name,b]));
const FPS = 120;
const clone = value => structuredClone(value);
const round = value => Math.round(value*1e6)/1e6;

// Shape-preserving, continuous velocity at intermediate keys. Intentional
// reversals/holds settle; passing poses do not insert an artificial pause.
function curve(keys) {
  const slopes = keys.map(()=>0);
  for(let i=1;i<keys.length-1;i++) {
    const h0=keys[i][0]-keys[i-1][0], h1=keys[i+1][0]-keys[i][0];
    const a=(keys[i][1]-keys[i-1][1])/h0, b=(keys[i+1][1]-keys[i][1])/h1;
    if(a*b>0) { const w0=2*h1+h0,w1=h1+2*h0; slopes[i]=(w0+w1)/(w0/a+w1/b); }
  }
  return t => {
    if(t<=keys[0][0]) return keys[0][1];
    for(let i=0;i<keys.length-1;i++) if(t<=keys[i+1][0]) {
      const h=keys[i+1][0]-keys[i][0],u=(t-keys[i][0])/h,u2=u*u,u3=u2*u;
      return (2*u3-3*u2+1)*keys[i][1]+(u3-2*u2+u)*h*slopes[i]
        +(-2*u3+3*u2)*keys[i+1][1]+(u3-u2)*h*slopes[i+1];
    }
    return keys.at(-1)[1];
  };
}
const wave=(t,length)=>Math.sin(t/length*Math.PI*2);
const pulse=(t,length)=>(1-Math.cos(t/length*Math.PI*2))/2;
function makeProfile(length, controls, events=[], blink=[]) {
  return {length,controls:Object.fromEntries(Object.entries(controls).map(([name,keys])=>[name,curve(keys)])),events,blink};
}
const profiles = {
  idle_loop: {length:6.4,loop:true,events:[{time:.02,name:'thrust_end'}],blink:[1.9,5.1],controls:{
    x:t=>4*wave(t,6.4), y:t=>-8*pulse(t,6.4), body:t=>3.2*wave(t,6.4),
    breath:t=>1.6*pulse(t,6.4), back:t=>7*(Math.sin(t/6.4*Math.PI*2-.15)-Math.sin(-.15)),
    front:t=>5*(Math.sin(t/6.4*Math.PI*2+.2)-Math.sin(.2)),
    cap:t=>1.7*(Math.sin(t/6.4*Math.PI*2-.22)-Math.sin(-.22)),
  }},
  attack:makeProfile(1.70,{
    x:[[0,0],[.28,9],[.64,-4],[.84,-2],[1.7,0]],
    y:[[0,0],[.27,-26],[.64,-30],[1.18,-30],[1.5,-8],[1.7,0]],
    body:[[0,0],[.30,-15],[.64,25],[.82,30],[1.18,-7],[1.7,0]],
    back:[[0,0],[.28,39],[.64,-43],[.83,-56],[1.22,13],[1.7,0]],
    backLower:[[0,0],[.28,-28],[.64,-24],[.83,13],[1.7,0]],
    front:[[0,0],[.33,24],[.66,-14],[1.08,13],[1.7,0]],
    cap:[[0,0],[.36,-5],[.70,10],[.97,-5],[1.34,2],[1.7,0]],
    curl:[[0,0],[.34,9],[.62,-17],[.82,-12],[1.7,0]],
    footB:[[0,0],[.25,0],[.50,-55],[1.22,-55],[1.53,0],[1.7,0]],
    liftB:[[0,0],[.25,0],[.37,25],[.50,0],[1.22,0],[1.37,22],[1.53,0],[1.7,0]],
    footF:[[0,0],[.50,0],[.71,-45],[.93,-45],[1.22,0],[1.7,0]],
    liftF:[[0,0],[.50,0],[.60,23],[.71,0],[.93,0],[1.07,22],[1.22,0],[1.7,0]],
  },[{time:.02,name:'thrust_end'},{time:.64,name:'attack_hit'}],[.57]),
  headbutt:makeProfile(1.85,{
    x:[[0,0],[.23,8],[.8,-3],[1.12,0],[1.85,0]],
    y:[[0,0],[.22,-30],[.8,-32],[1.4,-30],[1.7,-5],[1.85,0]],
    body:[[0,0],[.30,-17],[.8,30],[.94,33],[1.25,-8],[1.58,4],[1.85,0]],
    cap:[[0,0],[.43,-10],[.82,15],[1.06,-9],[1.35,4],[1.85,0]],
    back:[[0,0],[.32,26],[.8,42],[1.14,5],[1.85,0]],
    backLower:[[0,0],[.35,30],[.65,85],[1.10,85],[1.4,10],[1.85,0]],
    front:[[0,0],[.32,22],[.8,-28],[1.22,16],[1.85,0]],
    curl:[[0,0],[.52,-16],[.95,-20],[1.85,0]],
    footB:[[0,0],[.24,0],[.43,-45],[.62,-45],[.80,-115],[.98,-115],[1.18,-45],[1.43,-45],[1.68,0],[1.85,0]],
    liftB:[[0,0],[.24,0],[.33,22],[.43,0],[.62,0],[.71,25],[.80,0],[.98,0],[1.08,24],[1.18,0],[1.43,0],[1.55,22],[1.68,0],[1.85,0]],
    footF:[[0,0],[.43,0],[.62,-75],[1.18,-75],[1.43,0],[1.85,0]],
    liftF:[[0,0],[.43,0],[.52,25],[.62,0],[1.18,0],[1.30,24],[1.43,0],[1.85,0]],
  },[{time:.02,name:'thrust_end'},{time:.8,name:'attack_hit'}],[.72]),
  triple_attack:makeProfile(2.45,{
    x:[[0,0],[.2,5],[.48,-3],[.72,2],[.94,-3],[1.16,2],[1.4,-4],[1.7,0],[2.45,0]],
    y:[[0,0],[.22,-25],[.48,-30],[1.4,-30],[1.9,-26],[2.25,-7],[2.45,0]],
    body:[[0,0],[.2,-12],[.48,20],[.72,-10],[.94,23],[1.16,-12],[1.4,30],[1.7,8],[2.15,-3],[2.45,0]],
    back:[[0,0],[.2,30],[.48,-43],[.70,22],[.94,-35],[1.12,-60],[1.4,-23],[1.64,-5],[2.15,7],[2.45,0]],
    backLower:[[0,0],[.2,-20],[.48,-24],[.70,10],[.94,-80],[1.12,10],[1.4,-23],[1.7,10],[2.45,0]],
    front:[[0,0],[.25,20],[.5,-12],[.72,24],[.94,-16],[1.18,27],[1.43,-19],[1.75,10],[2.45,0]],
    frontLower:[[0,0],[.66,-10],[.94,-16],[1.15,-8],[1.48,-12],[2.45,0]],
    cap:[[0,0],[.29,-4],[.55,7],[.77,-5],[1.01,8],[1.22,-6],[1.48,11],[1.8,-4],[2.45,0]],
    curl:[[0,0],[.48,-17],[.72,6],[.94,-17],[1.16,6],[1.4,-21],[2.45,0]],
    footB:[[0,0],[.25,0],[.46,-45],[1.18,-45],[1.40,-95],[1.52,-95],[1.77,-40],[2.03,-40],[2.30,0],[2.45,0]],
    liftB:[[0,0],[.25,0],[.35,24],[.46,0],[1.18,0],[1.29,25],[1.40,0],[1.52,0],[1.65,23],[1.77,0],[2.03,0],[2.16,22],[2.30,0],[2.45,0]],
    footF:[[0,0],[.69,0],[.92,-75],[1.77,-75],[2.03,0],[2.45,0]],
    liftF:[[0,0],[.69,0],[.81,26],[.92,0],[1.77,0],[1.90,25],[2.03,0],[2.45,0]],
  },[{time:.02,name:'thrust_end'},...[.48,.94,1.4].map(time=>({time,name:'attack_hit'}))],[1.33]),
  summon:makeProfile(2.4,{
    y:[[0,0],[.48,-29],[.82,-4],[1.0,-5],[1.20,-12],[1.28,-32],[1.65,-8],[2.4,0]],
    rise:[[0,0],[.57,0],[.82,52],[.99,42],[1.20,0],[2.4,0]],
    liftF:[[0,0],[.57,0],[.82,73],[.99,58],[1.20,0],[2.4,0]],
    liftB:[[0,0],[.57,0],[.82,68],[.99,54],[1.20,0],[2.4,0]],
    body:[[0,0],[.5,-13],[.86,14],[1.22,18],[1.55,-5],[2.4,0]],
    breath:[[0,0],[.7,3.8],[.94,2.2],[1.3,.4],[2.4,0]],
    front:[[0,0],[.48,8],[.82,49],[1.16,38],[1.55,-8],[2.4,0]],
    frontLower:[[0,0],[.48,-8],[.82,-14],[1.16,-8],[1.55,8],[2.4,0]],
    back:[[0,0],[.48,21],[.82,-46],[1.16,-32],[1.55,10],[2.4,0]],
    cap:[[0,0],[.62,-8],[.9,13],[1.28,-8],[1.7,3],[2.4,0]],
    capSpread:[[0,0],[.7,.06],[.84,.09],[1.25,.03],[2.4,0]],
  },[{time:.02,name:'thrust_end'},{time:.82,name:'thrust_start'},{time:1.20,name:'ground_impact'},{time:1.48,name:'thrust_end'}],[.57]),
  power_up:makeProfile(2.1,{
    y:[[0,0],[.52,-23],[.73,-4],[1.1,-12],[1.6,-3],[2.1,0]],
    body:[[0,0],[.5,-12],[.74,10],[1.13,-5],[1.5,2],[2.1,0]],
    breath:[[0,0],[.62,3.5],[.78,2.5],[1.22,.4],[2.1,0]],
    front:[[0,0],[.46,6],[.71,38],[1.02,25],[1.5,-5],[2.1,0]],
    frontLower:[[0,0],[.46,10],[.71,-7],[1.02,-4],[1.5,4],[2.1,0]],
    back:[[0,0],[.46,12],[.71,-35],[1.02,-23],[1.5,6],[2.1,0]],
    cap:[[0,0],[.56,-7],[.8,10],[1.16,-5],[1.6,2],[2.1,0]],
    capSpread:[[0,0],[.62,.07],[.8,.06],[1.28,.01],[2.1,0]],
  },[{time:.02,name:'thrust_end'},{time:.68,name:'spores_start'},{time:1.32,name:'spores_end'}],[.51]),
  cast:makeProfile(1.55,{
    y:[[0,0],[.35,-20],[.55,-7],[.8,-12],[1.55,0]],
    body:[[0,0],[.35,-9],[.55,13],[.9,4],[1.55,0]],
    breath:[[0,0],[.42,2.7],[.7,.7],[1.55,0]],
    back:[[0,0],[.35,14],[.58,-33],[.82,-23],[1.55,0]],
    front:[[0,0],[.35,-9],[.58,31],[.82,20],[1.55,0]],
    cap:[[0,0],[.4,-5],[.62,8],[1.0,-3],[1.55,0]],
    capSpread:[[0,0],[.44,.05],[.65,.03],[1.55,0]],
  },[{time:.02,name:'thrust_end'},{time:.55,name:'thrust_start'},{time:.92,name:'thrust_end'}],[.44]),
  hurt:makeProfile(.85,{
    x:[[0,0],[.12,12],[.3,3],[.53,-2],[.85,0]],
    y:[[0,0],[.14,-14],[.36,-3],[.85,0]],
    body:[[0,0],[.13,-10.5],[.34,3],[.57,-1],[.85,0]],
    cap:[[0,0],[.2,-5],[.4,2.4],[.62,-.6],[.85,0]],
    back:[[0,0],[.18,12],[.43,-3],[.85,0]],
    front:[[0,0],[.18,-11],[.43,3],[.85,0]],
  },[{time:0,name:'thrust_end'}],[.07]),
};

function animationFor(p) {
  const result={bones:{},slots:{},events:p.events};
  const values=Object.fromEntries(raw.bones.map(b=>[b.name,[]]));
  const control=(name,t)=>p.controls[name]?.(p.loop?((t%p.length)+p.length)%p.length:Math.max(0,t))??0;
  const lag=t=>.7*(control('body',t-.09)-control('body',t));
  const lag0=lag(0);
  const n=Math.round(p.length*FPS);
  for(let i=0;i<=n;i++) {
    const t=i===n?p.length:i/FPS, b=clone(base);
    const u=Math.max(0,Math.min(1,(t-(p.length-.22))/.22));
    const settle=p.loop?1:1-u*u*u*(u*(6*u-15)+10);
    const breath=control('breath',t), back=control('back',t), front=control('front',t);
    // Each foot follows a separate lift/plant arc. Root travel transfers weight
    // between them; IK targets remain in the authored world-space positions.
    const footF=control('footF',t), footB=control('footB',t);
    const travel=(footF+footB)/2, rise=control('rise',t);
    b.root.x+=travel; b.root.y+=rise;
    b.leg_f_ik.x+=footF-travel; b.leg_b_ik.x+=footB-travel;
    b.leg_f_ik.y+=control('liftF',t)-rise;
    b.leg_b_ik.y+=control('liftB',t)-rise;
    b.shadow.y-=rise;
    b.shadow.sx*=1-rise*.002; b.shadow.sy*=1-rise*.002;
    b.cog.x+=control('x',t); b.cog.y+=control('y',t);
    b.bod.r+=control('body',t);
    b.bod.sx*=1+.01*breath; b.bod.sy*=1+.016*breath;
    b.chest_expand.sx*=1+.025*breath; b.chest_expand.sy*=1+.025*breath;
    b.head_wobble.r+=(lag(t)-lag0)*settle;
    b.head_pivot.r+=control('cap',t);
    // The cap's local Y axis spans its width. Its fleshy lobes inflate on
    // exhalation while the repaired neck/face weights remain untouched.
    b.head_pivot.sy*=1+control('capSpread',t);
    b.head_pivot.sx*=1+control('capSpread',t)*.35;
    b.arm_b_upper.r+=back;
    b.arm_b_lower.r+=control('backLower',t);
    b.shoulder_f.r+=front;
    b.arm_f_upper.r+=front<0?front*.32:-front*.18;
    b.arm_f_lower.r+=control('frontLower',t);
    for(const bone of raw.bones) {
      if(bone.name.endsWith('_skin')) b[bone.name].r+=control('curl',t);
      if(bone.name.startsWith('head_lump')) {
        const index='abczd'.indexOf(bone.name.at(-1));
        const delay=.035*(index+1);
        const wobble=control('cap',t-delay)-control('cap',-delay);
        b[bone.name].r+=wobble*.3*settle;
      }
    }
    // Existing VFX sockets were 600+ units outside the body. Put dust between
    // the feet and the spore cloud on the cap, in its parent's local frame.
    b.ground_dust.x=14; b.ground_dust.y=-rise;
    const parent=bind.findBone('head_pivot');
    const det=parent.a*parent.d-parent.b*parent.c, wx=-parent.worldX, wy=535-parent.worldY;
    b.head_thrust.x=(parent.d*wx-parent.b*wy)/det;
    b.head_thrust.y=(-parent.c*wx+parent.a*wy)/det;
    b.head_thrust.r=-Math.atan2(parent.c,parent.a)*180/Math.PI;
    for(const [name,v] of Object.entries(b)) values[name].push({t,...v});
  }
  for(const [name,frames] of Object.entries(values)) {
    const def=setup[name],channels={};
    for(const [channel,fields] of Object.entries({rotate:['r'],translate:['x','y'],scale:['sx','sy'],shear:['shx','shy']})) {
      let keys=frames.map(f=>{
        const key={time:round(f.t)};
        for(const field of fields) {
          const setupName={r:'rotation',sx:'scaleX',sy:'scaleY',shx:'shearX',shy:'shearY'}[field]??field;
          const isScale=channel==='scale', value=isScale?f[field]/(def[setupName]??1):f[field]-(def[setupName]??0);
          key[channel==='rotate'?'value':(field.endsWith('x')||field==='x'?'x':'y')]=round(value);
        }
        return key;
      });
      if(keys.every(k=>Object.keys(k).filter(f=>f!=='time').every(f=>k[f]===keys[0][f]))) keys=[keys[0],keys.at(-1)];
      channels[channel]=keys;
    }
    result.bones[name]=channels;
  }
  // Keep native leg IK and foot rotation constraints throughout the authored steps.
  result.ik=Object.fromEntries(raw.ik.map(c=>[c.name,[{mix:c.mix??1,bendPositive:c.bendPositive??true}]]));
  result.transform=Object.fromEntries(raw.transform.map(c=>[c.name,[{mixRotate:c.mixRotate??1,mixX:c.mixX??1,mixY:c.mixY??c.mixX??1,
    mixScaleX:c.mixScaleX??1,mixScaleY:c.mixScaleY??c.mixScaleX??1,mixShearY:c.mixShearY??1}]]));
  for(const slot of bind.slots) {
    const color=['r','g','b','a'].map(c=>Math.round(Math.max(0,Math.min(1,slot.color[c]))*255).toString(16).padStart(2,'0')).join('');
    result.slots[slot.data.name]={attachment:[{name:slot.attachment?.name??null}],rgba:[{color},{time:p.length,color}]};
  }
  result.slots['blink 1'].attachment=[{name:null}];
  for(const t of p.blink) result.slots['blink 1'].attachment.push({time:t,name:'blink 1 copy'},
    {time:t+.045,name:'blink 1 copy 3'},{time:t+.105,name:'blink 1 copy'},{time:t+.16,name:null});
  return result;
}
raw.events.attack_hit={};
raw.events.ground_impact={};
for(const [name,p] of Object.entries(profiles)) raw.animations[name]=animationFor(p);
raw.skeleton.hash='origin-fogmog-boss-motion-v2';
fs.writeFileSync(output,JSON.stringify(raw));
fs.writeFileSync('out/motion-contract.json',JSON.stringify(Object.fromEntries(Object.entries(profiles).map(([n,p])=>[n,{duration:p.length,events:p.events}])),null,2));
console.log(`FOGMOG_MOTION_BUILD_PASS ${Object.keys(profiles).length} authored motions; death/revive preserved`);
