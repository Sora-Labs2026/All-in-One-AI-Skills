# WebGL backgrounds and 3D on the page

Read this when a web page needs a live graphic layer: an animated shader background (light beams, atmospheric folds, a perspective grid, a dithered field), particles inside a section, a globe, a 3D hero object, a cursor-reactive image effect, an animated metallic border, a physics toy, or an embedded scene from a preset library or no-code editor. It covers choosing the cheapest renderer that delivers the look, a runtime contract every effect keeps, recipes with working numbers, and the accessibility and performance bar. Rendering animation to video is [directed-motion.md](directed-motion.md); seeded art pieces are [generative-art.md](generative-art.md); scroll-driven stories and pinned scenes are `../../ui-distiller/references/scroll-and-reveal-effects.md`; CSS-only finishes (masks, gradient borders, gooey filters, CSS dither) are `../../ui-distiller/references/css-craft-techniques.md`. The short rule set is `STY-12` in `../../../references/ui-rules/style-options.md`. Versions and support are as of late 2025.

## Should the page have one at all?

A live graphic earns its cost when it carries the brand or explains the product (a globe for a network that really spans regions, a 3D object for a physical product). It is decoration when it is a generic glowing background behind a generic headline; [taste.md](../../ui-distiller/references/taste.md) treats that as a tell. Rules that always hold:

- One continuous canvas per viewport. Two animated layers fight for attention and the GPU.
- The headline, navigation and calls to action are real DOM above the canvas; the canvas is `aria-hidden="true"` and `pointer-events: none` unless it is the interaction.
- A static poster (CSS gradient, image or one rendered frame) is the complete fallback for reduced motion, missing WebGL or WebGPU, low-power devices and the moment before script loads.

## Choose the renderer

| Look | Cheapest tool that delivers it | Step up when |
|---|---|---|
| Soft color fields, slow glows | CSS gradients, blurred shapes, `@property` animation | Shapes must interact or be procedural |
| Up to a few hundred 2D particles, small physics scenes | Canvas 2D with one rAF loop | Thousands of points, depth, per-pixel effects |
| Full-screen procedural light (beams, fog, folds, grids, dither) | One fragment shader on a full-screen triangle, raw WebGL2 | You need meshes, a camera, loaders |
| Meshes, lighting, cameras, point clouds, models | Three.js (`WebGLRenderer`; `WebGPURenderer` where its node materials help) | Compute-heavy simulation |
| Fluid or simulation effects driven by the cursor | WebGPU (or WebGL ping-pong textures) behind a capability gate | n/a |
| A decorative globe with markers | A small dedicated dotted-globe library (a few kilobytes) | Data layers: arcs, polygons, hex bins, labels |
| A data globe | A Three.js-based globe visualization library, or Three.js directly | Custom shading or interaction |
| A designed scene without writing shaders | A preset background library or a no-code scene editor's embed | The look must be owned and tuned in code |

Check each library's license and bundle size before adding it, pin exact versions, and self-host the files for anything long-lived rather than loading a moving CDN path.

## The runtime contract

Every effect, hand-written or embedded, runs through the same gate. This helper starts the effect only when it can be seen and is welcome, and stops it otherwise.

```js
export function mountEffect(host, start, { needsFinePointer = false, poster } = {}) {
  const prefs = [matchMedia("(prefers-reduced-motion: reduce)"), matchMedia("(hover: hover) and (pointer: fine)")];
  let stop = null, visible = false;
  const allowed = () => !prefs[0].matches && (!needsFinePointer || prefs[1].matches) && !document.hidden && visible;
  const sync = () => {
    if (allowed() && !stop) { stop = start(host) || (() => {}); host.dataset.live = ""; }
    else if (!allowed() && stop) { stop(); stop = null; delete host.dataset.live; }
  };
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; sync(); }, { rootMargin: "200px" });
  io.observe(host);
  prefs.forEach((q) => q.addEventListener("change", sync));
  document.addEventListener("visibilitychange", sync);
  return () => { io.disconnect(); prefs.forEach((q) => q.removeEventListener("change", sync));
    document.removeEventListener("visibilitychange", sync); stop?.(); };
}
```

