import os

import bpy
from bpy.types import Panel

from . import history
from .operators import get_state
from .preferences import get_api_key, get_output_folder, get_preset

# Brand colours as 0–1 float tuples (Blender uses linear RGB)
# #90F77C → (0.565, 0.969, 0.486)
# #1B1B1B → (0.106, 0.106, 0.106)
COLOR_GREEN = (0.565, 0.969, 0.486, 1.0)
COLOR_DARK = (0.106, 0.106, 0.106, 1.0)


def _separator(layout, factor=0.3):
    layout.separator(factor=factor)


class RUNWARE_PT_Main(Panel):
    bl_label = ""
    bl_idname = "RUNWARE_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Runware"
    bl_order = 0

    def draw_header(self, context):
        # Draw the Runware logo mark as a row of parallelogram-style icons
        # Blender doesn't support custom images in panel headers easily,
        # so we use the brand name with an icon accent.
        self.layout.label(text="RUNWARE", icon="SHADING_RENDERED")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False

        # ── Welcome / brand block ──────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 0.9

        row = col.row()
        row.label(text="Text & Image to 3D", icon="MESH_ICOSPHERE")
        col.label(text="Powered by Runware.ai", icon="BLANK1")

        _separator(layout)

        # ── API key status ─────────────────────────────────────────────────
        api_key = get_api_key()
        if not api_key:
            key_box = layout.box()
            key_col = key_box.column(align=True)
            row = key_col.row()
            row.alert = True
            row.label(text="No API key set", icon="ERROR")
            key_col.operator("runware.open_preferences", text="Set API Key in Preferences", icon="KEY_HLT")

        _separator(layout)

        # ── Generation form ────────────────────────────────────────────────
        props = context.scene.runware_props
        state = get_state()
        is_running = state["running"]

        form = layout.box()
        form_col = form.column(align=True)

        # Model selector
        form_col.label(text="Model", icon="MODIFIER")
        form_col.prop(props, "model", text="")
        _separator(form_col)

        # Mode toggle
        form_col.label(text="Mode", icon="IMAGE_DATA")
        row = form_col.row(align=True)
        row.prop_enum(props, "mode", "text")
        row.prop_enum(props, "mode", "image")
        _separator(form_col)

        # Prompt / image input
        if props.mode == "text":
            form_col.label(text="Prompt", icon="SYNTAX_ON")
            form_col.prop(props, "prompt", text="")
            if props.model == "tripo":
                form_col.prop(props, "tripo_negative_prompt", text="Negative Prompt")
        else:
            form_col.label(text="Reference Image", icon="IMAGE_REFERENCE")
            form_col.prop(props, "image_path", text="")

        _separator(form_col)

        # ── Advanced settings (collapsible) ────────────────────────────────
        adv_row = form_col.row()
        adv_row.prop(
            props,
            "show_advanced",
            text="Advanced Settings",
            icon="TRIA_DOWN" if props.show_advanced else "TRIA_RIGHT",
            emboss=False,
        )

        if props.show_advanced:
            adv_box = form_col.box()
            adv_col = adv_box.column(align=True)

            if props.model == "tripo":
                adv_col.label(text="Tripo v3.1", icon="MODIFIER_ON")
                adv_col.prop(props, "tripo_geometry_quality")
                adv_col.prop(props, "tripo_texture_quality")
                align_row = adv_col.row()
                align_row.enabled = props.mode == "image"
                align_row.prop(props, "tripo_texture_alignment")
                adv_col.prop(props, "tripo_face_limit")
                row = adv_col.row()
                row.prop(props, "tripo_pbr")
                texture_row = row.row()
                texture_row.enabled = props.mode != "image"
                texture_row.prop(props, "tripo_texture")
                row = adv_col.row()
                row.prop(props, "tripo_quad")
                slp_row = row.row()
                slp_row.enabled = False
                slp_row.prop(props, "tripo_smart_low_poly")
                if props.mode == "text":
                    _separator(adv_col, factor=0.5)
                    adv_col.prop(props, "tripo_seed")
            else:
                is_lowpoly = props.meshy_mesh_type == "lowpoly"
                adv_col.label(text="Meshy-6", icon="MODIFIER_ON")
                adv_col.prop(props, "meshy_mesh_type")
                # polyCount and topology are disabled for low-poly mesh type
                poly_row = adv_col.row()
                poly_row.enabled = not is_lowpoly
                poly_row.prop(props, "meshy_poly_count")
                topo_row = adv_col.row()
                topo_row.enabled = not is_lowpoly
                topo_row.prop(props, "meshy_topology", expand=True)
                adv_col.prop(props, "meshy_pose")
                adv_col.prop(props, "meshy_symmetry")
                _separator(adv_col, factor=0.5)
                row = adv_col.row()
                row.prop(props, "meshy_texture")
                row.prop(props, "meshy_pbr")
                tex_sub = adv_col.column(align=True)
                tex_sub.enabled = props.meshy_texture
                row = tex_sub.row()
                row.prop(props, "meshy_hd_texture")
                row.prop(props, "meshy_remove_lighting")
                if props.mode == "text":
                    tex_sub.prop(props, "meshy_texture_prompt", text="Texture Prompt")

        _separator(form_col)

        # ── Generate / Cancel button ───────────────────────────────────────
        btn_row = form_col.row(align=True)
        btn_row.scale_y = 1.6

        if is_running:
            btn_row.enabled = True
            btn_row.operator("runware.cancel", text="Cancel", icon="X")
        else:
            btn_row.enabled = bool(api_key)
            btn_row.operator("runware.generate", text="Generate", icon="PLAY")

        # ── Status panel ───────────────────────────────────────────────────
        status = state["status"]
        message = state["message"]
        elapsed = state["elapsed"]

        if status not in ("idle", "done") or message:
            _separator(layout)
            status_box = layout.box()
            s_col = status_box.column(align=True)

            if status == "error":
                row = s_col.row()
                row.alert = True
                row.label(text="Error", icon="ERROR")
                # Word-wrap long messages
                for line in _wrap_text(message, 32):
                    s_col.label(text=line)
                s_col.operator("runware.dismiss", text="Dismiss", icon="X")

            elif status == "done":
                s_col.label(text="Done!", icon="CHECKMARK")
                s_col.label(text=message)
                s_col.operator("runware.dismiss", text="Dismiss", icon="X")

            elif status in ("generating", "polling"):
                s_col.label(text=message, icon="TIME")
                if elapsed > 0:
                    s_col.label(text=f"Elapsed: {int(elapsed)}s", icon="BLANK1")

            elif status == "importing":
                s_col.label(text=message, icon="IMPORT")

        # ── Cost footer ────────────────────────────────────────────────────
        _separator(layout)
        hint = layout.row()
        hint.enabled = False
        last_cost = state.get("last_cost")
        if last_cost is not None:
            hint.label(text=f"Last generation: ${last_cost:.4f}", icon="BLANK1")
        else:
            if props.model == "tripo":
                est = "$0.30" if props.mode == "text" else "$0.40"
            else:
                est = "$0.80"
            hint.label(text=f"Est. cost: {est} / generation", icon="BLANK1")


