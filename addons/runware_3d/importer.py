"""Download a model from a URL, save to output folder, and import into the scene."""

import os
import shutil
import socket
import tempfile
import urllib.request
import urllib.error

import bpy

DOWNLOAD_TIMEOUT = 120  # seconds


class ModelImportError(Exception):
    pass


def download_model(url, fmt="GLB"):
    """Download model to a temp file, return the file path."""
    suffix = f".{fmt.lower()}"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as resp:
            with open(tmp.name, "wb") as f:
                shutil.copyfileobj(resp, f)
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise ModelImportError(f"Failed to download {fmt}: {e}") from e
    return tmp.name


def save_to_output_folder(tmp_path, output_folder, filename):
    """Copy the temp file to the output folder with the given filename."""
    os.makedirs(output_folder, exist_ok=True)
    dest = os.path.join(output_folder, filename)
    try:
        shutil.copy2(tmp_path, dest)
    except OSError as e:
        raise ModelImportError(f"Could not save to output folder: {e}") from e
    return dest


def import_model(filepath, fmt="GLB"):
    """Import a model file at world origin and return the imported objects."""
    if not os.path.isfile(filepath):
        raise ModelImportError(f"File not found: {filepath}")

    before = set(bpy.data.objects)

    try:
        if fmt.upper() == "FBX":
            bpy.ops.import_scene.fbx(filepath=filepath)
        else:
            bpy.ops.import_scene.gltf(filepath=filepath)
    except Exception as e:
        raise ModelImportError(f"Blender import failed ({fmt}): {e}") from e

    imported = list(set(bpy.data.objects) - before)

    try:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in imported:
            obj.select_set(True)
        if imported and bpy.context.view_layer:
            bpy.context.view_layer.objects.active = imported[0]
    except Exception:
        pass  # Selection failure is cosmetic — import already succeeded

    return imported


def download_and_save(url, fmt, output_folder, filename):
    """
    Download from URL and save permanently. Safe to call from a background thread.
    Returns the saved filepath. Does NOT import into Blender.
    """
    tmp_path = download_model(url, fmt)
    try:
        saved_path = save_to_output_folder(tmp_path, output_folder, filename)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return saved_path


def download_save_and_import(url, fmt, output_folder, filename):
    """Full pipeline: download, save, and import. Kept for external callers."""
    saved_path = download_and_save(url, fmt, output_folder, filename)
    import_model(saved_path, fmt)
    return saved_path
