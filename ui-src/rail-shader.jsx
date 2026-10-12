// The living gradient behind the left rail (docs/specs/UI_UX.md, "The living rail"). Built into app/static/vendor/rail-shader.js by
// `npm run build:rail`, loaded by app.js only on a tablet-width screen or wider with motion allowed, and never from the network:
// lightType "3d" needs no HDR file (the library's "env" lights would fetch them from a third-party host).
//
// The library's own canvas renders at the display's refresh rate, and on a laptop the browser shares the GPU with the models this
// page is waiting on: measured on a real GPU, a fast check took 2.6 s with the shader running against 1.1 s without it. So the canvas is
// built here instead (same settings as ShaderGradientCanvas: dpr, fov, linear, flat) with the render loop on demand and throttled to
// about 20 frames a second, 5 while a check is in flight, and antialiasing off. A slow drift needs no more.
import { Component, useEffect } from "react";
import { createRoot } from "react-dom/client";
import * as THREE from "three";
import { Canvas, useThree } from "@react-three/fiber";
import { ShaderGradient } from "@shadergradient/react";

// The cobalt of the brand (DESIGN.md "Proofreader's Cobalt"). Measured in the real page at four moments of the animation, light and dark,
// three widths: the rail's text keeps AA against the lightest point only with the legibility scrim in styles.css (.rail-shader::after),
// because the waves brighten well past the tuned mean at times.
const PALETTE = {
  light: { color1: "#1f40b4", color2: "#0f2373", color3: "#3359c9", brightness: 1.5 },
  dark: { color1: "#1a3399", color2: "#081650", color3: "#2c4fb8", brightness: 1.5 },
};
const FPS = { calm: 20, busy: 5 };

// What ShaderGradientCanvas does once, so a current three.js still compiles the library's shaders.
THREE.ShaderChunk.uv2_pars_vertex = "";
THREE.ShaderChunk.uv2_vertex = "";
THREE.ShaderChunk.uv2_pars_fragment = "";
THREE.ShaderChunk.encodings_fragment = "";

class Guard extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { if (this.props.onFail) this.props.onFail(); }
  render() { return this.state.failed ? null : this.props.children; }
}

// Asks the on-demand loop for a frame at the current rate; the rate is read each tick so a change applies at once.
function Pulse({ rate }) {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    let timer = 0;
    const tick = () => { invalidate(); timer = setTimeout(tick, 1000 / rate.current); };
    tick();
    return () => clearTimeout(timer);
  }, [invalidate, rate]);
  return null;
}

function Rail({ dark, rate, onFail }) {
  const p = PALETTE[dark ? "dark" : "light"];
  return (
    <Guard onFail={onFail}>
      <div style={{ width: "100%", height: "100%" }}>
        <Canvas id="gradientCanvas" frameloop="demand" dpr={0.7} camera={{ fov: 45 }} linear flat resize={{ offsetSize: true }}
                style={{ pointerEvents: "none" }} gl={{ antialias: false, powerPreference: "low-power" }}>
          <Pulse rate={rate} />
          <ShaderGradient control="props" type="plane" animate="on" uSpeed={0.14} uStrength={1.4} uDensity={1.2}
            color1={p.color1} color2={p.color2} color3={p.color3} lightType="3d" brightness={p.brightness} grain="off" reflection={0.05}
            cAzimuthAngle={180} cPolarAngle={90} cDistance={3.6} cameraZoom={1} />
        </Canvas>
      </div>
    </Guard>
  );
}

export function mount(el, { dark = false, onFail } = {}) {
  const root = createRoot(el);
  const rate = { current: FPS.calm };
  const draw = (isDark) => root.render(<Rail dark={isDark} rate={rate} onFail={onFail} />);
  draw(dark);
  return {
    setDark: draw,
    setBusy: (busy) => { rate.current = busy ? FPS.busy : FPS.calm; },
    destroy: () => root.unmount(),
  };
}
