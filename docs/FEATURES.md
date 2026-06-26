# Runforge — Features

Runforge is a Blender 4.x addon that connects Blender to Runware's AI 3D generation API. Type a prompt (or drop in a reference image), hit Generate, and the model appears in your scene — textured, imported, and ready to use.

---

## Supported Models

| Model | Text-to-3D | Image-to-3D | Output |
|---|---|---|---|
| Tripo v3.1 | ✓ ($0.30/gen) — GLB | ✓ ($0.40/gen) — FBX | GLB (text) · FBX (image) |
| Meshy-6 | ✓ — GLB | ✓ — GLB | GLB |

> **Note:** Tripo image-to-3D and Quad Mesh output FBX. Blender 4.2+ ships with the FBX importer as an optional extension — enable it in Edit > Preferences > Add-ons before using those modes.

Both models are selectable from a dropdown in the panel. Settings adapt automatically to whichever model is active.

---

## Generation Modes

### Text-to-3D
Write a prompt (up to 1024 chars for Tripo, 600 for Meshy-6) and generate a fully textured 3D model. A negative prompt field lets you steer away from unwanted results.

### Image-to-3D
Supply 1–4 reference images via a file picker. The model reconstructs geometry and texture from your references. Tripo supports up to 4 images; Meshy-6 also accepts a separate texture reference image.

---

## Advanced Settings

Accessible via a collapsible **Advanced** section in the panel. Settings are model-specific.

### Tripo v3.1
| Setting | Options | Notes |
|---|---|---|
| Geometry Quality | Standard / Detailed | |
| Texture Quality | Standard / Detailed | |
| Texture Alignment | Default / Match Image / Match Geometry | Image mode only |
| Face Limit | 500–20,000 | Polygon budget; 0 = no limit |
| PBR | On / Off | Physically-based rendering |
| Texture | On / Off | Auto-enabled in Image mode |
| Quad Mesh | On / Off | Quad topology output |
| Smart Low-Poly | Coming soon | Disabled — not yet functional |
| Negative Prompt | Text field | Steer away from unwanted elements; text mode only |
| Seed | Integer | Reproducible results; 0 = random |

### Meshy-6
| Setting | Options | Notes |
|---|---|---|
| Mesh Type | Standard / Low-Poly | Low-Poly disables topology and poly count controls |
| Poly Count | 100–300,000 | Default: 30,000; standard mesh only |
| Topology | Triangle / Quad | Standard mesh only |
| Pose | None / A-Pose / T-Pose | ⚠ Currently inoperable — Runware API issue |
| Symmetry | Auto / On / Off | |
| Texture | On / Off | |
| PBR | On / Off | |
| HD Texture | On / Off | 4K base colour texture (PBR always at 2K) |
| Remove Lighting | On / Off | Strips baked highlights/shadows; on by default |
| Texture Prompt | Text field | ⚠ Currently inoperable — Runware API issue; text mode only |

---

## Workflow

1. Open the **Runware** tab in Blender's N-panel (3D Viewport → N → Runware)
2. Enter your API key (stored securely in Blender preferences, persists across sessions)
3. Pick a model and mode
4. Enter a prompt or select reference images
5. Click **Generate**
6. Watch the status panel — the addon polls every 3 seconds and shows elapsed time
7. On completion the GLB is downloaded, saved to your output folder, and auto-imported at the world origin (0, 0, 0), selected and ready

---

## Output & History

- **Output folder:** configurable in preferences; defaults to `runware_output/` next to your `.blend` file
- **File naming:** `{model}_{prompt-slug}_{date}_{time}.glb` — human-readable and sortable
- **History panel:** last 10 generations listed with **Re-import** and **Show in Explorer** buttons
- **History persistence:** stored in `runware_history.json` alongside your output files; missing files are pruned automatically on load

---

## UI Panels

All panels live in the **Runware** tab of the 3D Viewport N-panel.

| Panel | Purpose |
|---|---|
| Welcome | Branding, link to Runware docs |
| API Key | Shows masked key; quick link to preferences |
| Generate | Model, mode, prompt/image, advanced settings, Generate/Cancel |
| Status | Progress, elapsed time, cost estimate, error messages |
| History | Last 10 generations with re-import and file explorer access |

---

## Technical Notes

- **Blender compatibility:** 4.0 and above
- **No external dependencies:** uses Python stdlib only (`urllib`, `json`, `threading`, `uuid`)
- **Thread-safe:** all network I/O runs in a background thread; Blender's main thread is never blocked
- **Retry logic:** network errors auto-retry up to 3 times before surfacing an error
- **Generation timeout:** polls for up to 5 minutes before surfacing a timeout error
- **Image size limit:** reference images must be under 20 MB (checked before upload)
- **Atomic file writes:** history JSON is written atomically (temp file + rename) to prevent corruption
- **Cross-platform:** Show in Explorer works on Windows (`explorer /select`), macOS (`open -R`), and Linux (`xdg-open`)
- **API base URL:** `https://api.runware.ai/v1`

---

## Generation Presets

A **Speed / Quality / Custom** toggle in **Edit → Preferences → Add-ons → Runware 3D** seeds the Advanced settings with sensible defaults.

| Setting | Speed | Quality |
|---|---|---|
| Tripo Geometry Quality | Standard | Detailed |
| Tripo Texture Quality | Standard | Detailed |
| Tripo Quad Mesh | Off | On |
| Tripo Texture Alignment | Default | Match Image |
| Meshy Poly Count | 10,000 | 50,000 |
| Meshy Topology | Triangle | Quad |
| Meshy HD Texture | Off | On |

Custom leaves all settings to manual control. Presets are applied per-scene with the **Apply Preset** button in preferences — individual settings can be tweaked after applying.

---

## Known API Issues

These settings are exposed in the panel but are currently inoperable due to issues on the Runware API side. They will become functional once resolved upstream.

- **Meshy-6 Pose** — A-Pose and T-Pose are accepted by the API but have no effect on output
- **Meshy-6 Texture Prompt** — accepted but does not influence texture generation
- **Tripo Smart Low-Poly** — disabled in UI; not yet functional, will be available in a future release

---

## Out of Scope

These are known gaps noted for future versions:

- Image-to-3D from a Blender viewport render
- Multiple simultaneous generations
- Model preview before import
- Webhook / push-based callbacks (currently polls every 3s)
- Per-`.blend` API key storage
- Meshy-6 Animate (rigged mesh with idle animation) — not available via Runware API