def _wrap_text(text, width):
    """Split text into lines of at most `width` characters."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


class RUNWARE_PT_History(Panel):
    bl_label = "History"
    bl_idname = "RUNWARE_PT_history"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Runware"
    bl_order = 1
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        try:
            from .operators import _history_cache, get_state as _get_state
            state = _get_state()
            output_folder = state.get("last_output_folder") or get_output_folder()
            entries = _history_cache.get(output_folder)
        except Exception:
            layout.label(text="Could not load history.", icon="ERROR")
            return

        row = layout.row()
        row.operator("runware.refresh_history", text="Refresh", icon="FILE_REFRESH")

        if not entries:
            layout.label(text="No generations yet.", icon="INFO")
            return

        for entry in entries:
            box = layout.box()
            col = box.column(align=True)

            # Row 1: prompt/label + timestamp (right-aligned)
            prompt = entry.get("prompt", "").strip()
            display = prompt[:28] + "…" if len(prompt) > 28 else prompt or "Image to 3D"
            mode_icon = "SYNTAX_ON" if entry.get("mode") == "text" else "IMAGE_REFERENCE"
            ts = entry.get("timestamp", "")
            row = col.row()
            row.label(text=display, icon=mode_icon)
            sub = row.row()
            sub.alignment = "RIGHT"
            sub.enabled = False
            sub.label(text=ts[:10] if ts else "")

            # Row 2: model + cost + buttons
            row = col.row(align=True)
            model_label = "Tripo v3.1" if entry.get("model") == "tripo" else "Meshy-6"
            cost = entry.get("cost")
            cost_str = f"${cost:.2f}" if cost is not None else ""
            row.label(text=f"{model_label}  {cost_str}")

            filepath = entry.get("filepath", "")
            fmt = "FBX" if filepath.lower().endswith(".fbx") else "GLB"

            op = row.operator("runware.reimport_model", text="", icon="IMPORT")
            op.filepath = filepath
            op.fmt = fmt

            op2 = row.operator("runware.show_in_explorer", text="", icon="FILE_FOLDER")
            op2.filepath = filepath


CLASSES = [RUNWARE_PT_Main, RUNWARE_PT_History]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
