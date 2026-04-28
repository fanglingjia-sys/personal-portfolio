#!/usr/bin/env python3
"""Management server for portfolio site builder.

Extends the static site server with write-capable API:
  GET  /api/status             — { ok: true, manage: true }
  POST /api/add-project        — multipart: title, subtitle, description, images[]
  POST /api/remove-project     — JSON: { project_id }
  POST /api/rebuild            — rebuild site in-place

Run via:
  python manage_server.py --input-dir <folder> [--port 8123] [--open-browser]
"""

from __future__ import annotations

import json
import re
import socketserver
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from site_builder_core import (  # noqa: E402
    IMAGE_EXTENSIONS,
    build_site,
    parse_args,
    read_json,
    resolve_output_dir,
    slugify,
    title_from_stem,
)

# Filename keywords that identify an image as an interaction document
DOC_KEYWORDS = {
    "交互",
    "总览",
    "流程",
    "文档",
    "doc",
    "document",
    "flow",
    "board",
    "mockup",
    "overview",
    "ux",
    "wireframe",
}


# ---------------------------------------------------------------------------
# Multipart form-data parser (no external dependencies)
# ---------------------------------------------------------------------------

def parse_multipart(
    content_type: str, body: bytes
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Return (fields, files) parsed from a multipart/form-data body."""
    boundary_match = re.search(r"boundary=([^\s;]+)", content_type)
    if not boundary_match:
        return {}, []
    boundary = boundary_match.group(1).strip("\"'")
    sep = f"--{boundary}".encode()

    fields: dict[str, str] = {}
    files: list[dict[str, Any]] = []

    for part in body.split(sep):
        part = part.strip(b"\r\n")
        if not part or part in (b"", b"--", b"--\r\n"):
            continue
        if b"\r\n\r\n" not in part:
            continue
        header_bytes, data = part.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]

        headers: dict[str, str] = {}
        for line in header_bytes.decode("utf-8", errors="replace").split("\r\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        disposition = headers.get("content-disposition", "")
        name_m = re.search(r'name="([^"]*)"', disposition)
        filename_m = re.search(r'filename="([^"]*)"', disposition)
        if not name_m:
            continue
        name = name_m.group(1)
        if filename_m:
            files.append(
                {
                    "name": name,
                    "filename": filename_m.group(1),
                    "data": data,
                    "content_type": headers.get("content-type", "application/octet-stream"),
                }
            )
        else:
            fields[name] = data.decode("utf-8", errors="replace")

    return fields, files


# ---------------------------------------------------------------------------
# Project creation helpers
# ---------------------------------------------------------------------------

def classify_image(filename: str) -> str:
    """Return 'interaction_doc' or 'screen' based on filename stem keywords."""
    stem = Path(filename).stem.lower()
    if any(k in stem for k in DOC_KEYWORDS):
        return "interaction_doc"
    return "screen"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    count = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{count}{path.suffix}")
        if not candidate.exists():
            return candidate
        count += 1


def unique_id(base_id: str, existing_ids: set[str]) -> str:
    if base_id not in existing_ids:
        return base_id
    count = 2
    while f"{base_id}-{count}" in existing_ids:
        count += 1
    return f"{base_id}-{count}"


def ensure_index(input_dir: Path) -> dict[str, Any]:
    """Load projects.index.json or return a fresh skeleton."""
    index_path = input_dir / "projects.index.json"
    if index_path.exists():
        return read_json(index_path)
    return {"title": input_dir.name, "projects": []}


def write_index(input_dir: Path, index: dict[str, Any]) -> None:
    path = input_dir / "projects.index.json"
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def create_project(
    input_dir: Path,
    title: str,
    subtitle: str,
    description: str,
    uploaded_files: list[dict[str, Any]],
) -> dict[str, str]:
    """Save uploaded images, create site.meta.json and return the new index entry."""
    index = ensure_index(input_dir)
    existing_ids = {p.get("id", "") for p in index.get("projects", [])}
    project_id = unique_id(slugify(title) or "project", existing_ids)
    project_dir = unique_path(input_dir / project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    interaction_doc: str | None = None
    screens: list[str] = []

    for file_info in uploaded_files:
        fname = Path(file_info["filename"]).name
        if Path(fname).suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        target = unique_path(project_dir / fname)
        target.write_bytes(file_info["data"])
        category = classify_image(fname)
        if category == "interaction_doc" and interaction_doc is None:
            interaction_doc = target.name
        else:
            screens.append(target.name)

    meta: dict[str, Any] = {
        "title": title,
        "subtitle": subtitle,
        "description": description,
    }
    if interaction_doc:
        meta["interaction_doc"] = {
            "file": interaction_doc,
            "title": f"{title} 交互文档",
        }
        meta["hero"] = interaction_doc
    elif screens:
        meta["hero"] = screens[0]

    if screens:
        meta["items"] = [
            {"file": f, "title": title_from_stem(Path(f).stem), "section": "界面"}
            for f in screens
        ]

    meta_path = project_dir / "site.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    entry: dict[str, str] = {
        "id": project_id,
        "path": project_dir.name,
        "title": title,
        "summary": description or subtitle,
    }
    index.setdefault("projects", []).append(entry)
    write_index(input_dir, index)
    return entry


def remove_project(input_dir: Path, project_id: str) -> None:
    """Remove a project entry from projects.index.json."""
    index = ensure_index(input_dir)
    index["projects"] = [p for p in index.get("projects", []) if p.get("id") != project_id]
    write_index(input_dir, index)


def _resolve_project_dir(input_dir: Path, project_id: str) -> Path:
    """Locate a project directory by id via projects.index.json (fallback: id == dir name)."""
    index = ensure_index(input_dir)
    entry = next(
        (p for p in index.get("projects", []) if p.get("id") == project_id),
        None,
    )
    project_path = (entry or {}).get("path") or project_id
    project_dir = (input_dir / project_path).resolve()
    input_resolved = input_dir.resolve()
    if not str(project_dir).startswith(str(input_resolved)):
        raise ValueError("project path escapes input dir")
    if not project_dir.exists():
        raise ValueError(f"project directory not found: {project_dir}")
    return project_dir


def _locate_project_meta(project_dir: Path) -> Path:
    for name in ("site.meta.json", "portfolio.meta.json"):
        candidate = project_dir / name
        if candidate.exists():
            return candidate
    return project_dir / "site.meta.json"


def remove_project_screen(
    input_dir: Path, project_id: str, relative_path: str, delete_file: bool = False
) -> dict[str, Any]:
    """Remove a screen from a project's site.meta.json items[] (optionally delete file)."""
    if not relative_path:
        raise ValueError("relative_path required")

    project_dir = _resolve_project_dir(input_dir, project_id)
    meta_path = _locate_project_meta(project_dir)
    meta = read_json(meta_path) if meta_path.exists() else {}
    items = meta.get("items")
    if not isinstance(items, list):
        raise ValueError("project has no items[] to remove from")

    original_count = len(items)
    meta["items"] = [
        entry for entry in items
        if not (isinstance(entry, dict) and str(entry.get("file", "")).replace("\\", "/") == relative_path)
    ]
    if len(meta["items"]) == original_count:
        raise ValueError(f"no items[] entry matched file='{relative_path}'")

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if delete_file:
        target = (project_dir / relative_path).resolve()
        if str(target).startswith(str(project_dir)) and target.exists():
            target.unlink()

    return {"ok": True, "project_id": project_id, "removed": relative_path}


def add_project_screen(
    input_dir: Path,
    project_id: str,
    upload: dict[str, Any],
    title: str = "",
    section: str = "",
    hover_title: str = "",
    hover_description: str = "",
) -> dict[str, Any]:
    """Save an uploaded image and append a new entry to a project's items[]."""
    raw: bytes = upload.get("data") or b""
    if not raw:
        raise ValueError("uploaded file is empty")

    project_dir = _resolve_project_dir(input_dir, project_id)
    upload_filename = Path(upload.get("filename", "screen")).name or "screen.png"
    if Path(upload_filename).suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"unsupported image type: {Path(upload_filename).suffix}")

    target = unique_path(project_dir / upload_filename)
    target.write_bytes(raw)

    meta_path = _locate_project_meta(project_dir)
    meta = read_json(meta_path) if meta_path.exists() else {}
    items = meta.get("items") if isinstance(meta.get("items"), list) else []

    new_entry = {
        "file": target.name,
        "title": title.strip() or title_from_stem(target.stem),
        "section": section.strip(),
        "hover_title": hover_title.strip(),
        "hover_description": hover_description.strip(),
    }
    items.append(new_entry)
    meta["items"] = items
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "project_id": project_id, "item": new_entry, "file": target.name}


