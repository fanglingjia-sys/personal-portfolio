---
name: portfolio-site-builder
description: Build a multi-project visual hub website from image folders, interaction documents, and feature demo videos. Use when the user asks to generate a项目总览页 with multiple project cards, enter a具体项目内容页, show交互文档 first, show single screens with hover descriptions, render an interactive flow diagram, or attach feature demo videos.
---

# Project Hub Site Builder

## Purpose

Use this skill to generate a static website with two layers:

- Project hub homepage: shows multiple project cards
- Project detail page: shows interaction document, single screens, flow diagram, and feature demo videos

Website text and image content should be edited through `projects.index.json` and `site.meta.json`, not by changing template code.

## Default Behavior

- Treat the site as a visual hub first
- Homepage shows multiple project cards when `projects.index.json` is present
- **New projects are inserted at index 0 in `projects.index.json`** so the
  most recent work appears first on the home page. The `/api/add-project`
  endpoint and any direct edits should follow this convention.
- Project detail renders sections in this order:
  - interaction document
  - single screens (with hover descriptions; click any thumbnail to open a fullscreen lightbox)
  - flow diagram (interactive node graph derived from `flow.nodes` / `flow.edges` in site.meta.json)
  - demo videos (compressed feature recordings — fullscreen lightbox playback with prev/next nav)

## Ask First

Before generating:

1. Confirm whether the input is:
   - one project folder
   - or a root folder containing multiple projects
2. Ask whether the user wants a multi-project homepage now.
3. Ask whether the interaction document file is already available.
4. Ask whether feature demo videos are available; if so, where the source files are and which project they belong to.
5. Ask whether a local preview URL should be started.

If the user does not care about details, use these defaults:

- Homepage: on when `projects.index.json` exists
- Interaction document: use explicit metadata only
- Demo videos: skip the section if no `videos[]` configured
- Preview: yes
- Port: `8123`

## Build Workflow

1. Inspect the input folder.
2. If `projects.index.json` exists, build a multi-project hub.
3. For each project folder, read `site.meta.json` or `portfolio.meta.json` if present.
4. Render project detail sections in this order:
   - interaction document
   - single screens with hover descriptions
   - flow diagram
   - demo videos (when `videos[]` populated)
5. Prefer updating metadata fields such as `title`, `description`, `labels`, `hero_image`, `interaction_doc.file`, `items[].file`, and `videos[].file` when the user asks to customize text, images, or videos.
6. If requested, start the local preview server.

## Demo Videos

When the user wants to attach feature recordings:

1. Place source video files anywhere on disk; the skill will compress them
   on the way into the project folder.
2. Compress with ffmpeg targeting **~5 MB per video** so the repo stays
   small and GitHub Pages loads quickly. Use 2-pass H.264:
   - codec: H.264 (libx264) preset slow, container: mp4 + `-movflags +faststart`
   - resolution: scale to `960:-2` (≈540p) — readable for screen
     recordings, far smaller than 720p+
   - bitrate: target total ≈ `5 MiB × 8 × 0.92 / duration_sec ÷ 1000` kbps;
     subtract 64 (audio) for video bitrate; floor at 120k for short clips
   - audio: 64k AAC mono/stereo if there is narration; strip with `-an`
     if silent
   - Run two passes via `-pass 1 -an -f null` then `-pass 2 -movflags +faststart`
     so the average bitrate hits the target precisely
3. Save the compressed mp4 under `<project>/videos/<short-name>.mp4`.
4. Add a `videos[]` array to `site.meta.json`:
   ```json
   {
     "videos": [
       {
         "file": "videos/draw-demo.mp4",
         "title": "Bingo 抽取动效",
         "caption": "完整抽取 → 翻开 → Bingo 反馈循环",
         "section": "核心循环",
         "duration": "0:24",
         "poster": "videos/draw-demo-poster.jpg"
       }
     ]
   }
   ```
5. `poster` is optional; when provided, use a still frame (`ffmpeg -ss <t> -frames:v 1`) to give the card a sharp thumbnail. Without a poster, the frontend uses the video's first decoded frame.

## Creating a New Project — MUST Read Interaction Document First

When generating `site.meta.json` for a **new** project (either first-time setup or when the user adds a new project folder), you MUST follow this protocol to produce accurate `flow` and `prototype` structures instead of empty placeholders:

### Step 1 — Read the interaction document image

Use the `Read` tool directly on the project's interaction document file (any file matching `交互文档.*`, `flow.*`, `overview.*`, `*-doc.*`, etc.). Claude can see the image via multimodal input.

```
Read("<project_dir>/交互文档.jpg")
```

### Step 2 — Extract flow structure from the image

From the interaction document image, identify:

