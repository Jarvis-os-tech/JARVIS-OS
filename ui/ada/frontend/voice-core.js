// Particle ribbons, geodesic core and shaders adapted from the supplied voice_core.html.
// All rendering dependencies are local; conversation/audio remain owned by app.js.
import * as THREE from './vendor/three/build/three.module.js';
import {orbLayout} from './project-layout.js?v=9';
import { EffectComposer } from './vendor/three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from './vendor/three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from './vendor/three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from './vendor/three/examples/jsm/postprocessing/ShaderPass.js';
import { OutputPass } from './vendor/three/examples/jsm/postprocessing/OutputPass.js';

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
function mulberry(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const NOISE = /* glsl */`
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1./6.,1./3.); const vec4 D=vec4(0.,.5,1.,2.);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy; i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
  float n_=.142857142857; vec3 ns=n_*D.wyz-D.xzx; vec4 j=p-49.*floor(p*ns.z*ns.z);
  vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.*x_); vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw); vec4 s0=floor(b0)*2.+1.; vec4 s1=floor(b1)*2.+1.; vec4 sh=-step(h,vec4(0.));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3))); p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
  vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.); m=m*m;
  return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}`;


export function createVoiceCore(canvas) {
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, depth: false, stencil: false, powerPreference: 'high-performance', preserveDrawingBuffer: false });
renderer.setPixelRatio(1);
renderer.debug.onShaderError = () => { throw new Error("Voice core shader compilation failed"); };
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
camera.position.set(0, 0, 10);

const COL = new THREE.Color('#4fd9cf');
const HOT = new THREE.Color('#e9fffc');
const additive = { transparent: true, depthWrite: false, depthTest: false, blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor };

