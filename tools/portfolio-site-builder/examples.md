# Examples

## Example 1: One Project Detail Site

User request:

```text
先把这个项目做成一个可浏览的网址，项目详情里先放交互文档，再放单独界面
```

Suggested command:

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/car-repair" --serve --port 8123
```

Expected behavior:

- Homepage contains one project card
- Clicking the card enters project detail
- Project detail shows interaction document first
- Screen cards show hover descriptions

## Example 2: Multi-Project Hub

User request:

```text
把这些项目整理成一个项目总览站，点进每个项目看具体内容
```

Suggested command:

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/projects-root" --serve --port 8123
```

Expected behavior:

- Homepage shows multiple project cards
- Clicking a project card enters the selected project detail page
- Each project detail page uses its own `site.meta.json`

## Example 3: Hover Descriptions From Interaction Doc

User request:

```text
单独界面需要鼠标悬浮显示状态说明，内容参考交互文档
```

Suggested approach:

- Fill `hover_title`, `hover_description`, `states`, `notes`, and `doc_refs` in `site.meta.json`
- Then regenerate the site

## Example 4: Customize Website Text And Images

User request:

```text
我想自己改网站里的固定文案和展示图片
```

Suggested approach:

- In `projects.index.json`, edit:
  - `title`
  - `subtitle`
  - `description`
  - `hero_image`
  - `labels`
- In each `site.meta.json`, edit:
  - `hero_image`
  - `hero` / `detail_cover`
  - `card_cover`
  - `interaction_doc.file`
  - `items[].file`
  - `labels`

Then regenerate:

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/projects-root" --serve --port 8123
```

## Example 5: Enable Prototype Only On Demand

User request:

```text
根据交互文档生成可演示的交互原型
```

Suggested command:

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/projects-root" --enable-prototype --serve --port 8123
```

Expected behavior:

- Homepage stays the same
- Project detail still shows interaction document and screens first
- Prototype section appears after the screen section

## Example 6: Keep Prototype Off

User request:

```text
项目先做成总览和详情，原型模块先别开
```

Suggested command:

```bash
python scripts/generate_portfolio_site.py --input-dir "D:/designs/projects-root" --serve --port 8123
```

Expected behavior:

- Prototype section is replaced by a note saying it is not enabled
- The project detail still remains fully usable as a visual documentation site
