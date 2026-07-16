const state = {
  data: null,
  baseData: null,
  overrides: {},
  editMode: false,
  manageMode: false,
  showAddPanel: false,
  showSectionPanel: false,
  sectionConfig: {},
  pendingImagePath: null,
  currentProjectId: null,
  showAbout: false,
  currentSceneIndex: 0,
  activeHotspotIndex: 0,
  lightboxScreenIndex: 0,
  lightboxVariantIndex: 0,
  lightboxVideoIndex: 0,
  lightboxShowcaseIndex: 0,
  activeHomeCategory: "casual-events",
};

const app = document.getElementById("app");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderTags(tags) {
  if (!Array.isArray(tags) || !tags.length) {
    return "";
  }
  return `<div class="chips">${tags.map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}</div>`;
}

function renderList(title, items, className) {
  if (!Array.isArray(items) || !items.length) {
    return "";
  }
  return `
    <div>
      <h4>${escapeHtml(title)}</h4>
      <ul class="${className}">
        ${items.map((item) => `<li>${escapeHtml(typeof item === "string" ? item : item.text || item.title || "")}</li>`).join("")}
      </ul>
    </div>
  `;
}

function getLabels(site, project) {
  return {
    ...(site?.labels || {}),
    ...((project && project.labels) || {}),
  };
}

function cloneData(value) {
  return JSON.parse(JSON.stringify(value));
}

function getStorageKey() {
  const title = state.baseData?.site?.title || "project-hub";
  return `portfolio-site-builder:${title}:${location.pathname}`;
}

function applyNested(target, source) {
  if (!source || typeof source !== "object") {
    return target;
  }
  Object.entries(source).forEach(([key, value]) => {
    const actualKey = Array.isArray(target) ? Number(key) : key;
    if (value && typeof value === "object") {
      const valueIsArray = Array.isArray(value);
      if (target[actualKey] === undefined || target[actualKey] === null) {
        target[actualKey] = valueIsArray ? [] : {};
      }
      applyNested(target[actualKey], value);
      return;
    }
    target[actualKey] = value;
  });
  return target;
}

function refreshData() {
  state.data = cloneData(state.baseData);
  applyNested(state.data, state.overrides);
  // Defensive: drop any project entry that lacks an id (phantom from stale
  // localStorage overrides whose source project was deleted).
  if (Array.isArray(state.data?.projects)) {
    state.data.projects = state.data.projects.filter(p => p && typeof p === "object" && p.id);
  }
  document.title = state.data.site?.title || "Project Hub";
  if (state.data.site?.theme?.accent) {
    document.documentElement.style.setProperty("--accent", state.data.site.theme.accent);
  }
  if (state.data.site?.theme?.background) {
    document.documentElement.style.setProperty("--bg", state.data.site.theme.background);
  }
}

function saveOverrides() {
  localStorage.setItem(getStorageKey(), JSON.stringify(state.overrides));
}

function loadOverrides() {
  try {
    const saved = localStorage.getItem(getStorageKey());
    state.overrides = saved ? JSON.parse(saved) : {};
  } catch (error) {
    console.error(error);
    state.overrides = {};
  }
}

function setByPath(target, path, value) {
  const parts = path.split(".");
  let cursor = target;
  parts.forEach((part, index) => {
    const isLast = index === parts.length - 1;
    const nextPart = parts[index + 1];
    const nextIsIndex = /^\d+$/.test(nextPart || "");
    if (isLast) {
      cursor[part] = value;
      return;
    }
    if (cursor[part] === undefined || cursor[part] === null) {
      cursor[part] = nextIsIndex ? [] : {};
    }
    cursor = cursor[part];
  });
}

function deleteByPath(target, path) {
  const parts = path.split(".");
  const ancestors = [target];
  let cursor = target;
  for (let index = 0; index < parts.length - 1; index += 1) {
    if (!cursor || typeof cursor !== "object") {
      return;
    }
    cursor = cursor[parts[index]];
    ancestors.push(cursor);
  }
  if (cursor && typeof cursor === "object") {
    delete cursor[parts[parts.length - 1]];
  }
  // Walk up and prune empty wrapper objects/arrays left behind
  for (let i = ancestors.length - 1; i > 0; i -= 1) {
    const node = ancestors[i];
    if (!node || typeof node !== "object") break;
    const keys = Object.keys(node);
    const isEmpty = Array.isArray(node)
      ? node.every((v) => v === undefined)
      : keys.length === 0;
    if (!isEmpty) break;
    const parent = ancestors[i - 1];
    if (parent && typeof parent === "object") {
      delete parent[parts[i - 1]];
    }
  }
}

function updateOverride(path, value) {
  setByPath(state.overrides, path, value);
  saveOverrides();
  refreshData();
  render();
}

function clearOverride(path) {
  deleteByPath(state.overrides, path);
  saveOverrides();
  refreshData();
  render();
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function openImageEditor(path, currentValue) {
  const choice = window.prompt(
    "图片编辑：输入 1 修改为路径/URL，输入 2 上传本地图片，输入 3 恢复默认",
    "1"
  );
  if (choice === null) {
    return;
  }
  if (choice === "1") {
    const nextValue = window.prompt("输入新的图片路径、URL 或 data URL", currentValue || "");
    if (nextValue !== null && nextValue.trim()) {
      updateOverride(path, nextValue.trim());
    }
    return;
  }
  if (choice === "2") {
    state.pendingImagePath = path;
    document.getElementById("editor-image-input")?.click();
    return;
  }
  if (choice === "3") {
    clearOverride(path);
  }
}

function bindEditorInteractions() {
  document.getElementById("editor-toggle")?.addEventListener("click", () => {
    state.editMode = !state.editMode;
    render();
  });

  document.getElementById("editor-export")?.addEventListener("click", () => {
    downloadJson("site-overrides.json", state.overrides);
  });

  document.getElementById("editor-save-to-source")?.addEventListener("click", (e) => {
    saveOverridesToSource(e.currentTarget);
  });

  document.getElementById("editor-reset")?.addEventListener("click", () => {
    if (!window.confirm("确定清空当前浏览器中的网页编辑修改吗？")) {
      return;
    }
    state.overrides = {};
    saveOverrides();
    refreshData();
    render();
  });

  document.getElementById("editor-import-trigger")?.addEventListener("click", () => {
    document.getElementById("editor-import-input")?.click();
  });

  document.getElementById("editor-import-input")?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    try {
      const text = await file.text();
      state.overrides = JSON.parse(text);
      saveOverrides();
      refreshData();
      render();
    } catch (error) {
      console.error(error);
      window.alert("导入失败，JSON 格式不正确。");
    } finally {
      event.target.value = "";
    }
  });

  document.getElementById("editor-image-input")?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file || !state.pendingImagePath) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      updateOverride(state.pendingImagePath, String(reader.result || ""));
      state.pendingImagePath = null;
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  });

  document.querySelectorAll("[data-edit-path]").forEach((node) => {
    node.addEventListener("click", (event) => {
      if (!state.editMode) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const path = node.getAttribute("data-edit-path");
      const currentValue = node.textContent?.trim() || "";
      const nextValue = window.prompt("编辑文本内容", currentValue);
      if (path && nextValue !== null) {
        updateOverride(path, nextValue);
      }
    });
  });

  document.querySelectorAll("[data-image-path]").forEach((node) => {
    node.addEventListener("click", (event) => {
      if (!state.editMode) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const path = node.getAttribute("data-image-path");
      const currentValue = node.getAttribute("src") || "";
      if (path) {
        openImageEditor(path, currentValue);
      }
    });
  });
}

function renderEditorToolbar() {
  return `
    <div class="panel editor-toolbar">
      <div class="editor-toolbar-info">
        <div class="editor-toolbar-title">网页内编辑模式</div>
        <div class="editor-toolbar-note">
          ${state.editMode
            ? (state.manageMode
                ? "编辑模式已开启:点击文字或图片即可修改。改完点「保存全部到源文件」把文字 + 图片一起写回磁盘, 然后到 Fork 里 commit + push 即可。"
                : "编辑模式已开启:点击文字或图片即可修改。修改仅保存在当前浏览器,可导出 JSON。")
            : "当前为浏览模式。点击「开启编辑」后可直接修改文字和图片。"}
        </div>
      </div>
      <div class="editor-toolbar-actions">
        <button type="button" id="editor-toggle" class="${state.editMode ? "primary" : ""}">${state.editMode ? "退出编辑" : "开启编辑"}</button>
        ${state.editMode && state.manageMode ? `<button type="button" id="editor-save-to-source" class="primary" title="把本浏览器内的所有修改 (文字 + 图片) 写回源文件并重建站点, 之后即可在 Fork 里 commit + push">保存全部到源文件</button>` : ""}
        <button type="button" id="editor-export">导出修改</button>
        <button type="button" id="editor-import-trigger">导入修改</button>
        <button type="button" id="editor-reset">清空修改</button>
      </div>
      <input id="editor-import-input" type="file" accept="application/json" hidden />
      <input id="editor-image-input" type="file" accept="image/*" hidden />
      ${state.manageMode ? `
      <div class="editor-toolbar-sep"></div>
      <div class="editor-toolbar-info">
        <div class="editor-toolbar-title">项目管理</div>
        <div class="editor-toolbar-note">可在当前站点中增减项目，图片会自动部署到正确位置。</div>
      </div>
      <div class="editor-toolbar-actions">
        <button type="button" id="manage-add-project" class="primary">+ 添加项目</button>
      </div>` : ""}
      ${state.currentProjectId ? `
      <div class="editor-toolbar-sep"></div>
      <div class="editor-toolbar-info">
        <div class="editor-toolbar-title">模块管理</div>
        <div class="editor-toolbar-note">可显示/隐藏各内置模块，或新增自定义模块。</div>
      </div>
      <div class="editor-toolbar-actions">
        <button type="button" id="open-section-panel">管理模块</button>
      </div>` : ""}
    </div>
  `;
}

function getProjectById(projectId) {
  return state.data.projects.find((project) => project.id === projectId) || null;
}

function hasPrototype(project) {
  const enabled = Boolean(state.data.site.prototype_enabled) || Boolean(project.prototype?.enabled);
  return enabled && Array.isArray(project.prototype?.scenes) && project.prototype.scenes.length > 0;
}

function setProject(projectId) {
  state.showAbout = false;
  state.currentProjectId = projectId;
  state.currentSceneIndex = 0;
  state.activeHotspotIndex = 0;
  window.location.hash = projectId ? `#${projectId}` : "";
  render();
}

function openAbout() {
  state.showAbout = true;
  state.currentProjectId = null;
  window.location.hash = "about";
  render();
}

function setScene(index) {
  state.currentSceneIndex = index;
  state.activeHotspotIndex = 0;
  rerenderPrototypeOnly();
}

function setHotspot(index) {
  state.activeHotspotIndex = index;
  rerenderPrototypeOnly();
}

// Partial DOM update: replace only the prototype section instead of the
// whole page. Avoids the visible flash that came with full render() calls.
function rerenderPrototypeOnly() {
  const existing = document.getElementById("prototype-section");
  if (!existing) {
    render();
    return;
  }
  if (!state.currentProjectId || !state.data) {
    render();
    return;
  }
  const projectIndex = (state.data.projects || []).findIndex(
    (p) => p && p.id === state.currentProjectId
  );
  if (projectIndex < 0) {
    render();
    return;
  }
  const project = state.data.projects[projectIndex];
  const html = renderPrototype(project, projectIndex);
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  const next = tmp.firstElementChild;
  if (!next) return;

  // If the scene image src is unchanged (e.g. clicking an info hotspot
  // that doesn't change the active scene), keep the already-loaded <img>
  // element. The browser otherwise creates a fresh node which causes a
  // brief flash even when the file is cached.
  const oldImg = existing.querySelector(".proto-stage > img");
  const newImg = next.querySelector(".proto-stage > img");
  if (oldImg && newImg && oldImg.getAttribute("src") === newImg.getAttribute("src")) {
    newImg.replaceWith(oldImg);
  }

  existing.replaceWith(next);
  bindPrototypeEvents();
}

function bindPrototypeEvents() {
  document.querySelectorAll("#prototype-section [data-scene-index]").forEach((node) => {
    node.addEventListener("click", () => setScene(Number(node.getAttribute("data-scene-index"))));
  });
  document.querySelectorAll("#prototype-section [data-hotspot-index]").forEach((node) => {
    node.addEventListener("click", () => {
      const idx = Number(node.getAttribute("data-hotspot-index"));
      const gotoAttr = node.getAttribute("data-goto-scene");
      if (gotoAttr !== null && gotoAttr !== "") {
        setScene(Number(gotoAttr));
      } else {
        setHotspot(idx);
      }
    });
  });
}

function getCurrentScene(project) {
  const scenes = project.prototype?.scenes || [];
  if (!scenes.length) {
    return null;
  }
  const safeIndex = Math.max(0, Math.min(state.currentSceneIndex, scenes.length - 1));
  state.currentSceneIndex = safeIndex;
  const scene = scenes[safeIndex];
  const hotspots = Array.isArray(scene.hotspots) ? scene.hotspots : [];
  if (!hotspots.length) {
    state.activeHotspotIndex = -1;
  } else if (state.activeHotspotIndex < 0 || state.activeHotspotIndex >= hotspots.length) {
    state.activeHotspotIndex = 0;
  }
  return scene;
}