/* ---------- background: teal vignette + faint hex grid ---------- */
const bgMat = new THREE.ShaderMaterial({
  uniforms: { uRes: { value: new THREE.Vector2(1, 1) }, uCenter: { value: new THREE.Vector2() }, uR: { value: 300 }, uTime: { value: 0 }, uLevel: { value: 0 }, uOn: { value: 0 } },
  vertexShader: `void main(){ gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: `
    uniform vec2 uRes, uCenter; uniform float uR, uTime, uLevel, uOn;
    float hexDist(vec2 p){ p = abs(p); return max(dot(p, normalize(vec2(1.0, 1.7320508))), p.x); }
    vec4 hexCoords(vec2 uv){
      vec2 r = vec2(1.0, 1.7320508); vec2 h = r * 0.5;
      vec2 a = mod(uv, r) - h; vec2 b = mod(uv - h, r) - h;
      vec2 gv = dot(a, a) < dot(b, b) ? a : b; return vec4(gv, uv - gv);
    }
    void main(){
      vec2 fc = gl_FragCoord.xy;
      float d = length(fc - uCenter) / uR;
      vec3 deep = vec3(0.0009, 0.0035, 0.0040), mid = vec3(0.0016, 0.0095, 0.0105);
      vec3 col = mix(mid, deep, smoothstep(0.2, 2.6, d));
      col += vec3(0.001, 0.006, 0.006) * exp(-d * d * 0.9) * (1.0 + 1.5 * uLevel);
      vec4 hx = hexCoords(fc / (uR * 0.115));
      float edge = smoothstep(0.47, 0.5, hexDist(hx.xy));
      float scan = exp(-pow((fc.y / uRes.y) - (1.0 - fract(uTime * 0.06)), 2.0) * 90.0);
      float mask = smoothstep(0.9, 2.2, d) * (0.55 + 0.45 * sin(hx.z * 0.37 + hx.w * 0.23 + uTime * 0.2));
      col += vec3(0.010, 0.050, 0.050) * edge * mask * (0.35 + scan * 1.6) * uOn;
      gl_FragColor = vec4(col, 1.0);
    }`,
  depthWrite: false, depthTest: false,
});
const bg = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bgMat);
bg.frustumCulled = false; bg.renderOrder = -10; scene.add(bg);

/* ---------- groups: tilted ring plane + ambient particles ---------- */
const ringGroup = new THREE.Group(); scene.add(ringGroup);
const flatGroup = new THREE.Group(); scene.add(flatGroup);

/* ---------- the ring: point-cloud tube + twisting ribbons ---------- */
// [count, radiusOffset, width, twists, alpha] , [mode 1=tube 0=ribbon, axial squash, size, phase]
const RIBBONS = [
  [[64000, 0.000, 0.066, 0.0, 0.080], [1, 0.85, 0.85, 0.0]],
  [[42000, -0.050, 0.055, 3.0, 0.100], [0, 1.00, 0.80, 1.3]],
  [[34000, 0.042, 0.042, -2.0, 0.100], [0, 1.00, 0.80, 2.6]],
  [[16000, -0.118, 0.010, 1.0, 0.150], [0, 1.00, 0.70, 3.9]],
];
let ribbonGeometry;
const ringUniforms = {
  uTime: { value: 0 }, uLevel: { value: 0 }, uBoot: { value: 0 }, uFlash: { value: 0 }, uPx: { value: 1 },
  uSpec: { value: new Array(24).fill(0) }, uColor: { value: COL }, uHot: { value: HOT },
  uRibA: { value: RIBBONS.map(r => new THREE.Vector4(...r[0].slice(1))) },
  uRibB: { value: RIBBONS.map(r => new THREE.Vector4(...r[1])) },
};
{
  const total = RIBBONS.reduce((s, r) => s + r[0][0], 0);
  const data = new Float32Array(total * 4); const rnd = mulberry(7); let k = 0;
  for (let i = 0; i < total; i++) {
    const pick = (i * 0.61803398875 % 1) * total;
    let ri = 0, cumulative = RIBBONS[0][0][0];
    while (pick >= cumulative && ri < 3) cumulative += RIBBONS[++ri][0][0];
    const vv = rnd() * 2 - 1;
    data[k++] = rnd(); data[k++] = ri === 0 ? vv : Math.sign(vv) * Math.pow(Math.abs(vv), 0.33);
    data[k++] = rnd(); data[k++] = ri;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(total * 3), 3));
  g.setAttribute('aData', new THREE.BufferAttribute(data, 4));
  ribbonGeometry = g;
  const m = new THREE.ShaderMaterial({
    uniforms: ringUniforms, ...additive,
    vertexShader: NOISE + `
      uniform float uTime, uLevel, uBoot, uFlash, uPx; uniform float uSpec[24];
      uniform vec4 uRibA[4]; uniform vec4 uRibB[4];
      attribute vec4 aData; varying float vA; varying float vSpark;
      float specAt(float u){ float x = abs(fract(u * 2.0 + 0.25) * 2.0 - 1.0) * 23.0; int i = int(floor(x)); return mix(uSpec[i], uSpec[min(i + 1, 23)], fract(x)); }
      void main(){
        float u = aData.x, v = aData.y, seed = aData.z; int ri = int(aData.w + 0.5);
        vec4 A = uRibA[ri]; vec4 B = uRibB[ri];
        float th = u * 6.2831853, t = uTime, L = uLevel, Ld = pow(uLevel, 1.6);
        float lob = sin(3.0 * th + t * 0.55 + B.w) * 0.55 + sin(5.0 * th - t * 0.9 + B.w * 1.7) * 0.30 + sin(9.0 * th + t * 1.7 - B.w) * 0.15;
        float n = snoise(vec3(cos(th) * 1.15, sin(th) * 1.15, t * 0.17 + B.w));
        float sp = specAt(u);
        float R = 1.0 + A.x + 0.005 * sin(t * 1.3 + B.w) + (0.006 + 0.075 * Ld) * lob + (0.008 + 0.030 * Ld) * n + 0.060 * sp * Ld;
        float w = A.y * (1.0 + 0.30 * Ld + 0.25 * sp * Ld);
        vec2 cs;
        if (B.x > 0.5) { float phi = v * 3.14159265 + t * 0.2; cs = vec2(cos(phi), sin(phi) * B.y) * w; }
        else { float psi = A.z * th + t * 0.22 + n * (0.8 + 3.2 * Ld) + B.w; cs = vec2(cos(psi), sin(psi)) * v * w; }
        float rr = R + cs.x;
        vec3 p = vec3(cos(th) * rr, sin(th) * rr, cs.y);
        vec3 q = p * 2.3 + vec3(0.0, 0.0, t * 0.35 + B.w);
        float jn = snoise(q); float ja = 0.003 + 0.016 * Ld; p.xy += vec2(cos(th), sin(th)) * jn * ja; p.z += sin(jn * 5.0 + seed * 20.0) * ja * 0.6;
        float stray = smoothstep(0.975, 1.0, seed);
        p.xy *= 1.0 + stray * (0.05 + 0.25 * fract(seed * 977.0)) * (0.3 + L);
        float e = clamp((uBoot - seed * 0.45 - u * 0.2) / 0.85, 0.0, 1.0); e = e * e * (3.0 - 2.0 * e);
        float rad0 = 1.2 + seed * 1.2 + fract(seed * 13.7) * 0.5;
        vec3 start = vec3(cos(th + 1.2) * rad0, sin(th + 1.2) * rad0, (fract(seed * 53.1) - 0.5) * 2.4);
        vec3 pp = mix(start, p, e);
        float sw = (1.0 - e) * (3.2 + seed + t * 0.9); pp.xy = mat2(cos(sw), sin(sw), -sin(sw), cos(sw)) * pp.xy;
        pp.xy *= 1.0 + uFlash * 0.05;
        vec4 mv = modelViewMatrix * vec4(pp, 1.0);
        gl_Position = projectionMatrix * mv;
        float size = B.z * (0.7 + 0.6 * fract(seed * 91.7)) * (1.0 + 0.2 * L);
        gl_PointSize = max(1.0, size * mix(1.7, 1.0, e) * uPx * (10.0 / -mv.z));
        vA = A.w * mix(5.0 * smoothstep(0.0, 0.3, uBoot), 1.0, e) * (0.5 + 0.5 * fract(seed * 37.3)) * (0.85 + 0.5 * L + 0.6 * uFlash) * (1.0 - 0.5 * stray);
        vSpark = step(0.996, fract(seed * 713.1 + floor(t * 9.0) * 0.371)) * (0.25 + L);
      }`,
    fragmentShader: `
      uniform vec3 uColor, uHot; varying float vA; varying float vSpark;
      void main(){
        float d = length(gl_PointCoord - 0.5);
        float a = smoothstep(0.5, 0.05, d);
        vec3 c = mix(uColor, uHot, clamp(vSpark * 2.0, 0.0, 1.0));
        gl_FragColor = vec4(c * a * (vA + vSpark * 1.5), 1.0);
      }`,
  });
  const pts = new THREE.Points(g, m); pts.frustumCulled = false; pts.renderOrder = 3; ringGroup.add(pts);
}

/* ---------- inner HUD: rings, teeth, dashes, spectrum fringe (one shader) ---------- */
const hudUniforms = { uTime: { value: 0 }, uLevel: { value: 0 }, uReveal: { value: 0 }, uFlash: { value: 0 }, uSpec: { value: new Array(24).fill(0) }, uColor: { value: COL } };
{
  const m = new THREE.ShaderMaterial({
    uniforms: hudUniforms, ...additive,
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      uniform float uTime, uLevel, uReveal, uFlash; uniform float uSpec[24]; uniform vec3 uColor; varying vec2 vUv;
      float specAt(float u){ float x = abs(fract(u * 2.0 + 0.25) * 2.0 - 1.0) * 23.0; int i = int(floor(x)); return mix(uSpec[i], uSpec[min(i + 1, 23)], fract(x)); }
      float line(float r, float r0, float px, float fw){ return 1.0 - smoothstep(px * 0.5 * fw, px * 0.5 * fw + fw, abs(r - r0)); }
      float band(float r, float a, float b, float fw){ return smoothstep(a - fw, a, r) * (1.0 - smoothstep(b, b + fw, r)); }
      float dash(float a01, float n, float duty, float phase, float aw){ float f = fract(a01 * n + phase); float w = aw * n; return smoothstep(-w, w, duty - f) * smoothstep(-w, w, f); }
      void main(){
        vec2 p = (vUv - 0.5) * 2.0;
        float r = length(p); float a01 = atan(p.y, p.x) / 6.2831853 + 0.5;
        float fw = fwidth(r); float aw = fw / (6.2831853 * max(r, 1e-3));
        float t = uTime, L = uLevel;
        float rev = uReveal * 1.15;
        float c = 0.0;
        c += exp(-pow(r / 0.25, 2.0)) * (0.015 + 0.05 * L + 0.25 * uFlash) * smoothstep(0.0, 0.3, uReveal);
        c += line(r, 0.300, 1.3, fw) * 0.30 * smoothstep(a01, a01 + 0.02, rev);
        c += line(r, 0.380, 1.0, fw) * 0.13 * dash(a01, 6.0, 0.86, t * 0.02, aw) * smoothstep(a01, a01 + 0.02, rev - 0.05);
        c += line(r, 0.470, 1.0, fw) * 0.07 * smoothstep(a01, a01 + 0.02, rev - 0.1);
        c += band(r, 0.472, 0.486, fw) * 0.06 * dash(a01, 120.0, 0.35, -t * 0.006, aw) * smoothstep(a01, a01 + 0.02, rev - 0.1);
        c += band(r, 0.575, 0.582, fw) * 0.15 * dash(a01, 3.0, 0.80, t * 0.03, aw) * smoothstep(a01, a01 + 0.02, rev - 0.15);
        c += band(r, 0.566, 0.592, fw) * 0.18 * dash(a01, 3.0, 0.015, t * 0.03 + 0.79, aw) * smoothstep(a01, a01 + 0.02, rev - 0.15);
        c += line(r, 0.700, 1.6, fw) * 0.09 * dash(a01, 180.0, 0.3, -t * 0.012, aw) * smoothstep(a01, a01 + 0.02, rev - 0.2);
        float sp = specAt(a01);
        float len = 0.004 + 0.05 * sp * (0.25 + L);
        c += band(r, 0.795, 0.795 + len, fw) * dash(a01, 160.0, 0.28, 0.0, aw) * (0.04 + 0.14 * L) * smoothstep(a01, a01 + 0.02, rev - 0.25);
        gl_FragColor = vec4(uColor * c, 1.0);
      }`,
  });
  const disc = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), m); disc.renderOrder = 1; ringGroup.add(disc);
}

