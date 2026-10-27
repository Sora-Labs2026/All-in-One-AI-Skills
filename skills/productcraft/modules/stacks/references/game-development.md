# Game development

Read this when you build or change a game or interactive simulation: the game loop, architecture, performance, Unity, Unreal Engine, Godot or a web game, multiplayer networking, save data, builds and tests. Game design and UI art direction are out of scope; menus and HUDs follow `../../ui-rules.md` and `../../responsive-accessibility.md`.

## Choose the engine

| Engine or library | Language | Fits | Notes |
|---|---|---|---|
| Unity | C# | 2D and 3D, mobile, broad platform support, large asset ecosystem | Commercial license; terms changed in recent years, so read the current ones |
| Unreal Engine | C++ and Blueprints | High-end 3D, large worlds, built-in replication | Royalty on revenue above a threshold; heavy editor and builds |
| Godot | GDScript, C# | 2D and lighter 3D, small teams, open source (MIT) | Fewer console and store integrations out of the box |
| Phaser, PixiJS | JavaScript or TypeScript | 2D browser games (Phaser is a full framework, PixiJS a renderer) | Browser limits on memory, audio and input |
| three.js, Babylon.js, PlayCanvas | JavaScript or TypeScript | 3D in the browser | WebGL today; WebGPU support is growing, check targets |
| Bevy | Rust | ECS-first engine for Rust teams | Young; APIs change between releases |

Read license and revenue terms before committing and record the choice as an ADR. Changing engines mid-project is close to a rewrite.

## The game loop

Simulation (movement, physics, rules) runs at a fixed timestep; rendering runs as fast as the display allows and interpolates between the last two simulation states. That makes gameplay independent of frame rate and is the basis for deterministic replays and networking.

```ts
const STEP = 1 / 60;           // simulation step in seconds
const MAX_FRAME = 0.25;        // clamp long pauses to avoid the "spiral of death"
let accumulator = 0;
let last = performance.now() / 1000;

function frame(nowMs: number) {
  const now = nowMs / 1000;
  accumulator += Math.min(now - last, MAX_FRAME);
  last = now;
  while (accumulator >= STEP) {
    previous = current;
    current = simulate(current, STEP, readInput());   // pure update; no rendering here
    accumulator -= STEP;
  }
  render(interpolate(previous, current, accumulator / STEP));
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
```

Engines provide this split: Unity `FixedUpdate` and `Update`, Unreal's physics substepping and `Tick`, Godot `_physics_process` and `_process`. Put physics and gameplay rules in the fixed step, input sampling and visuals in the frame step, and multiply any per-frame motion by the frame's delta time.

## Frame budget and profiling

- 60 frames per second leaves 16.7 ms per frame for everything; 120 leaves 8.3 ms; 90 (common in VR) leaves 11.1 ms. The CPU main thread, render thread and GPU each have to fit.
- Measure on the lowest-spec target device, in a development build with the profiler attached, then confirm in a release build. Editor numbers mislead.
- Tools: Unity Profiler, Frame Debugger and Memory Profiler; Unreal Insights with `stat unit` and `stat gpu`; Godot's profiler and monitors; browser DevTools Performance panel for web games. Follow the measure, change one thing, re-measure loop in `../../engineering-practices/references/performance.md`.
- On mobile, test sustained play for 15 minutes or more; thermal throttling lowers performance after the first minutes.

## Where frame time usually goes