def _deep_set(target: Any, dotted: str, value: Any) -> None:
    """Set a dotted-path value inside nested dicts / lists, creating
    containers as needed. Numeric path parts target list indices, others
    target dict keys."""
    parts = dotted.split(".")
    cur = target
    for i, part in enumerate(parts[:-1]):
        next_part = parts[i + 1]
        next_is_idx = next_part.isdigit()
        if isinstance(cur, list):
            idx = int(part)
            while len(cur) <= idx:
                cur.append({})
            if not isinstance(cur[idx], (dict, list)):
                cur[idx] = [] if next_is_idx else {}
            cur = cur[idx]
        else:
            if part not in cur or not isinstance(cur[part], (dict, list)):
                cur[part] = [] if next_is_idx else {}
            cur = cur[part]
    last = parts[-1]
    if isinstance(cur, list):
        idx = int(last)
        while len(cur) <= idx:
            cur.append(None)
        cur[idx] = value
    else:
        cur[last] = value


# Top-level project entry fields that live in projects.index.json
_PROJECT_INDEX_FIELDS = {"id", "path", "title", "subtitle", "summary", "tags", "labels"}

# Override `screens.<n>.<field>` corresponds to `items.<n>.<field>` in site.meta.json
_RESOURCE_FIELDS_FILE_MAP = {
    "interaction_doc.src": ("interaction_doc.file", "interaction_doc"),
    "card_cover.src": ("card_cover", None),
    "cover.src": ("cover", None),
}