/* ---------- geodesic core: wire edges + vertex nodes ---------- */
const coreGroup = new THREE.Group(); ringGroup.add(coreGroup);
const coreUniforms = { uReveal: { value: 0 }, uLevel: { value: 0 }, uFlash: { value: 0 }, uTime: { value: 0 }, uColor: { value: COL }, uHot: { value: HOT }, uPx: { value: 1 } };
{
  const ico = new THREE.IcosahedronGeometry(1, 4); const P = ico.attributes.position;
  const key = new Map(), verts = [], idx = [];
  for (let i = 0; i < P.count; i++) { const x = P.getX(i), y = P.getY(i), z = P.getZ(i); const k = `${x.toFixed(4)},${y.toFixed(4)},${z.toFixed(4)}`; let id = key.get(k); if (id === undefined) { id = verts.length / 3; key.set(k, id); verts.push(x, y, z); } idx.push(id); }
  const seen = new Set(), E = [];
  for (let i = 0; i < idx.length; i += 3) for (const [a, b] of [[idx[i], idx[i + 1]], [idx[i + 1], idx[i + 2]], [idx[i + 2], idx[i]]]) { const k = a < b ? a + '_' + b : b + '_' + a; if (!seen.has(k)) { seen.add(k); E.push(a, b); } }
  const dir = new THREE.Vector3(0.3, 1, 0.2).normalize(); const rnd = mulberry(11);
  const ord = (i) => Math.acos(clamp(verts[i * 3] * dir.x + verts[i * 3 + 1] * dir.y + verts[i * 3 + 2] * dir.z, -1, 1)) / Math.PI;
  const lp = new Float32Array(E.length * 3), lo = new Float32Array(E.length);
  E.forEach((v, j) => { lp.set(verts.slice(v * 3, v * 3 + 3), j * 3); lo[j] = ord(v); });
  const lg = new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.BufferAttribute(lp, 3)); lg.setAttribute('aOrd', new THREE.BufferAttribute(lo, 1));
  const lm = new THREE.ShaderMaterial({
    uniforms: coreUniforms, ...additive,
    vertexShader: `uniform float uReveal; attribute float aOrd; varying float vA;
      void main(){ vec3 n = normalize(normalMatrix * position); vA = mix(0.10, 0.55, smoothstep(-0.6, 0.8, n.z)) * smoothstep(aOrd, aOrd + 0.12, uReveal * 1.15);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform vec3 uColor; uniform float uLevel, uFlash; varying float vA;
      void main(){ gl_FragColor = vec4(uColor * vA * (0.5 + 0.5 * uLevel + 0.8 * uFlash), 1.0); }`,
  });
  const lines = new THREE.LineSegments(lg, lm); lines.renderOrder = 2; lines.frustumCulled = false; coreGroup.add(lines);
  const nv = verts.length / 3, va = new Float32Array(nv * 2);
  for (let i = 0; i < nv; i++) { va[i * 2] = ord(i); va[i * 2 + 1] = rnd(); }
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(verts), 3)); pg.setAttribute('aV', new THREE.BufferAttribute(va, 2));
  const pm = new THREE.ShaderMaterial({
    uniforms: coreUniforms, ...additive,
    vertexShader: `uniform float uReveal, uTime, uLevel, uPx; attribute vec2 aV; varying float vA; varying float vS;
      void main(){ vec3 n = normalize(normalMatrix * position); vec4 mv = modelViewMatrix * vec4(position, 1.0);
        float tw = step(0.93, fract(aV.y * 61.0 + floor(uTime * 6.0) * 0.27)) * uLevel;
        vA = mix(0.12, 0.9, smoothstep(-0.6, 0.8, n.z)) * smoothstep(aV.x, aV.x + 0.12, uReveal * 1.15); vS = tw;
        gl_PointSize = (2.2 + 2.5 * tw) * uPx; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform vec3 uColor, uHot; uniform float uFlash; varying float vA; varying float vS;
      void main(){ float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d);
        gl_FragColor = vec4(mix(uColor, uHot, vS) * a * vA * (0.7 + 0.8 * uFlash + 1.2 * vS), 1.0); }`,
  });
  const nodes = new THREE.Points(pg, pm); nodes.renderOrder = 2; nodes.frustumCulled = false; coreGroup.add(nodes);
  coreGroup.scale.setScalar(0.285);
  ico.dispose();
}