- `start` creates the renderer, loop and listeners and returns a function that disposes all of them. Unmounting is the pause: no hidden loop keeps running.
- Lazy-load the heavy module inside `start` (`await import("./globe-scene.js")`), so visitors who never qualify never download it.
- CSS mirrors the gate, so a late or failed start never exposes a broken canvas: `@media (prefers-reduced-motion: reduce) { .fx canvas { display: none } }`, and the poster stays underneath until the effect marks itself live, then fades out over 300-500ms.
- Cap device pixel ratio: `Math.min(devicePixelRatio, 1.5)` for soft full-screen fields, 2 for crisp geometry. Soft effects (fog, glow, blur-like fields) can render at half resolution and scale up unnoticed.
- Size from the element (`ResizeObserver`), not the window, and keep the drawing buffer and CSS size in step.
- Handle context loss: `preventDefault()` on `webglcontextlost`, rebuild on `webglcontextrestored`. Browsers cap live WebGL contexts per page (Chromium at about 16), and the oldest is lost silently past that.
- Time-base all motion in seconds from the frame timestamp; clamp the delta after a tab returns (at most about 50ms per step).

## A full-screen shader skeleton

Raw WebGL2, no buffers: a single triangle that covers the screen, and a fragment shader that does the work.

```js
const VERT = `#version 300 es
void main(){ vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); gl_Position = vec4(p * 2.0 - 1.0, 0, 1); }`;

export function shaderLayer(canvas, frag, uniforms = {}) {
  const gl = canvas.getContext("webgl2", { alpha: true, antialias: false, powerPreference: "low-power" });
  if (!gl) return null;                                   // caller keeps the poster
  const prog = gl.createProgram();
  for (const [type, src] of [[gl.VERTEX_SHADER, VERT], [gl.FRAGMENT_SHADER, frag]]) {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    gl.attachShader(prog, s);
  }
  gl.linkProgram(prog); gl.useProgram(prog);
  const loc = (n) => gl.getUniformLocation(prog, n);
  return {
    draw(t) {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(loc("uRes"), canvas.width, canvas.height); gl.uniform1f(loc("uTime"), t);
      for (const [k, v] of Object.entries(uniforms)) gl[`uniform${v.length}fv`](loc(k), v);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
    dispose() { gl.deleteProgram(prog); gl.getExtension("WEBGL_lose_context")?.loseContext(); },
  };
}
```

Fragment shaders below assume `uniform vec2 uRes; uniform float uTime; uniform vec3 uAccent;`, `out vec4 o;`, centered coordinates `vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;` and a cheap value-noise `fbm()` with four or five octaves. Read the accent from the design token (`getComputedStyle(root).getPropertyValue("--accent")`) and convert to linear 0-1 RGB, so the effect follows the brand and the theme instead of a hardcoded blue.

## Recipes

**Light beam (a thin laser down the page).** Intensity from the horizontal distance `d` to the beam: a white-hot core `exp(-pow(d / 0.004, 2.0))`, a halo `exp(-d / 0.03)` tinted toward the accent, and smoke `fbm(p * 3.0 + vec2(0, -uTime * 0.03))` multiplied by a wide falloff so fog gathers near the beam and fades outward. The core stays near white; only halo and smoke carry the accent. Pulse the halo by at most 10% over 4-6s. Never thicken the core into a neon bar.

**Corner emitter.** Two or three rays leave one off-center point (for example 20% in from a top corner) in clearly different directions. For each ray, project `p - origin` onto its direction and use the perpendicular distance for a thin core, and the distance along the ray for a slow fade. Add a bright bloom at the origin (`exp(-length(p - origin) * 9.0)`) as the hottest point, and a faint accent haze around it with a vignette. Asymmetry is the point; a centered composition loses it.

**Atmospheric folds.** Five to nine tall overlapping bands, each a soft vertical gaussian whose x center drifts with `sin(uTime * 0.05 + phase) * 0.08`, brighter toward the bottom, blended additively so overlaps glow. A radial glow in one lower corner gives the scene a focal point. Drift periods of 20-60s; brightness changes of a few percent. It should read as light through fabric or fog, never as columns.