def _strip_asset_prefix(value: str, project_id: str) -> str:
    """Convert 'assets/<project_id>/<rel>' (or '/assets/...') to '<rel>'.
    Leaves anything else untouched (data: URLs, http URLs, raw filenames)."""
    if not isinstance(value, str):
        return value
    v = value.lstrip("./")
    prefix = f"assets/{project_id}/"
    if v.startswith(prefix):
        return v[len(prefix):]
    return value


def apply_text_overrides(
    input_dir: Path,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Walk a nested override tree and dispatch each leaf to the correct
    source file (projects.index.json or per-project site.meta.json).

    Returns:
      {
        "ok": True,
        "applied": int,                # text leaves written
        "skipped_image_data": int,     # data: URL leaves left for image API
        "skipped_orphan": int,         # entries pointing at deleted projects
        "files_modified": [paths]
      }
    """
    if not isinstance(overrides, dict):
        raise ValueError("overrides must be an object")

    index_path = input_dir / "projects.index.json"
    index = read_json(index_path) if index_path.exists() else {"projects": []}
    project_entries = index.get("projects", [])

    metas: dict[Path, dict[str, Any]] = {}

    def get_meta_for_project(idx: int):
        if idx < 0 or idx >= len(project_entries):
            return None, None
        entry = project_entries[idx]
        project_path = entry.get("path") or entry.get("id")
        if not project_path:
            return None, None
        project_dir = (input_dir / project_path).resolve()
        meta_path = _locate_project_meta(project_dir)
        if meta_path not in metas:
            metas[meta_path] = read_json(meta_path) if meta_path.exists() else {}
        return meta_path, metas[meta_path]

    leaves: list[tuple[str, Any]] = []

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if v is None:
                    continue
                walk(v, f"{path}.{i}")
        else:
            leaves.append((path, obj))

    walk(overrides, "")

    applied = 0
    skipped_image = 0
    skipped_orphan = 0

    for path, value in leaves:
        # Skip non-scalar leftovers
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            continue

        # Image data: URL — caller handles via /api/replace-image
        if isinstance(value, str) and value.startswith("data:") and path.endswith(".src"):
            skipped_image += 1
            continue

        if path.startswith("site."):
            sub = path[len("site."):]
            _deep_set(index, sub, value)
            applied += 1
            continue

        if not path.startswith("projects."):
            continue

        rest_parts = path.split(".", 2)
        if len(rest_parts) < 3 or not rest_parts[1].isdigit():
            continue
        proj_idx = int(rest_parts[1])
        rest = rest_parts[2]

        # Skip overrides for projects that no longer exist
        if proj_idx >= len(project_entries):
            skipped_orphan += 1
            continue

        first_token = rest.split(".")[0]
        project_id = project_entries[proj_idx].get("id", "")

        # Path-based src edits (cover/card_cover/interaction_doc/screens/prototype):
        # convert "assets/<project_id>/<rel>" -> "<rel>"
        normalized_value: Any = value
        if path.endswith(".src") and isinstance(value, str) and not value.startswith("data:"):
            normalized_value = _strip_asset_prefix(value, project_id)

        # 1) Top-level project entry fields → projects.index.json
        if first_token in _PROJECT_INDEX_FIELDS:
            _deep_set(index, f"projects.{proj_idx}.{rest}", value)
            applied += 1
            continue

        # 2) Resource src overrides (cover/card_cover/interaction_doc) →
        #    write the resolved relative filename to the source meta file.
        meta_path, meta = get_meta_for_project(proj_idx)
        if meta_path is None or meta is None:
            skipped_orphan += 1
            continue

        if rest in _RESOURCE_FIELDS_FILE_MAP:
            target_field, _ = _RESOURCE_FIELDS_FILE_MAP[rest]
            _deep_set(meta, target_field, normalized_value)
            applied += 1
            continue

        # 3) screens.<n>.<field> → items.<n>.<field>; src path-based →
        #    items.<n>.file
        if rest.startswith("screens."):
            screen_rest = rest[len("screens."):]  # e.g. "2.hover_title" or "2.src"
            tokens = screen_rest.split(".", 1)
            if len(tokens) >= 1 and tokens[0].isdigit():
                screen_idx = tokens[0]
                tail = tokens[1] if len(tokens) > 1 else ""
                if tail == "src":
                    _deep_set(meta, f"items.{screen_idx}.file", normalized_value)
                else:
                    _deep_set(meta, f"items.{screen_idx}.{tail}" if tail else f"items.{screen_idx}", value)
                applied += 1
                continue

        # 4) interaction_doc.<field> / flow.<field> / prototype.<field> /
        #    labels.<key> — direct mapping to site.meta.json
        if rest.startswith(("interaction_doc.", "flow.", "prototype.", "labels.")):
            # Special: prototype.scenes.<n>.src -> prototype.scenes.<n>.file
            if rest.endswith(".src") and rest.startswith("prototype.scenes."):
                rest_no_src = rest[: -len(".src")]
                _deep_set(meta, f"{rest_no_src}.file", normalized_value)
            else:
                _deep_set(meta, rest, value)
            applied += 1
            continue

        # Unknown field — skip silently to avoid corrupting unknown structures
        # (could be an ad-hoc field a user added; safer not to write blindly)

    # Persist modified files
    files_modified: list[str] = []
    if applied:
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        files_modified.append(str(index_path))
        for meta_path, meta in metas.items():
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            files_modified.append(str(meta_path))

    return {
        "ok": True,
        "applied": applied,
        "skipped_image_data": skipped_image,
        "skipped_orphan": skipped_orphan,
        "files_modified": files_modified,
    }


def update_project_flow(
    input_dir: Path,
    project_id: str,
    flow_data: Any,
) -> dict[str, Any]:
    """Replace a project's flow block in site.meta.json with the given structure."""
    if not isinstance(flow_data, dict):
        raise ValueError("flow data must be an object")

    project_dir = _resolve_project_dir(input_dir, project_id)
    meta_path = _locate_project_meta(project_dir)
    meta = read_json(meta_path) if meta_path.exists() else {}

    cleaned: dict[str, Any] = {
        "title": str(flow_data.get("title", "交互流程图") or "交互流程图"),
        "description": str(flow_data.get("description", "")),
        "nodes": [],
        "edges": [],
    }

    raw_nodes = flow_data.get("nodes")
    if isinstance(raw_nodes, list):
        for node in raw_nodes:
            if not isinstance(node, dict) or not str(node.get("id", "")).strip():
                continue
            cleaned["nodes"].append({
                "id": str(node["id"]).strip(),
                "label": str(node.get("label", "")).strip() or str(node["id"]).strip(),
                "screen_id": str(node["screen_id"]).strip() if node.get("screen_id") not in (None, "") else None,
                "col": int(node.get("col", 0) or 0),
                "row": int(node.get("row", 0) or 0),
            })

    # Drop nodes with screen_id=None (cleaner output)
    for node in cleaned["nodes"]:
        if node["screen_id"] is None:
            node.pop("screen_id", None)

    raw_edges = flow_data.get("edges")
    if isinstance(raw_edges, list):
        for edge in raw_edges:
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("from", "")).strip()
            dst = str(edge.get("to", "")).strip()
            if not src or not dst:
                continue
            entry: dict[str, Any] = {
                "from": src,
                "to": dst,
                "label": str(edge.get("label", "")).strip(),
            }
            if str(edge.get("type", "")).strip() == "back":
                entry["type"] = "back"
            cleaned["edges"].append(entry)

    meta["flow"] = cleaned
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "project_id": project_id, "flow": cleaned}


