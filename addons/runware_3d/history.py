"""Persistent generation history stored as JSON next to the output files."""

import json
import os
import re
import tempfile

HISTORY_FILENAME = "runware_history.json"
PROMPT_MAX_CHARS = 40
MAX_ENTRIES = 10


def _history_path(output_folder):
    return os.path.join(output_folder, HISTORY_FILENAME)


def load(output_folder):
    """Return list of history entries, newest first, pruned to files that exist on disk."""
    path = _history_path(output_folder)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []

    # Drop entries whose files no longer exist on disk
    valid = [e for e in entries if os.path.isfile(e.get("filepath", ""))]

    # Write back atomically if any were pruned
    if len(valid) != len(entries):
        try:
            _atomic_save(path, valid)
        except OSError:
            pass

    return valid


def save(output_folder, entries):
    _atomic_save(_history_path(output_folder), entries)


def _atomic_save(path, entries):
    """Write JSON to a temp file then rename — prevents corruption on partial writes."""
    folder = os.path.dirname(path)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
        except Exception:
            os.unlink(tmp_path)
            raise
        os.replace(tmp_path, path)  # atomic on POSIX; near-atomic on Windows
    except OSError as e:
        raise OSError(f"Failed to save history: {e}") from e


def add_entry(output_folder, *, model, mode, prompt, filepath, cost, timestamp):
    """Prepend a new entry, cap at MAX_ENTRIES, and write to disk."""
    entries = load(output_folder)
    entries.insert(0, {
        "model": model,
        "mode": mode,
        "prompt": prompt,
        "filepath": filepath,
        "cost": cost,
        "timestamp": timestamp,
    })
    entries = entries[:MAX_ENTRIES]
    save(output_folder, entries)
    return entries


def make_filename(prompt, model, fmt, timestamp):
    """
    Build a filesystem-safe filename like:
      tripo_a-cute-cartoon-cat_2026-06-25_143022.glb
    """
    slug = prompt.strip()[:PROMPT_MAX_CHARS] if prompt else "image-to-3d"
    slug = re.sub(r"[^\w\s-]", " ", slug)
    slug = re.sub(r"\s+", "-", slug.strip()).lower() or "model"
    slug = slug[:40]

    # Safe timestamp parsing — handle missing or short timestamps
    date_str = timestamp[:10] if len(timestamp) >= 10 else "0000-00-00"
    time_part = timestamp[11:19] if len(timestamp) >= 19 else ""
    time_str = time_part.replace(":", "") if time_part else "000000"

    ext = fmt.lower()
    return f"{model}_{slug}_{date_str}_{time_str}.{ext}"