**Perspective grid floor.** Cast a ray from a camera about 1.5 units above a plane through each pixel; where it hits the plane (`t = camY / -dir.y` for rays pointing down), take the plane coordinates `g = hit.xz + vec2(0, uTime * 0.15)`. Anti-aliased lines: `vec2 a = abs(fract(g - 0.5) - 0.5) / fwidth(g); float line = 1.0 - min(min(a.x, a.y), 1.0);`. Fade by distance (`exp(-t * 0.08)`) so the far field dissolves before the horizon aliases. Lines at 15-30% white, the accent only on sparse dust points. Pointer parallax shifts the camera by at most 0.1 units, eased at about 0.05 per frame.

**Shader dither.** Compute a smooth brightness field (fbm masses, a vignette), snap coordinates to cells (`floor(gl_FragCoord.xy / cell)`), compare against a 4x4 Bayer threshold indexed by the cell position modulo 4, and quantize to four to six grays. Same composition rules as the canvas version in `css-craft-techniques.md`: visible cells (5-10 CSS px), slow drift, no per-frame randomness.

**Section particles (canvas 2D).** Petals, snow, sparks, paper or confetti bounded to one section, behind content. One configuration object (count, gravity, wind, sway amplitude and frequency, size and opacity ranges, rotation, end mode: recycle, exit, settle with a height cap, or static). Derive the count from section area (about one particle per 12,000-20,000 px²), clamp it lower on phones, and thin it behind long text. Pointer disturbance is one listener on the section applying a small radial push (radius 80-120px) that decays back; never a listener per particle. Celebratory bursts follow `MOT-02` and the delight rules in `../../ethical-persuasion.md`: short, skippable, never in front of the next step.

**Particle globe with an orbital ring.** Two point populations in one `THREE.Points` with a custom shader: a sphere of 2,000-4,000 points spread evenly with a Fibonacci lattice (`y = 1 - 2(i + 0.5) / n`, `r = sqrt(1 - y²)`, angle `i * π(3 - √5)`), slightly jittered in radius for depth, and a thinner tilted ring of 800-1,500 points at 1.4-1.6 times the radius. Round soft points in the fragment shader (`smoothstep(0.5, 0.0, length(gl_PointCoord - 0.5))`), size attenuated by depth, additive blending with `depthWrite: false`. Core near white; the accent on the ring and rim. Rotation about 0.1 rad/s, tilt 20-30 degrees, pointer tilt under 0.1 rad.

**Globes with real geography.** A tiny dotted-globe library renders a shaded sphere with land dots, a glow and markers from latitude and longitude; give it a square canvas with the drawing buffer set to CSS size times capped DPR, update its rotation in its render callback, and destroy it on unmount. Let people drag to rotate with momentum only if the globe means something interactive; otherwise spin slowly (about one turn per 40-60s). For arcs, polygons, hex bins and labels use a Three.js-based globe visualization library; keep point counts in the low thousands on phones and use a dark texture when overlays must glow. Markers and arcs must reflect real data; never draw offices or traffic that do not exist.

**A 3D hero object.** Real geometry (an icosahedron or a product glTF compressed with Draco or Meshopt, textures as KTX2), a perspective camera at 30-40 degrees field of view, a physically based material (`MeshStandardMaterial`; `MeshPhysicalMaterial` for clearcoat or glass), and image-based lighting from an environment map (Three.js `RoomEnvironment` through `PMREMGenerator` works offline) plus one key light and a rim light tinted with the accent. Starting materials: brushed metal metalness 0.5-0.7 with roughness 0.25-0.4; ceramic metalness 0-0.1 with roughness 0.4-0.6. Ground it with a contact shadow or a `ShadowMaterial` plane at 0.15-0.2 opacity instead of full shadow maps. Motion: rotation 0.15-0.3 rad/s, a float of 0.04-0.1 units over 6-8s, never camera moves unless the object is the interaction. Set `renderer.outputColorSpace = THREE.SRGBColorSpace` and ACES tone mapping; dispose geometry, materials, textures and the renderer on teardown.

**Cursor-reactive image effects.** Ripples that displace a photo, or a halftone trail that sparkles where the pointer passed, need a simulation texture updated each frame (two render targets swapped, a "ping-pong") or a WebGPU shader component library that provides one. Gate on `navigator.gpu` (or WebGL2), a fine pointer, normal motion and transparency preferences (`prefers-reduced-transparency`), and visibility; lazy-load the module behind the gate; keep the real `<img>` underneath as the accessible image and fallback, and fade the canvas in only once its first frame is ready. Keep the original crop identical between image and canvas. One canvas per media panel; replace any older pointer-spotlight code rather than layering both. Under reduced motion, coarse pointers, or forced colors, show the image alone.

