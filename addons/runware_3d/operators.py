import datetime
import threading
import time

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty, FloatProperty

from . import api, history, importer
from .preferences import get_api_key, get_output_folder

POLL_INTERVAL = 3.0     # seconds between status checks
MAX_POLL_RETRIES = 3    # consecutive network errors before giving up
MAX_POLL_DURATION = 600 # seconds before timing out (10 minutes)

# ─── History cache — avoids reading JSON on every panel redraw ────────────────

class _HistoryCache:
    def __init__(self):
        self._entries = None
        self._folder = None

    def get(self, output_folder):
        if self._entries is None or self._folder != output_folder:
            try:
                self._entries = history.load(output_folder)
            except Exception:
                self._entries = []
            self._folder = output_folder
        return self._entries

    def invalidate(self):
        self._entries = None


_history_cache = _HistoryCache()

# Shared state written by background thread, read by timer on main thread
_state = {
    "running": False,
    "task_uuid": None,
    "status": "idle",        # idle | generating | polling | importing | done | error
    "message": "",
    "file_url": None,
    "file_fmt": "GLB",
    "saved_path": None,      # local path set by thread after download; timer imports from here
    "last_cost": None,
    "last_prompt": "",
    "last_model": "",
    "last_mode": "",
    "last_timestamp": "",
    "last_output_folder": None,  # resolved at generation time; used for history reads
    "elapsed": 0.0,
    "cancelled": False,
}
_state_lock = threading.Lock()


def _set_state(**kwargs):
    if "message" in kwargs and not isinstance(kwargs["message"], str):
        kwargs["message"] = str(kwargs["message"])
    with _state_lock:
        _state.update(kwargs)


def get_state():
    with _state_lock:
        return dict(_state)


# ─── Background thread ────────────────────────────────────────────────────────

def _generation_thread(api_key, model, mode, prompt, image_path, tripo_settings, tripo_top, meshy_settings, timestamp, output_folder, filename):
    start = time.monotonic()

    try:
        # 1. Submit the job
        _set_state(status="generating", message="Submitting to Runware…")

        IMAGE_SIZE_LIMIT = 20 * 1024 * 1024  # 20 MB

        image_urls = None
        if mode == "image" and image_path:
            import base64, mimetypes, os as _os
            if not _os.path.isfile(image_path):
                _set_state(status="error", message=f"Image file not found: {image_path}", running=False)
                return
            try:
                file_size = _os.path.getsize(image_path)
                if file_size > IMAGE_SIZE_LIMIT:
                    _set_state(
                        status="error",
                        message=f"Image is too large ({file_size // (1024*1024)} MB). Please use an image under 20 MB.",
                        running=False,
                    )
                    return
                mime = mimetypes.guess_type(image_path)[0] or "image/png"
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                image_urls = [f"data:{mime};base64,{b64}"]
            except OSError as e:
                _set_state(status="error", message=f"Could not read image: {e}", running=False)
                return

        if model == "tripo":
            task_uuid = api.submit_tripo(
                api_key,
                prompt=prompt if mode == "text" else None,
                image_urls=image_urls,
                settings=tripo_settings or None,
                extra=tripo_top or None,
            )
        else:
            task_uuid = api.submit_meshy(
                api_key,
                prompt=prompt if mode == "text" else None,
                image_urls=image_urls,
                settings=meshy_settings or None,
            )

        _set_state(task_uuid=task_uuid, status="polling", message="Generating 3D model…")

        # 2. Poll until done or cancelled, with retry on transient network errors
        poll_errors = 0
        poll_start = time.monotonic()
        while True:
            if time.monotonic() - poll_start > MAX_POLL_DURATION:
                _set_state(
                    status="error",
                    message=f"Generation timed out after {MAX_POLL_DURATION // 60} minutes — the job may still be running. Check your Runware dashboard.",
                    running=False,
                )
                return
            with _state_lock:
                if _state["cancelled"]:
                    _state.update(status="idle", message="Cancelled.", running=False)
                    return

            time.sleep(POLL_INTERVAL)
            elapsed = time.monotonic() - start
            _set_state(elapsed=elapsed, message=f"Generating 3D model… ({int(elapsed)}s)")

            with _state_lock:
                if _state["cancelled"]:
                    _state.update(status="idle", message="Cancelled.", running=False)
                    return

            try:
                result = api.poll_task(api_key, task_uuid)
                poll_errors = 0  # reset on success
            except api.RunwareAPIError as e:
                poll_errors += 1
                if poll_errors >= MAX_POLL_RETRIES:
                    _set_state(status="error", message=f"Lost connection after {MAX_POLL_RETRIES} retries: {e}", running=False)
                    return
                _set_state(message=f"Network error, retrying… ({poll_errors}/{MAX_POLL_RETRIES})")
                continue

            if result["status"] == "completed":
                file_url = result["file_url"]
                if not file_url:
                    import json as _json
                    _set_state(
                        status="error",
                        message=f"Got 'success' but no URL found. Raw: {_json.dumps(result.get('raw', {}))}",
                        running=False,
                    )
                    return
                fmt = result.get("format", "GLB")
                _set_state(
                    status="importing",
                    message="Downloading…",
                    file_url=file_url,
                    file_fmt=fmt,
                    last_cost=result.get("cost"),
                )

                # Download and save on the background thread — keeps main thread free
                # output_folder was computed on the main thread; fix the file extension for the real fmt
                actual_filename = filename.rsplit(".", 1)[0] + "." + fmt.lower()
                try:
                    saved_path = importer.download_and_save(file_url, fmt, output_folder, actual_filename)
                except Exception as e:
                    _set_state(status="error", message=f"Download failed: {e}", running=False)
                    return

                # Check cancel one final time before signalling the timer to import
                with _state_lock:
                    if _state["cancelled"]:
                        _state.update(status="idle", message="Cancelled.", running=False)
                        return

                # Signal timer: file is ready locally, just needs bpy import
                _set_state(
                    status="importing",
                    message="Importing…",
                    saved_path=saved_path,
                )
                return  # timer on main thread handles the bpy import

            elif result["status"] == "failed":
                _set_state(
                    status="error",
                    message=f"Generation failed: {result['error']}",
                    running=False,
                )
                return

            # still pending — loop again

    except api.RunwareAPIError as e:
        _set_state(status="error", message=str(e), running=False)
    except Exception as e:
        _set_state(status="error", message=f"Unexpected error: {e}", running=False)


