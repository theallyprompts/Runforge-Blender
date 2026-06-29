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