**Animated metallic border.** A WebGL ring painted around one control (selected tab, primary call to action, active card) with a flowing chrome or iridescent pattern. Mount one renderer shared by all instances; pause the pattern on idle instances and under reduced motion; keep the selected state in `aria-pressed`, `aria-selected` or the current-route marker, plus a static CSS edge as fallback ([css-craft-techniques.md](../../ui-distiller/references/css-craft-techniques.md), gradient borders). Check that any style normalization the component applies does not remove the control's focus outline. Never put it on every control.

**Physics toys.** Falling tags, draggable stacks or a playful footer built with a 2D rigid-body engine (Matter.js is the common choice). Use the engine's debug renderer only while building; draw bodies yourself onto a canvas, or move DOM elements with transforms from body positions so text stays crisp. Fix the time step (1/60 s) and step from your own rAF loop, pause off-screen, and remove bodies that leave the world. Mouse dragging needs a non-drag way to reach any content involved (WCAG 2.5.7); the real content also exists as a normal list. Reduced motion: bodies rendered at rest.

**Preset backgrounds and no-code scene embeds.** Preset libraries inject a canvas into a sized container with a handful of options; no-code editors export a scene that loads from an embed script with attributes for render scale, pixel density, frame-rate cap and lazy loading. In both cases: the container needs explicit dimensions; render scale 0.5-0.75 and 30-45 fps for ambient scenes; one or two per page; destroy the instance on unmount; wait for a published build if the site builder's editor does not render it; and keep a poster for reduced motion. Self-host an exported scene file when the plan allows, so the page does not depend on another service at runtime.

## Accessibility

- Decorative canvases: `aria-hidden="true"`, no focusable content, `pointer-events: none`, content and controls stacked above.
- Measure text contrast against the brightest frame and the brightest region that can pass behind the text, not the average; dim the effect or add a scrim until body text holds 4.5:1 and large text 3:1.
- No flashing above three times per second (WCAG 2.3.1, `MOT-21`); pulses and shimmers stay slow and low in amplitude.
- Reduced motion shows the poster or a single still render; anything moving for more than five seconds beside content needs a pause control (`MOT-19`) unless it is unmounted under reduced motion and is purely ambient behind a static section.
- An interactive 3D viewer needs keyboard controls (arrow keys rotate, +/- zoom, a reset button) and a text description of what it shows.

## Performance budget

- Frame time under about 4ms on a mid-range phone for a background effect; profile with 4x CPU throttling and watch GPU time in the Performance panel.
- Mobile: DPR 1-1.5, half the particles, render scale 0.5-0.75 for soft fields, or the poster alone below a width or memory threshold (`navigator.deviceMemory` where available).
- Three.js is a large dependency: lazy-load it, import only what you use, and never ship it for an effect a 40-line shader can draw.
- Shader cost: keep fbm to four or five octaves, avoid loops whose count depends on uniforms, and cap full-screen passes at one or two.

## Pitfalls

- A canvas covering links, or listening for pointer events that the content below needed.
- Animation loops that continue off-screen, in hidden tabs, or after the route changed; leaked contexts that hit the per-page limit.
- Accent colors hardcoded in the shader, so the effect ignores the brand and the dark theme.
- Drawing buffer sized from the window while CSS sizes the element, giving blurry or stretched output.
- Bloom and particles so strong they hide the object's form or wash out the headline.
- Effects that only work with a mouse but carry information touch users need.

## Done when

- [ ] The renderer is the cheapest one that delivers the look, and the dependency, license and bytes are recorded.
- [ ] The effect starts only when visible, welcome and supported, stops when not, and disposes everything on teardown; repeated mounting leaves one loop.
- [ ] A static poster gives a complete page with script off, under reduced motion and without WebGL or WebGPU.
- [ ] Colors come from the design tokens and work in light and dark themes.
- [ ] Text over the effect meets contrast at the worst frame; no flashing above three per second.
- [ ] A throttled profile on a mid-range phone stays within the frame budget at 390, 768 and 1440px widths.