# ─── Timer callback (main thread) ─────────────────────────────────────────────

def _tag_redraw():
    try:
        screen = bpy.context.screen
        if screen is None:
            return
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    except Exception:
        pass


def _timer_callback():
    state = get_state()

    if state["status"] == "importing" and state.get("saved_path"):
        # Download already done by background thread — just do the bpy import here
        try:
            saved_path = state["saved_path"]
            fmt = state.get("file_fmt", "GLB")
            importer.import_model(saved_path, fmt)
            output_folder = state.get("last_output_folder") or get_output_folder()
            history.add_entry(
                output_folder,
                model=state.get("last_model", ""),
                mode=state.get("last_mode", ""),
                prompt=state.get("last_prompt", ""),
                filepath=saved_path,
                cost=state.get("last_cost"),
                timestamp=state.get("last_timestamp", ""),
            )
            _set_state(status="done", message="Done! Model imported at origin.", running=False)
            _history_cache.invalidate()
        except Exception as e:
            _set_state(status="error", message=str(e), running=False)
        _tag_redraw()
        return None  # unregister timer

    if state["status"] in ("done", "error", "idle") and not state["running"]:
        _tag_redraw()
        return None  # unregister timer

    # Still running — redraw and reschedule
    _tag_redraw()
    return POLL_INTERVAL


# ─── Operators ────────────────────────────────────────────────────────────────