/* ---------- shockwaves (expanding light rings) ---------- */
const SHOCKS = 5;
const shockUniforms = { uShock: { value: Array.from({ length: SHOCKS }, () => new THREE.Vector3(0, 0, 0)) }, uColor: { value: COL } };
const shockMesh = new THREE.Mesh(new THREE.PlaneGeometry(7.0, 7.0), new THREE.ShaderMaterial({
  uniforms: shockUniforms, ...additive,
  vertexShader: `varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform vec3 uShock[${SHOCKS}]; uniform vec3 uColor; varying vec2 vP;
    void main(){ float r = length(vP); float c = 0.0;
      for (int i = 0; i < ${SHOCKS}; i++){ vec3 s = uShock[i]; if (s.y > 0.001){ float d = (r - s.x) / s.z; c += exp(-d * d) * s.y; } }
      gl_FragColor = vec4(uColor * c * smoothstep(3.4, 2.6, r), 1.0); }`,
}));
shockMesh.renderOrder = 4; ringGroup.add(shockMesh);
const shocks = Array.from({ length: SHOCKS }, () => ({ t0: -99, amp: 0, speed: 1, width: 0.02 }));
let shockNext = 0;
function spawnShock(t, amp, speed, width) { const s = shocks[shockNext++ % SHOCKS]; s.t0 = t; s.amp = amp; s.speed = speed; s.width = width; }

