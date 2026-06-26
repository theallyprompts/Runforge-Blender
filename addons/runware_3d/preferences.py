import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, EnumProperty
import os


PRESET_SETTINGS = {
    "speed": {
        "tripo_geometry_quality":  "standard",
        "tripo_texture_quality":   "standard",
        "tripo_quad":              False,
        "tripo_pbr":               True,
        "tripo_texture":           True,
        "tripo_face_limit":        0,
        "tripo_texture_alignment": "default",
        "meshy_poly_count":        10000,
        "meshy_topology":          "triangle",
        "meshy_hd_texture":        False,
        "meshy_remove_lighting":   True,
    },
    "quality": {
        "tripo_geometry_quality":  "detailed",
        "tripo_texture_quality":   "detailed",
        "tripo_quad":              True,
        "tripo_pbr":               True,
        "tripo_texture":           True,
        "tripo_face_limit":        0,
        "tripo_texture_alignment": "original_image",
        "meshy_poly_count":        50000,
        "meshy_topology":          "quad",
        "meshy_hd_texture":        True,
        "meshy_remove_lighting":   True,
    },
}


class RunwareAddonPreferences(AddonPreferences):
    bl_idname = __package__

    api_key: StringProperty(
        name="API Key",
        description="Your Runware API key (from runware.ai dashboard)",
        default="",
        subtype="PASSWORD",
    )

    output_folder: StringProperty(
        name="Output Folder",
        description="Where generated 3D models are saved. Leave blank to use a 'runware_output' folder next to the .blend file",
        default="",
        subtype="DIR_PATH",
    )

    preset: EnumProperty(
        name="Generation Preset",
        description="Default quality/speed trade-off applied to new generations",
        items=[
            ("speed",   "Speed",   "Standard geometry, smart low-poly — faster and lighter"),
            ("quality", "Quality", "Detailed geometry, quad mesh — best fidelity"),
            ("custom",  "Custom",  "Settings are managed manually in the Advanced panel"),
        ],
        default="custom",
    )

    def draw(self, context):
        layout = self.layout

        layout.label(text="Runware API Key")
        row = layout.row()
        row.prop(self, "api_key", text="")
        row = layout.row()
        row.operator("wm.url_open", text="Get API Key", icon="URL").url = (
            "https://runware.ai/dashboard"
        )

        layout.separator()
        layout.label(text="Output Folder")
        layout.prop(self, "output_folder", text="")
        layout.label(
            text="Defaults to 'runware_output/' next to the .blend file if blank.",
            icon="INFO",
        )

        layout.separator()
        layout.label(text="Generation Preset")
        row = layout.row(align=True)
        row.prop(self, "preset", expand=True)
        if self.preset != "custom":
            layout.operator("runware.apply_preset", text="Apply Preset to Current Scene", icon="CHECKMARK")


def _get_prefs():
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        return None


def get_api_key():
    prefs = _get_prefs()
    if prefs is None:
        return ""
    return prefs.api_key.strip()


def get_output_folder():
    """Return an absolute path to the output folder, creating it if needed."""
    prefs = _get_prefs()
    folder = prefs.output_folder.strip() if prefs else ""

    if folder:
        folder = bpy.path.abspath(folder)
    else:
        blend_path = bpy.data.filepath
        if blend_path:
            folder = os.path.join(os.path.dirname(bpy.path.abspath(blend_path)), "runware_output")
        else:
            folder = os.path.join(os.path.expanduser("~"), "runware_output")

    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        # Fall back to home directory if the configured path isn't writable
        folder = os.path.join(os.path.expanduser("~"), "runware_output")
        os.makedirs(folder, exist_ok=True)

    return folder


def get_preset():
    prefs = _get_prefs()
    return prefs.preset if prefs else "custom"


class RUNWARE_OT_ApplyPreset(bpy.types.Operator):
    bl_idname = "runware.apply_preset"
    bl_label = "Apply Preset"
    bl_description = "Apply the selected preset to the current scene's advanced settings"

    def execute(self, context):
        prefs = _get_prefs()
        if prefs is None or prefs.preset == "custom":
            return {"CANCELLED"}
        settings = PRESET_SETTINGS.get(prefs.preset, {})
        props = context.scene.runware_props
        for key, value in settings.items():
            if hasattr(props, key):
                setattr(props, key, value)
        self.report({"INFO"}, f"Applied '{prefs.preset}' preset.")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(RunwareAddonPreferences)
    bpy.utils.register_class(RUNWARE_OT_ApplyPreset)


def unregister():
    bpy.utils.unregister_class(RUNWARE_OT_ApplyPreset)
    bpy.utils.unregister_class(RunwareAddonPreferences)