- **Nodes**: every distinct screen/state shown in the flowchart, with its label text and the matching screen filename (e.g. "主界面" → `1.png` if that's the screen shown under that label in the doc)
- **Position**: approximate `col` (horizontal) and `row` (vertical) grid position of each node in the diagram — match the visual layout of the document
- **Edges**: every arrow connecting two nodes, with its label (e.g. "点击开始", "挑战失败", "返回"). If an arrow represents a return/back transition, mark it with `"type": "back"`

Write these as `flow.nodes` and `flow.edges` in the `site.meta.json`.

### Step 3 — Enrich each screen's `items[]` entry

Read each individual screen image (1.png, 2.png, …) and fill in:

- `title` — a concise state name ("战前准备 · 初始", not generic "界面 01")
- `hover_title` — the interactive headline shown on hover
- `hover_description` — what the player sees and can do on this screen, referencing concrete UI elements visible in the image
- `states` — 1–3 short state labels ("初始", "已选将")
- `notes` — 1–3 contextual observations (mechanics, edge cases)

### Step 4 — Leave `prototype.scenes: []` empty

If `flow` is populated, the generator auto-builds prototype scenes with navigation hotspots from the edges. Do **not** hand-author prototype scenes unless the user explicitly wants different scenes than the flow implies.

```json
{
  "flow": { ... },
  "prototype": {
    "intro": "<one-sentence demo intro>",
    "scenes": []
  }
}
```

### Step 5 — Ask for corrections if unsure

If any screen's meaning is ambiguous, or an arrow's label is unclear, **ask the user to clarify** before committing to the meta.json. Prefer explicit confirmation over silent guessing on anything that shapes the flow graph.

### Fallback — manual annotations

If the interaction document is hard to read (hand-drawn, low contrast, ambiguous arrows), the user can provide an explicit `interaction_doc.annotations` array in the meta, listing each node's `label`, `screen_id`, `col`, `row`, and `from`. Use that as authoritative input instead of re-parsing the image.

## Commands

Run from this skill directory.

### Generate one project (preview only)

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/my-project" --serve --port 8123
```

### Generate one project with prototype module

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/my-project" --enable-prototype --serve --port 8123
```

### Generate a multi-project hub

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/projects-root" --serve --port 8123
```

### Start management server (add / remove projects from browser)

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/projects-root" --manage --port 8123 --open-browser
```

Management mode starts a special server that:
- Serves the same static site
- Exposes `/api/add-project`, `/api/remove-project`, `/api/rebuild`
- Shows a "项目管理" panel in the browser toolbar
- Adds a delete button (✕) on every project card (hover to reveal)

#### Adding a project from the browser

1. Click **+ 添加项目** in the toolbar.
2. Fill in title (required), subtitle, description.
3. Upload one or more images (drag & drop or file picker).
   - Files whose name contains `交互 / 总览 / 流程 / board / flow / doc / mockup` → auto-classified as **交互文档**
   - Everything else → **界面图**
4. Click **确认添加**. The server saves the images under `<input-dir>/<project-id>/`, writes `site.meta.json`, updates `projects.index.json`, and rebuilds the site.

#### Removing a project

Hover over any project card and click the red **✕** button. The server removes the entry from `projects.index.json` (source files are kept on disk).

#### Replacing images via edit mode

Image replacement reuses the built-in **edit mode** flow:

1. Click **开启编辑** in the top toolbar.
2. Click any image — a prompt offers: enter a new URL, upload a local file, or revert.
3. Uploaded images are stored as data-URL overrides in `localStorage` so the preview updates instantly.
4. In management mode (`--manage`), a **保存到源文件** button appears in the toolbar while edit mode is on. Click it to:
   - Walk the overrides for every image whose `src` is a data URL
   - Upload each one to `POST /api/replace-image` (multipart: `project_id`, `file` = relative path within the project folder, `image` = the blob)
   - Overwrite the original file on disk at its current relative path (filename preserved so `site.meta.json` and rendered URLs stay valid)
   - Rebuild the site, reload `site-data.json`, clear the saved overrides, and cache-bust all `<img>` tags

Text overrides (titles, captions) still live in `localStorage` — use 导出修改 / 导入修改 to move them between browsers.

### Generate a multi-project hub with prototype module

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/projects-root" --enable-prototype --serve --port 8123
```

## Output Contract

Always tell the user:

- Which folder was used as input
- Whether the site was built as one project or a multi-project hub
- Where the site was generated
- The preview URL if a server was started
- Whether the prototype module was enabled
- How the project detail is organized:
  - interaction document first
  - single screens with hover descriptions second
  - optional dynamic prototype third

## Metadata

Use:

- `projects.index.json` for the homepage project list
- `site.meta.json` for each project detail

For the schema and examples, read:

- [reference.md](reference.md)
- [examples.md](examples.md)

## Notes

- Prefer this skill when the user wants a website-style project hub rather than one merged image.
- Prefer structured metadata over guessing screen descriptions.
- Only enable the prototype module when the user explicitly asks for it.
