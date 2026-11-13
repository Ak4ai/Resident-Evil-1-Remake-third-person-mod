# Roadmap

*[Versão em português](ROADMAP.pt-BR.md)*

## Done

### Engine / mod
- [x] `d3d9.dll` proxy loader and hot-reloadable mod DLL
- [x] Free third-person camera: follow, right-stick orbit, collision-safe distance
- [x] Over-the-shoulder aim mode with reticle; character turns to the camera
- [x] Automatic search for the player node in memory (no Cheat Engine needed)
- [x] Live tuning through `ctl.txt`
- [x] Room mesh formats RMS2 / RMS3 (per-vertex light) / RMS4 (lightmap)
- [x] Lightmap shader with 4 animated layers (main, fireplace, candles, sconces)
- [x] Emissive-only bloom, halos, grain, colour grading
- [x] Volumetric moonlight beams through the windows
- [x] 800-probe ambient grid lighting the character, plus the moonbeam
- [x] Hide the game's own 2D fire particles when the 3D room is drawn

### Room 105 (dining hall)
- [x] 3D reconstruction matched against the game's backgrounds and depth maps
- [x] Clean pilasters, cornices, niches, ceiling and wall panels
- [x] Baked lighting in Blender/Cycles (OptiX)
- [x] Lightmap UV v3: thin faces (chamfers, mouldings) widened, so no more black lines on corners
- [x] Model checker: z-fighting, hidden faces, too-thin lightmap faces, rendered from game cameras
- [x] Fireplace z-fighting removed

## In progress
- [ ] Re-bake fireplace, candle and sconce layers on UV v3
- [ ] Lightning layer: strong light through the north windows during thunder, stored in the alpha channel of the base lightmap
- [ ] Moonlight layer: window patches on the floor, stored in the alpha channel of the fireplace lightmap
- [ ] Shader support for both window layers

## To do
- [ ] Confirm thunder detection from the game's shader constants
- [ ] Match light distribution to the original backgrounds, camera by camera
- [ ] Small detailed props (chairs, chandeliers, lanterns, statues) lit per vertex instead of in the lightmap atlas
- [ ] Reliable crack/gap test in the model checker
- [ ] Character shadows from the room lights
- [ ] Configurable paths (no hard-coded user folders)
- [ ] Release package and install guide
- [ ] Next rooms
