# Inspecting 3D motion state in Blender

Read this when an animated character or object in Blender looks wrong (twisted, mirrored, facing backwards, sliding, sinking into or floating above the floor, changing scale) or must be checked before rendering or retargeting. Screenshots hide axis conventions, bone names, scale and per-frame contact, so extract structured state with Blender's Python API first, then confirm with renders. Examples target Blender 4.2 to 4.5 (the 2024 and 2025 long-term releases); the Python API changes between major versions, so check names against the installed version.

Contents: safety · running Blender headless · what to extract · an inspection script · diagnosing common faults · confirming visually · renders for compositing · report · done when.

## Safety

- **Work on a copy** of the `.blend` file. The inspection reads the scene and writes only its own JSON report; it never saves the scene.
- **Untrusted files can run code:** a `.blend` file can contain Python scripts and drivers that run on open when auto-run is enabled. Open files from others with auto-run disabled (`-Y`, `--disable-autoexec`) and start from factory settings (`--factory-startup`) so user add-ons stay out of it.
- Do not "fix" anything during inspection (no applying transforms, no deleting helper objects). Report first; repair only when asked, on a copy.

## Running Blender headless

```bash
blender --background --factory-startup -Y shot_042.blend \
  --python inspect_motion.py -- --frames 1,12,24,36,48 --out shot_042.state.json
```

Arguments after `--` go to the script (`sys.argv`). `bpy` only exists inside Blender's own Python (or the separately distributed `bpy` module built for a matching Blender version), not in the system interpreter.

## What to extract

- **Scene:** Blender version, unit system and scale (`scene.unit_settings`), frame rate (`fps / fps_base`), frame range, the active camera.
- **Inventory:** every object with type, parent, visibility in renders, modifiers (an Armature modifier tells you which mesh a rig deforms), constraints, its action, and world-space scale. Separate the character's meshes from helpers, proxies, control shapes and stray imports before judging anything.
- **Skeleton:** armature names, bone names and parents, rest-pose heads and tails, and per sampled frame the pose bones' heads and tails in world space. Map semantic bones (hips, spine, head, shoulders, hands, thighs, knees, ankles, feet, toes) by name, noting the naming scheme (`.L`/`.R`, `Left`/`Right`, prefixes).
- **Deformed geometry per frame:** the evaluated mesh (after modifiers) in world space, at least its lowest point and bounding box; for contact, the lowest vertex of each foot region.

## An inspection script

```python
# inspect_motion.py: read-only scene report. Run with blender -b --factory-startup -Y file.blend --python inspect_motion.py -- --frames 1,24 --out state.json
import argparse, json, sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--frames", default="")
ap.add_argument("--out", default="state.json")
args = ap.parse_args(argv)

scene = bpy.context.scene
step = max(1, (scene.frame_end - scene.frame_start) // 12)
frames = [int(f) for f in args.frames.split(",") if f.strip()] or list(range(scene.frame_start, scene.frame_end + 1, step))
r5 = lambda v: [round(c, 5) for c in v]

state = {
    "blender": bpy.app.version_string, "file": bpy.data.filepath,
    "units": {"system": scene.unit_settings.system, "scale_length": scene.unit_settings.scale_length},
    "fps": scene.render.fps / scene.render.fps_base, "frame_range": [scene.frame_start, scene.frame_end],
    "objects": [{
        "name": ob.name, "type": ob.type, "parent": ob.parent.name if ob.parent else None,
        "render_visible": not ob.hide_render, "modifiers": [m.type for m in getattr(ob, "modifiers", [])],
        "constraints": [c.type for c in ob.constraints],
        "action": ob.animation_data.action.name if ob.animation_data and ob.animation_data.action else None,
        "world_scale": r5(ob.matrix_world.to_scale()),
    } for ob in scene.objects],
    "frames": [],
}
for f in frames:
    scene.frame_set(f)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    snap = {"frame": f, "bones": {}, "mesh_min_z": {}, "mesh_bbox": {}}
    for ob in scene.objects:
        if ob.type == "ARMATURE":
            mw = ob.matrix_world
            snap["bones"][ob.name] = {pb.name: {"head": r5(mw @ pb.head), "tail": r5(mw @ pb.tail)}
                                      for pb in ob.pose.bones}
        elif ob.type == "MESH" and not ob.hide_render:
            ev = ob.evaluated_get(depsgraph)
            mesh = ev.to_mesh()
            pts = [ev.matrix_world @ v.co for v in mesh.vertices]
            if pts:
                snap["mesh_min_z"][ob.name] = round(min(p.z for p in pts), 5)
                snap["mesh_bbox"][ob.name] = [r5([min(p[i] for p in pts) for i in range(3)]),
                                              r5([max(p[i] for p in pts) for i in range(3)])]
            ev.to_mesh_clear()
    state["frames"].append(snap)

with open(args.out, "w", encoding="utf-8") as fh:
    json.dump(state, fh, indent=1)
print(f"wrote {args.out}: {len(state['objects'])} objects, {len(frames)} frames")
```