/* ---------- drifting dust for depth ---------- */
const dustUniforms = { uTime: { value: 0 }, uPx: { value: 1 }, uColor: { value: COL }, uOn: { value: 0 } };
{
  const n = 1400, rnd = mulberry(21), pos = new Float32Array(n * 3), sd = new Float32Array(n);
  for (let i = 0; i < n; i++) { pos[i * 3] = (rnd() - 0.5) * 7; pos[i * 3 + 1] = (rnd() - 0.5) * 12; pos[i * 3 + 2] = -1.5 - rnd() * 6; sd[i] = rnd(); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('aS', new THREE.BufferAttribute(sd, 1));
  const m = new THREE.ShaderMaterial({ uniforms: dustUniforms, ...additive,
    vertexShader: `uniform float uTime, uPx; attribute float aS; varying float vA;
      void main(){ vec3 p = position; p.y = mod(p.y + uTime * (0.03 + 0.06 * aS) + 6.0, 12.0) - 6.0; p.x += sin(uTime * 0.2 + aS * 40.0) * 0.08;
        vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
        gl_PointSize = (0.8 + 1.6 * aS) * uPx * (10.0 / -mv.z); vA = 0.05 + 0.10 * fract(aS * 17.0); }`,
    fragmentShader: `uniform vec3 uColor; uniform float uOn; varying float vA; void main(){ float d = length(gl_PointCoord - 0.5); gl_FragColor = vec4(uColor * smoothstep(0.5, 0.0, d) * vA * uOn, 1.0); }`,
  });
  const dust = new THREE.Points(g, m); dust.frustumCulled = false; dust.renderOrder = 0; flatGroup.add(dust);
}

/* ---------- post: bloom, chromatic fringe, grain, vignette ---------- */
const composer = new EffectComposer(renderer);
// Every visual layer uses additive blending with depth testing disabled.
// Depth attachments would only consume bandwidth on these flat effect buffers.
composer.renderTarget1.depthBuffer = composer.renderTarget2.depthBuffer = false;
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), 0.5, 0.45, 0.10);
for (const target of [bloom.renderTargetBright, ...bloom.renderTargetsHorizontal, ...bloom.renderTargetsVertical]) target.depthBuffer = false;
// Bloom is intentionally soft. Its blur buffers do not need the sharp scene's
// full resolution; this quarters their pixel work while keeping text untouched.
const resizeBloom = bloom.setSize.bind(bloom);
bloom.setSize = (width, height) => resizeBloom(Math.max(1, Math.round(width * .5)), Math.max(1, Math.round(height * .5)));
composer.addPass(bloom);
const finalPass = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uFade: { value: 1 }, uCenter: { value: new THREE.Vector2(0.5, 0.5) }, uAspect: { value: 1 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uTime, uFade, uAspect; uniform vec2 uCenter; varying vec2 vUv;
    float hash(vec2 p){ p = fract(p * vec2(443.897, 441.423)); p += dot(p, p.yx + 19.19); return fract((p.x + p.y) * p.x); }
    void main(){
      vec2 d = vUv - uCenter; float k = 0.010 * dot(d * vec2(uAspect, 1.0), d * vec2(uAspect, 1.0));
      vec3 c = vec3(texture2D(tDiffuse, vUv - d * k).r, texture2D(tDiffuse, vUv).g, texture2D(tDiffuse, vUv + d * k).b);
      vec2 v = (vUv - 0.5) * vec2(uAspect, 1.0);
      c *= mix(0.45, 1.0, smoothstep(0.95, 0.15, length(v)));
      c += (hash(vUv * 1000.0 + fract(uTime * 13.37) * 100.0) - 0.5) * 0.0015;
      gl_FragColor = vec4(max(c, 0.0) * uFade, 1.0);
    }`,
});
composer.addPass(finalPass);
composer.addPass(new OutputPass());


// Keep the reference's proportions while centering it in the entire viewport.
let scale = 1, lastShock = -10, slowLevel = 0, disposed = false;
let bufferSize = '';
const targetColor = new THREE.Color();
function resize(width, height, pixelRatio, detail) {
  const workspace = document.body.classList.contains('has-workspace');
  const quality = clamp(detail * (workspace ? .40 : .55), 0.18, 1);
  const nextSize = [width, height, pixelRatio].join(':');
  if (nextSize !== bufferSize) {
    bufferSize = nextSize;
    if (renderer.getPixelRatio() !== pixelRatio) renderer.setPixelRatio(pixelRatio);
    renderer.setSize(width, height, false);
    // The composer works in drawing-buffer pixels, avoiding a second buffer
    // allocation when both CSS size and pixel ratio change together.
    composer.setSize(canvas.width, canvas.height);
  }
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  const {x, y, radius} = orbLayout(width, height);
  const unitsPerPixel = 2 * 10 * Math.tan(THREE.MathUtils.degToRad(16)) / height;
  flatGroup.position.set((x - width / 2) * unitsPerPixel, (height / 2 - y) * unitsPerPixel, 0);
  ringGroup.position.copy(flatGroup.position);
  scale = radius * 2 * 10 * Math.tan(THREE.MathUtils.degToRad(16)) / height;
  flatGroup.scale.setScalar(scale);
  const px = pixelRatio * radius / 232;
  ringUniforms.uPx.value = px;
  coreUniforms.uPx.value = px;
  dustUniforms.uPx.value = px;
  ribbonGeometry.setDrawRange(0, Math.floor(ribbonGeometry.attributes.position.count * quality));
  // Compensate for fewer samples without changing the shape of the ribbons.
  RIBBONS.forEach((r, i) => { ringUniforms.uRibA.value[i].w = r[0][4] / quality; });
  bgMat.uniforms.uRes.value.set(canvas.width, canvas.height);
  bgMat.uniforms.uCenter.value.set(x * pixelRatio, (height - y) * pixelRatio);
  bgMat.uniforms.uR.value = radius * pixelRatio;
  finalPass.uniforms.uAspect.value = width / height;
}

function render({time, age, dt, energy, listening, spectrum, color, brightness, reduced}) {
  if (disposed) return;
  const t = reduced ? 5 : time, bootAge = reduced ? 5 : age;
  const L = reduced ? 0 : clamp(energy + listening * 0.18);
  slowLevel += (L - slowLevel) * (1 - Math.exp(-dt / 0.8));
  if (!reduced && L - slowLevel > 0.16 && t - lastShock > 0.65 && bootAge > 2.5) {
    spawnShock(t, 0.045 + 0.075 * L, 0.85, 0.008); lastShock = t;
  }
  const flash = reduced || bootAge < 1.8 ? 0 : Math.exp(-(bootAge - 1.8) * 4) * 0.35;
  targetColor.set(color);
  if (reduced) COL.copy(targetColor);
  else COL.lerp(targetColor, 1 - Math.exp(-dt / 0.28));
  if (Math.abs(COL.r-targetColor.r)+Math.abs(COL.g-targetColor.g)+Math.abs(COL.b-targetColor.b) < 0.0001) COL.copy(targetColor);
  ringUniforms.uTime.value = t;
  ringUniforms.uLevel.value = L;
  ringUniforms.uBoot.value = clamp(bootAge * 1.15, 0, 1.8);
  ringUniforms.uFlash.value = flash;
  for (let k = 0; k < 24; k++) {
    const value = reduced ? 0 : spectrum[k];
    ringUniforms.uSpec.value[k] = value;
    hudUniforms.uSpec.value[k] = value;
  }
  hudUniforms.uTime.value = t;
  hudUniforms.uLevel.value = L;
  hudUniforms.uReveal.value = smooth(0.35, 1.8, bootAge);
  hudUniforms.uFlash.value = flash;
  coreUniforms.uReveal.value = smooth(0.5, 1.85, bootAge);
  coreUniforms.uLevel.value = L;
  coreUniforms.uFlash.value = flash;
  coreUniforms.uTime.value = t;
  dustUniforms.uTime.value = t;
  dustUniforms.uOn.value = smooth(0.1, 1.2, bootAge);
  bgMat.uniforms.uTime.value = t;
  bgMat.uniforms.uLevel.value = L;
  bgMat.uniforms.uOn.value = smooth(0.1, 1.2, bootAge);
  shocks.forEach((s, i) => {
    const age = t - s.t0, value = shockUniforms.uShock.value[i];
    if (reduced || age < 0 || age > 2.5) { value.set(0, 0, 1); return; }
    value.set(0.3 + age * s.speed, s.amp * Math.exp(-age * 1.8), s.width + age * 0.01);
  });
  shockMesh.visible = !reduced && shocks.some(s => t - s.t0 >= 0 && t - s.t0 < 2.5);
  ringGroup.rotation.set(-0.26 + 0.045 * Math.sin(t * 0.21), 0.07 * Math.sin(t * 0.17), t * 0.035);
  ringGroup.scale.setScalar(scale * (1 + 0.009 * Math.sin(t * 0.85) + L * 0.012));
  coreGroup.rotation.set(t * 0.11, t * 0.17 + L * 0.18, 0);
  coreGroup.scale.setScalar(0.285 * (1 + 0.07 * L + 0.10 * flash));
  finalPass.uniforms.uTime.value = t;
  finalPass.uniforms.uFade.value = smooth(0, 0.35, bootAge) * brightness;
  bloom.strength = 0.45 + 0.35 * L + 0.35 * flash;
  composer.render(dt);
}

function dispose() {
  if (disposed) return;
  disposed = true;
  scene.traverse(object => {
    object.geometry?.dispose();
    if (Array.isArray(object.material)) object.material.forEach(material => material.dispose());
    else object.material?.dispose();
  });
  composer.passes.forEach(pass => pass.dispose?.());
  composer.dispose();
  renderer.dispose();
}
return {resize, render, dispose};
}