def replace_project_image(
    input_dir: Path,
    project_id: str,
    file_rel: str,
    upload: dict[str, Any],
) -> dict[str, str]:
    """Overwrite a project-local image file with uploaded bytes.

    `file_rel` is the path relative to the project folder (e.g. "1.png", "交互文档.jpg").
    The original filename is preserved so site.meta.json / rendered URLs stay valid.
    """
    raw: bytes = upload.get("data") or b""
    if not raw:
        raise ValueError("uploaded file is empty")
    if not file_rel:
        raise ValueError("file path required")

    # Locate project directory via projects.index.json, fall back to `project_id == dir name`
    index = ensure_index(input_dir)
    entry = next(
        (p for p in index.get("projects", []) if p.get("id") == project_id),
        None,
    )
    project_path = (entry or {}).get("path") or project_id
    project_dir = (input_dir / project_path).resolve()
    input_resolved = input_dir.resolve()
    if not str(project_dir).startswith(str(input_resolved)):
        raise ValueError("project path escapes input dir")

    # Reject path traversal in file_rel
    candidate = (project_dir / file_rel).resolve()
    if not str(candidate).startswith(str(project_dir)):
        raise ValueError("file path escapes project dir")

    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_bytes(raw)
    return {"ok": True, "file": file_rel, "project_id": project_id}


