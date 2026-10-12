---
name: shader-gradient-r3f
description: Use when a TruthLens UI task wants an animated WebGL gradient background (ShaderGradient) or a custom 3D/WebGL scene (react-three-fiber). Wraps the two installed npm libraries with their verified API, the traps found in them, and the rules of this project (vanilla, offline, calm, reduced motion). Read before adding any WebGL to the UI; for ordinary CSS or SVG motion use animate instead.
---

# ShaderGradient and react-three-fiber in TruthLens

Both libraries are installed at the repo root (`package.json`, `node_modules/`, git-ignored): `@shadergradient/react` 2.4.20, `@react-three/fiber` 9.8.1, `three` 0.186.1, `react` and `react-dom` 19.3. **The shipped app (`app/static`) is vanilla JS and CSS, offline, no build step, and imports none of them.** Using them is a decision, not a default.

## Decide first (the project's own rules win)
- `PRODUCT.md` and `DESIGN.md` set the tone: calm, trustworthy, colour never the only signal, no fake progress, motion respects `prefers-reduced-motion`. A moving gradient is decoration; it must carry no meaning and must never sit behind text without a contrast check on both themes (AA is measured, see `docs/specs/UI_UX.md` "Desktop workspace").
- The phone column was pinned by the owner; any WebGL belongs to the desktop workspace only (1100 px and up) unless told otherwise.
- These libraries need React and a bundler. To use one in `app/static` build a separate bundle (for example Vite or esbuild into `app/static/vendor/`) and commit the output; never load from a CDN (the app must work offline). Ask the owner before introducing a build step.
- Weigh the cost: WebGL runs on the same GPU as the models when served from this machine's browser; a 60 fps shader behind an answer card can compete with the page. Prefer a static CSS gradient as the fallback and for `prefers-reduced-motion`.

## ShaderGradient (verified in the installed types and dist)
```jsx
import { ShaderGradientCanvas, ShaderGradient } from '@shadergradient/react'

<ShaderGradientCanvas style={{ position: 'absolute', inset: 0 }} pointerEvents="none" pixelDensity={1} fov={45}>
  <ShaderGradient
    control="props"                 // always say so; see traps
    type="plane"                    // 'plane' | 'sphere' | 'waterPlane'
    animate={reduceMotion ? 'off' : 'on'}
    uSpeed={0.2} uStrength={1.2} uDensity={1.2}
    color1="#..." color2="#..." color3="#..."   // take these from DESIGN.md tokens, never invent a palette
    lightType="3d"                  // not 'env': see traps
    brightness={1} grain="off" reflection={0.1}
    cAzimuthAngle={180} cPolarAngle={90} cDistance={3.6} cameraZoom={1}
  />
</ShaderGradientCanvas>
```
- Canvas props: `pixelDensity`, `fov`, `pointerEvents` (`'none'` for a backdrop), `lazyLoad` (default **true**: it only starts rendering when scrolled into view), `threshold`, `rootMargin`, `preserveDrawingBuffer`, `powerPreference`, `envBasePath`.
- Gradient props (type `GradientT`): shape (`type`, `uStrength`, `uDensity`, `uFrequency`, `uAmplitude`), motion (`animate`, `uSpeed`, `uTime`, `loop`, `loopDuration`), colour (`color1` to `color3`, `reflection`, `wireframe`), view (`cAzimuthAngle`, `cPolarAngle`, `cDistance`, `cameraZoom`, `positionX/Y/Z`, `rotationX/Y/Z`), light (`lightType` `'3d'|'env'`, `envPreset` `'city'|'dawn'|'lobby'`, `brightness`), `grain` + `grainBlending`.
- Presets exported: `presets` / `presetsArray` with `halo`, `pensive`, `mint`, `interstella`, `nightyNight`, `violaOrientalis`, `universe`, `sunset`, `mandarin`, `cottonCandy`. A preset is `{ title, color, props }`; spread `presets.halo.props` to start, then override colours from the design tokens.

### Traps found in the package
1. **`control="query"` ignores your props**: it parses `urlString` instead. Pass `control="props"`.
2. **`lightType="env"` fetches HDR files from `https://ruucm.github.io/shadergradient/ui@0.0.0/assets/hdr/`** (default `envBasePath`). That is a network call to a third party and breaks offline use. Use `lightType="3d"`, or self-host the three `.hdr` files and set `envBasePath` on the canvas.
3. **Undeclared peers:** the dist imports `three` and `@react-three/fiber` but lists only React as a peer. Both must be installed (they are).
4. **Version skew:** it was built against `@react-three/fiber` 8.17 and `three` 0.169; this repo has r3f 9.8 and three 0.186 on React 19. The package imports cleanly together in Node (all exports resolve); **a real render in a browser has not been verified here**. Check it in a browser before relying on it.
5. No README ships in the package; the types are `node_modules/@shadergradient/react/dist/index.d.mts`.

## react-three-fiber (readme and installed package)
- `npm install three @react-three/fiber`. **v9 pairs with React 19**; React 18 needs v8.
- `<Canvas>` makes the renderer, scene, camera and loop. JSX tags are three.js objects (`<mesh />` is `new THREE.Mesh()`), props set properties (`position={[0,1,0]}`, `args={[...]}` for constructor arguments).
- `useFrame((state, delta) => ...)` runs every frame: mutate refs (`ref.current.rotation.x += delta`), **never call `setState` inside it**. Hooks: `useThree()` for gl/scene/camera/size, `useLoader()`, `extend({...})` to register custom classes.
- Performance: `<Canvas frameloop="demand">` renders only when invalidated (right for a mostly static scene); lower `dpr` (for example `dpr={[1, 1.5]}`); dispose of what you create; keep the scene small on this machine.
- Everything three.js has works; pmndrs `@react-three/drei` (helpers) is NOT installed, add it only if needed.

## Checklist before shipping any WebGL into the UI
Fallback and reduced-motion branch are CSS only; no network request at runtime (`grep` the built bundle for `https://`); contrast measured on the actual rendered colours in light and dark; GPU and battery cost looked at on the phone width; `scripts/demo_check.py` still passes; the owner has approved a build step.
