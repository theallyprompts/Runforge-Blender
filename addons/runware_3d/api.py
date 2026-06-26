"""Runware REST API calls — all network I/O, no bpy imports."""

import json
import uuid
import urllib.request
import urllib.error

BASE_URL = "https://api.runware.ai/v1"


class RunwareAPIError(Exception):
    pass


def _post(api_key, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(body, dict) and body.get("errors"):
                errors = body["errors"]
                if isinstance(errors, list):
                    msgs = "; ".join(
                        err.get("message", str(err)) if isinstance(err, dict) else str(err)
                        for err in errors
                    )
                else:
                    msgs = str(errors)
                raise RunwareAPIError(msgs) from e
        except (json.JSONDecodeError, KeyError):
            pass
        raise RunwareAPIError(f"HTTP {e.code}: {raw.decode('utf-8', errors='replace')}") from e
    except urllib.error.URLError as e:
        raise RunwareAPIError(f"Network error: {e.reason}") from e

    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RunwareAPIError(f"Invalid response from API: {e}") from e

    if isinstance(body, dict) and body.get("errors"):
        errors = body["errors"]
        if isinstance(errors, list):
            msgs = "; ".join(
                err.get("message", str(err)) if isinstance(err, dict) else str(err)
                for err in errors
            )
        else:
            msgs = str(errors)
        raise RunwareAPIError(msgs)

    return body.get("data", []) if isinstance(body, dict) else []


def submit_tripo(api_key, *, prompt=None, image_urls=None, settings=None, extra=None):
    task_uuid = str(uuid.uuid4())
    task = {
        "taskType": "3dInference",
        "taskUUID": task_uuid,
        "model": "tripo:v3.1@0",
        "deliveryMethod": "async",
        "includeCost": True,
    }
    if prompt:
        task["positivePrompt"] = prompt[:1024]
    if image_urls:
        task["inputs"] = {"images": image_urls[:4]}
    if settings:
        task["settings"] = settings
    if extra:
        task.update(extra)
    _post(api_key, [task])
    return task_uuid


def submit_meshy(api_key, *, prompt=None, image_urls=None, settings=None):
    task_uuid = str(uuid.uuid4())
    task = {
        "taskType": "3dInference",
        "taskUUID": task_uuid,
        "model": "meshy:meshy@6",
        "deliveryMethod": "async",
        "includeCost": True,
    }
    if prompt:
        task["positivePrompt"] = prompt[:600]
    if image_urls:
        task["inputs"] = {"images": image_urls[:4]}
    if settings:
        task["settings"] = settings
    _post(api_key, [task])
    return task_uuid


def poll_task(api_key, task_uuid):
    """
    Returns a dict with keys:
      status:   "pending" | "completed" | "failed"
      file_url: str | None
      format:   "GLB" | "FBX"
      cost:     float | None
      error:    str | None
      raw:      dict  (full item, for debugging)
    """
    payload = [{"taskType": "getResponse", "taskUUID": task_uuid}]
    data = _post(api_key, payload)

    if not isinstance(data, list):
        return {"status": "pending", "file_url": None, "format": "GLB", "cost": None, "error": None, "raw": {}}

    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("taskUUID") != task_uuid:
            continue

        task_status = str(item.get("status", "")).lower()

        if task_status in ("success", "succeeded", "completed"):
            # Primary location: outputs.files[0].url
            file_url = None
            outputs = item.get("outputs")
            if isinstance(outputs, dict):
                files = outputs.get("files")
                if isinstance(files, list) and files:
                    first = files[0]
                    file_url = first.get("url") if isinstance(first, dict) else None

            # Fallbacks for alternative response shapes
            if not file_url:
                for key in ("modelUrl", "fileUrl", "outputUrl", "glbUrl", "fbxUrl", "url"):
                    val = item.get(key)
                    if val and isinstance(val, str):
                        file_url = val
                        break
            if not file_url:
                urls = item.get("outputFileUrls")
                if isinstance(urls, list) and urls:
                    file_url = urls[0]

            # Infer format from URL extension if not explicit in response
            fmt = str(item.get("outputFormat", "")).upper()
            if not fmt and file_url:
                fmt = "FBX" if str(file_url).lower().endswith(".fbx") else "GLB"
            fmt = fmt or "GLB"

            cost = item.get("cost")
            cost = float(cost) if cost is not None else None

            return {"status": "completed", "file_url": file_url, "format": fmt, "cost": cost, "error": None, "raw": item}

        elif task_status in ("failed", "error"):
            err = item.get("error") or item.get("message") or "Generation failed"
            return {"status": "failed", "file_url": None, "format": "GLB", "cost": None, "error": str(err), "raw": item}

        else:
            return {"status": "pending", "file_url": None, "format": "GLB", "cost": None, "error": None, "raw": item}

    return {"status": "pending", "file_url": None, "format": "GLB", "cost": None, "error": None, "raw": {}}
