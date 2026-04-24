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
            # Prevent browser caching of all responses so rebuilt files are always fresh
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