class RUNWARE_OT_Generate(Operator):
    bl_idname = "runware.generate"
    bl_label = "Generate 3D Model"
    bl_description = "Send a generation request to Runware and import the result"

    @classmethod
    def poll(cls, context):
        return not get_state()["running"]

    def execute(self, context):
        api_key = get_api_key()
        if not api_key:
            self.report({"ERROR"}, "No API key set. Go to Edit > Preferences > Add-ons > Runware 3D.")
            return {"CANCELLED"}

        props = context.scene.runware_props

        if props.mode == "text" and not props.prompt.strip():
            self.report({"ERROR"}, "Prompt cannot be empty.")
            return {"CANCELLED"}

        if props.mode == "image" and not props.image_path.strip():
            self.report({"ERROR"}, "Please select an image file.")
            return {"CANCELLED"}

        # Tripo image mode and quad=true output FBX — check importer is available
        if props.model == "tripo" and (props.mode == "image" or props.tripo_quad):
            if "IMPORT_SCENE_OT_fbx" not in dir(bpy.types):
                reason = "image-to-3D" if props.mode == "image" else "Quad Mesh (outputs FBX)"
                self.report(
                    {"ERROR"},
                    f"Tripo {reason} requires the FBX importer. "
                    "Go to Edit > Preferences > Add-ons and enable 'Import-Export: FBX format'.",
                )
                return {"CANCELLED"}

        # Build advanced settings dicts
        tripo_settings = {}
        tripo_top = {}   # top-level Tripo fields (not inside settings{})
        meshy_settings = {}

        if props.model == "tripo":
            if props.tripo_geometry_quality != "standard":
                tripo_settings["geometryQuality"] = props.tripo_geometry_quality
            if props.tripo_texture_quality != "standard":
                tripo_settings["textureQuality"] = props.tripo_texture_quality
            if props.tripo_quad:
                tripo_settings["quad"] = True
            # faceLimit: only send when > 0 (0 means "no limit"); API min is 500 when sent
            if props.tripo_face_limit >= 500:
                tripo_settings["faceLimit"] = props.tripo_face_limit
            tripo_settings["pbr"] = props.tripo_pbr
            tripo_settings["texture"] = True if props.mode == "image" else props.tripo_texture
            if props.tripo_texture_alignment != "default" and props.mode == "image":
                tripo_settings["textureAlignment"] = props.tripo_texture_alignment
            if props.tripo_negative_prompt.strip() and props.mode == "text":
                tripo_top["negativePrompt"] = props.tripo_negative_prompt.strip()[:255]
            if props.tripo_seed > 0:
                tripo_top["seed"] = props.tripo_seed
        else:
            is_lowpoly = props.meshy_mesh_type == "lowpoly"
            meshy_settings["meshType"] = props.meshy_mesh_type
            if not is_lowpoly:
                # polyCount and topology require remesh=true; only valid for standard mesh
                needs_remesh = False
                if props.meshy_poly_count != 30000:
                    meshy_settings["polyCount"] = props.meshy_poly_count
                    needs_remesh = True
                if props.meshy_topology != "triangle":
                    meshy_settings["topology"] = props.meshy_topology
                    needs_remesh = True
                if needs_remesh:
                    meshy_settings["remesh"] = True
            meshy_settings["texture"] = props.meshy_texture
            if props.meshy_texture:
                meshy_settings["pbr"] = props.meshy_pbr
                if props.meshy_hd_texture:
                    meshy_settings["hdTexture"] = True
                meshy_settings["removeLighting"] = props.meshy_remove_lighting
                if props.meshy_texture_prompt.strip() and props.mode == "text":
                    meshy_settings["texturePrompt"] = props.meshy_texture_prompt.strip()[:600]
            if props.meshy_pose != "none":
                meshy_settings["pose"] = props.meshy_pose
            if props.meshy_symmetry != "auto":
                meshy_settings["symmetry"] = props.meshy_symmetry

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Compute output_folder and filename on the main thread — bpy calls are not thread-safe
        output_folder = get_output_folder()
        filename = history.make_filename(
            props.prompt if props.mode == "text" else "",
            props.model,
            "GLB",  # placeholder fmt; thread will use the real fmt from the API response
            timestamp,
        )

        _set_state(
            running=True,
            task_uuid=None,
            status="generating",
            message="Starting…",
            file_url=None,
            file_fmt="GLB",
            saved_path=None,
            last_cost=None,
            last_prompt=props.prompt if props.mode == "text" else "",
            last_model=props.model,
            last_mode=props.mode,
            last_timestamp=timestamp,
            last_output_folder=output_folder,
            elapsed=0.0,
            cancelled=False,
        )

        thread = threading.Thread(
            target=_generation_thread,
            args=(
                api_key,
                props.model,
                props.mode,
                props.prompt,
                props.image_path,
                tripo_settings or None,
                tripo_top or None,
                meshy_settings or None,
                timestamp,
                output_folder,
                filename,
            ),
            daemon=True,
        )
        thread.start()

        if bpy.app.timers.is_registered(_timer_callback):
            bpy.app.timers.unregister(_timer_callback)
        bpy.app.timers.register(_timer_callback, first_interval=POLL_INTERVAL)

        return {"FINISHED"}


