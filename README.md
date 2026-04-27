# 个人作品集 (Personal Portfolio)

UX / UI 作品集仓库。本地双击 `启动编辑.bat` 启动编辑服务器，改完 push 到 GitHub 即可。

## 目录结构

```
Personal/
├── projects.index.json      ← 项目总览索引
├── Color_Guess_Game/        ← 项目 1 的图片 + site.meta.json
├── K6Secret/                ← 项目 2 的图片 + site.meta.json
├── tools/
│   └── portfolio-site-builder/   ← 站点构建脚本 (Python)
├── _portfolio_site/         ← 自动生成的静态站 (已 gitignore)
├── 启动编辑.bat             ← 双击启动本地编辑服务器
└── .gitignore
```

## 环境要求

- Python 3.9+
- Git 客户端 (推荐 [Fork](https://git-fork.com/))

## 日常使用流程

### 首次使用 / 新机器

1. `git clone <仓库地址>`
2. 安装 Python 3.9+ (勾选 "Add to PATH")
3. 双击 `启动编辑.bat`

### 编辑内容

1. Fork 里 **Pull** 拉最新
2. 双击 `启动编辑.bat`
3. 浏览器自动打开 `http://127.0.0.1:8123`
4. 点 **开启编辑** → 点文字/图片修改 → 点 **保存到源文件** 把图片写回磁盘
5. 在终端窗口按 `Ctrl+C` 停止服务器
6. Fork 里 **Commit + Push** 推上去

### 添加新项目

两种方式：

**A. 浏览器内 (推荐)**

在工具栏点 `+ 添加项目` → 填写标题、上传图片 → 确认添加。

**B. 手动**

1. 新建文件夹 `MyProject/`，放入图片和 `site.meta.json`
2. 在 `projects.index.json` 的 `projects` 数组追加一条记录
3. 重启编辑服务器

## 部署到 GitHub Pages

每次 `git push` 到 main 后, GitHub Actions 会自动构建静态站并发布到:

```
https://fanglingjia-sys.github.io/personal-portfolio/
```

### 一次性配置

1. 仓库 **Settings → General** → Change visibility → **Public** (Pages 在免费账号上仅支持 Public 仓库)
2. 仓库 **Settings → Pages** → Build and deployment → Source 选 **GitHub Actions**
3. 任意一次 push 即可触发首次部署, 或在 **Actions** 标签页点 **Run workflow** 手动触发

### Workflow 文件

`.github/workflows/deploy.yml` 定义了构建和部署逻辑, 触发条件是:

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
```

如果再想暂停自动发布, 把 `push` 那段注释掉即可。

## 命令行 (不用 bat 的情况下)

```bash
python tools/portfolio-site-builder/scripts/generate_portfolio_site.py \
  --input-dir . \
  --enable-prototype \
  --manage \
  --port 8123 \
  --open-browser
```
