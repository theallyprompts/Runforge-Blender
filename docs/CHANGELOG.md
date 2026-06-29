# Changelog

All notable changes to Runforge are documented here.

---

## [1.0.0] — 2026-06-29

### Changed

- **Converted to Blender Extension format** — Runforge is now a native Blender Extension (requires Blender 4.2+). It installs via Extensions rather than Legacy Add-ons, and includes a `blender_manifest.toml` declaring network and file permissions. The `bl_info` dict has been removed.
- **Minimum Blender version raised to 4.2** — required for extension support.

---

## [0.1.3] — 2026-06-26

### Added

- **Tripo: Negative Prompt** — text field below the main prompt to steer away from unwanted elements (text mode only)
- **Tripo: Seed** — integer seed for reproducible results; 0 = random
- **Tripo: Texture Alignment** — Match Image vs Match Geometry (image mode only; greyed out in text mode)
- **Meshy-6: Topology** — Triangle / Quad output mesh (standard mesh type only; automatically sets `remesh=true`)
- **Meshy-6: HD Texture** — 4K base colour texture toggle
- **Meshy-6: Remove Lighting** — strips baked highlights and shadows from texture; on by default for cleaner results in Blender
- **Meshy-6: Texture Prompt** — additional prompt to guide texturing (text mode only; greyed out when texture is off)
- **Generation presets** — Speed / Quality / Custom selector in addon preferences; applies sensible defaults to all advanced settings per scene
- **History refresh button** — Refresh button inside the History panel to re-scan the output folder on demand

### Fixed

- **Tripo always outputs FBX** — the API only accepts `outputFormat: "FBX"`; sending `"GLB"` caused every text-to-3D generation to fail. FBX importer pre-flight check now runs for all Tripo generations, not just image mode
- **Tripo Quad Mesh outputs FBX** — the schema requires `outputFormat=FBX` when `quad=true`; this is now enforced correctly
- **Tripo Texture Alignment caused timeouts in text mode** — `textureAlignment: "original_image"` requires a source image to align to; sending it for text-to-3D caused Tripo's backend to hang. Now only sent in image mode
- **faceLimit values below 500 sent to API** — the API minimum is 500; values 1–499 were previously sent and rejected. Now only sent when ≥ 500
- **History disappeared after saving .blend file** — the history cache key was derived from `bpy.data.filepath`; saving changed the path, causing a cache miss against the new (empty) folder. Output folder is now pinned at generation time and reused for all subsequent history reads
- **Refresh button opened/closed panel instead of refreshing** — `draw_header` buttons are swallowed by the panel collapse toggle; moved Refresh into `draw()` as a proper button row
- **Cancel operator had no `poll`** — could fire after a job finished, setting `message="Cancelling…"` with no dismiss path. Added `poll` returning `get_state()["running"]`
- **Meshy Low-Poly mesh type sent invalid settings** — polyCount, topology, and remesh are forbidden when `meshType=lowpoly`; these are now excluded automatically

---

## [0.1.2] — 2026-06-26

### Fixed

- **Download could hang indefinitely** — `urllib.request.urlretrieve` opens its own socket and ignores `socket.setdefaulttimeout`; on a stalled connection the download would block forever. Replaced with `urlopen(url, timeout=120)` which enforces the timeout directly on the connection.
- **Cancel showed "Cancelling…" permanently after generation finished** — `RUNWARE_OT_Cancel` had no `poll` method, so it could fire even when nothing was running. Clicking cancel post-generation left the status box stuck showing "Cancelling…" with no way to dismiss it. Added `poll` returning `get_state()["running"]`.
- **bpy calls in background thread** — `get_output_folder()` (which calls `bpy.context`) was being called from the generation thread. All bpy-dependent values (`output_folder`, `filename`) are now computed on the main thread in `execute()` and passed as arguments to the thread.
- **Cancel silently ignored during download** — if the user cancelled while the model was downloading, the cancel flag was not checked after `download_and_save()` completed, so the import would proceed anyway. A cancel check now runs immediately after the download finishes.

---

## [0.1.1] — 2026-06-26

### Fixed

- **Model download always failed** — `socket.setdefaulttimeout()` was used as a context manager (it returns `None`), raising `TypeError` on every download attempt. Replaced with an explicit save/restore using `finally`.
- **Cancel deadlocked Blender** — `_set_state()` was called inside a `with _state_lock:` block; since `threading.Lock` is non-reentrant, cancelling any generation caused a permanent deadlock. Now updates `_state` directly inside the lock.
- **Tripo image-to-3D would charge the API then fail on import** — no pre-flight check for the FBX importer. Now shows a clear error ("enable the FBX importer in Preferences") before submitting if the importer is absent.
- **Generation could spin forever** — the poll loop had no wall-clock timeout. A 5-minute limit now surfaces a timeout error with a note to check the Runware dashboard.
- **Large images caused out-of-memory crash** — no size guard before base64-encoding reference images. Files over 20 MB are now rejected with a clear message before any upload is attempted.
- **`class ImportError` shadowed Python built-in** — renamed to `ModelImportError` throughout `importer.py`.

---

## [0.1.0] — 2026-06-26

Initial release.

### Added

**Core generation**
- Text-to-3D and Image-to-3D generation via Runware API
- Tripo v3.1 support: text ($0.30/gen) and image ($0.40/gen) modes
- Meshy-6 support: text and image modes, GLB output
- Async generation with 3-second polling and elapsed-time display
- Cancel button to abort in-flight generations
- Up to 3 automatic retries on network errors

**Advanced settings — Tripo v3.1**
- Geometry quality (Standard / Detailed)
- Texture quality (Standard / Detailed)
- Face limit (500–20,000)
- PBR, texture, quad mesh, smart low-poly toggles
- Output format selector (GLB / FBX)

**Advanced settings — Meshy-6**
- Mesh type (Standard / Low-Poly)
- Poly count (100–300,000; default 30,000)
- Texture, PBR, HD texture toggles
- Pose (None / A-Pose / T-Pose)
- Symmetry (Auto / On / Off)

**Output & history**
- Auto-import on completion: GLB downloaded, saved, imported at world origin (0, 0, 0), auto-selected
- Configurable output folder (defaults to `runware_output/` next to `.blend`)
- Timestamp-based file naming: `{model}_{slug}_{date}_{time}.glb`
- History panel: last 10 generations with Re-import and Show in Explorer actions
- History stored as `runware_history.json`; missing entries pruned automatically

**UI**
- N-panel sidebar in the 3D Viewport ("Runware" tab)
- Welcome panel with link to Runware docs
- API key panel with masked display and preferences shortcut
- Collapsible Advanced settings section
- Status panel: progress, elapsed time, cost estimate, error messages with auto-dismiss

**Infrastructure**
- API key stored in Blender AddonPreferences (persists in `userpref.blend`)
- No external Python dependencies (stdlib only)
- Thread-safe background I/O with `bpy.app.timers` main-thread callbacks
- Atomic JSON writes for history
- Cross-platform Show in Explorer (Windows, macOS, Linux)
- Blender 4.0+ compatibility

### Known limitations
- Polling only (no webhook / push callbacks)
- Tripo image-to-3D requires the FBX importer addon (optional in Blender 4.2+)
- Single generation at a time
- No viewport render → Image-to-3D shortcut
- No per-`.blend` API key storage