class RUNWARE_OT_Cancel(Operator):
    bl_idname = "runware.cancel"
    bl_label = "Cancel Generation"
    bl_description = "Cancel the running generation job"

    @classmethod
    def poll(cls, context):
        return get_state()["running"]

    def execute(self, context):
        _set_state(cancelled=True, message="Cancelling…")
        return {"FINISHED"}


class RUNWARE_OT_OpenPreferences(Operator):
    bl_idname = "runware.open_preferences"
    bl_label = "Set API Key"
    bl_description = "Open Runware addon preferences to enter your API key"

    def execute(self, context):
        bpy.ops.screen.userpref_show()
        bpy.context.preferences.active_section = "ADDONS"
        return {"FINISHED"}


class RUNWARE_OT_Dismiss(Operator):
    bl_idname = "runware.dismiss"
    bl_label = "Dismiss"
    bl_description = "Dismiss the status message"

    def execute(self, context):
        _set_state(status="idle", message="", running=False)
        return {"FINISHED"}


class RUNWARE_OT_ReimportModel(Operator):
    bl_idname = "runware.reimport_model"
    bl_label = "Re-import"
    bl_description = "Import this previously generated model into the current scene"

    filepath: StringProperty()
    fmt: StringProperty(default="GLB")

    def execute(self, context):
        import os
        if not os.path.exists(self.filepath):
            self.report({"ERROR"}, f"File not found: {self.filepath}")
            return {"CANCELLED"}
        try:
            importer.import_model(self.filepath, self.fmt)
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        return {"FINISHED"}


class RUNWARE_OT_RefreshHistory(Operator):
    bl_idname = "runware.refresh_history"
    bl_label = "Refresh History"
    bl_description = "Re-scan the output folder and update the history list"

    def execute(self, context):
        _history_cache.invalidate()
        return {"FINISHED"}


class RUNWARE_OT_ShowInExplorer(Operator):
    bl_idname = "runware.show_in_explorer"
    bl_label = "Show in Explorer"
    bl_description = "Open the folder containing this file in the system file browser"

    filepath: StringProperty()

    def execute(self, context):
        import os, subprocess, sys
        folder = os.path.dirname(self.filepath)
        if not os.path.exists(folder):
            self.report({"ERROR"}, f"Folder not found: {folder}")
            return {"CANCELLED"}
        if sys.platform == "win32":
            # Select the file in Explorer rather than just opening the folder
            subprocess.Popen(["explorer", "/select,", self.filepath])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", self.filepath])
        else:
            subprocess.Popen(["xdg-open", folder])
        return {"FINISHED"}


# ─── Scene properties ─────────────────────────────────────────────────────────