- **Allocations per frame** cause garbage-collection spikes in C# and JavaScript: string building, LINQ, closures, boxing, new arrays in update loops. Reuse buffers; pool frequently spawned objects (Unity has `UnityEngine.Pool.ObjectPool<T>`).
- **Lookups per frame:** cache component references (`GetComponent`, `Find`, node paths) at startup instead of every update; compare tags with `CompareTag` in Unity.
- **Draw calls and overdraw:** batching, GPU instancing, texture atlases, fewer materials; limit large transparent particles on mobile.
- **Physics:** collision layers and matrices so objects test only what they can hit, primitive colliders over mesh colliders, sleeping bodies, a fixed step no smaller than needed.
- **Content:** level-of-detail meshes, occlusion and distance culling, texture compression per platform (ASTC on mobile, BC formats on desktop), and streaming or asynchronous loading (Unity Addressables, Unreal level streaming) instead of loading everything up front.
- **Proximity queries:** checking every object against every other grows with the square of the count. Use a spatial structure (uniform grid, quadtree or octree, or the physics engine's overlap queries) for "what is near me".
- **Update counts:** thousands of objects each running their own update are slower than one manager updating arrays. That is the case for data-oriented designs and ECS.

## Architecture

- Composition over deep inheritance: behavior as components on entities or nodes.
- Data in assets, not code: Unity ScriptableObjects, Unreal Data Assets and Data Tables, Godot Resources. Designers tune values without recompiling.
- Explicit state machines for game flow (menu, playing, paused, game over) and for actor behavior; behavior trees or utility AI when state machines grow unmanageable.
- Events or signals decouple systems; always unsubscribe when the listener is destroyed.
- Singletons and service locators only for truly global services (audio, save system), with a way to replace them in tests.
- **ECS** (Unity Entities, Unreal Mass, Bevy, flecs, EnTT) pays off with many similar entities processed each frame. It adds complexity; use it where profiling shows object-per-entity code is the bottleneck, not by default.

## Unity specifics

- Lifecycle: `Awake` (own setup), `OnEnable`, `Start` (setup that needs other objects), `FixedUpdate`, `Update`, `LateUpdate` (cameras), `OnDisable`, `OnDestroy`. Do not depend on the order of `Awake` across objects without setting script execution order.
- Destroyed objects compare equal to `null` through Unity's overloaded `==`, but `?.` and `??` bypass that check and touch the destroyed object. Use explicit `== null` or `if (obj)` for Unity objects.
- Expose fields with `[SerializeField] private`, not public fields.
- Async: coroutines stop when their object is disabled; with `async` methods or Unity 6's `Awaitable`, pass `destroyCancellationToken` so work stops when the object is destroyed.
- Assembly definitions cut compile times in large projects. Use the Input System package for new projects.
- Tests: Unity Test Framework with Edit Mode tests for pure logic and Play Mode tests for scene behavior, run in CI with `-batchmode -runTests`.

## Unreal Engine specifics

- Garbage collection only sees `UObject` pointers held in `UPROPERTY()` fields (or `TObjectPtr` in UE5). A raw pointer to a `UObject` in a plain member can dangle after collection. Use `TWeakObjectPtr` for non-owning references and `TSharedPtr` and `TUniquePtr` for non-`UObject` types.
- Turn ticking off where it is not needed (`PrimaryActorTick.bCanEverTick = false`) and use timers or events instead.
- Systems in C++, exposed through `UFUNCTION(BlueprintCallable)` and `UPROPERTY(EditAnywhere)` for designers; keep heavy loops out of Blueprint graphs.
- Replication: mark state with `UPROPERTY(Replicated)` or `ReplicatedUsing`, register it in `GetLifetimeReplicatedProps`, and check `HasAuthority()` before changing authoritative state. Server RPCs validate their parameters; never trust what the client sends.
- The Gameplay Ability System suits games with many abilities, effects and attributes; it is heavy for small projects.
- Tests: the Automation framework for functional and unit tests; Gauntlet for build-level runs.

## Godot specifics

- Scenes composed of nodes; signals for decoupling; `_physics_process` for movement and physics.
- Static typing in GDScript (`var speed: float = 200.0`, typed function signatures) catches errors earlier and runs faster.
- Autoloads (global singletons) sparingly; Resources for shared data.
- Tests with GUT or gdUnit4; headless exports in CI with `godot --headless --export-release`.

## Multiplayer networking

- **Authority:** for anything competitive or with value, the server owns the game state. Clients send inputs, not positions or outcomes, and the server validates every input (rate, range, cooldowns, ownership). Client-side checks and obfuscation are not security.
- **Topology:** dedicated servers for competitive games; a listen server (one player hosts) or relay for co-op; deterministic lockstep for strategy games with many units (every client simulates the same inputs; requires bit-identical simulation, which floating point across platforms makes hard).
- **Hiding latency** in client-server action games:
  - Client-side prediction: apply local inputs immediately, tagged with sequence numbers.
  - Server reconciliation: when an authoritative state arrives, rewind to it and replay inputs the server has not acknowledged yet.
  - Entity interpolation: draw other players slightly in the past, between two received snapshots.
  - Lag compensation: the server checks hits against where targets were at the shooter's view time, with a bounded rewind window.

```ts
// Client: predict locally, reconcile on each authoritative update.
const pending: Input[] = [];
function onLocalInput(input: Input) {
  input.seq = nextSeq++;
  pending.push(input);
  player = applyInput(player, input);          // same pure function the server runs
  send({ type: "input", ...input });
}
function onServerState(state: { player: PlayerState; lastProcessedSeq: number }) {
  player = state.player;                        // authoritative
  while (pending.length && pending[0].seq <= state.lastProcessedSeq) pending.shift();
  for (const input of pending) player = applyInput(player, input);  // replay unacknowledged
}
```

- **Bandwidth:** send deltas against the last acknowledged snapshot, quantize floats, send only what each client can see or needs (interest management), and prioritize nearby and important entities.
- **Transport:** UDP with reliable and unreliable channels (engine transports, ENet and similar) for real-time games; WebSockets or WebRTC data channels in browsers (`realtime-websockets.md`).
- **Testing:** simulate latency, jitter and packet loss (Unity's network simulator, Unreal's packet-lag console variables, `tc netem` on Linux); run bots for load; in lockstep games, compare state checksums every few ticks to catch desyncs early.

## Save data

- Version the save format and migrate old saves forward; never assume the current structure.
- Write atomically: write to a temporary file, flush, then rename over the old save. A crash mid-write must not destroy progress.
- Treat save files and cloud saves as untrusted input when they affect multiplayer or purchases; validate on the server.

## Builds and assets

- Large binary assets: Git LFS with file locking for small teams, or Perforce for large teams; set up `.gitattributes` before the first asset commit.
- Headless builds in CI (Unity `-batchmode -quit -executeMethod`, Unreal `RunUAT BuildCookRun`, Godot `--headless --export-release`), with crash-report symbols kept per build.
- Console certification requirements come from the platform holders under NDA; follow their documentation. Store submissions are the owner's action.

## Web games

- Drive the loop with `requestAnimationFrame`; pause the simulation on `visibilitychange`.
- Browsers block audio until a user gesture; unlock the audio context on the first input.
- Handle WebGL context loss and restore (`webglcontextlost`); mobile browsers drop contexts under memory pressure.
- Compress assets: KTX2 or Basis textures, Draco or meshopt geometry for glTF, and a loading screen with real progress.

## Accessibility and player respect

- Remappable controls, subtitles with speaker names, colorblind-safe signals (shape or pattern as well as color), options to reduce camera shake, flashing and motion, and adjustable difficulty or assist modes.
- Monetization follows `../../ethical-persuasion.md`: no fake scarcity or manipulative timers. Loot boxes, age ratings and children's data carry legal duties that vary by market (`../../legal-ready/GUIDE.md`).

## Done when

- [ ] Gameplay runs on a fixed step and stays correct at different frame rates.
- [ ] Frame-time claims come from a profiler on the lowest target device, before and after.
- [ ] No per-frame allocations or lookups in hot update paths that the profiler flags.
- [ ] Multiplayer state changes are validated on the server; the game was tested with simulated latency and packet loss.
- [ ] Saves are versioned and written atomically; the project's automated tests run headless in CI.