For dense meshes, read coordinates in bulk (`mesh.vertices.foreach_get("co", buffer)` with NumPy) instead of a Python loop, and restrict contact checks to the vertices of the feet (a vertex group) to keep it fast.

**Which frames:** the first and last; extremes of the motion; every frame where a foot is lowest (contacts) and the frames around them; turns, jumps and landings. For short clips, sample every frame; it is cheap.

## Diagnosing common faults

Work from the JSON, with the scene's unit scale in mind (tolerances below assume meters; a scene modeled in centimeters at scale 1 needs them scaled).

- **Facing and axes.** Blender is Z-up and right-handed; characters conventionally face −Y. glTF is Y-up with the front facing +Z, and FBX files vary by exporter, so importers convert. Compute the character's forward vector from anatomy, not from one mesh normal: with `right = right_shoulder − left_shoulder` (or the hips), `forward = up × right`. Compare it with the direction the hips actually travel. If they oppose, the import or the retarget's forward axis is wrong; fix the mapping, not the animation curves.
- **Mirroring.** Left bones on the character's right side (in its own frame) after import or retarget mean a mirrored axis or swapped `.L`/`.R` mapping.
- **Ground contact.** Per frame, compare each foot's lowest point with the floor height: below by more than a small tolerance is penetration, above it during a planted step is floating. Choose the tolerance from the shot (a close-up shows millimeters; a wide shot hides a centimeter) and state it.
- **Foot sliding.** Find planted intervals (foot near the floor and nearly still), then measure the foot's horizontal travel across the interval; anything visible at the shot's framing needs foot locking or a retarget constraint review.
- **Leg crossover.** Project ankles onto the character's right vector each frame; a sign swap between left and right means the legs cross, which may be intended in a turn but not in a walk.
- **Twist.** Separate a bone's swing (where it points) from its twist (rotation around its own axis). Extreme forearm or thigh twist shows as "candy-wrapper" collapse in the mesh and usually means rest-pose mismatch or missing twist bones, not bad keys.
- **Scale drift.** Compare the evaluated bounding box against the rest pose over time; unexpected changes of more than a few percent point to constraints, stretch-to bones, inherited scale or a scaled parent.
- **Retarget mismatch.** Missing bone pairs, a T-pose source on an A-pose target (arms offset by a constant angle), root motion applied to the hips instead of the root bone (the character drifts away from its origin, or slides back each loop).
- **Integrity before blame.** Check the rest pose first: a broken import (giant proxy meshes, crushed bodies, wrong materials) explains symptoms that look like animation faults.

## Confirming visually

After the numbers say where to look, render evidence at the flagged frames from fixed orthographic front, side and top cameras placed by script, so every frame is framed the same way. In background mode, Cycles on the CPU renders anywhere; Eevee and Workbench need a working graphics context, which headless servers and containers often lack. Lay the stills out next to the numbers in the report.

## Renders for compositing

When the 3D render will be graded with the rest of the footage (`reference-look-measurement.md`):
- Render with the **Standard** view transform and no look, or to scene-linear OpenEXR, so the grade is applied once in the edit. Blender's default since 4.0 is AgX, which applies its own tone curve; grading on top of it compounds the two.
- Enable **Film > Transparent** for elements that will be composited, and light with a key plus a rim so the silhouette holds against dark plates.
- Record render settings (engine, samples, view transform, resolution, frame rate) in the report.

## Report

```markdown
## Motion inspection: shot_042.blend (Blender 4.2.3, metric, scale 1.0, 24 fps)
### Inventory
- Character: mesh `Body` deformed by armature `Rig` (Armature modifier); helpers: `WGT-*` control shapes (not rendered)
### Orientation
- Forward from shoulders: −Y; hips travel: +Y over frames 1-72  →  facing opposes travel
### Findings
| Frame | Finding | Evidence | Tolerance |
|---|---|---|---|
| 18-24 | Left foot slides while planted | `foot.L` x 0.21 → 0.28 m over 6 frames | 0.01 m |
| 96 | Right foot below floor | `Body` foot region min z = −0.041 m | 0.01 m |
### Verdict
- Not render-ready. Fix the retarget forward axis first; then lock the left foot for frames 18-24.
```

Separate confirmed facts (measured) from suspicions (visual only), and give frame numbers, object and bone names, coordinates and the tolerance used.

## Done when

- The scene was inspected from a copy, with auto-run disabled, and nothing in it was changed.
- The report states units, frame rate, inventory, the character's measured forward axis, and per-frame findings with evidence and tolerances.
- Each finding was confirmed with renders from fixed cameras, or marked as unconfirmed.
- The likely cause and the fix are stated, ordered so that import and retarget faults are fixed before animation cleanup.
