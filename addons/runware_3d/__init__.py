bl_info = {
    "name": "Runware 3D",
    "author": "Runware",
    "version": (0, 1, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Runware",
    "description": "Generate 3D models via Runware API (Tripo v3.1, Meshy-6)",
    "category": "Import-Export",
}

import bpy

from . import preferences, operators, panels, history


def register():
    modules = [preferences, operators, panels]
    registered = []
    try:
        for mod in modules:
            mod.register()
            registered.append(mod)
    except Exception as e:
        # Roll back any modules that did register to avoid partial state
        for mod in reversed(registered):
            try:
                mod.unregister()
            except Exception:
                pass
        raise e


def unregister():
    for mod in reversed([preferences, operators, panels]):
        try:
            mod.unregister()
        except Exception:
            pass