# ---------------------------------------------------------------------------
# Management HTTP handler factory
# ---------------------------------------------------------------------------

def make_management_handler(input_dir: Path, output_dir: Path, args: Any) -> type:
    """Return a request handler class bound to the given paths and args."""

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a: Any, **kw: Any) -> None:
            super().__init__(*a, directory=str(output_dir), **kw)

        def log_message(self, fmt: str, *msg_args: Any) -> None:  # type: ignore[override]
            # Suppress API request noise; keep static-file logs
            path_str = str(msg_args[0]) if msg_args else ""
            if not path_str.startswith("/api"):
                super().log_message(fmt, *msg_args)

        # ---- helpers -------------------------------------------------------

        def send_json(self, data: Any, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", 0))
            return self.rfile.read(length) if length > 0 else b""

        def _rebuild(self) -> None:
            build_site(args)

        # ---- routing -------------------------------------------------------

        def do_OPTIONS(self) -> None:  # type: ignore[override]
            self.send_response(200)
            self.end_headers()

        def end_headers(self) -> None:
            # Static rebuild artifacts (HTML / CSS / JS / JSON) must never be
            # cached so a freshly rebuilt site shows up immediately.
            #
            # Asset images, on the other hand, should be cached briefly: when
            # a user navigates between prototype scenes we must NOT refetch
            # the same image on every click — that's what was causing the
            # visible flash. After an image is replaced via /api/replace-image
            # the client side calls bustAllImages() which appends ?v=<ts> to
            # every <img>, busting the cache for the new bytes.
            req_path = (self.path or "").split("?")[0].lower()
            is_asset = req_path.startswith("/assets/") or req_path.endswith((
                ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
            ))
            if is_asset:
                self.send_header("Cache-Control", "public, max-age=300")
            else:
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self) -> None:  # type: ignore[override]
            clean_path = self.path.split("?")[0]
            if clean_path == "/api/status":
                self.send_json({"ok": True, "manage": True})
                return
            super().do_GET()

        def do_POST(self) -> None:  # type: ignore[override]
            clean_path = self.path.split("?")[0]
            handlers = {
                "/api/add-project": self._handle_add,
                "/api/remove-project": self._handle_remove,
                "/api/replace-image": self._handle_replace_image,
                "/api/add-screen": self._handle_add_screen,
                "/api/remove-screen": self._handle_remove_screen,
                "/api/update-flow": self._handle_update_flow,
                "/api/save-overrides": self._handle_save_overrides,
                "/api/rebuild": self._handle_rebuild,
            }
            fn = handlers.get(clean_path)
            if fn:
                fn()
            else:
                self.send_error(404, "Not Found")

        # ---- API handlers --------------------------------------------------

        def _handle_rebuild(self) -> None:
            try:
                self._rebuild()
                self.send_json({"ok": True})
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

        def _handle_add(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            body = self.read_body()

            if "multipart/form-data" in content_type:
                fields, files = parse_multipart(content_type, body)
            else:
                try:
                    fields = json.loads(body)
                    files = []
                except Exception:
                    self.send_json({"error": "Invalid request body"}, 400)
                    return

            title = fields.get("title", "").strip()
            if not title:
                self.send_json({"error": "title is required"}, 400)
                return

            try:
                entry = create_project(
                    input_dir,
                    title=title,
                    subtitle=fields.get("subtitle", "").strip(),
                    description=fields.get("description", "").strip(),
                    uploaded_files=files,
                )
                self._rebuild()
                self.send_json({"ok": True, "project": entry})
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

        def _handle_remove(self) -> None:
            body = self.read_body()
            try:
                data = json.loads(body)
            except Exception:
                self.send_json({"error": "Invalid JSON"}, 400)
                return

            project_id = str(data.get("project_id", "")).strip()
            if not project_id:
                self.send_json({"error": "project_id required"}, 400)
                return

            try:
                remove_project(input_dir, project_id)
                self._rebuild()
                self.send_json({"ok": True})
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

        def _handle_replace_image(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            body = self.read_body()

            if "multipart/form-data" not in content_type:
                self.send_json({"error": "expected multipart/form-data"}, 400)
                return

            fields, files = parse_multipart(content_type, body)
            project_id = fields.get("project_id", "").strip()
            file_rel = fields.get("file", "").strip()

            if not project_id:
                self.send_json({"error": "project_id required"}, 400)
                return
            if not file_rel:
                self.send_json({"error": "file (relative path) required"}, 400)
                return
            if not files:
                self.send_json({"error": "no image uploaded"}, 400)
                return

            upload = files[0]
            upload_ext = Path(upload.get("filename", "")).suffix.lower()
            if upload_ext and upload_ext not in IMAGE_EXTENSIONS:
                self.send_json({"error": f"unsupported image type: {upload_ext}"}, 400)
                return

            try:
                result = replace_project_image(input_dir, project_id, file_rel, upload)
                self._rebuild()
                self.send_json({"ok": True, **result})
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

        def _handle_add_screen(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            body = self.read_body()

            if "multipart/form-data" not in content_type:
                self.send_json({"error": "expected multipart/form-data"}, 400)
                return

            fields, files = parse_multipart(content_type, body)
            project_id = fields.get("project_id", "").strip()

            if not project_id:
                self.send_json({"error": "project_id required"}, 400)
                return
            if not files:
                self.send_json({"error": "no image uploaded"}, 400)
                return

            try:
                result = add_project_screen(
                    input_dir,
                    project_id,
                    files[0],
                    title=fields.get("title", ""),
                    section=fields.get("section", ""),
                    hover_title=fields.get("hover_title", ""),
                    hover_description=fields.get("hover_description", ""),
                )
                self._rebuild()
                self.send_json(result)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

        def _handle_save_overrides(self) -> None:
            body = self.read_body()
            try:
                data = json.loads(body)
            except Exception:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            overrides = data.get("overrides")
            if overrides is None:
                # Allow the bare overrides object as the body too
                overrides = data
            if not isinstance(overrides, dict):
                self.send_json({"error": "overrides must be an object"}, 400)
                return
            try:
                result = apply_text_overrides(input_dir, overrides)
                if result.get("applied"):
                    self._rebuild()
                self.send_json(result)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

        def _handle_update_flow(self) -> None:
            body = self.read_body()
            try:
                data = json.loads(body)
            except Exception:
                self.send_json({"error": "Invalid JSON"}, 400)
                return
            project_id = str(data.get("project_id", "")).strip()
            flow_data = data.get("flow")
            if not project_id:
                self.send_json({"error": "project_id required"}, 400)
                return
            try:
                result = update_project_flow(input_dir, project_id, flow_data)
                self._rebuild()
                self.send_json(result)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

        def _handle_remove_screen(self) -> None:
            body = self.read_body()
            try:
                data = json.loads(body)
            except Exception:
                self.send_json({"error": "Invalid JSON"}, 400)
                return

            project_id = str(data.get("project_id", "")).strip()
            relative_path = str(data.get("relative_path", "") or data.get("file", "")).strip()
            delete_file = bool(data.get("delete_file", False))

            if not project_id:
                self.send_json({"error": "project_id required"}, 400)
                return
            if not relative_path:
                self.send_json({"error": "relative_path required"}, 400)
                return

            try:
                result = remove_project_screen(input_dir, project_id, relative_path, delete_file)
                self._rebuild()
                self.send_json(result)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)

    return Handler


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def start_management_server(
    input_dir: Path,
    output_dir: Path,
    args: Any,
    port: int,
    open_browser: bool,
) -> None:
    Handler = make_management_handler(input_dir, output_dir, args)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as server:
        url = f"http://127.0.0.1:{port}"
        print(f"\n[Management server started]")
        print(f"  Preview: {url}")
        print(f"  API:     {url}/api/*  (add / remove / rebuild)")
        print("  Press Ctrl+C to stop.\n")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    _args = parse_args()
    _input_dir = Path(_args.input_dir).expanduser().resolve()
    _output_dir = resolve_output_dir(_input_dir, _args.output_dir)
    build_site(_args)
    start_management_server(_input_dir, _output_dir, _args, _args.port, _args.open_browser)