class RunwareProperties(bpy.types.PropertyGroup):
    model: EnumProperty(
        name="Model",
        items=[
            ("tripo", "Tripo v3.1", "Tripo 3D v3.1 — text or image to 3D"),
            ("meshy", "Meshy-6", "Meshy-6 — text or image to 3D"),
        ],
        default="tripo",
    )
    mode: EnumProperty(
        name="Mode",
        items=[
            ("text", "Text to 3D", "Generate from a text prompt"),
            ("image", "Image to 3D", "Generate from a reference image"),
        ],
        default="text",
    )
    prompt: StringProperty(
        name="Prompt",
        description="Describe the 3D model you want to generate",
        default="",
    )
    image_path: StringProperty(
        name="Image",
        description="Reference image for image-to-3D generation",
        default="",
        subtype="FILE_PATH",
    )

    # Tripo advanced
    tripo_geometry_quality: EnumProperty(
        name="Geometry Quality",
        items=[("standard", "Standard", "Balanced detail and speed"), ("detailed", "Detailed", "Maximum geometric detail, slower")],
        default="standard",
    )
    tripo_texture_quality: EnumProperty(
        name="Texture Quality",
        items=[("standard", "Standard", "Balanced quality and speed"), ("detailed", "Detailed", "Higher resolution textures")],
        default="standard",
    )
    tripo_face_limit: IntProperty(
        name="Face Limit",
        description="Maximum faces in output mesh (0 = no limit). API minimum is 500 when set",
        default=0, min=0, max=20000,
    )
    tripo_pbr: BoolProperty(name="PBR", default=True, description="Physically-based rendering materials")
    tripo_texture: BoolProperty(name="Texture", default=True, description="Generate texture. Disabled in image mode (always on)")
    tripo_quad: BoolProperty(name="Quad Mesh", default=False, description="Quad topology output. Forces FBX format — requires FBX importer")
    tripo_smart_low_poly: BoolProperty(name="Smart Low-Poly", default=False, description="Optimised low-poly reduction. May fail on complex models")
    tripo_negative_prompt: StringProperty(
        name="Negative Prompt",
        description="Describe what to exclude from the generation (text mode only)",
        default="",
    )
    tripo_seed: IntProperty(
        name="Seed",
        description="Seed for reproducible results (0 = random)",
        default=0, min=0, max=20240919,
    )
    tripo_texture_alignment: EnumProperty(
        name="Texture Alignment",
        description="Whether texture should match the source image or the geometry",
        items=[
            ("default", "Default", "Let the model decide"),
            ("original_image", "Match Image", "Prioritise visual fidelity to source image"),
            ("geometry", "Match Geometry", "Prioritise structural accuracy"),
        ],
        default="default",
    )

    # Meshy advanced
    meshy_mesh_type: EnumProperty(
        name="Mesh Type",
        items=[
            ("standard", "Standard", "Full-detail mesh with topology and polycount control"),
            ("lowpoly", "Low-Poly", "Stylised low-poly output — topology/polycount controls disabled"),
        ],
        default="standard",
    )
    meshy_poly_count: IntProperty(
        name="Poly Count",
        description="Target polygon count (standard mesh type only)",
        default=30000, min=100, max=300000,
    )
    meshy_topology: EnumProperty(
        name="Topology",
        description="Output mesh topology (standard mesh type only)",
        items=[("triangle", "Triangle", "Triangulated mesh"), ("quad", "Quad", "Quad mesh — cleaner for animation and subdivision")],
        default="triangle",
    )
    meshy_texture: BoolProperty(name="Texture", default=True, description="Generate colour texture")
    meshy_pbr: BoolProperty(name="PBR", default=True, description="Generate PBR maps (metallic, roughness, normal)")
    meshy_hd_texture: BoolProperty(name="HD Texture", default=False, description="4K base colour texture (PBR maps always at 2K)")
    meshy_remove_lighting: BoolProperty(name="Remove Lighting", default=True, description="Strip baked highlights and shadows for cleaner custom lighting in Blender")
    meshy_pose: EnumProperty(
        name="Pose",
        items=[("none", "None", ""), ("a-pose", "A-Pose", ""), ("t-pose", "T-Pose", "")],
        default="none",
    )
    meshy_symmetry: EnumProperty(
        name="Symmetry",
        items=[("auto", "Auto", ""), ("on", "On", ""), ("off", "Off", "")],
        default="auto",
    )
    meshy_texture_prompt: StringProperty(
        name="Texture Prompt",
        description="Additional prompt to guide the texturing (text mode only)",
        default="",
    )

    show_advanced: BoolProperty(name="Advanced", default=False)


CLASSES = [
    RunwareProperties,
    RUNWARE_OT_Generate,
    RUNWARE_OT_Cancel,
    RUNWARE_OT_OpenPreferences,
    RUNWARE_OT_Dismiss,
    RUNWARE_OT_RefreshHistory,
    RUNWARE_OT_ReimportModel,
    RUNWARE_OT_ShowInExplorer,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.runware_props = bpy.props.PointerProperty(type=RunwareProperties)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.runware_props
