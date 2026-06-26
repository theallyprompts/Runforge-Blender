# Runforge for Blender

**AI 3D asset generation inside Blender powered by [Runware.ai](https://runware.ai/)** Type a prompt or drop in a reference image — Runforge calls the Runware.ai API and imports the finished model directly into your scene.

Supports **[Tripo v3.1](https://runware.ai/models/tripo-v3-1)** and **[Meshy-6](https://runware.ai/models/meshy-6)**. No external Python dependencies. Blender 4.0+.

<img width="1920" height="1080" alt="Screenshot 2026-06-26 152735" src="https://github.com/user-attachments/assets/c84d6ed1-6eee-4485-9974-f62e1bce8062" />

---

## What it does

Runforge adds a sidebar panel to Blender's 3D Viewport (shortcut `N`). From there you can:

- Generate a textured 3D model from a text prompt
- Reconstruct geometry from a single reference images
- Watch generation progress with a live elapsed timer
- Cancel mid-flight if you change your mind
- Re-import or locate any previous generation from the History panel

The model is downloaded, saved to your output folder, and imported at the world origin — selected and ready — without leaving Blender.



## Models

| Model | Text → 3D | Image → 3D | Output format |
|---|---|---|---|
| Tripo v3.1 | ✓ — $0.30 / gen | ✓ — $0.40 / gen | GLB (text) · FBX (image) |
| Meshy-6 | ✓ — ~$0.80 / gen | ✓ — ~$0.80 / gen | GLB |

---

## Installation

1. Go to the [Releases](../../releases) page and download the latest `runforge-x.x.x.zip`
2. In Blender: **Edit → Preferences → Add-ons → Install from Disk...**
   <img width="934" height="229" alt="Screenshot 2026-06-26 151206" src="https://github.com/user-attachments/assets/55ed6b02-8d77-44d9-97b9-77fa9b3ee13d" />
4. Select the downloaded zip — do not unzip it first
5. Enable **Runware 3D** in the add-ons list
   <img width="914" height="578" alt="Screenshot 2026-06-26 151326" src="https://github.com/user-attachments/assets/6986aeaf-74be-4a36-97c1-9c964bd0e3dc" />
7. Enter your Runware API key in the add-on preferences

Your API key is stored in Blender's own preferences file (`userpref.blend`) and persists across sessions.

### Requirements

- Blender 4.0 or later
- A free [Runware account](https://runware.ai) & API key

---

## Usage

Open the **Runware** tab in the 3D Viewport N-panel (`N` key).

1. **Model** — choose Tripo v3.1 or Meshy-6
2. **Mode** — Text to 3D or Image to 3D
3. **Prompt / Image** — enter a description or select a reference file
4. **Advanced Settings** — expand for geometry quality, texture, poly count limit, and more
5. **Generate** — the panel shows live status; click **Cancel** at any time

On completion the model appears in your scene at the origin, auto-selected.

### Advanced settings — Tripo v3.1

| Setting | Options |
|---|---|
| Geometry Quality | Standard · Detailed |
| Texture Quality | Standard · Detailed |
| Texture Alignment | Default · Match Image · Match Geometry (image mode only) |
| Face Limit | 0–20,000 (0 = no limit) |
| PBR | On · Off |
| Texture | On · Off |
| Quad Mesh | On · Off |
| Smart Low-Poly | Coming soon |
| Negative Prompt | Text to steer away from unwanted elements (text mode only) |
| Seed | Integer for reproducible results (0 = random) |

### Advanced settings — Meshy-6

| Setting | Options |
|---|---|
| Mesh Type | Standard · Low-Poly |
| Poly Count | 100–300,000 (default 30,000; standard mesh only) |
| Topology | Triangle · Quad (standard mesh only) |
| Pose | None · A-Pose · T-Pose |
| Symmetry | Auto · On · Off |
| Texture | On · Off |
| PBR | On · Off |
| HD Texture | On · Off — 4K base colour texture |
| Remove Lighting | On · Off — strips baked highlights for custom lighting |
| Texture Prompt | Additional prompt to guide texturing (text mode only) |

### Generation presets

A **Speed / Quality / Custom** preset can be set in **Edit → Preferences → Add-ons → Runware 3D**. Speed uses Standard geometry and lower poly counts. Quality uses Detailed geometry, Quad mesh, HD Texture, and higher poly counts. Custom leaves all settings to you.

### History

The **History** panel lists your last 10 generations. Each entry has a **Re-import** button and a **Show in Explorer** button. A **Refresh** button re-scans the output folder — deleted files are pruned from the list automatically.

---

## Output & file management

- **Output folder:** set in preferences; defaults to `runware_output/` next to your `.blend` file (or `~/runware_output/` if the file hasn't been saved yet)
- **File naming:** `{model}_{prompt-slug}_{date}_{time}.glb` — human-readable and sortable by date
- **History file:** `runware_history.json` in the output folder — plain JSON, easy to inspect or version-control

---

## Security

- **Your API key is never written to disk by Runforge.** It is stored exclusively by Blender's own preferences system (`userpref.blend`), the same place Blender stores all add-on settings.
- **No data is sent anywhere except `api.runware.ai`.** Runforge makes POST requests to `https://api.runware.ai/v1` only — your prompts and images go to Runware's API and nowhere else.
- **No external Python packages are installed.** Runforge uses Python's standard library only (`urllib`, `json`, `threading`, `base64`). Nothing is pip-installed, no network calls happen at install time.
- **Reference images are encoded locally.** When you supply a reference image it is base64-encoded in memory and sent directly to the API — it is never uploaded to a third-party service or cached externally by this add-on.

---

## Costs

Runforge itself is free and open source. Generation costs are charged by Runware directly against your account balance:

| Generation | Approximate cost |
|---|---|
| Tripo v3.1 text → 3D | $0.30 |
| Tripo v3.1 image → 3D | $0.40 |
| Meshy-6 (text or image) | $0.80 |

Costs are shown in the panel after each generation. The exact amount depends on your Runware plan and any active credits. Check [runware.ai/pricing](https://runware.ai/pricing) for current rates.

---

## Limitations

- **One generation at a time** — queue or parallel generation is not yet supported
- **Single Reference Image** — multiple reference images for Image to 3D is not yet supported
- **Polling only** — status is checked every 3 seconds; there are no push callbacks
- **10-minute timeout** — if the API hasn't responded in 10 minutes, the job is surfaced as timed out (it may still complete on the Runware side)
- **Reference image size limit** — reference images must be under 20 MB
- **No viewport render shortcut** — Image-to-3D from a Blender render requires saving the render to disk first
- **Model Availability** - Meshy-6 and Tripo V3.1 are available in this version. I will expand to cover all of [Runware's 3D Models](https://runware.ai/collections/best-3d-models) in a later version.

---

## Known issues

- **Meshy-6 Pose (A-Pose / T-Pose) has no effect** — the parameter is accepted but the output ignores it.
- **Meshy-6 Texture Prompt has no effect** — the parameter is accepted but does not influence texturing.
- **Tripo Smart Low-Poly is disabled** — the setting is not yet functional and will be available in a future release.

---

## Contributing

Bug reports and pull requests are welcome. Please open an issue before starting significant work so we can discuss direction.

---

## License

MIT — see [LICENSE](LICENSE).
