"use client";

// Animated phosphor field: a domain-warped fbm noise shader on a fullscreen
// quad, mapped from near-black to acid lime with a cool-blue undertone and a
// slow horizontal scan. Pure WebGL accent — sits behind content, reacts
// gently to the pointer. Lazy-loaded (no SSR) by <ShaderField>.

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const vertex = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position, 1.0);
  }
`;

const fragment = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform vec2 uRes;
  uniform vec2 uMouse;

  // hash + value noise + fbm
  float hash(vec2 p){ p = fract(p*vec2(123.34,456.21)); p += dot(p,p+45.32); return fract(p.x*p.y); }
  float noise(vec2 p){
    vec2 i=floor(p); vec2 f=fract(p);
    float a=hash(i), b=hash(i+vec2(1.,0.)), c=hash(i+vec2(0.,1.)), d=hash(i+vec2(1.,1.));
    vec2 u=f*f*(3.-2.*f);
    return mix(a,b,u.x)+(c-a)*u.y*(1.-u.x)+(d-b)*u.x*u.y;
  }
  float fbm(vec2 p){
    float v=0., a=0.5;
    for(int i=0;i<5;i++){ v+=a*noise(p); p*=2.03; a*=0.5; }
    return v;
  }

  void main(){
    vec2 uv = vUv;
    float aspect = uRes.x/uRes.y;
    vec2 p = uv; p.x *= aspect;

    // pointer-influenced flow
    vec2 m = uMouse; m.x *= aspect;
    float t = uTime*0.06;

    // domain warp
    vec2 q = vec2(fbm(p*2.0 + t), fbm(p*2.0 - t + 4.7));
    float n = fbm(p*2.4 + q*1.6 + vec2(t*1.3, -t));

    // distance falloff from pointer for a soft spotlight
    float d = length(p - m);
    float glow = smoothstep(1.1, 0.0, d) * 0.5;

    float intensity = pow(n, 1.7) + glow*n;

    vec3 bg   = vec3(0.039,0.043,0.039);
    vec3 deep = vec3(0.06,0.10,0.05);
    vec3 lime = vec3(0.714,1.0,0.235);
    vec3 blue = vec3(0.435,0.659,1.0);

    vec3 col = mix(bg, deep, smoothstep(0.2,0.6,intensity));
    col = mix(col, blue*0.5, smoothstep(0.45,0.75,intensity)*0.4);
    col = mix(col, lime, smoothstep(0.66,0.95,intensity));

    col += lime * 0.04 * sin(uv.y*900.0)*step(0.7,n);

    // vignette — creates the cloud shape across the full hero
    col *= smoothstep(1.3,0.2,length(uv-0.5));

    gl_FragColor = vec4(col, 1.0);
  }
`;

function FieldMesh() {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const { size, viewport } = useThree();
  const target = useRef(new THREE.Vector2(0.5, 0.5));

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uRes: { value: new THREE.Vector2(size.width, size.height) },
      uMouse: { value: new THREE.Vector2(0.5, 0.5) },
    }),
    [size.width, size.height],
  );

  useFrame((state, dt) => {
    if (!mat.current) return;
    mat.current.uniforms.uTime.value += dt;
    target.current.set((state.pointer.x + 1) / 2, (state.pointer.y + 1) / 2);
    const m = mat.current.uniforms.uMouse.value as THREE.Vector2;
    m.lerp(target.current, 0.04);
  });

  return (
    <mesh scale={[viewport.width, viewport.height, 1]}>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial
        ref={mat}
        vertexShader={vertex}
        fragmentShader={fragment}
        uniforms={uniforms}
      />
    </mesh>
  );
}

export function ShaderField() {
  return (
    <Canvas
      gl={{ antialias: false, alpha: false }}
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 1] }}
    >
      <FieldMesh />
    </Canvas>
  );
}