function renderAbout(data) {
  const about = data.site?.about || {};
  const capabilities = Array.isArray(about.capabilities) ? about.capabilities : [];
  const experience = Array.isArray(about.experience) ? about.experience : [];
  const education = Array.isArray(about.education) ? about.education : [];
  const focus = Array.isArray(about.focus) ? about.focus : [];
  const tools = Array.isArray(about.tools) ? about.tools : [];
  const aiTools = Array.isArray(about.ai_tools) ? about.ai_tools : [];
  const languages = Array.isArray(about.languages) ? about.languages : [];

  return `
    <div class="shell about-page">
      <nav class="portfolio-nav" aria-label="个人主页导航">
        <button type="button" class="portfolio-mark portfolio-mark-button" data-back-home>Fangling Jia · Portfolio</button>
        <div class="portfolio-nav-actions">
          <span class="portfolio-nav-link is-active">关于我</span>
          <button type="button" class="portfolio-project-button" data-back-home>查看项目 <span aria-hidden="true">→</span></button>
        </div>
      </nav>

      <header class="about-hero">
        <div class="about-hero-copy">
          <div class="section-kicker">About / ${escapeHtml(about.name_en || "Fangling Jia")}</div>
          <h1>${escapeHtml(about.headline || "从玩法逻辑，到可运行界面。")}</h1>
          <div class="about-hero-actions">
            <button type="button" class="about-project-cta" data-back-home>查看项目作品 <span aria-hidden="true">→</span></button>
          </div>
          ${focus.length ? `<div class="about-focus">${focus.map(item => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
        </div>
        <aside class="about-identity-card">
          <div class="about-monogram" aria-hidden="true">${escapeHtml(about.name_en || "JiaJia")}</div>
          <div>
            <p class="about-name-cn">${escapeHtml(about.name || "方菱葭")}</p>
            <p class="about-name-en">${escapeHtml(about.name_en || "Fangling Jia")}</p>
          </div>
          <div class="about-role">${escapeHtml(about.role || "游戏体验设计师")}</div>
          <p class="about-privacy-note">本页仅展示与作品集相关的职业信息。</p>
        </aside>
      </header>

      <section class="about-section">
        <div class="about-section-heading">
          <div class="section-kicker">Capabilities</div>
          <h2>从体验方案到真机落地</h2>
        </div>
        <div class="about-capability-grid">
          ${capabilities.map((item, index) => `
            <article class="about-capability-card">
              <span>${String(index + 1).padStart(2, "0")}</span>
              <h3>${escapeHtml(item.title || "")}</h3>
              <p>${escapeHtml(item.description || "")}</p>
            </article>`).join("")}
        </div>
      </section>

      <section class="about-section about-education-section">
        <div class="about-section-heading">
          <div class="section-kicker">Education</div>
          <h2>教育背景</h2>
        </div>
        <div class="about-education-list">
          ${education.map(item => `
            <article class="about-education-card">
              <span>${escapeHtml(item.period || "")}</span>
              <h3>${escapeHtml(item.school || "")}</h3>
              <p>${escapeHtml(item.degree || "")}</p>
            </article>`).join("")}
        </div>
      </section>

      <section class="about-section about-experience-section">
        <div class="about-section-heading">
          <div class="section-kicker">Experience</div>
          <h2>工作经历</h2>
        </div>
        <div class="about-timeline">
          ${experience.map(item => `
            <article class="about-timeline-item">
              <div class="about-timeline-meta">
                <span>${escapeHtml(item.period || "")}</span>
                <strong>${escapeHtml(item.company || "")}</strong>
              </div>
              <div class="about-timeline-content">
                <p class="about-product">${escapeHtml(item.product || "")}</p>
                <h3>${escapeHtml(item.role || "")}</h3>
                <p>${escapeHtml(item.summary || "")}</p>
                ${Array.isArray(item.details) && item.details.length ? `<ul>${item.details.map(detail => `<li>${escapeHtml(detail)}</li>`).join("")}</ul>` : ""}
              </div>
            </article>`).join("")}
        </div>
      </section>

      <section class="about-section about-toolkit-section">
        <div class="about-section-heading">
          <div class="section-kicker">Toolkit</div>
          <h2>工具与工作流</h2>
        </div>
        <div class="about-toolkit-layout">
          <div class="about-tool-group">
            <h3>设计与实现</h3>
            <div class="about-tool-cloud">${tools.map(item => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </div>
          <div class="about-tool-group">
            <h3>AI 协作</h3>
            <div class="about-tool-cloud accent">${aiTools.map(item => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </div>
        </div>
        ${languages.length ? `<p class="about-language">语言能力 · ${languages.map(escapeHtml).join(" / ")}</p>` : ""}
      </section>

      <footer class="about-footer">
        <p>继续查看我的系统玩法、运营活动与休闲小游戏设计。</p>
        <button type="button" class="hero-cta" data-back-home>返回项目列表 <span aria-hidden="true">→</span></button>
      </footer>
    </div>`;
}

function renderHome(data) {
  const labels   = getLabels(data.site, null);
  const heroImg  = data.site.hero_image || null;
  const owner    = data.site.owner  || "";
  const role     = data.site.role   || "";
  const bio      = data.site.bio    || "";
  const allTags  = data.site.all_tags || [];

  // Aggregated stats
  const totalProjects = data.projects.length;
  const totalScreens  = data.projects.reduce((s, p) => s + (p.screens?.length || 0), 0);
  const totalDocs     = data.projects.filter(p => p.interaction_doc).length;

  const tagCloud = allTags.length
    ? `<div class="hub-tags">${allTags.map((t, i) =>
        `<span class="hub-tag" data-edit-path="site.all_tags.${i}">${escapeHtml(t)}</span>`
      ).join("")}</div>`
    : "";

  return `
    <div class="shell">
      <nav class="portfolio-nav" aria-label="作品集导航">
        <div class="portfolio-mark">Fangling Jia · Portfolio</div>
        <div class="portfolio-nav-actions">
          <div class="portfolio-nav-meta">Game UX / Interaction Design · 2026</div>
          <button type="button" class="portfolio-about-button" data-open-about>个人主页 <span aria-hidden="true">→</span></button>
        </div>
      </nav>
      <header class="hub-hero editorial-hero panel">
        <div class="pixel-avatar" aria-hidden="true">
          <div class="pixel-girl">
            <i class="pg-hair"></i><i class="pg-face"></i><i class="pg-bangs"></i>
            <i class="pg-eye pg-eye-left"></i><i class="pg-eye pg-eye-right"></i>
            <i class="pg-blush pg-blush-left"></i><i class="pg-blush pg-blush-right"></i>
            <i class="pg-mouth"></i><i class="pg-neck"></i><i class="pg-shirt"></i>
          </div>
          <div class="pixel-gamepad">
            <i class="pad-body"></i><i class="pad-grip pad-grip-left"></i><i class="pad-grip pad-grip-right"></i>
            <i class="pad-cross"></i><i class="pad-button pad-button-a"></i><i class="pad-button pad-button-b"></i>
            <i class="pad-light"></i>
          </div>
        </div>
        <div class="hub-hero-left">
          <p class="hero-intro">${escapeHtml(role || "UX Designer")} · Independent Portfolio</p>
          <h1 class="hero-statement">把复杂玩法，设计成<em>清晰好玩</em>的体验。</h1>
          ${bio   ? `<p class="hub-bio" data-edit-path="site.bio">${escapeHtml(bio)}</p>` : ""}
          <div class="hero-footer">
            <div class="hero-primary-actions">
              <a class="hero-cta" href="#selected-work">浏览全部项目 <span aria-hidden="true">↓</span></a>
              <button type="button" class="hero-about-cta" data-open-about>了解我 / About <span aria-hidden="true">→</span></button>
            </div>
            ${tagCloud}
          </div>
        </div>
      </header>
      <section class="section panel editorial-section" id="selected-work">
        <div class="section-head">
          <div>
            <div class="section-kicker">Project Index</div>
            <h2 class="section-title">全部项目</h2>
          </div>
          ${state.manageMode ? `<button type="button" class="btn-outline" id="open-add-panel">+ 添加项目</button>` : ""}
        </div>
        ${data.site.asset_note ? `<div class="portfolio-disclosure"><strong>作品说明</strong><p>${escapeHtml(data.site.asset_note)}</p></div>` : ""}
        ${renderEqualProjectList(data)}
      </section>
    </div>
  `;
}

// Render the home page project list as either:
// - One grid per category (when site.categories is configured), or
// - A single ungrouped grid (when no categories are defined)
function renderProjectGroups(data) {
  const projects = Array.isArray(data.projects) ? data.projects : [];
  const categories = Array.isArray(data.site?.categories) ? data.site.categories : [];

  const renderCard = (project, globalIndex) => `
    <article class="panel project-card" data-project-id="${project.id}" role="button" tabindex="0" aria-label="查看项目：${escapeHtml(project.title)}">
      ${state.manageMode ? `<button type="button" class="manage-delete-btn" data-remove-project="${project.id}" title="删除此项目">✕</button>` : ""}
      <div class="project-cover">
        ${project.card_cover ? `<img src="${project.card_cover.thumb || project.card_cover.src}" alt="${escapeHtml(project.title)}" data-image-path="projects.${globalIndex}.card_cover.src" decoding="async" loading="lazy" />` : ""}
      </div>
      <div class="project-meta">
        <div class="case-overline"><span>Case ${String(globalIndex + 1).padStart(2, "0")}</span><span class="case-view">View case →</span></div>
        <h3 data-edit-path="projects.${globalIndex}.title">${escapeHtml(project.title)}</h3>
        ${project.subtitle ? `<p class="muted" data-edit-path="projects.${globalIndex}.subtitle">${escapeHtml(project.subtitle)}</p>` : ""}
        ${project.summary ? `<p class="muted" data-edit-path="projects.${globalIndex}.summary">${escapeHtml(project.summary)}</p>` : ""}
        ${renderTags(project.tags)}
      </div>
    </article>
  `;

  // No categories configured → fall back to one grid
  if (!categories.length) {
    return `
      <div class="project-grid">
        ${projects.map((p, i) => renderCard(p, i)).join("")}
      </div>
    `;
  }

  // Build a map: category id -> [(project, globalIndex)]
  const buckets = new Map();
  categories.forEach((c) => buckets.set(c.id, []));
  const uncategorized = [];
  projects.forEach((p, i) => {
    if (p.category && buckets.has(p.category)) {
      buckets.get(p.category).push([p, i]);
    } else {
      uncategorized.push([p, i]);
    }
  });

  const groups = categories
    .filter((c) => buckets.get(c.id).length > 0)
    .map((c) => {
      const items = buckets.get(c.id);
      return `
        <div class="project-category">
          <div class="project-category-head">
            <h3 class="project-category-label">${escapeHtml(c.label)}</h3>
            ${c.description ? `<p class="project-category-desc">${escapeHtml(c.description)}</p>` : ""}
          </div>
          <div class="project-grid">
            ${items.map(([p, i]) => renderCard(p, i)).join("")}
          </div>
        </div>
      `;
    });

  // Trailing "Other" group for any project missing / with unknown category
  if (uncategorized.length) {
    groups.push(`
      <div class="project-category">
        <div class="project-category-head">
          <h3 class="project-category-label">其他</h3>
        </div>
        <div class="project-grid">
          ${uncategorized.map(([p, i]) => renderCard(p, i)).join("")}
        </div>
      </div>
    `);
  }

  return groups.join("");
}

function renderEqualProjectList(data) {
  const projects = Array.isArray(data.projects) ? data.projects : [];
  const categories = Array.isArray(data.site?.categories) ? data.site.categories : [];
  const categoryLabels = new Map(categories.map((category) => [category.id, category.label]));
  const availableCategories = categories.filter((category) => projects.some((project) => project.category === category.id));
  const fallbackCategory = availableCategories[0]?.id || "";
  const activeCategory = availableCategories.some((category) => category.id === state.activeHomeCategory)
    ? state.activeHomeCategory
    : fallbackCategory;
  state.activeHomeCategory = activeCategory;
  const visibleProjects = projects
    .map((project, sourceIndex) => ({ project, sourceIndex }))
    .filter(({ project }) => !activeCategory || project.category === activeCategory);

  const tabs = availableCategories.map((category) => {
    const count = projects.filter((project) => project.category === category.id).length;
    const active = category.id === activeCategory;
    return `<button type="button" class="category-tab${active ? " is-active" : ""}" role="tab" aria-selected="${active}" data-home-category="${escapeHtml(category.id)}">
      <span>${escapeHtml(category.label)}</span><b>${String(count).padStart(2, "0")}</b>
    </button>`;
  }).join("");

  const cards = visibleProjects.map(({ project, sourceIndex }, visibleIndex) => {
    const index = sourceIndex;
    const categoryLabel = categoryLabels.get(project.category) || "Project";
    return `
      <article class="project-card project-row" data-project-id="${project.id}" role="button" tabindex="0" aria-label="View project: ${escapeHtml(project.title)}">
        ${state.manageMode ? `<button type="button" class="manage-delete-btn" data-remove-project="${project.id}" title="Remove project">×</button>` : ""}
        <div class="project-cover">
          ${project.card_cover ? `<img src="${project.card_cover.src || project.card_cover.thumb}" alt="${escapeHtml(project.title)}" data-image-path="projects.${index}.card_cover.src" decoding="async" loading="lazy" />` : ""}
        </div>
        <div class="project-meta">
          <div class="case-overline">
            <span>${String(visibleIndex + 1).padStart(2, "0")} · ${escapeHtml(categoryLabel)}</span>
            <span class="case-view">View case →</span>
          </div>
          <h3 data-edit-path="projects.${index}.title">${escapeHtml(project.title)}</h3>
          ${project.subtitle ? `<p class="project-subtitle" data-edit-path="projects.${index}.subtitle">${escapeHtml(project.subtitle)}</p>` : ""}
          ${project.summary ? `<p class="project-summary" data-edit-path="projects.${index}.summary">${escapeHtml(project.summary)}</p>` : ""}
          ${renderTags(project.tags)}
        </div>
      </article>`;
  });

  return `
    <div class="category-switcher" role="tablist" aria-label="Project categories">${tabs}</div>
    <div class="project-list" role="tabpanel">${cards.join("")}</div>`;
}

function renderInteractionDoc(project, projectIndex) {
  const labels = getLabels(state.data.site, project);
  if (!project.interaction_doc) {
    return `
      <section class="section panel">
        <div class="section-head">
          <div>
            <div class="section-kicker" data-edit-path="projects.${projectIndex}.labels.interaction_doc_kicker">${escapeHtml(labels.interaction_doc_kicker || "Document")}</div>
            <h2 class="section-title" data-edit-path="projects.${projectIndex}.labels.interaction_doc_title">${escapeHtml(labels.interaction_doc_title || "交互文档")}</h2>
          </div>
        </div>
        <div class="empty" data-edit-path="projects.${projectIndex}.labels.interaction_doc_empty">${escapeHtml(labels.interaction_doc_empty || "当前项目还没有配置交互文档。")}</div>
      </section>
    `;
  }

  const hasDocMeta = project.interaction_doc.title
    || project.interaction_doc.caption
    || project.interaction_doc.summary
    || (project.interaction_doc.notes && project.interaction_doc.notes.length)
    || (project.interaction_doc.states && project.interaction_doc.states.length);

  return `
    <section class="section panel">
      <div class="section-head">
        <div>
          <div class="section-kicker" data-edit-path="projects.${projectIndex}.labels.interaction_doc_kicker">${escapeHtml(labels.interaction_doc_kicker || "Document")}</div>
          <h2 class="section-title" data-edit-path="projects.${projectIndex}.labels.interaction_doc_title">${escapeHtml(labels.interaction_doc_title || "交互文档")}</h2>
          <p class="muted" data-edit-path="projects.${projectIndex}.labels.interaction_doc_description">${escapeHtml(labels.interaction_doc_description || "先展示整张交互文档，用来承接整体流程和页面关系说明。")}</p>
        </div>
      </div>
      <div class="doc-layout">
        <div class="doc-image-wrap" id="doc-wrap-${projectIndex}">
          <button type="button" class="doc-zoom-btn" data-doc-zoom="${escapeHtml(project.id)}" title="点击放大查看完整文档">⤢ 查看大图</button>
          <div class="doc-image">
            <img src="${project.interaction_doc.preview || project.interaction_doc.src}" alt="${escapeHtml(project.interaction_doc.title || "交互文档")}" data-image-path="projects.${projectIndex}.interaction_doc.src" data-doc-zoom="${escapeHtml(project.id)}" loading="lazy" decoding="async" />
          </div>
          <div class="doc-expand-bar">
            <button type="button" class="doc-expand-btn doc-expand-toggle" data-expand-toggle="${projectIndex}">
              <span class="doc-expand-icon">▼</span>
              <span class="doc-expand-label">展开查看完整文档</span>
            </button>
          </div>
          <div class="doc-collapse-bar">
            <button type="button" class="doc-expand-btn doc-expand-toggle" data-expand-toggle="${projectIndex}">
              <span class="doc-expand-icon">▲</span>
              <span class="doc-expand-label">收起文档</span>
            </button>
          </div>
        </div>
        ${hasDocMeta ? `
        <div class="doc-meta">
          <h3 data-edit-path="projects.${projectIndex}.interaction_doc.title">${escapeHtml(project.interaction_doc.title)}</h3>
          ${project.interaction_doc.caption ? `<p class="muted" data-edit-path="projects.${projectIndex}.interaction_doc.caption">${escapeHtml(project.interaction_doc.caption)}</p>` : ""}
          ${project.interaction_doc.summary ? `<p class="muted" data-edit-path="projects.${projectIndex}.interaction_doc.summary">${escapeHtml(project.interaction_doc.summary)}</p>` : ""}
          ${renderList(labels.doc_notes_title || "关键说明", project.interaction_doc.notes, "doc-list")}
          ${renderList(labels.doc_states_title || "流程节点", project.interaction_doc.states, "doc-list")}
        </div>` : ""}
      </div>
    </section>
  `;
}

function renderScreens(project, projectIndex) {
  // Allow per-project layout override (default = "grid"; "inline" = each
  // screen as a full-width block for poster-style art projects)
  const layout = project.display?.screens_layout || "grid";
  if (layout === "inline") {
    return renderScreensInline(project, projectIndex);
  }
  return renderScreensGrid(project, projectIndex);
}

function renderScreensGrid(project, projectIndex) {
  const labels = getLabels(state.data.site, project);
  const allScreens = Array.isArray(project.screens) ? project.screens : [];
  // Build a map from parent id -> array of child variant items
  const variantsByParent = {};
  allScreens.forEach((s) => {
    if (s && s.parent) {
      (variantsByParent[s.parent] = variantsByParent[s.parent] || []).push(s);
    }
  });
  // Cards only show top-level screens (those without a `parent` field)
  const topLevel = allScreens.filter((s) => s && !s.parent);

  if (!topLevel.length) {
    return `
      <section class="section panel">
        <div class="section-head">
          <div>
            <div class="section-kicker" data-edit-path="projects.${projectIndex}.labels.screens_kicker">${escapeHtml(labels.screens_kicker || "Screens")}</div>
            <h2 class="section-title" data-edit-path="projects.${projectIndex}.labels.screens_title">${escapeHtml(labels.screens_title || "单独界面")}</h2>
          </div>
        </div>
        <div class="empty" data-edit-path="projects.${projectIndex}.labels.screens_empty">${escapeHtml(labels.screens_empty || "当前项目还没有配置界面列表。")}</div>
      </section>
    `;
  }

  return `
    <section class="section panel">
      <div class="section-head">
        <div>
          <div class="section-kicker" data-edit-path="projects.${projectIndex}.labels.screens_kicker">${escapeHtml(labels.screens_kicker || "Screens")}</div>
          <h2 class="section-title" data-edit-path="projects.${projectIndex}.labels.screens_title">${escapeHtml(labels.screens_title || "单独界面")}</h2>
          <p class="muted" data-edit-path="projects.${projectIndex}.labels.screens_description">${escapeHtml(labels.screens_description || "点击卡片查看大图; 同一界面的多个状态会以子标签形式集中在大图视图里。")}</p>
        </div>
      </div>
      <div class="screen-grid">
        ${topLevel.map((screen, topIndex) => {
          const title = screen.title || screen.hover_title || "";
          const notes = Array.isArray(screen.notes) ? screen.notes : [];
          const variantCount = (variantsByParent[screen.id] || []).length;
          const canManage = state.editMode && state.manageMode;
          return `
          <article class="panel screen-card" data-screen-index="${topIndex}" tabindex="0">
            <span class="screen-zoom-badge" aria-hidden="true">⤢</span>
            ${variantCount > 0 ? `<span class="screen-variant-badge" title="${variantCount + 1} 个状态">+${variantCount} 状态</span>` : ""}
            ${canManage ? `<button type="button" class="manage-delete-btn screen-delete-btn" data-remove-screen="${escapeHtml(screen.relative_path || "")}" title="删除此界面">✕</button>` : ""}
            <div class="screen-image">
              <img src="${screen.src}" alt="${escapeHtml(screen.title)}" loading="lazy" decoding="async"
                   data-image-path="projects.${projectIndex}.screens.${topIndex}.src" />
            </div>
            <div class="screen-desc">
              <h4 data-edit-path="projects.${projectIndex}.screens.${topIndex}.title">${escapeHtml(title)}</h4>
              ${notes.length ? `<ul class="screen-desc-notes">${notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>` : ""}
            </div>
          </article>`;
        }).join("")}
        ${state.editMode && state.manageMode ? `
          <article class="panel screen-card screen-add-tile" id="screen-add-tile" data-project-slot="${escapeHtml(project.id)}">
            <div class="screen-add-inner">
              <span class="screen-add-plus">+</span>
              <span class="screen-add-label">添加界面</span>
              <span class="screen-add-hint">点击上传图片并填写描述</span>
            </div>
          </article>` : ""}
      </div>
    </section>
  `;
}

// Inline layout — each item rendered as a full-width block: large image
// on top, optional section kicker + title + notes below. Reuses the
// existing screen lightbox on click for max-zoom inspection.
function renderScreensInline(project, projectIndex) {
  const labels = getLabels(state.data.site, project);
  const allScreens = Array.isArray(project.screens) ? project.screens : [];
  // Inline layout treats every screen as a top-level showcase page; parent
  // variants would be confusing here, so we still filter to top-level but
  // include parented items as separate rows. (Poster-style projects
  // typically don't use the parent grouping.)
  const items = allScreens.filter((s) => s && !s.parent);

  if (!items.length) {
    return `
      <section class="section panel">
        <div class="section-head">
          <div>
            <div class="section-kicker">Screens</div>
            <h2 class="section-title">${escapeHtml(labels.screens_title || "单独界面")}</h2>
          </div>
        </div>
        <div class="empty">当前项目还没有配置界面列表。</div>
      </section>
    `;
  }

  return `
    <section class="section panel">
      <div class="section-head">
        <div>
          <div class="section-kicker">Pages</div>
          <h2 class="section-title">${escapeHtml(labels.screens_title || "单独界面")}</h2>
          <p class="muted">每页完整展示, 点击图片可放大查看细节。</p>
        </div>
      </div>
      <div class="screen-inline-list">
        ${items.map((screen, topIndex) => {
          const title = screen.title || screen.hover_title || "";
          const section = screen.section || "";
          const notes = Array.isArray(screen.notes) ? screen.notes : [];
          return `
            <article class="screen-inline-card" data-screen-index="${topIndex}" tabindex="0">
              <div class="screen-inline-image">
                <img src="${screen.src}" alt="${escapeHtml(screen.title || "")}"
                     loading="lazy" decoding="async" />
                <div class="screen-inline-zoom">⤢ 点击放大</div>
              </div>
              <div class="screen-inline-meta">
                ${section ? `<div class="screen-inline-section">${escapeHtml(section)}</div>` : ""}
                <h3>${escapeHtml(title)}</h3>
                ${notes.length ? `<ul class="screen-inline-notes">${notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>` : ""}
              </div>
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function renderFlow(project, projectIndex) {
  const flow = project.flow;
  const canEdit = state.editMode && state.manageMode;
  if (!flow || !Array.isArray(flow.nodes) || !flow.nodes.length) {
    if (canEdit) {
      return `
        <section class="section panel">
          <div class="section-head">
            <div>
              <div class="section-kicker">Flow</div>
              <h2 class="section-title">交互流程图</h2>
              <p class="muted">当前项目还没有流程图, 点右侧按钮新建。</p>
            </div>
            <button type="button" class="btn-outline" id="flow-edit-btn" data-project-id="${escapeHtml(project.id)}">✎ 编辑流程图</button>
          </div>
        </section>
      `;
    }
    return "";
  }

  const cols = Math.max(...flow.nodes.map(n => n.col || 0)) + 1;
  const rows = Math.max(...flow.nodes.map(n => n.row || 0)) + 1;

  return `
    <section class="section panel">
      <div class="section-head">
        <div>
          <div class="section-kicker">Flow</div>
          <h2 class="section-title">${escapeHtml(flow.title || "交互流程图")}</h2>
          ${flow.description ? `<p class="muted">${escapeHtml(flow.description)}</p>` : ""}
        </div>
        ${canEdit ? `<button type="button" class="btn-outline" id="flow-edit-btn" data-project-id="${escapeHtml(project.id)}">✎ 编辑流程图</button>` : ""}
      </div>
      <div class="flow-wrap">
        <div class="flow-container" id="flow-${projectIndex}"
             style="grid-template-columns:repeat(${cols},180px);grid-template-rows:repeat(${rows},auto)">
          <svg class="flow-svg" id="flow-svg-${projectIndex}" aria-hidden="true"></svg>
          ${flow.nodes.map(node => {
            const screen = (project.screens || []).find(s => s.id === node.screen_id)
                        || (project.interaction_doc?.id === node.screen_id ? project.interaction_doc : null);
            return `
              <div class="flow-node" id="fnode-${projectIndex}-${escapeHtml(node.id)}"
                   style="grid-column:${(node.col||0)+1};grid-row:${(node.row||0)+1}">
                ${screen
                  ? `<img src="${screen.src}" alt="${escapeHtml(node.label)}" loading="lazy" decoding="async" />`
                  : `<div class="flow-node-placeholder"></div>`}
                <div class="flow-node-label">${escapeHtml(node.label)}</div>
              </div>`;
          }).join("")}
        </div>
      </div>
    </section>
  `;
}

// ── Showcase section (artwork gallery) ──────────────────────────────────
function renderShowcase(project, projectIndex) {
  const items = Array.isArray(project.showcase) ? project.showcase : [];
  const canEdit = state.editMode && state.manageMode;
  if (!items.length && !canEdit) return "";

  const head = `
      <div class="section-head">
        <div>
          <div class="section-kicker">Showcase</div>
          <h2 class="section-title">作品展示</h2>
          <p class="muted">完整作品集 — 点击放大查看细节, 配合说明阅读。</p>
        </div>
      </div>
  `;

  if (!items.length) {
    return `
      <section class="section panel">
        ${head}
        <div class="empty">在 site.meta.json 中添加 showcase[] 条目即可上架: { "file": "art.jpg", "title": "...", "description": "..." }</div>
      </section>
    `;
  }

  return `
    <section class="section panel">
      ${head}
      <div class="showcase-list">
        ${items.map((it, i) => `
          <article class="showcase-card" data-showcase-index="${i}" tabindex="0">
            <div class="showcase-image">
              <img src="${escapeHtml(it.src)}" alt="${escapeHtml(it.title || "")}"
                   loading="lazy" decoding="async" />
              <div class="screen-inline-zoom">⤢ 点击放大</div>
            </div>
            ${(it.title || it.description) ? `
              <div class="showcase-meta">
                ${it.title ? `<h3>${escapeHtml(it.title)}</h3>` : ""}
                ${it.description ? `<p class="muted">${escapeHtml(it.description)}</p>` : ""}
              </div>
            ` : ""}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function openShowcaseLightbox(idx) {
  const project = (state.data?.projects || []).find(p => p.id === state.currentProjectId);
  if (!project || !Array.isArray(project.showcase) || !project.showcase.length) return;
  state.lightboxShowcaseIndex = Math.max(0, Math.min(idx, project.showcase.length - 1));
  if (!document.getElementById("showcase-lightbox-overlay")) {
    document.body.insertAdjacentHTML("beforeend", renderShowcaseLightbox(project));
    bindShowcaseLightbox(project);
  } else {
    refreshShowcaseLightbox(project);
  }
}

function renderShowcaseLightbox(project) {
  const items = project.showcase;
  const idx = Math.max(0, Math.min(state.lightboxShowcaseIndex || 0, items.length - 1));
  const item = items[idx];
  if (!item) return "";
  return `
    <div class="lightbox-overlay" id="showcase-lightbox-overlay">
      <button type="button" class="lightbox-close" id="showcase-lb-close" title="关闭 (ESC)">✕</button>
      <button type="button" class="lightbox-nav lightbox-nav-prev" id="showcase-lb-prev" title="上一张 (←)">‹</button>
      <button type="button" class="lightbox-nav lightbox-nav-next" id="showcase-lb-next" title="下一张 (→)">›</button>
      <div class="lightbox-content">
        <div class="lightbox-image-wrap">
          <img src="${escapeHtml(item.src)}" alt="${escapeHtml(item.title || "")}" />
        </div>
        <aside class="lightbox-info">
          ${item.title ? `<h2 class="lightbox-title">${escapeHtml(item.title)}</h2>` : ""}
          ${item.description ? `<p class="lightbox-desc">${escapeHtml(item.description)}</p>` : ""}
          <div class="lightbox-counter">作品 ${idx + 1} / ${items.length}</div>
        </aside>
      </div>
    </div>
  `;
}

function refreshShowcaseLightbox(project) {
  const overlay = document.getElementById("showcase-lightbox-overlay");
  if (!overlay) return;
  const html = renderShowcaseLightbox(project);
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  const next = tmp.firstElementChild;
  if (!next) return;
  overlay.replaceWith(next);
  bindShowcaseLightbox(project);
}

function bindShowcaseLightbox(project) {
  const overlay = document.getElementById("showcase-lightbox-overlay");
  if (!overlay) return;
  const total = project.showcase.length;
  const close = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
  };
  const navTo = (delta) => {
    state.lightboxShowcaseIndex = ((state.lightboxShowcaseIndex + delta) % total + total) % total;
    refreshShowcaseLightbox(project);
  };
  const onKey = (e) => {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") navTo(-1);
    else if (e.key === "ArrowRight") navTo(1);
  };
  overlay.querySelector("#showcase-lb-close").addEventListener("click", close);
  overlay.querySelector("#showcase-lb-prev").addEventListener("click", () => navTo(-1));
  overlay.querySelector("#showcase-lb-next").addEventListener("click", () => navTo(1));
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", onKey);
}

// ── PDF / Documents section ──────────────────────────────────────────────
function renderPdfs(project, projectIndex) {
  const pdfs = Array.isArray(project.pdfs) ? project.pdfs : [];
  const canEdit = state.editMode && state.manageMode;
  if (!pdfs.length && !canEdit) return "";

  const head = `
      <div class="section-head">
        <div>
          <div class="section-kicker">Document</div>
          <h2 class="section-title">作品 PDF</h2>
          <p class="muted">嵌入查看完整 PDF, 或下载到本地高保真浏览。</p>
        </div>
      </div>
  `;

  if (!pdfs.length) {
    return `
      <section class="section panel">
        ${head}
        <div class="empty">在 site.meta.json 中加入 "pdf": "filename.pdf" 即可上架。</div>
      </section>
    `;
  }

  return `
    <section class="section panel">
      ${head}
      <div class="pdf-list">
        ${pdfs.map((pdf, i) => {
          const safeSrc = escapeHtml(pdf.src);
          const sizeChip = pdf.size_label ? `<span class="pdf-chip">${escapeHtml(pdf.size_label)}</span>` : "";
          const pagesChip = pdf.page_count ? `<span class="pdf-chip">${escapeHtml(String(pdf.page_count))} 页</span>` : "";
          return `
            <article class="panel pdf-card" data-pdf-index="${i}">
              <div class="pdf-meta">
                <div class="pdf-meta-text">
                  <h3>${escapeHtml(pdf.title || "")}</h3>
                  ${pdf.description ? `<p class="muted">${escapeHtml(pdf.description)}</p>` : ""}
                  <div class="pdf-chips">${sizeChip}${pagesChip}</div>
                </div>
                <div class="pdf-meta-actions">
                  <a class="pdf-btn pdf-btn-primary" href="${safeSrc}" target="_blank" rel="noopener" title="在新标签页全屏查看">
                    <span>📖</span><span>全屏查看</span>
                  </a>
                  <a class="pdf-btn" href="${safeSrc}" download title="下载到本地">
                    <span>⬇</span><span>下载</span>
                  </a>
                </div>
              </div>
              <div class="pdf-embed">
                <object data="${safeSrc}#view=FitH&toolbar=1" type="application/pdf" width="100%" height="720">
                  <iframe src="${safeSrc}" width="100%" height="720" loading="lazy"
                          title="${escapeHtml(pdf.title || "PDF")}"></iframe>
                  <p class="muted">浏览器无法嵌入预览 — <a href="${safeSrc}" target="_blank" rel="noopener">点击在新标签打开</a> 或 <a href="${safeSrc}" download>下载</a>。</p>
                </object>
              </div>
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

// ── Videos section ──────────────────────────────────────────────────────
function renderVideos(project, projectIndex) {
  const labels = getLabels(state.data.site, project);
  const videos = Array.isArray(project.videos) ? project.videos : [];
  const canEdit = state.editMode && state.manageMode;

  if (!videos.length && !canEdit) return "";

  const head = `
      <div class="section-head">
        <div>
          <div class="section-kicker">Videos</div>
          <h2 class="section-title">演示视频</h2>
        </div>
      </div>
  `;

  if (!videos.length) {
    return `
      <section class="section panel">
        ${head}
        <div class="empty">当前项目还没有演示视频, 在 site.meta.json 的 videos[] 中加入条目即可。</div>
      </section>
    `;
  }

  return `
    <section class="section panel">
      ${head}
      <div class="video-grid">
        ${videos.map((video, vIndex) => {
          const posterSrc = video.poster?.src || "";
          const caption = video.caption || "";
          const section = video.section || "";
          return `
            <article class="panel video-card" data-video-index="${vIndex}" tabindex="0">
              <div class="video-thumb">
                ${posterSrc
                  ? `<img src="${escapeHtml(posterSrc)}" alt="${escapeHtml(video.title || "")}" loading="lazy" decoding="async" />`
                  : `<video src="${escapeHtml(video.src)}" preload="none" muted playsinline></video>`}
                <div class="video-thumb-shade"></div>
                <span class="video-play-icon" aria-hidden="true">▶</span>
                ${video.duration ? `<span class="video-duration">${escapeHtml(video.duration)}</span>` : ""}
              </div>
              <div class="video-meta">
                ${section ? `<div class="video-section">${escapeHtml(section)}</div>` : ""}
                <h4>${escapeHtml(video.title || "")}</h4>
                ${caption ? `<p class="muted">${escapeHtml(caption)}</p>` : ""}
              </div>
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function openVideoLightbox(videoIndex) {
  const project = (state.data?.projects || []).find(p => p.id === state.currentProjectId);
  if (!project) return;
  const videos = Array.isArray(project.videos) ? project.videos : [];
  if (!videos.length) return;
  state.lightboxVideoIndex = Math.max(0, Math.min(videoIndex, videos.length - 1));
  if (!document.getElementById("video-lightbox-overlay")) {
    document.body.insertAdjacentHTML("beforeend", renderVideoLightbox(project));
    bindVideoLightbox(project);
  }
}

function renderVideoLightbox(project) {
  const idx = state.lightboxVideoIndex || 0;
  const video = project.videos[idx];
  if (!video) return "";
  const total = project.videos.length;
  const caption = video.caption || "";
  return `
    <div class="lightbox-overlay video-lightbox" id="video-lightbox-overlay">
      <button type="button" class="lightbox-close" id="video-lb-close" title="关闭 (ESC)">✕</button>
      <button type="button" class="lightbox-nav lightbox-nav-prev" id="video-lb-prev" title="上一段 (←)">‹</button>
      <button type="button" class="lightbox-nav lightbox-nav-next" id="video-lb-next" title="下一段 (→)">›</button>
      <div class="lightbox-content video-lightbox-content">
        <div class="lightbox-image-wrap video-stage">
          <video id="video-lb-player" src="${escapeHtml(video.src)}" controls autoplay playsinline preload="metadata"
                 ${video.poster?.src ? `poster="${escapeHtml(video.poster.src)}"` : ""}></video>
        </div>
        <aside class="lightbox-info">
          ${video.section ? `<div class="lightbox-section">${escapeHtml(video.section)}</div>` : ""}
          <h2 class="lightbox-title">${escapeHtml(video.title || "")}</h2>
          ${caption ? `<p class="lightbox-desc">${escapeHtml(caption)}</p>` : ""}
          <div class="lightbox-counter">${idx + 1} / ${total}</div>
        </aside>
      </div>
    </div>
  `;
}

function bindVideoLightbox(project) {
  const overlay = document.getElementById("video-lightbox-overlay");
  if (!overlay) return;
  const close = () => {
    const player = overlay.querySelector("#video-lb-player");
    if (player) { try { player.pause(); } catch {} }
    overlay.remove();
    document.removeEventListener("keydown", onKey);
  };
  const navTo = (delta) => {
    const total = project.videos.length;
    state.lightboxVideoIndex = ((state.lightboxVideoIndex + delta) % total + total) % total;
    const html = renderVideoLightbox(project);
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    const next = tmp.firstElementChild;
    if (next) {
      overlay.replaceWith(next);
      bindVideoLightbox(project);
    }
  };
  const onKey = (e) => {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") navTo(-1);
    else if (e.key === "ArrowRight") navTo(1);
  };
  overlay.querySelector("#video-lb-close").addEventListener("click", close);
  overlay.querySelector("#video-lb-prev").addEventListener("click", () => navTo(-1));
  overlay.querySelector("#video-lb-next").addEventListener("click", () => navTo(1));
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", onKey);
}

function drawFlowArrows(projectIndex, flow) {
  if (!flow?.nodes?.length || !flow?.edges?.length) return;
  const container = document.getElementById(`flow-${projectIndex}`);
  const svg       = document.getElementById(`flow-svg-${projectIndex}`);
  if (!container || !svg) return;

  const cr = container.getBoundingClientRect();
  svg.style.width  = cr.width  + "px";
  svg.style.height = cr.height + "px";

  const pos = {};
  flow.nodes.forEach(node => {
    const el = document.getElementById(`fnode-${projectIndex}-${node.id}`);
    if (!el) return;
    const r = el.getBoundingClientRect();
    pos[node.id] = {
      cx: r.left - cr.left + r.width  / 2,
      cy: r.top  - cr.top  + r.height / 2,
      x1: r.left - cr.left,
      x2: r.left - cr.left + r.width,
      y1: r.top  - cr.top,
      y2: r.top  - cr.top  + r.height,
      w:  r.width, h: r.height,
    };
  });

  const maxY2 = Math.max(...Object.values(pos).map(p => p.y2));
  const backRailY = maxY2 + 52;   // horizontal rail under all nodes

  const idFwd  = `ahf${projectIndex}`;
  const idBack = `ahb${projectIndex}`;
  let inner = `
    <defs>
      <marker id="${idFwd}" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
        <polygon points="0 0,9 3.5,0 7" fill="rgba(124,92,255,0.85)" />
      </marker>
      <marker id="${idBack}" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
        <polygon points="0 0,9 3.5,0 7" fill="rgba(94,234,212,0.75)" />
      </marker>
    </defs>`;

  let backOffset = 0;   // stagger multiple back arrows so rails don't overlap

  (flow.edges || []).forEach(edge => {
    const f = pos[edge.from];
    const t = pos[edge.to];
    if (!f || !t) return;

    const isBack = edge.type === "back" || (f.cx > t.cx + 20);
    let d, lx, ly;

    if (!isBack) {
      // Forward: cubic bezier – exit right, enter left
      const x1 = f.x2 + 3, y1 = f.cy;
      const x2 = t.x1 - 3, y2 = t.cy;
      const mx  = (x1 + x2) / 2;
      d  = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
      // Label above midpoint of curve
      lx = mx;
      ly = (y1 + y2) / 2 - 14;
    } else {
      // Back: orthogonal L-route with rounded corners going below all nodes
      backOffset += 0;   // same rail, OK for most cases
      const railY = backRailY + backOffset;
      const rc = 10;     // corner radius
      const x1 = f.cx, y1 = f.y2 + 3;
      const x2 = t.cx, y2 = t.y2 + 3;
      const goLeft = x2 < x1;
      // Path: straight down → corner → horizontal → corner → straight up
      d = `M${x1},${y1}
           L${x1},${railY - rc}
           Q${x1},${railY} ${goLeft ? x1 - rc : x1 + rc},${railY}
           L${goLeft ? x2 + rc : x2 - rc},${railY}
           Q${x2},${railY} ${x2},${railY - rc}
           L${x2},${y2}`;
      lx = (x1 + x2) / 2;
      ly = railY + 16;
    }

    const cls = isBack ? "flow-arrow-back" : "flow-arrow";
    const mid = isBack ? idBack : idFwd;
    inner += `<path d="${d}" class="${cls}" marker-end="url(#${mid})" />`;

    if (edge.label) {
      const tw = edge.label.length * 7 + 14;
      const th = 18;
      inner += `
        <rect x="${lx - tw/2}" y="${ly - th/2}" width="${tw}" height="${th}"
              rx="4" ry="4" class="flow-edge-label-bg" />
        <text x="${lx}" y="${ly}" class="flow-edge-label">${escapeHtml(edge.label)}</text>`;
    }
  });

  svg.innerHTML = inner;
}

function renderPrototype(project, projectIndex) {
  const labels = getLabels(state.data.site, project);
  const protoEnabled = Boolean(state.data.site.prototype_enabled) || Boolean(project.prototype?.enabled);
  if (!protoEnabled) {
    return `
      <section class="section panel" id="prototype-section">
        <div class="section-head">
          <div>
            <div class="section-kicker" data-edit-path="projects.${projectIndex}.labels.prototype_kicker">${escapeHtml(labels.prototype_kicker || "Prototype")}</div>
            <h2 class="section-title" data-edit-path="projects.${projectIndex}.labels.prototype_title">${escapeHtml(labels.prototype_title || "动态交互原型")}</h2>
            <p class="muted" data-edit-path="projects.${projectIndex}.labels.prototype_disabled">${escapeHtml(labels.prototype_disabled || "当前未启用原型模块。只有在明确要求生成可演示交互原型时，才会渲染这一段内容。")}</p>
          </div>
        </div>
      </section>
    `;
  }

  if (!hasPrototype(project)) {
    return `
      <section class="section panel" id="prototype-section">
        <div class="section-head">
          <div>
            <div class="section-kicker" data-edit-path="projects.${projectIndex}.labels.prototype_kicker">${escapeHtml(labels.prototype_kicker || "Prototype")}</div>
            <h2 class="section-title" data-edit-path="projects.${projectIndex}.labels.prototype_title">${escapeHtml(labels.prototype_title || "动态交互原型")}</h2>
            <p class="muted" data-edit-path="projects.${projectIndex}.labels.prototype_empty">${escapeHtml(labels.prototype_empty || "原型模块已启用，但当前项目尚未配置 prototype 场景数据。")}</p>
          </div>
        </div>
      </section>
    `;
  }

  const scene = getCurrentScene(project);
  const hotspots = Array.isArray(scene.hotspots) ? scene.hotspots : [];
  const activeHotspot = hotspots[state.activeHotspotIndex] || null;

  return `
    <section class="section panel" id="prototype-section">
      <div class="section-head">
        <div>
          <div class="section-kicker" data-edit-path="projects.${projectIndex}.labels.prototype_kicker">${escapeHtml(labels.prototype_kicker || "Prototype")}</div>
          <h2 class="section-title" data-edit-path="projects.${projectIndex}.labels.prototype_title">${escapeHtml(labels.prototype_title || "动态交互原型")}</h2>
          <p class="muted" data-edit-path="projects.${projectIndex}.labels.prototype_description">${escapeHtml(labels.prototype_description || "流程和热点说明来自交互文档整理后的原型配置。")}</p>
        </div>
      </div>
      <div class="proto-layout">
        <div class="panel proto-main">
          <h3 data-edit-path="projects.${projectIndex}.prototype.scenes.${state.currentSceneIndex}.title">${escapeHtml(scene.title)}</h3>
          ${scene.summary ? `<p class="muted" data-edit-path="projects.${projectIndex}.prototype.scenes.${state.currentSceneIndex}.summary">${escapeHtml(scene.summary)}</p>` : ""}
          <div class="proto-stage">
            <img src="${scene.src}" alt="${escapeHtml(scene.title)}" data-image-path="projects.${projectIndex}.prototype.scenes.${state.currentSceneIndex}.src" loading="lazy" decoding="async" />
            ${hotspots.map((hotspot, index) => {
              const isNav = hotspot.goto_scene_index !== undefined && hotspot.goto_scene_index !== null;
              const label = escapeHtml(hotspot.label || hotspot.title || (isNav ? "→" : String(index + 1)));
              const title = escapeHtml(hotspot.title || hotspot.label || `热点 ${index + 1}`);
              const gotoAttr = isNav ? `data-goto-scene="${hotspot.goto_scene_index}"` : "";
              const cls = `proto-hotspot${isNav ? " proto-hotspot-nav" : ""}${(!isNav && index === state.activeHotspotIndex) ? " active" : ""}`;
              return `<button type="button" class="${cls}"
                style="left:${Number(hotspot.x)||0}%;top:${Number(hotspot.y)||0}%"
                data-hotspot-index="${index}" ${gotoAttr}
                title="${title}"
              >${isNav ? `${label} →` : String(index + 1)}</button>`;
            }).join("")}
          </div>
          ${activeHotspot ? `
            <div class="proto-panel">
              <h4>${escapeHtml(activeHotspot.title || activeHotspot.label || labels.hotspot_title || "热点说明")}</h4>
              <p class="muted">${escapeHtml(activeHotspot.content || activeHotspot.description || "")}</p>
            </div>
          ` : ""}
        </div>
        <aside class="panel proto-side">
          <div>
            <h3 data-edit-path="projects.${projectIndex}.labels.scene_list_title">${escapeHtml(labels.scene_list_title || "流程场景")}</h3>
            <div class="proto-nav">
              ${project.prototype.scenes.map((item, index) => `
                <button type="button" class="${index === state.currentSceneIndex ? "active" : ""}" data-scene-index="${index}">
                  ${index + 1}. ${escapeHtml(item.title)}
                </button>
              `).join("")}
            </div>
          </div>
          ${renderList(labels.steps_title || "步骤说明", scene.steps, "proto-step-list")}
          ${hotspots.length ? `
            <div>
              <h3 data-edit-path="projects.${projectIndex}.labels.hotspot_title">${escapeHtml(labels.hotspot_title || "热点说明")}</h3>
              <div class="proto-hotspot-list">
                ${hotspots.map((item, index) => `
                  <button type="button" class="${index === state.activeHotspotIndex ? "active" : ""}" data-hotspot-index="${index}">
                    ${index + 1}. ${escapeHtml(item.title || item.label || "未命名热点")}
                  </button>
                `).join("")}
              </div>
            </div>
          ` : ""}
        </aside>
      </div>
    </section>
  `;
}

function renderContribution(project, projectIndex) {
  const contribution = project.contribution;
  if (!contribution || typeof contribution !== "object") return "";
  const items = Array.isArray(contribution.items) ? contribution.items : [];
  return `
    <section class="section panel contribution-section" id="contribution-section">
      <div class="section-head">
        <div>
          <div class="section-kicker">Contribution</div>
          <h2 class="section-title" data-edit-path="projects.${projectIndex}.contribution.title">${escapeHtml(contribution.title || "个人职责")}</h2>
          ${contribution.summary ? `<p class="contribution-summary" data-edit-path="projects.${projectIndex}.contribution.summary">${escapeHtml(contribution.summary)}</p>` : ""}
        </div>
      </div>
      ${items.length ? `<div class="contribution-grid">
        ${items.map((item, itemIndex) => `
          <article class="contribution-item">
            <h3 data-edit-path="projects.${projectIndex}.contribution.items.${itemIndex}.title">${escapeHtml(item.title || "")}</h3>
            <p data-edit-path="projects.${projectIndex}.contribution.items.${itemIndex}.description">${escapeHtml(item.description || "")}</p>
          </article>`).join("")}
      </div>` : ""}
    </section>`;
}

function renderProject(project, projectIndex) {
  const labels = getLabels(state.data.site, project);
  return `
    <div class="shell">
      <div class="topbar">
        <button type="button" class="back-button" data-back-home data-edit-path="projects.${projectIndex}.labels.back_to_home">${escapeHtml(labels.back_to_home || "返回项目总览")}</button>
      </div>
      <header class="hero">
        <section class="panel hero-copy">
          <div class="eyebrow" data-edit-path="projects.${projectIndex}.labels.project_detail_eyebrow">${escapeHtml(labels.project_detail_eyebrow || "Project Detail")}</div>
          <h1 class="title" data-edit-path="projects.${projectIndex}.title">${escapeHtml(project.title)}</h1>
          ${project.subtitle ? `<p class="subtitle" data-edit-path="projects.${projectIndex}.subtitle">${escapeHtml(project.subtitle)}</p>` : ""}
          ${project.summary ? `<p class="description" data-edit-path="projects.${projectIndex}.summary">${escapeHtml(project.summary)}</p>` : ""}
          ${renderTags(project.tags)}
        </section>
        <section class="panel hero-preview">
          ${project.cover ? `<img src="${project.cover.src}" alt="${escapeHtml(project.title)}" data-image-path="projects.${projectIndex}.cover.src" decoding="async" fetchpriority="high" />` : ""}
        </section>
      </header>
      ${renderContribution(project, projectIndex)}
      ${isSectionVisible(project.id, "interaction_doc") ? renderInteractionDoc(project, projectIndex) : ""}
      ${isSectionVisible(project.id, "screens")         ? renderScreens(project, projectIndex) : ""}
      ${isSectionVisible(project.id, "videos")          ? renderVideos(project, projectIndex) : ""}
      ${isSectionVisible(project.id, "pdfs")            ? renderPdfs(project, projectIndex) : ""}
      ${isSectionVisible(project.id, "showcase")        ? renderShowcase(project, projectIndex) : ""}
      ${renderCustomSections(project.id, projectIndex)}
    </div>
  `;
}

function render() {
  if (!state.data || !Array.isArray(state.data.projects)) {
    app.innerHTML = '<div class="empty">No project data found.</div>';
    return;
  }

  const projectIndex = state.currentProjectId
    ? state.data.projects.findIndex((project) => project && project.id === state.currentProjectId)
    : -1;
  const project = projectIndex >= 0 ? state.data.projects[projectIndex] : null;
  // Edit mode UI only shows when management server is reachable (local dev).
  // Public GitHub Pages deploy gets no /api/status -> manageMode=false -> no toolbar.
  app.classList.toggle("edit-mode", state.editMode && state.manageMode);
  try {
    const toolbar = state.manageMode ? renderEditorToolbar() : "";
    app.innerHTML = `${toolbar}${state.showAbout ? renderAbout(state.data) : (project ? renderProject(project, projectIndex) : renderHome(state.data))}`;
  } catch (err) {
    console.error("render failed:", err);
    const stack = (err && (err.stack || err.message)) || String(err);
    app.innerHTML = `<div class="empty" style="padding:24px;white-space:pre-wrap;font-family:monospace;font-size:12px;color:#f87171;">Render error.${escapeHtml(" — ") + escapeHtml(stack)}</div>`;
    return;
  }
  bindEditorInteractions();
  if (state.manageMode) bindManageInteractions();

  // Section manager button
  document.getElementById("open-section-panel")?.addEventListener("click", () => {
    if (!project || document.getElementById("section-mgr-overlay")) return;
    document.body.insertAdjacentHTML("beforeend", renderSectionPanel(project));
    bindSectionPanel(project);
  });

  // Draw flow arrows after DOM is ready
  if (project?.flow) {
    requestAnimationFrame(() => drawFlowArrows(projectIndex, project.flow));
  }

  document.querySelectorAll("[data-home-category]").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.activeHomeCategory = tab.getAttribute("data-home-category") || "casual-events";
      render();
      document.getElementById("selected-work")?.scrollIntoView({ block: "start" });
    });
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const tabs = [...document.querySelectorAll("[data-home-category]")];
      const current = tabs.indexOf(tab);
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(current + offset + tabs.length) % tabs.length];
      event.preventDefault();
      next?.click();
      requestAnimationFrame(() => document.querySelector(`[data-home-category="${state.activeHomeCategory}"]`)?.focus());
    });
  });

  document.querySelectorAll("[data-project-id]").forEach((node) => {
    node.addEventListener("click", () => {
      if (state.editMode) {
        return;
      }
      setProject(node.getAttribute("data-project-id"));
    });
    node.addEventListener("keydown", (event) => {
      if (state.editMode || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      setProject(node.getAttribute("data-project-id"));
    });
  });

  document.querySelectorAll("[data-back-home]").forEach((node) => {
    node.addEventListener("click", () => {
      if (state.editMode) {
        return;
      }
      setProject(null);
    });
  });

  document.querySelectorAll("[data-open-about]").forEach((node) => {
    node.addEventListener("click", () => {
      if (!state.editMode) openAbout();
    });
  });

  document.querySelectorAll("[data-scene-index]").forEach((node) => {
    node.addEventListener("click", () => setScene(Number(node.getAttribute("data-scene-index"))));
  });

  document.querySelectorAll("[data-hotspot-index]").forEach((node) => {
    node.addEventListener("click", () => {
      const idx = Number(node.getAttribute("data-hotspot-index"));
      const gotoAttr = node.getAttribute("data-goto-scene");
      if (gotoAttr !== null && gotoAttr !== "") {
        // Navigation hotspot: switch scene and reset hotspot selection
        setScene(Number(gotoAttr));
      } else {
        setHotspot(idx);
      }
    });
  });

  // Click on screen card (grid OR inline) → open screen lightbox
  // (only when not in edit mode, since edit mode reserves clicks for
  // inline image / text editing).
  document.querySelectorAll(".screen-card[data-screen-index], .screen-inline-card[data-screen-index]").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (state.editMode) return;
      if (e.target.closest(".manage-delete-btn")) return;
      const idx = Number(card.dataset.screenIndex);
      openScreenLightbox(idx);
    });
    card.addEventListener("keydown", (e) => {
      if (state.editMode) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const idx = Number(card.dataset.screenIndex);
        openScreenLightbox(idx);
      }
    });
  });

  // Click on showcase card → open showcase lightbox
  document.querySelectorAll(".showcase-card[data-showcase-index]").forEach((card) => {
    card.addEventListener("click", () => {
      if (state.editMode) return;
      openShowcaseLightbox(Number(card.dataset.showcaseIndex));
    });
    card.addEventListener("keydown", (e) => {
      if (state.editMode) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openShowcaseLightbox(Number(card.dataset.showcaseIndex));
      }
    });
  });

  // Click / keyboard on a video card → open video lightbox
  document.querySelectorAll(".video-card[data-video-index]").forEach((card) => {
    card.addEventListener("click", () => {
      if (state.editMode) return;
      openVideoLightbox(Number(card.dataset.videoIndex));
    });
    card.addEventListener("keydown", (e) => {
      if (state.editMode) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openVideoLightbox(Number(card.dataset.videoIndex));
      }
    });
  });

  // Click on the interaction doc image or its zoom button → open doc lightbox
  document.querySelectorAll("[data-doc-zoom]").forEach((node) => {
    node.addEventListener("click", (e) => {
      if (state.editMode) return;
      const pid = node.dataset.docZoom;
      if (pid) openDocLightbox(pid);
    });
  });

  // Expand / collapse the inline interaction doc preview
  document.querySelectorAll("[data-expand-toggle]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = btn.dataset.expandToggle;
      const wrap = document.getElementById("doc-wrap-" + idx);
      if (!wrap) return;
      const willExpand = !wrap.classList.contains("expanded");
      wrap.classList.toggle("expanded", willExpand);
      // When collapsing, scroll the top edge of the doc back into view so
      // the user doesn't end up stranded mid-section
      if (!willExpand) {
        wrap.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
}

// ── Interaction Doc Lightbox ─────────────────────────────────────────────

function openDocLightbox(projectId) {
  const project = (state.data?.projects || []).find(p => p.id === projectId);
  if (!project?.interaction_doc?.src) return;
  if (document.getElementById("doc-lightbox-overlay")) return;
  document.body.insertAdjacentHTML("beforeend", renderDocLightbox(project));
  bindDocLightbox(project);
}

function renderDocLightbox(project) {
  const doc = project.interaction_doc;
  return `
    <div class="lightbox-overlay doc-lightbox" id="doc-lightbox-overlay" data-zoom="fit">
      <button type="button" class="lightbox-close" id="doc-lb-close" title="关闭 (ESC)">✕</button>
      <div class="doc-lb-toolbar">
        <button type="button" class="doc-lb-btn" data-zoom-action="out" title="缩小 (-)">−</button>
        <span class="doc-lb-zoom-pct" id="doc-lb-zoom-pct">适应宽度</span>
        <button type="button" class="doc-lb-btn" data-zoom-action="in" title="放大 (+)">+</button>
        <button type="button" class="doc-lb-btn" data-zoom-action="fit" title="适应宽度 (0)">适应</button>
        <button type="button" class="doc-lb-btn" data-zoom-action="actual" title="原始尺寸 (1)">1:1</button>
        <span class="doc-lb-hint">滚轮缩放 · 拖拽平移 · 双击切换</span>
      </div>
      <div class="doc-lb-scroll" id="doc-lb-scroll">
        <img id="doc-lb-img" src="${escapeHtml(doc.src)}" alt="${escapeHtml(doc.title || "交互文档")}" />
      </div>
    </div>
  `;
}

function bindDocLightbox(project) {
  const overlay = document.getElementById("doc-lightbox-overlay");
  if (!overlay) return;
  const img = overlay.querySelector("#doc-lb-img");
  const stage = overlay.querySelector("#doc-lb-scroll");
  const pctLabel = overlay.querySelector("#doc-lb-zoom-pct");

  // Transform-based pan / zoom engine. (tx, ty) is the offset in stage
  // pixels from the stage's top-left to the image's top-left;
  // scale multiplies the image's natural pixel size.
  let scale = 1;
  let tx = 0;
  let ty = 0;
  let fitScale = 1;
  const MIN_SCALE = 0.1;
  const MAX_SCALE = 8;

  function apply() {
    img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    img.style.transformOrigin = "0 0";
    const isFitWidth = Math.abs(scale - fitScale) < 0.001;
    pctLabel.textContent = isFitWidth ? "适应宽度" : `${Math.round((scale / fitScale) * 100)}%`;
  }

  function computeFitScale() {
    const stageW = stage.clientWidth;
    if (!img.naturalWidth) return 1;
    return stageW / img.naturalWidth;
  }

  function fit() {
    fitScale = computeFitScale();
    scale = fitScale;
    tx = 0;
    const imgH = img.naturalHeight * scale;
    ty = imgH < stage.clientHeight ? (stage.clientHeight - imgH) / 2 : 0;
    apply();
  }

  function actual() {
    fitScale = computeFitScale();
    const cx = stage.clientWidth / 2;
    const cy = stage.clientHeight / 2;
    zoomAt(cx, cy, 1 / scale); // first reset to scale=1 around center
  }

  function zoomAt(px, py, factor) {
    const newScale = Math.max(MIN_SCALE, Math.min(scale * factor, MAX_SCALE));
    if (newScale === scale) return;
    // Convert the point in stage coords to image coords (pre-zoom)
    const ix = (px - tx) / scale;
    const iy = (py - ty) / scale;
    scale = newScale;
    // Keep that image point under the same stage point after zoom
    tx = px - ix * scale;
    ty = py - iy * scale;
    apply();
  }

  function zoomCenter(factor) {
    zoomAt(stage.clientWidth / 2, stage.clientHeight / 2, factor);
  }

  function close() {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("resize", onResize);
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  }

  function onResize() {
    // Re-fit if user was at fit scale; otherwise just refresh fitScale ref
    const wasFit = Math.abs(scale - fitScale) < 0.001;
    fitScale = computeFitScale();
    if (wasFit) fit();
    else apply();
  }

  function onKey(e) {
    if (e.key === "Escape") return close();
    if (e.key === "+" || e.key === "=") { e.preventDefault(); zoomCenter(1.25); }
    else if (e.key === "-" || e.key === "_") { e.preventDefault(); zoomCenter(1 / 1.25); }
    else if (e.key === "0") { e.preventDefault(); fit(); }
    else if (e.key === "1") { e.preventDefault(); actual(); }
    else if (e.key === "ArrowUp")    { ty += 80; apply(); }
    else if (e.key === "ArrowDown")  { ty -= 80; apply(); }
    else if (e.key === "ArrowLeft")  { tx += 80; apply(); }
    else if (e.key === "ArrowRight") { tx -= 80; apply(); }
  }

  // ── Drag-to-pan ──────────────────────────────────────────────
  let dragging = false;
  let dragStartX, dragStartY, dragStartTx, dragStartTy;
  let dragMoved = false;

  function onMouseDown(e) {
    if (e.button !== 0) return;
    if (e.target.closest(".doc-lb-toolbar") || e.target.closest(".lightbox-close")) return;
    e.preventDefault();
    dragging = true;
    dragMoved = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragStartTx = tx;
    dragStartTy = ty;
    stage.classList.add("dragging");
  }
  function onMouseMove(e) {
    if (!dragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true;
    tx = dragStartTx + dx;
    ty = dragStartTy + dy;
    apply();
  }
  function onMouseUp() {
    if (!dragging) return;
    dragging = false;
    stage.classList.remove("dragging");
  }

  // ── Touch (pinch + drag) ─────────────────────────────────────
  let touchStartDist = null;
  let touchStartScale = 1;
  let touchStartCenter = { x: 0, y: 0 };
  let touchStartTx = 0, touchStartTy = 0;
  let touchSingleStart = null;

  function onTouchStart(e) {
    if (e.touches.length === 2) {
      const [a, b] = e.touches;
      touchStartDist = Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
      touchStartScale = scale;
      const rect = stage.getBoundingClientRect();
      touchStartCenter = {
        x: (a.clientX + b.clientX) / 2 - rect.left,
        y: (a.clientY + b.clientY) / 2 - rect.top,
      };
      touchStartTx = tx;
      touchStartTy = ty;
      touchSingleStart = null;
    } else if (e.touches.length === 1) {
      const t = e.touches[0];
      touchSingleStart = { x: t.clientX, y: t.clientY, tx, ty };
      touchStartDist = null;
    }
  }
  function onTouchMove(e) {
    if (e.touches.length === 2 && touchStartDist != null) {
      e.preventDefault();
      const [a, b] = e.touches;
      const d = Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
      const factor = d / touchStartDist;
      const newScale = Math.max(MIN_SCALE, Math.min(touchStartScale * factor, MAX_SCALE));
      // Anchor zoom at the initial midpoint of the two fingers
      const px = touchStartCenter.x;
      const py = touchStartCenter.y;
      const ix = (px - touchStartTx) / touchStartScale;
      const iy = (py - touchStartTy) / touchStartScale;
      scale = newScale;
      tx = px - ix * scale;
      ty = py - iy * scale;
      apply();
    } else if (e.touches.length === 1 && touchSingleStart) {
      e.preventDefault();
      const t = e.touches[0];
      tx = touchSingleStart.tx + (t.clientX - touchSingleStart.x);
      ty = touchSingleStart.ty + (t.clientY - touchSingleStart.y);
      apply();
    }
  }
  function onTouchEnd(e) {
    if (e.touches.length === 0) {
      touchStartDist = null;
      touchSingleStart = null;
    }
  }

  // ── Wire DOM events ──────────────────────────────────────────
  overlay.querySelector("#doc-lb-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    // Close on backdrop click — but only if it's the overlay itself,
    // not after a drag, and not when clicking toolbar / image
    if (e.target === overlay && !dragMoved) close();
  });

  overlay.querySelectorAll("[data-zoom-action]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const action = btn.dataset.zoomAction;
      if (action === "in")        zoomCenter(1.25);
      else if (action === "out")  zoomCenter(1 / 1.25);
      else if (action === "fit")  fit();
      else if (action === "actual") actual();
    });
  });

  // Wheel zooms toward the cursor; Shift+wheel pans horizontally
  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    if (e.shiftKey) {
      // shift+wheel = horizontal pan, like spreadsheets / photoshop
      tx -= e.deltaY;
      apply();
      return;
    }
    const rect = stage.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    zoomAt(px, py, factor);
  }, { passive: false });

  stage.addEventListener("mousedown", onMouseDown);
  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", onMouseUp);

  stage.addEventListener("touchstart", onTouchStart, { passive: false });
  stage.addEventListener("touchmove", onTouchMove, { passive: false });
  stage.addEventListener("touchend", onTouchEnd);
  stage.addEventListener("touchcancel", onTouchEnd);

  // Double-click toggles fit ↔ 100% anchored at the click point
  stage.addEventListener("dblclick", (e) => {
    if (e.target.closest(".doc-lb-toolbar")) return;
    const rect = stage.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const atFit = Math.abs(scale - fitScale) < 0.001;
    if (atFit) {
      zoomAt(px, py, 1 / fitScale);
    } else {
      fit();
    }
  });

  document.addEventListener("keydown", onKey);
  window.addEventListener("resize", onResize);

  // Initial fit (depends on image being loaded for naturalWidth)
  if (img.complete && img.naturalWidth) {
    fit();
  } else {
    img.addEventListener("load", fit, { once: true });
  }
}

// ── Screen Lightbox ──────────────────────────────────────────────────────

function openScreenLightbox(topLevelIndex) {
  const project = (state.data?.projects || []).find(p => p.id === state.currentProjectId);
  if (!project || !Array.isArray(project.screens) || !project.screens.length) return;
  const topLevel = project.screens.filter(s => s && !s.parent);
  if (!topLevel.length) return;
  state.lightboxScreenIndex = Math.max(0, Math.min(topLevelIndex, topLevel.length - 1));
  state.lightboxVariantIndex = 0;
  if (!document.getElementById("screen-lightbox-overlay")) {
    document.body.insertAdjacentHTML("beforeend", renderScreenLightbox(project));
    bindScreenLightbox(project);
  } else {
    refreshScreenLightbox(project);
  }
}

function renderScreenLightbox(project) {
  const allScreens = Array.isArray(project.screens) ? project.screens : [];
  const topLevel = allScreens.filter((s) => s && !s.parent);
  const parentIdx = Math.max(0, Math.min(state.lightboxScreenIndex || 0, topLevel.length - 1));
  const parent = topLevel[parentIdx];
  if (!parent) return "";
  const variants = allScreens.filter((s) => s && s.parent === parent.id);
  const group = [parent, ...variants];
  const variantIdx = Math.max(0, Math.min(state.lightboxVariantIndex || 0, group.length - 1));
  const current = group[variantIdx];
  const title = current.title || current.hover_title || "";
  const notes = Array.isArray(current.notes) ? current.notes : [];
  const total = topLevel.length;
  return `
    <div class="lightbox-overlay" id="screen-lightbox-overlay">
      <button type="button" class="lightbox-close" id="lightbox-close" title="关闭 (ESC)">✕</button>
      <button type="button" class="lightbox-nav lightbox-nav-prev" id="lightbox-prev" title="上一组 (←)">‹</button>
      <button type="button" class="lightbox-nav lightbox-nav-next" id="lightbox-next" title="下一组 (→)">›</button>
      <div class="lightbox-content" id="lightbox-content">
        <div class="lightbox-stage">
          <div class="lightbox-image-wrap">
            <img id="lightbox-image" src="${escapeHtml(current.src)}" alt="${escapeHtml(current.title || "")}" />
          </div>
          ${group.length > 1 ? `
            <div class="lightbox-variants">
              ${group.map((item, i) => `
                <button type="button" class="lightbox-variant-btn ${i === variantIdx ? "active" : ""}" data-variant-index="${i}" title="${escapeHtml(item.title || "")}">
                  <img src="${escapeHtml(item.src)}" alt="" loading="lazy" decoding="async" />
                  <span>${escapeHtml(item.title || "")}</span>
                </button>
              `).join("")}
            </div>` : ""}
        </div>
        <aside class="lightbox-info">
          <h2 class="lightbox-title">${escapeHtml(title)}</h2>
          ${notes.length ? `
            <div class="lightbox-block">
              <h4>备注</h4>
              <ul class="lightbox-notes">${notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>
            </div>` : ""}
          ${group.length > 1 ? `<div class="lightbox-group-counter">状态 ${variantIdx + 1} / ${group.length}</div>` : ""}
          <div class="lightbox-counter">界面 ${parentIdx + 1} / ${total}</div>
        </aside>
      </div>
    </div>
  `;
}

function refreshScreenLightbox(project) {
  const overlay = document.getElementById("screen-lightbox-overlay");
  if (!overlay) return;
  const html = renderScreenLightbox(project);
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  const next = tmp.firstElementChild;
  if (!next) return;
  overlay.replaceWith(next);
  bindScreenLightbox(project);
}

// Surgical update for variant switching inside the same parent — avoids
// the flash from full overlay replacement. Only the image src, info
// panel contents, and active class on the variant strip change.
function updateLightboxVariantInPlace(project) {
  const overlay = document.getElementById("screen-lightbox-overlay");
  if (!overlay) return;
  const allScreens = Array.isArray(project.screens) ? project.screens : [];
  const topLevel = allScreens.filter((s) => s && !s.parent);
  const parentIdx = Math.max(0, Math.min(state.lightboxScreenIndex || 0, topLevel.length - 1));
  const parent = topLevel[parentIdx];
  if (!parent) return;
  const variants = allScreens.filter((s) => s && s.parent === parent.id);
  const group = [parent, ...variants];
  const variantIdx = Math.max(0, Math.min(state.lightboxVariantIndex || 0, group.length - 1));
  const current = group[variantIdx];
  if (!current) return;

  // Swap image src in place (browser reuses the <img> element, only the
  // bytes change — and assets serve with max-age=300 so cached hits are
  // instant). Setting alt updates a11y too.
  const img = overlay.querySelector("#lightbox-image");
  if (img) {
    if (img.getAttribute("src") !== current.src) img.setAttribute("src", current.src);
    img.setAttribute("alt", current.title || "");
  }

  // Refresh just the info panel (title + notes + counters)
  const info = overlay.querySelector(".lightbox-info");
  if (info) {
    const title = current.title || current.hover_title || "";
    const notes = Array.isArray(current.notes) ? current.notes : [];
    const total = topLevel.length;
    info.innerHTML = `
      <h2 class="lightbox-title">${escapeHtml(title)}</h2>
      ${notes.length ? `
        <div class="lightbox-block">
          <h4>备注</h4>
          <ul class="lightbox-notes">${notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>
        </div>` : ""}
      ${group.length > 1 ? `<div class="lightbox-group-counter">状态 ${variantIdx + 1} / ${group.length}</div>` : ""}
      <div class="lightbox-counter">界面 ${parentIdx + 1} / ${total}</div>
    `;
  }

  // Toggle active class on variant strip buttons
  overlay.querySelectorAll(".lightbox-variant-btn").forEach((btn, i) => {
    btn.classList.toggle("active", i === variantIdx);
  });
}

function bindScreenLightbox(project) {
  const overlay = document.getElementById("screen-lightbox-overlay");
  if (!overlay) return;

  const topLevel = (project.screens || []).filter(s => s && !s.parent);

  const close = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
  };
  const navTo = (delta) => {
    const total = topLevel.length || 1;
    state.lightboxScreenIndex = ((state.lightboxScreenIndex + delta) % total + total) % total;
    state.lightboxVariantIndex = 0;
    refreshScreenLightbox(project);
  };
  const onKey = (e) => {
    if (e.key === "Escape") { close(); }
    else if (e.key === "ArrowLeft") { navTo(-1); }
    else if (e.key === "ArrowRight") { navTo(1); }
  };

  overlay.querySelector("#lightbox-close").addEventListener("click", close);
  overlay.querySelector("#lightbox-prev").addEventListener("click", () => navTo(-1));
  overlay.querySelector("#lightbox-next").addEventListener("click", () => navTo(1));
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", onKey);

  // Variant thumbnail strip — use a surgical update instead of full
  // refresh to avoid the visible flash from rebuilding the overlay.
  overlay.querySelectorAll(".lightbox-variant-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      state.lightboxVariantIndex = Number(btn.dataset.variantIndex) || 0;
      updateLightboxVariantInPlace(project);
    });
  });
}

function applyHash() {
  const projectId = window.location.hash.replace(/^#/, "");
  state.showAbout = projectId === "about";
  state.currentProjectId = state.showAbout ? null : (projectId || null);
}

// ── Section Manager ──────────────────────────────────────────────────────

const BUILTIN_SECTIONS = [
  { id: "interaction_doc", label: "交互文档",  icon: "📄" },
  { id: "screens",         label: "单独界面",  icon: "🖼" },
  { id: "videos",          label: "演示视频",  icon: "▶" },
  { id: "pdfs",            label: "作品 PDF",  icon: "📑" },
  { id: "showcase",        label: "作品展示",  icon: "🎨" },
];

const SECTION_CFG_KEY = "portfolio_section_cfg_v1";

function loadSectionConfig() {
  try {
    const raw = localStorage.getItem(SECTION_CFG_KEY);
    if (raw) state.sectionConfig = JSON.parse(raw);
  } catch { state.sectionConfig = {}; }
}

function saveSectionConfig() {
  localStorage.setItem(SECTION_CFG_KEY, JSON.stringify(state.sectionConfig));
}

function getProjectCfg(projectId) {
  if (!state.sectionConfig[projectId]) {
    state.sectionConfig[projectId] = { visible: {}, custom: [] };
  }
  return state.sectionConfig[projectId];
}

function isSectionVisible(projectId, sectionId) {
  // Per-project meta hide takes hard priority — used by non-game projects
  // to permanently turn off modules that don't apply (e.g. interaction_doc
  // on installation-art projects).
  const project = (state.data?.projects || []).find(p => p && p.id === projectId);
  const hide = project?.display?.hide_sections;
  if (Array.isArray(hide) && hide.includes(sectionId)) return false;
  return getProjectCfg(projectId).visible[sectionId] !== false;
}

function toggleSection(projectId, sectionId) {
  const cfg = getProjectCfg(projectId);
  cfg.visible[sectionId] = !isSectionVisible(projectId, sectionId);
  saveSectionConfig();
  render();
}

function addCustomSection(projectId, title, kicker, body) {
  const cfg = getProjectCfg(projectId);
  if (!Array.isArray(cfg.custom)) cfg.custom = [];
  cfg.custom.push({
    id: "cs-" + Date.now(),
    title: title.trim(),
    kicker: kicker.trim(),
    body: body.trim(),
  });
  saveSectionConfig();
  render();
}

function removeCustomSection(projectId, sectionId) {
  const cfg = getProjectCfg(projectId);
  cfg.custom = (cfg.custom || []).filter(s => s.id !== sectionId);
  saveSectionConfig();
  render();
}

function renderCustomSections(projectId, projectIndex) {
  const cfg = getProjectCfg(projectId);
  if (!Array.isArray(cfg.custom) || !cfg.custom.length) return "";
  return cfg.custom.map(section => `
    <section class="section">
      <div class="custom-section-card">
        ${section.kicker ? `<div class="section-kicker">${escapeHtml(section.kicker)}</div>` : ""}
        <h2 class="section-title">${escapeHtml(section.title)}</h2>
        ${section.body ? `<p class="custom-section-body">${escapeHtml(section.body)}</p>` : ""}
      </div>
    </section>
  `).join("");
}

function renderSectionPanel(project) {
  const cfg = getProjectCfg(project.id);
  const custom = Array.isArray(cfg.custom) ? cfg.custom : [];
  return `
    <div class="section-mgr-overlay" id="section-mgr-overlay">
      <div class="section-mgr-panel">
        <div class="section-mgr-head">
          <h3>模块管理</h3>
          <button type="button" id="section-mgr-close">&#x2715;</button>
        </div>
        <div class="section-mgr-group">
          <div class="section-mgr-group-title">内置模块</div>
          ${BUILTIN_SECTIONS.map(s => {
            const visible = isSectionVisible(project.id, s.id);
            return `
              <div class="section-toggle-row">
                <div class="section-toggle-label">
                  <span class="section-toggle-icon">${s.icon}</span>
                  <span class="section-toggle-name" style="${!visible ? "opacity:.4" : ""}">${s.label}</span>
                </div>
                <button type="button"
                        class="toggle-eye-btn ${visible ? "" : "hidden-section"}"
                        data-toggle-section="${project.id}"
                        data-section-id="${s.id}">
                  ${visible ? "显示中" : "已隐藏"}
                </button>
              </div>`;
          }).join("")}
        </div>
        <div class="section-mgr-group">
          <div class="section-mgr-group-title">自定义模块</div>
          ${custom.length ? custom.map(s => `
            <div class="section-toggle-row">
              <div class="section-toggle-label">
                <span class="section-toggle-icon">&#x1F4DD;</span>
                <span class="section-toggle-name">${escapeHtml(s.title)}</span>
              </div>
              <button type="button" class="section-del-btn"
                      data-del-custom="${project.id}"
                      data-custom-id="${s.id}">删除</button>
            </div>`).join("") : `<div style="font-size:13px;color:var(--text-soft)">暂无自定义模块</div>`}
        </div>
        <div class="section-mgr-add">
          <div class="section-mgr-group-title">新增自定义模块</div>
          <div id="section-add-wrap">
            <button type="button" class="section-mgr-add-btn" id="show-cs-form">+ 新增自定义模块</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function showAddSectionForm(projectId) {
  const wrap = document.getElementById("section-add-wrap");
  if (!wrap) return;
  wrap.innerHTML = `
    <div class="section-mgr-add-form">
      <input type="text" id="cs-title" placeholder="模块标题（必填）" />
      <input type="text" id="cs-kicker" placeholder="标签文字（可选，如 Design / Notes）" />
      <textarea id="cs-body" rows="4" placeholder="正文内容（可选）"></textarea>
      <div class="section-mgr-add-form-actions">
        <button type="button" class="primary" id="cs-confirm">确认添加</button>
        <button type="button" id="cs-cancel">取消</button>
      </div>
    </div>
  `;
  const rebindCancel = () => {
    document.getElementById("cs-cancel")?.addEventListener("click", () => {
      wrap.innerHTML = `<button type="button" class="section-mgr-add-btn" id="show-cs-form">+ 新增自定义模块</button>`;
      document.getElementById("show-cs-form")?.addEventListener("click", () => showAddSectionForm(projectId));
    });
  };
  rebindCancel();
  document.getElementById("cs-confirm")?.addEventListener("click", () => {
    const title = document.getElementById("cs-title")?.value.trim() || "";
    if (!title) { document.getElementById("cs-title")?.focus(); return; }
    addCustomSection(
      projectId,
      title,
      document.getElementById("cs-kicker")?.value || "",
      document.getElementById("cs-body")?.value || "",
    );
  });
}

function bindSectionPanel(project) {
  const overlay = document.getElementById("section-mgr-overlay");
  if (!overlay) return;
  overlay.querySelector("#section-mgr-close")?.addEventListener("click", () => {
    overlay.remove(); state.showSectionPanel = false;
  });
  overlay.addEventListener("click", e => {
    if (e.target === overlay) { overlay.remove(); state.showSectionPanel = false; }
  });
  overlay.querySelectorAll("[data-toggle-section]").forEach(btn => {
    btn.addEventListener("click", () => toggleSection(btn.dataset.toggleSection, btn.dataset.sectionId));
  });
  overlay.querySelectorAll("[data-del-custom]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (confirm("确认删除此自定义模块？")) removeCustomSection(btn.dataset.delCustom, btn.dataset.customId);
    });
  });
  overlay.querySelector("#show-cs-form")?.addEventListener("click", () => showAddSectionForm(project.id));
}

// ── Management: add / remove projects ─────────────────────────────────────

async function checkManagementApi() {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (res.ok) {
      const json = await res.json();
      state.manageMode = Boolean(json.manage);
    }
  } catch {
    state.manageMode = false;
  }
}

async function reloadSiteData() {
  const res = await fetch("./site-data.json?v=d6ce4561", { cache: "no-store" });
  state.baseData = await res.json();
  refreshData();
}

function renderAddProjectPanel() {
  return `
    <div class="manage-overlay" id="add-project-overlay">
      <div class="manage-panel">
        <div class="manage-panel-head">
          <h2>添加新项目</h2>
          <button type="button" id="manage-panel-close">✕</button>
        </div>
        <form id="manage-add-form" class="manage-form" enctype="multipart/form-data">
          <label class="manage-field">
            <span class="manage-label">项目标题 <em>*</em></span>
            <input type="text" name="title" placeholder="请输入项目标题" required />
          </label>
          <label class="manage-field">
            <span class="manage-label">副标题</span>
            <input type="text" name="subtitle" placeholder="可选" />
          </label>
          <label class="manage-field">
            <span class="manage-label">项目说明</span>
            <textarea name="description" rows="3" placeholder="可选，对项目做简短介绍"></textarea>
          </label>
          <div class="manage-field">
            <span class="manage-label">上传图片</span>
            <p class="manage-hint">可同时上传多张图片。文件名含「交互/总览/流程/board/flow/doc」的将自动识别为交互文档，其余为界面图。</p>
            <label class="manage-upload-zone" id="manage-upload-zone">
              <input type="file" name="images" accept="image/*" multiple id="manage-file-input" hidden />
              <span class="manage-upload-icon">⬆</span>
              <span>点击选择图片，或将文件拖拽至此处</span>
            </label>
            <div class="manage-preview" id="manage-preview"></div>
          </div>
          <div class="manage-form-actions">
            <button type="submit" class="primary">确认添加</button>
            <button type="button" id="manage-cancel-btn">取消</button>
          </div>
          <div id="manage-status" class="manage-status"></div>
        </form>
      </div>
    </div>
  `;
}

function bindManagePanel() {
  const overlay = document.getElementById("add-project-overlay");
  if (!overlay) return;

  // close
  overlay.querySelector("#manage-panel-close").addEventListener("click", () => {
    overlay.remove();
  });
  overlay.querySelector("#manage-cancel-btn").addEventListener("click", () => {
    overlay.remove();
  });

  // click outside to close
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });

  // file input via zone click
  const zone = overlay.querySelector("#manage-upload-zone");
  const fileInput = overlay.querySelector("#manage-file-input");
  zone.addEventListener("click", () => fileInput.click());

  // drag & drop
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    const dt = new DataTransfer();
    Array.from(fileInput.files || []).forEach((f) => dt.items.add(f));
    Array.from(e.dataTransfer.files).forEach((f) => dt.items.add(f));
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event("change"));
  });

  // preview
  const DOC_KW = ["交互","总览","流程","文档","doc","document","flow","board","mockup","overview","ux","wireframe"];
  fileInput.addEventListener("change", () => {
    const preview = overlay.querySelector("#manage-preview");
    preview.innerHTML = Array.from(fileInput.files).map((f) => {
      const stem = f.name.toLowerCase().replace(/[.][^.]+$/, "");
      const isDoc = DOC_KW.some((k) => stem.includes(k));
      const tag = isDoc
        ? `<span class="chip" style="background:var(--accent,#6c63ff);color:#fff">交互文档</span>`
        : `<span class="chip">界面图</span>`;
      return `<div class="manage-file-chip">${tag} ${escapeHtml(f.name)}</div>`;
    }).join("");
  });

  // submit
  const form = overlay.querySelector("#manage-add-form");
  const status = overlay.querySelector("#manage-status");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    status.textContent = "正在上传并重建站点，请稍候…";

    const fd = new FormData(form);
    // Ensure all selected files are in FormData under "images"
    Array.from(fileInput.files).forEach((f) => {
      if (!fd.getAll("images").includes(f)) fd.append("images", f);
    });

    try {
      const res = await fetch("/api/add-project", { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed");
      status.textContent = "✓ 项目已添加，站点已重建！";
      await reloadSiteData();
      setTimeout(() => { overlay.remove(); render(); }, 800);
    } catch (err) {
      status.textContent = "✗ 添加失败：" + err.message;
      btn.disabled = false;
    }
  });
}

async function handleRemoveProject(projectId) {
  if (!confirm(`确认删除项目"${projectId}"？此操作不可撤销（仅从站点索引移除，不删除源文件）。`)) return;
  try {
    // Capture index BEFORE removal so we can prune overrides for the same slot
    const oldIndex = (state.baseData?.projects || []).findIndex(p => p && p.id === projectId);

    const res = await fetch("/api/remove-project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Failed");

    // Prune overrides for the removed slot AND any stale slot whose id no longer
    // matches a real project, so phantom cards never accumulate.
    pruneOverridesForRemoved(projectId, oldIndex);

    await reloadSiteData();
    render();
  } catch (err) {
    alert("删除失败：" + err.message);
  }
}

// Remove override entries that point at a project that no longer exists.
function pruneOverridesForRemoved(removedId, removedIndex) {
  const projOverrides = state.overrides && state.overrides.projects;
  if (!projOverrides) return;
  let changed = false;

  if (Array.isArray(projOverrides)) {
    if (removedIndex >= 0 && removedIndex < projOverrides.length) {
      delete projOverrides[removedIndex];
      changed = true;
    }
    // Also drop any sparse entry that doesn't match a still-living project
    const liveIds = new Set((state.baseData?.projects || []).filter(p => p && p.id !== removedId).map(p => p.id));
    projOverrides.forEach((entry, i) => {
      // We only know it's stale if base no longer has a project at index i with a matching id.
      // Conservative: if the override has nothing left in it after pruning, drop it.
      if (entry && typeof entry === "object" && Object.keys(entry).length === 0) {
        delete projOverrides[i];
        changed = true;
      }
    });
  } else if (projOverrides && typeof projOverrides === "object") {
    Object.keys(projOverrides).forEach((k) => {
      if (Number(k) === removedIndex) {
        delete projOverrides[k];
        changed = true;
      }
    });
  }

  if (changed) saveOverrides();
}

// Force all images inside #app to refetch (defeats browser cache after replacement)
function bustAllImages() {
  const stamp = Date.now();
  document.querySelectorAll("#app img").forEach((img) => {
    try {
      const url = new URL(img.getAttribute("src"), window.location.href);
      url.searchParams.set("v", stamp);
      img.src = url.pathname + url.search;
    } catch {
      // data: URLs or malformed, skip
    }
  });
}

// Walk state.overrides for any image src that was replaced in edit mode.
// Each entry returned has everything needed to POST /api/replace-image.
function collectImageOverrideTasks(overrides, baseData) {
  const tasks = [];
  const walk = (obj, path) => {
    if (!obj || typeof obj !== "object") return;
    Object.entries(obj).forEach(([key, value]) => {
      const p = path ? `${path}.${key}` : key;
      if (key === "src" && typeof value === "string" && value.startsWith("data:")) {
        const parentPath = path;
        const parent = parentPath
          .split(".")
          .filter(Boolean)
          .reduce((cur, part) => (cur == null ? cur : cur[part]), baseData);
        const projMatch = /^projects\.(\d+)\b/.exec(parentPath || "");
        const projectSlot = projMatch ? baseData?.projects?.[Number(projMatch[1])] : null;
        const relativePath = parent && parent.relative_path;
        if (projectSlot && projectSlot.id && relativePath) {
          tasks.push({
            overridePath: p,
            projectId: projectSlot.id,
            relativePath: relativePath,
            dataUrl: value,
          });
        }
      } else if (value && typeof value === "object") {
        walk(value, p);
      }
    });
  };
  walk(overrides, "");
  return tasks;
}

async function saveOverridesToSource(btn) {
  const imageTasks = collectImageOverrideTasks(state.overrides, state.baseData);
  const hasOverrides = state.overrides && Object.keys(state.overrides).length > 0;

  if (!imageTasks.length && !hasOverrides) {
    alert("当前没有待保存的修改。在编辑模式下改文字或图片后再保存。");
    return;
  }

  const originalLabel = btn.textContent;
  btn.disabled = true;
  const errors = [];
  let textApplied = 0;
  let textSkipped = 0;

  // 1. Save text overrides (and any path-based src edits) in one call
  try {
    btn.textContent = "保存文字…";
    const res = await fetch("/api/save-overrides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ overrides: state.overrides }),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
    textApplied = Number(json.applied) || 0;
    textSkipped = (Number(json.skipped_image_data) || 0) + (Number(json.skipped_orphan) || 0);
  } catch (err) {
    errors.push(`文字保存: ${err.message}`);
  }

  // 2. Save image overrides via the existing /api/replace-image flow
  for (let i = 0; i < imageTasks.length; i += 1) {
    const t = imageTasks[i];
    btn.textContent = `保存图片 (${i + 1}/${imageTasks.length})…`;
    try {
      const blob = await (await fetch(t.dataUrl)).blob();
      const fd = new FormData();
      fd.append("project_id", t.projectId);
      fd.append("file", t.relativePath);
      fd.append("image", blob, `upload-${i}.png`);
      const res = await fetch("/api/replace-image", { method: "POST", body: fd });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
    } catch (err) {
      errors.push(`图片 ${t.relativePath}: ${err.message}`);
    }
  }

  // 3. Clear local overrides — source files are now the truth
  if (!errors.length) {
    state.overrides = {};
    saveOverrides();
  }

  // 4. Reload site-data + re-render
  try {
    await reloadSiteData();
    render();
    bustAllImages();
  } catch (err) {
    console.error("reload after save failed:", err);
  }

  btn.disabled = false;
  btn.textContent = originalLabel;

  const summary = [];
  if (textApplied) summary.push(`${textApplied} 处文字`);
  if (imageTasks.length - errors.filter(e => e.startsWith("图片")).length > 0) {
    summary.push(`${imageTasks.length} 张图片`);
  }
  if (errors.length) {
    alert(`保存部分成功 — ${summary.join(", ") || "无变更"} 已写入。失败项:\n${errors.join("\n")}`);
  } else if (summary.length) {
    alert(`✓ ${summary.join(" + ")} 已写回源文件, 站点已重建。\n现在可在 Fork 里 commit + push。`);
  } else {
    alert("没有需要保存的修改。");
  }
}

function bindManageInteractions() {
  // Add project button in toolbar
  document.getElementById("manage-add-project")?.addEventListener("click", () => {
    if (!document.getElementById("add-project-overlay")) {
      document.body.insertAdjacentHTML("beforeend", renderAddProjectPanel());
      bindManagePanel();
    }
  });

  // Remove buttons on project cards
  document.querySelectorAll("[data-remove-project]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      handleRemoveProject(btn.dataset.removeProject);
    });
  });

  // Remove buttons on screen cards
  document.querySelectorAll("[data-remove-screen]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      handleRemoveScreen(btn.dataset.removeScreen);
    });
  });

  // Add screen tile
  document.getElementById("screen-add-tile")?.addEventListener("click", () => {
    const projectId = document.getElementById("screen-add-tile")?.dataset.projectSlot || state.currentProjectId;
    if (!projectId) return;
    if (!document.getElementById("add-screen-overlay")) {
      document.body.insertAdjacentHTML("beforeend", renderAddScreenPanel(projectId));
      bindAddScreenPanel(projectId);
    }
  });

  // Flow editor button
  document.getElementById("flow-edit-btn")?.addEventListener("click", (e) => {
    const projectId = e.currentTarget.dataset.projectId || state.currentProjectId;
    if (!projectId) return;
    openFlowEditor(projectId);
  });
}

async function handleRemoveScreen(relativePath) {
  if (!relativePath) return;
  if (!state.currentProjectId) {
    alert("找不到当前项目 id");
    return;
  }
  if (!confirm(`确认删除界面"${relativePath}"？\n只从项目配置中移除, 源文件保留在磁盘上。`)) return;
  try {
    const res = await fetch("/api/remove-screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.currentProjectId, relative_path: relativePath }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Failed");
    await reloadSiteData();
    render();
    bustAllImages();
  } catch (err) {
    alert("删除失败: " + err.message);
  }
}

function renderAddScreenPanel(projectId) {
  return `
    <div class="manage-overlay" id="add-screen-overlay">
      <div class="manage-panel">
        <div class="manage-panel-head">
          <h2>添加新界面</h2>
          <button type="button" id="add-screen-close">✕</button>
        </div>
        <form id="add-screen-form" class="manage-form" enctype="multipart/form-data">
          <input type="hidden" name="project_id" value="${escapeHtml(projectId)}" />
          <label class="manage-field">
            <span class="manage-label">界面图片 <em>*</em></span>
            <label class="manage-upload-zone" id="add-screen-upload-zone">
              <input type="file" name="image" accept="image/*" required id="add-screen-file-input" hidden />
              <span class="manage-upload-icon">⬆</span>
              <span>点击选择图片, 或拖拽至此处</span>
            </label>
            <div class="manage-preview" id="add-screen-preview"></div>
          </label>
          <label class="manage-field">
            <span class="manage-label">标题</span>
            <input type="text" name="title" placeholder="例: 主界面 · 初始状态" />
          </label>
          <label class="manage-field">
            <span class="manage-label">分类 (section)</span>
            <input type="text" name="section" placeholder="例: 核心流程 / 反馈" />
          </label>
          <label class="manage-field">
            <span class="manage-label">悬停标题 (hover title)</span>
            <input type="text" name="hover_title" placeholder="鼠标移入时显示的标题" />
          </label>
          <label class="manage-field">
            <span class="manage-label">悬停描述 (hover description)</span>
            <textarea name="hover_description" rows="3" placeholder="悬停时显示的详细说明"></textarea>
          </label>
          <div class="manage-form-actions">
            <button type="submit" class="primary">确认添加</button>
            <button type="button" id="add-screen-cancel">取消</button>
          </div>
          <div id="add-screen-status" class="manage-status"></div>
        </form>
      </div>
    </div>
  `;
}

function bindAddScreenPanel(projectId) {
  const overlay = document.getElementById("add-screen-overlay");
  if (!overlay) return;

  const close = () => overlay.remove();
  overlay.querySelector("#add-screen-close").addEventListener("click", close);
  overlay.querySelector("#add-screen-cancel").addEventListener("click", close);

  const fileInput = overlay.querySelector("#add-screen-file-input");
  const preview = overlay.querySelector("#add-screen-preview");
  fileInput.addEventListener("change", () => {
    preview.innerHTML = "";
    const file = fileInput.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const img = document.createElement("img");
      img.src = String(reader.result || "");
      preview.appendChild(img);
    };
    reader.readAsDataURL(file);
  });

  const form = overlay.querySelector("#add-screen-form");
  const status = overlay.querySelector("#add-screen-status");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!fileInput.files?.length) {
      status.textContent = "请选择图片";
      return;
    }
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    status.textContent = "上传中…";
    try {
      const fd = new FormData(form);
      const res = await fetch("/api/add-screen", { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed");
      await reloadSiteData();
      close();
      render();
      bustAllImages();
    } catch (err) {
      status.textContent = "添加失败: " + err.message;
      submitBtn.disabled = false;
    }
  });
}

// ── Flow Editor ──────────────────────────────────────────────────────────

function openFlowEditor(projectId) {
  const project = (state.data?.projects || []).find(p => p.id === projectId);
  if (!project) {
    alert("找不到项目: " + projectId);
    return;
  }
  if (document.getElementById("flow-editor-overlay")) return;

  const screens = Array.isArray(project.screens) ? project.screens : [];
  const interactionDoc = project.interaction_doc || null;

  // Deep clone existing flow into a working copy
  const flow = project.flow || { title: "交互流程图", description: "", nodes: [], edges: [] };
  const workingFlow = {
    title: flow.title || "交互流程图",
    description: flow.description || "",
    nodes: (flow.nodes || []).map(n => ({
      id: n.id || "",
      label: n.label || "",
      screen_id: n.screen_id || "",
      col: Number(n.col) || 0,
      row: Number(n.row) || 0,
    })),
    edges: (flow.edges || []).map(e => ({
      from: e.from || "",
      to: e.to || "",
      label: e.label || "",
      type: e.type === "back" ? "back" : "forward",
    })),
  };

  document.body.insertAdjacentHTML("beforeend", renderFlowEditorPanel(projectId));
  bindFlowEditor(projectId, workingFlow, screens, interactionDoc);
}

function renderFlowEditorPanel(projectId) {
  return `
    <div class="manage-overlay" id="flow-editor-overlay">
      <div class="manage-panel flow-editor-panel">
        <div class="manage-panel-head">
          <h2>流程图编辑 · ${escapeHtml(projectId)}</h2>
          <button type="button" id="flow-editor-close">✕</button>
        </div>
        <div class="flow-editor-body">
          <div class="flow-editor-meta">
            <label class="manage-field">
              <span class="manage-label">标题</span>
              <input type="text" id="flow-meta-title" />
            </label>
            <label class="manage-field">
              <span class="manage-label">描述</span>
              <textarea id="flow-meta-description" rows="2"></textarea>
            </label>
          </div>

          <div class="flow-editor-section">
            <div class="flow-editor-section-head">
              <h3>节点 (Nodes)</h3>
              <button type="button" class="btn-outline" id="flow-add-node">+ 添加节点</button>
            </div>
            <div class="flow-editor-hint">每个节点对应一个界面 (screen)。col/row 是流程图中的网格位置 (从 0 开始)。</div>
            <div class="flow-nodes-list" id="flow-nodes-list"></div>
          </div>

          <div class="flow-editor-section">
            <div class="flow-editor-section-head">
              <h3>连线 (Edges)</h3>
              <button type="button" class="btn-outline" id="flow-add-edge">+ 添加连线</button>
            </div>
            <div class="flow-editor-hint">从一个节点到另一个节点的箭头。type=back 表示反向 / 返回连接。</div>
            <div class="flow-edges-list" id="flow-edges-list"></div>
          </div>
        </div>
        <div class="flow-editor-foot">
          <button type="button" id="flow-editor-cancel">取消</button>
          <button type="button" class="primary" id="flow-editor-save">保存并应用</button>
          <span class="manage-status" id="flow-editor-status"></span>
        </div>
      </div>
    </div>
  `;
}

function bindFlowEditor(projectId, flow, screens, interactionDoc) {
  const overlay = document.getElementById("flow-editor-overlay");
  if (!overlay) return;

  const titleInput = overlay.querySelector("#flow-meta-title");
  const descInput  = overlay.querySelector("#flow-meta-description");
  titleInput.value = flow.title || "";
  descInput.value  = flow.description || "";

  // Build options for screen selector
  const screenOptions = [
    { value: "", label: "(无对应界面)" },
    ...screens.map(s => ({ value: s.id, label: `${s.id} — ${s.title || s.relative_path || ""}` })),
  ];
  if (interactionDoc) {
    screenOptions.push({ value: interactionDoc.id, label: `${interactionDoc.id} — 交互文档` });
  }

  const close = () => overlay.remove();

  function renderNodeRow(node, index) {
    const nodeOpts = screenOptions.map(o =>
      `<option value="${escapeHtml(o.value)}" ${node.screen_id === o.value ? "selected" : ""}>${escapeHtml(o.label)}</option>`
    ).join("");
    return `
      <div class="flow-editor-row" data-row-kind="node" data-row-index="${index}">
        <div class="flow-editor-cell">
          <span class="flow-editor-cell-label">id</span>
          <input type="text" data-field="id" value="${escapeHtml(node.id)}" placeholder="prep" />
        </div>
        <div class="flow-editor-cell">
          <span class="flow-editor-cell-label">label</span>
          <input type="text" data-field="label" value="${escapeHtml(node.label)}" placeholder="战前准备" />
        </div>
        <div class="flow-editor-cell flow-editor-cell-wide">
          <span class="flow-editor-cell-label">screen</span>
          <select data-field="screen_id">${nodeOpts}</select>
        </div>
        <div class="flow-editor-cell flow-editor-cell-narrow">
          <span class="flow-editor-cell-label">col</span>
          <input type="number" data-field="col" value="${node.col}" min="0" />
        </div>
        <div class="flow-editor-cell flow-editor-cell-narrow">
          <span class="flow-editor-cell-label">row</span>
          <input type="number" data-field="row" value="${node.row}" min="0" />
        </div>
        <button type="button" class="flow-editor-row-del" data-row-del="node" data-row-index="${index}" title="删除节点">✕</button>
      </div>
    `;
  }

  function renderEdgeRow(edge, index, currentNodes) {
    const nodeOpts = (id) => [{ value: "", label: "(选择节点)" }, ...currentNodes.map(n => ({ value: n.id, label: n.id || "(空 id)" }))]
      .map(o => `<option value="${escapeHtml(o.value)}" ${id === o.value ? "selected" : ""}>${escapeHtml(o.label)}</option>`).join("");
    return `
      <div class="flow-editor-row" data-row-kind="edge" data-row-index="${index}">
        <div class="flow-editor-cell flow-editor-cell-wide">
          <span class="flow-editor-cell-label">from</span>
          <select data-field="from">${nodeOpts(edge.from)}</select>
        </div>
        <div class="flow-editor-cell flow-editor-cell-wide">
          <span class="flow-editor-cell-label">to</span>
          <select data-field="to">${nodeOpts(edge.to)}</select>
        </div>
        <div class="flow-editor-cell">
          <span class="flow-editor-cell-label">label</span>
          <input type="text" data-field="label" value="${escapeHtml(edge.label)}" placeholder="点击..." />
        </div>
        <div class="flow-editor-cell flow-editor-cell-narrow">
          <span class="flow-editor-cell-label">type</span>
          <select data-field="type">
            <option value="forward" ${edge.type !== "back" ? "selected" : ""}>正向</option>
            <option value="back" ${edge.type === "back" ? "selected" : ""}>back</option>
          </select>
        </div>
        <button type="button" class="flow-editor-row-del" data-row-del="edge" data-row-index="${index}" title="删除连线">✕</button>
      </div>
    `;
  }

  function renderAll() {
    const nodesList = overlay.querySelector("#flow-nodes-list");
    const edgesList = overlay.querySelector("#flow-edges-list");
    nodesList.innerHTML = flow.nodes.map((n, i) => renderNodeRow(n, i)).join("") || `<div class="flow-editor-empty">暂无节点, 点上方 + 添加节点</div>`;
    edgesList.innerHTML = flow.edges.map((e, i) => renderEdgeRow(e, i, flow.nodes)).join("") || `<div class="flow-editor-empty">暂无连线, 点上方 + 添加连线</div>`;
    bindRowEvents();
  }

  function bindRowEvents() {
    overlay.querySelectorAll('.flow-editor-row[data-row-kind="node"]').forEach((row) => {
      const idx = Number(row.dataset.rowIndex);
      row.querySelectorAll('input, select').forEach((inp) => {
        inp.addEventListener('input', () => {
          const f = inp.dataset.field;
          const v = inp.value;
          if (!flow.nodes[idx]) return;
          if (f === "col" || f === "row") flow.nodes[idx][f] = Number(v) || 0;
          else flow.nodes[idx][f] = v;
          // If id changed, edges referencing the old id stay broken — just re-render to refresh selectors
          if (f === "id") renderAll();
        });
      });
    });
    overlay.querySelectorAll('.flow-editor-row[data-row-kind="edge"]').forEach((row) => {
      const idx = Number(row.dataset.rowIndex);
      row.querySelectorAll('input, select').forEach((inp) => {
        inp.addEventListener('input', () => {
          const f = inp.dataset.field;
          if (!flow.edges[idx]) return;
          flow.edges[idx][f] = inp.value;
        });
      });
    });
    overlay.querySelectorAll('[data-row-del]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const kind = btn.dataset.rowDel;
        const idx = Number(btn.dataset.rowIndex);
        if (kind === "node") flow.nodes.splice(idx, 1);
        else flow.edges.splice(idx, 1);
        renderAll();
      });
    });
  }

  overlay.querySelector("#flow-editor-close").addEventListener("click", close);
  overlay.querySelector("#flow-editor-cancel").addEventListener("click", close);

  overlay.querySelector("#flow-add-node").addEventListener("click", () => {
    // Suggest a unique id like node-1, node-2, ...
    const used = new Set(flow.nodes.map(n => n.id));
    let i = flow.nodes.length + 1;
    let candidate;
    do { candidate = `node-${i++}`; } while (used.has(candidate));
    const maxRow = flow.nodes.reduce((m, n) => Math.max(m, n.row || 0), -1);
    flow.nodes.push({ id: candidate, label: candidate, screen_id: "", col: 0, row: maxRow + 1 });
    renderAll();
  });

  overlay.querySelector("#flow-add-edge").addEventListener("click", () => {
    flow.edges.push({ from: "", to: "", label: "", type: "forward" });
    renderAll();
  });

  titleInput.addEventListener("input", () => { flow.title = titleInput.value; });
  descInput.addEventListener("input", () => { flow.description = descInput.value; });

  overlay.querySelector("#flow-editor-save").addEventListener("click", async () => {
    const status = overlay.querySelector("#flow-editor-status");
    const saveBtn = overlay.querySelector("#flow-editor-save");

    // Client-side validation
    const ids = flow.nodes.map(n => (n.id || "").trim()).filter(Boolean);
    const dupes = ids.filter((id, i) => ids.indexOf(id) !== i);
    if (dupes.length) {
      status.textContent = "节点 id 重复: " + Array.from(new Set(dupes)).join(", ");
      return;
    }
    const idSet = new Set(ids);
    const orphanEdges = flow.edges.filter(e => (e.from && !idSet.has(e.from)) || (e.to && !idSet.has(e.to)));
    if (orphanEdges.length) {
      status.textContent = "存在指向不存在节点的连线, 请先修复";
      return;
    }

    saveBtn.disabled = true;
    status.textContent = "保存中…";
    try {
      const res = await fetch("/api/update-flow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, flow }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed");
      await reloadSiteData();
      close();
      render();
      bustAllImages();
    } catch (err) {
      status.textContent = "保存失败: " + err.message;
      saveBtn.disabled = false;
    }
  });

  renderAll();
}

// ── Boot ──────────────────────────────────────────────────────────────────

async function boot() {
  try {
    await checkManagementApi();
    const response = await fetch("./site-data.json?v=d6ce4561", { cache: "no-store" });
    state.baseData = await response.json();
    loadOverrides();
    loadSectionConfig();
    refreshData();

    if (state.data.site?.theme?.accent) {
      document.documentElement.style.setProperty("--accent", state.data.site.theme.accent);
    }
    if (state.data.site?.theme?.background) {
      document.documentElement.style.setProperty("--bg", state.data.site.theme.background);
    }

    applyHash();
    render();
    window.addEventListener("hashchange", () => {
      applyHash();
      render();
    });
  } catch (error) {
    console.error(error);
    const msg = error && (error.stack || error.message || String(error)) || "unknown";
    app.innerHTML = `<div class="empty" style="padding:24px;white-space:pre-wrap;font-family:monospace;font-size:12px;color:#f87171;">Failed to load site data.${escapeHtml(" — ") + escapeHtml(msg)}</div>`;
  }
}

boot();
