# Reference

## What The Generator Produces

The generator writes a static site to the output directory:

```text
output/
  index.html
  styles.css
  app.js
  site-data.json
  assets/
```

The site has two layers:

- Homepage: project overview cards
- Project detail: interaction document, screen hover descriptions, optional prototype

## Input Types

### One project folder

Use a single project directory with `site.meta.json`:

```text
my-project/
  site.meta.json
  interaction-doc.png
  screen-01.png
  screen-02.png
```

### Multiple projects

Use a root directory with `projects.index.json` plus one folder per project:

```text
projects-root/
  projects.index.json
  car-repair/
    site.meta.json
    ...
  shop-rework/
    site.meta.json
    ...
```

## `projects.index.json`

Use this file to control the homepage project cards.

```json
{
  "title": "项目总览",
  "subtitle": "多个活动项目集合",
  "description": "点击项目卡片进入具体项目详情。",
  "theme": {
    "accent": "#42d7dd",
    "background": "#101826"
  },
  "projects": [
    {
      "id": "car-repair",
      "path": "car-repair",
      "title": "赛车维修组队活动",
      "summary": "主打组队维修、商店兑换、礼包承接。",
      "tags": ["活动", "赛车", "组队"]
    },
    {
      "id": "shop-rework",
      "path": "shop-rework",
      "title": "商店改版",
      "summary": "商店项目示例。",
      "tags": ["商店", "改版"]
    }
  ]
}
```

Fields:

- `title`: homepage title
- `subtitle`: homepage subtitle
- `description`: homepage summary
- `hero_image`: optional homepage hero image
- `labels`: optional global text overrides
- `theme`: optional global colors
- `projects`: ordered project list

Each project entry supports:

- `id`: optional project id
- `path`: required, relative path to the project folder
- `title`: optional card title override
- `subtitle`: optional subtitle override
- `summary`: optional card summary override
- `card_cover`: optional project card image override
- `detail_cover`: optional project detail cover override
- `labels`: optional text overrides for this project
- `tags`: optional string array

## `site.meta.json`

Use this file to control one project detail page.

```json
{
  "title": "赛车维修组队活动",
  "subtitle": "交互文档整理版",
  "description": "该项目详情页先展示交互文档，再展示单独界面和可选原型。",
  "hero": "main-screen.png",
  "hero_image": "home-banner.png",
  "labels": {
    "home_section_title": "活动项目总览",
    "screens_title": "页面拆解",
    "prototype_title": "交互演示"
  },
  "interaction_doc": {
    "file": "interaction-doc.png",
    "title": "交互文档",
    "caption": "整体流程和页面关系说明",
    "summary": "用于解释入口、流程、奖励和支线模块。",
    "notes": ["总览流程", "页面关系", "关键入口"],
    "states": ["入口", "主玩法", "支线模块"]
  },
  "theme": {
    "accent": "#42d7dd",
    "background": "#1d232f"
  },
  "tags": ["活动", "赛车"],
  "items": [
    {
      "id": "main-screen",
      "file": "main-screen.png",
      "title": "主界面",
      "caption": "展示活动入口和主状态。",
      "section": "核心界面",
      "summary": "主玩法总入口。",
      "hover_title": "主界面入口层",
      "hover_description": "鼠标悬浮时显示的说明。",
      "states": ["入口按钮", "队伍状态", "奖励预览"],
      "notes": ["来自交互文档整理"],
      "doc_refs": ["交互文档 1-1"]
    },
    {
      "file": "shop-screen.png",
      "title": "兑换商店",
      "section": "核心界面"
    }
  ],
  "prototype": {
    "intro": "只有在显式启用 prototype 时才显示。",
    "scenes": [
      {
        "id": "flow-01",
        "file": "main-screen.png",
        "title": "主界面进入流程",
        "summary": "演示入口点击后的流程。",
        "steps": ["点击入口", "进入弹窗", "查看结果"],
        "hotspots": [
          {
            "x": 62,
            "y": 18,
            "title": "入口按钮",
            "content": "热点说明"
          }
        ]
      }
    ]
  }
}
```

## Metadata Fields

- `title`: project title
- `subtitle`: project subtitle
- `description`: project summary
- `hero`: detail header cover image
- `hero_image`: optional homepage hero image for the single-project site
- `interaction_doc`: interaction document block
- `labels`: optional fixed-text overrides
- `theme`: optional project colors
- `tags`: optional tag array
- `items`: ordered screen list
- `prototype.scenes`: optional prototype scene list

Each `items` entry supports:

- `id`: optional screen id
- `file`: required image path, relative or absolute
- `title`: screen title
- `caption`: short visible caption
- `section`: section label
- `summary`: extra description
- `hover_title`: hover card title
- `hover_description`: hover card summary
- `states`: bullet list shown on hover
- `notes`: extra bullet list shown on hover
- `doc_refs`: references back to the interaction document
- `tags`: optional tags

Useful editable text keys in `labels`:

- `home_eyebrow`
- `home_section_title`
- `home_section_description`
- `back_to_home`
- `interaction_doc_title`
- `screens_title`
- `screens_description`
- `prototype_title`
- `prototype_disabled`
- `scene_list_title`
- `steps_title`
- `hotspot_title`
- `stat_project_count`
- `stat_screen_count`

Each `prototype.scenes` entry supports:

- `id`: optional scene id
- `file`: required image path
- `title`: scene title
- `summary`: scene explanation
- `steps`: ordered step list
- `hotspots`: hotspot list

Each hotspot supports:

- `x`: horizontal percentage, 0-100
- `y`: vertical percentage, 0-100
- `title`: hotspot title
- `content`: hotspot explanation

## Prototype Module Switch

Prototype is off by default.

Only pass `--enable-prototype` when the user explicitly asks for:

- 可演示的交互原型
- 演示流程
- 热点说明
- 场景切换
- 交互 walkthrough

Without `--enable-prototype`, the site still renders:

- homepage
- project detail
- interaction document
- single screens with hover descriptions

## Local Preview

Use the built-in server by passing `--serve`.

Default preview URL:

```text
http://127.0.0.1:8123
```

## Deploy Later

Because the output is static HTML/CSS/JS, it can be deployed to:

- GitHub Pages
- Netlify
- Vercel
- Any nginx / static file host
