#!/usr/bin/env python3
"""Core generator for portfolio and prototype hub sites."""

from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import json
import re
import shutil
import socketserver
import sys
import webbrowser
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
DOCUMENT_EXTENSIONS = {".pdf"}
IGNORE_DIR_NAMES = {"_portfolio_site", "__pycache__"}
DEFAULT_LABELS = {
    "home_eyebrow": "Project Hub",
    "home_section_kicker": "Projects",
    "home_section_title": "项目总览",
    "home_section_description": "点击任意项目卡片，进入具体项目内容查看交互文档、界面说明，以及按指令启用的动态交互原型。",
    "back_to_home": "返回项目总览",
    "project_detail_eyebrow": "Project Detail",
    "interaction_doc_kicker": "Document",
    "interaction_doc_title": "交互文档",
    "interaction_doc_description": "先展示整张交互文档，用来承接整体流程和页面关系说明。",
    "interaction_doc_empty": "当前项目还没有配置交互文档。",
    "screens_kicker": "Screens",
    "screens_title": "单独界面",
    "screens_description": "鼠标移入界面图时，会显示该界面的状态描述、说明和交互文档整理出的备注。",
    "screens_empty": "当前项目还没有配置界面列表。",
    "prototype_kicker": "Prototype",
    "prototype_title": "动态交互原型",
    "prototype_disabled": "当前未启用原型模块。只有在明确要求生成可演示交互原型时，才会渲染这一段内容。",
    "prototype_empty": "原型模块已启用，但当前项目尚未配置 prototype 场景数据。",
    "prototype_description": "流程和热点说明来自交互文档整理后的原型配置。",
    "hotspot_title": "热点说明",
    "scene_list_title": "流程场景",
    "steps_title": "步骤说明",
    "doc_notes_title": "关键说明",
    "doc_states_title": "流程节点",
    "screen_states_title": "状态说明",
    "screen_notes_title": "备注",
    "screen_refs_title": "文档引用",
    "stat_project_count": "项目数量",
    "stat_screen_count": "界面数量",
    "stat_prototype": "原型模块",
    "stat_detail_screens": "界面数量",
    "stat_detail_doc": "交互文档",
    "stat_detail_scenes": "原型场景",
}


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Project Hub</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap">
  <link rel="stylesheet" href="./styles.css" />
</head>
<body>
  <a class="skip-link" href="#selected-work">跳到精选项目</a>
  <div id="app" class="app">
    <div class="loading">Loading site...</div>
  </div>
  <script src="./app.js"></script>
__ANALYTICS_PLACEHOLDER__
</body>
</html>
"""


CSS_TEMPLATE = """* {
  box-sizing: border-box;
}

:root {
  --bg: #0b1020;
  --bg-soft: rgba(255, 255, 255, 0.04);
  --panel: rgba(15, 23, 42, 0.88);
  --panel-border: rgba(148, 163, 184, 0.16);
  --text: #e5eefc;
  --text-soft: #94a3b8;
  --accent: #7c5cff;
  --accent-2: #2dd4bf;
  --shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
  --radius: 24px;
  --font-body: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  --font-display: "Manrope", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}

body {
  margin: 0;
  font-family: var(--font-body);
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(124, 92, 255, 0.18), transparent 28%),
    radial-gradient(circle at top right, rgba(45, 212, 191, 0.14), transparent 24%),
    var(--bg);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

/* Route all headlines + key display text through Manrope.
   Chinese characters automatically fall back to PingFang SC / 微软雅黑
   since Manrope only contains Latin glyphs. */
h1, h2, h3, h4, h5, h6,
.hub-owner,
.title,
.section-title,
.project-meta h3,
.lightbox-title,
.video-meta h4,
.project-category-label,
.eyebrow,
.section-kicker {
  font-family: var(--font-display);
}

/* Tighten headlines and bump weight contrast against body copy */
h1, h2, h3, h4 {
  letter-spacing: -0.012em;
  line-height: 1.18;
}

.hub-owner, .title {
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1.05;
}

.section-title {
  font-weight: 700;
  letter-spacing: -0.015em;
}

.project-meta h3,
.video-meta h4,
.lightbox-title {
  font-weight: 700;
  letter-spacing: -0.012em;
}

/* Eyebrow / kicker get tracked-out caps treatment */
.section-kicker,
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-weight: 600;
}

.app {
  min-height: 100vh;
  padding: 32px;
}

.shell {
  max-width: 1480px;
  margin: 0 auto;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  backdrop-filter: blur(14px);
}

.loading,
.empty {
  display: grid;
  place-items: center;
  min-height: 60vh;
  color: var(--text-soft);
  font-size: 18px;
}

/* ── Portfolio Hub Hero ─────────────────────────── */

.hub-hero {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 48px 40px;
  margin-bottom: 24px;
  background: linear-gradient(135deg,
    rgba(124,92,255,0.08) 0%,
    rgba(11,16,32,0) 60%);
  border: 1px solid rgba(124,92,255,0.14);
}

.hub-hero-left {
  flex: 1 1 0;
  min-width: 0;
}

.hub-owner {
  margin: 0 0 8px;
  font-size: clamp(32px, 4vw, 56px);
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -0.02em;
  background: linear-gradient(130deg, #fff 30%, var(--accent-2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hub-role {
  display: inline-block;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent-2);
  border: 1px solid rgba(94,234,212,0.3);
  border-radius: 20px;
  padding: 3px 14px;
  margin-bottom: 20px;
}

.hub-bio {
  margin: 0 0 22px;
  color: var(--text-soft);
  font-size: 15px;
  line-height: 1.75;
  max-width: 560px;
}

.hub-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 28px;
}

.hub-tag {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(124,92,255,0.12);
  border: 1px solid rgba(124,92,255,0.28);
  color: rgba(255,255,255,0.72);
  cursor: default;
}

.hub-stats {
  display: flex;
  align-items: center;
  gap: 0;
}

.hub-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0 28px 0 0;
}

.hub-stat:first-child {
  padding-left: 0;
}

.hub-stat-num {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  color: var(--text);
}

.hub-stat-lbl {
  margin-top: 5px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-soft);
}

.hub-stat-divider {
  width: 1px;
  height: 36px;
  background: rgba(148,163,184,0.18);
  margin: 0 28px 0 0;
}

.hub-hero-right {
  flex: 0 0 320px;
  max-width: 380px;
}

.hub-hero-right img {
  display: block;
  width: 100%;
  border-radius: 18px;
  box-shadow: var(--shadow);
}

/* ── Project detail hero ───────────────────────── */

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: 24px;
  margin-bottom: 28px;
}

.hero-copy,
.hero-preview,
.section {
  padding: 24px;
}

.eyebrow {
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-2);
  margin-bottom: 12px;
}

.title {
  margin: 0;
  font-size: clamp(24px, 3.1vw, 40px);
  line-height: 1.1;
  font-weight: 800;
}

.subtitle {
  margin: 12px 0 0;
  color: var(--text-soft);
  font-size: 16px;
}

.description {
  margin: 14px 0 0;
  color: #dbe6fb;
  font-size: 14px;
  line-height: 1.75;
}

.stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.stat {
  min-width: 96px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--bg-soft);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.stat-value {
  display: block;
  font-size: 22px;
  font-weight: 700;
}

.stat-label {
  display: block;
  margin-top: 5px;
  color: var(--text-soft);
  font-size: 12px;
}

/* Hero cover image — constrained height so it doesn't flood the page */
.hero-preview {
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-preview img {
  display: block;
  width: 100%;
  max-height: 320px;
  object-fit: cover;
  object-position: top center;
  border-radius: 18px;
  box-shadow: var(--shadow);
}

/* ── Section / project-level styles ───────────── */

.project-cover img,
.doc-image img,
.screen-image img,
.proto-stage img {
  display: block;
  max-width: 100%;
}

.project-cover img,
.doc-image img,
.screen-image img,
.proto-stage img {
  width: 100%;
  border-radius: 18px;
  box-shadow: var(--shadow);
}

/* Lock home-page card covers to a uniform 16:9 thumbnail regardless of
   source dimensions so every project card visually aligns. */
.project-cover img {
  aspect-ratio: 16 / 9;
  object-fit: cover;
  object-position: center;
}

.contribution-section .section-head {
  margin-bottom: 22px;
}

.contribution-summary {
  max-width: 820px;
  margin: 0;
  color: var(--text-soft);
  font-size: 15px;
  line-height: 1.8;
}

.contribution-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.contribution-item {
  min-width: 0;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.035);
}

.contribution-item h3 {
  margin: 0 0 10px;
  font-size: 17px;
}

.contribution-item p {
  margin: 0;
  color: var(--text-soft);
  font-size: 13px;
  line-height: 1.75;
}

@media (max-width: 760px) {
  .contribution-grid { grid-template-columns: 1fr; }
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.back-button,
.project-card,
.proto-nav button,
.proto-hotspot-list button,
.proto-stage button {
  transition: 160ms ease;
}

.back-button {
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
  cursor: pointer;
}

.back-button:hover,
.proto-nav button:hover,
.proto-hotspot-list button:hover {
  transform: translateY(-1px);
  background: rgba(124, 92, 255, 0.18);
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

/* Category grouping on home page */
.project-category {
  margin-top: 28px;
}

.project-category:first-child {
  margin-top: 0;
}

.project-category-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--panel-border);
}

.project-category-label {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.02em;
  position: relative;
  padding-left: 12px;
}

.project-category-label::before {
  content: "";
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 3px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--accent), var(--accent-2));
}

.project-category-desc {
  margin: 0;
  font-size: 12px;
  color: var(--text-soft);
}

.project-card {
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  position: relative;
  border: 1px solid var(--panel-border);
  transition:
    transform 0.45s cubic-bezier(0.2, 0.7, 0.3, 1),
    box-shadow 0.45s cubic-bezier(0.2, 0.7, 0.3, 1),
    border-color 0.3s ease;
}

.project-card .project-meta {
  flex: 1 1 auto;
}

/* Clip the cover so the inner image can scale beyond its box without
   leaking outside the rounded card. */
.project-card .project-cover {
  overflow: hidden;
}

.project-card .project-cover img {
  transition: transform 0.55s cubic-bezier(0.2, 0.7, 0.3, 1);
  will-change: transform;
}

.project-card:hover {
  transform: translateY(-6px);
  border-color: rgba(124, 92, 255, 0.55);
  box-shadow:
    0 22px 44px -14px rgba(124, 92, 255, 0.45),
    0 10px 28px rgba(0, 0, 0, 0.4);
}

.project-card:hover .project-cover img {
  transform: scale(1.045);
}

/* Soft accent sweep that fades in from the top when hovered.
   Pure CSS, no extra DOM. */
.project-card::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  opacity: 0;
  background: linear-gradient(180deg, rgba(124, 92, 255, 0.08), transparent 35%);
  transition: opacity 0.35s ease;
}

.project-card:hover::after {
  opacity: 1;
}

.project-cover {
  padding: 16px 16px 0;
}

.project-meta {
  padding: 18px;
}

.project-meta h3,
.section-title,
.proto-side h3 {
  margin: 0 0 10px;
  font-size: 22px;
}

.muted {
  color: var(--text-soft);
  line-height: 1.7;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(124, 92, 255, 0.16);
  color: #d9cbff;
  font-size: 12px;
}

.section + .section {
  margin-top: 22px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.section-kicker {
  color: var(--accent-2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  margin-bottom: 8px;
}

.doc-layout {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.doc-image img {
  width: 100%;
  max-width: 100%;
  border-radius: 18px;
  box-shadow: var(--shadow);
  display: block;
}

.doc-meta {
  padding: 18px 20px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.doc-list,
.screen-list,
.proto-step-list,
.proto-hotspot-list {
  margin: 14px 0 0;
  padding-left: 20px;
}

.doc-list li + li,
.proto-step-list li + li {
  margin-top: 8px;
}

.screen-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
}

/* ── Inline screen layout (poster-style projects) ─────────── */

.screen-inline-list {
  display: flex;
  flex-direction: column;
  gap: 36px;
}

.screen-inline-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  padding: 18px 18px 22px;
  cursor: zoom-in;
  transition: transform 0.45s cubic-bezier(0.2, 0.7, 0.3, 1),
              border-color 0.3s ease,
              box-shadow 0.45s cubic-bezier(0.2, 0.7, 0.3, 1);
}

.screen-inline-card:hover {
  transform: translateY(-3px);
  border-color: rgba(124, 92, 255, 0.5);
  box-shadow: 0 16px 36px -16px rgba(124, 92, 255, 0.35);
}

.screen-inline-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}

.screen-inline-image {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0,0,0,0.35);
}

.screen-inline-image img {
  display: block;
  width: 100%;
  height: auto;
  transition: transform 0.6s cubic-bezier(0.2, 0.7, 0.3, 1);
}

.screen-inline-card:hover .screen-inline-image img {
  transform: scale(1.015);
}

.screen-inline-zoom {
  position: absolute;
  top: 14px;
  right: 14px;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(11, 16, 32, 0.75);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  backdrop-filter: blur(6px);
  opacity: 0;
  transform: translateY(-2px);
  transition: opacity 0.2s, transform 0.2s;
  pointer-events: none;
}

.screen-inline-card:hover .screen-inline-zoom,
.screen-inline-card:focus-visible .screen-inline-zoom,
.showcase-card:hover .screen-inline-zoom,
.showcase-card:focus-visible .screen-inline-zoom {
  opacity: 1;
  transform: translateY(0);
}

.screen-inline-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 4px;
}

.screen-inline-section {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-2);
  font-weight: 600;
}

.screen-inline-meta h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.012em;
}

.screen-inline-notes {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-soft);
}

/* ── Showcase module (作品展示) ────────────────────────────── */

.showcase-list {
  display: flex;
  flex-direction: column;
  gap: 36px;
}

.showcase-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--panel-border);
  border-radius: 16px;
  padding: 16px 16px 20px;
  cursor: zoom-in;
  transition: transform 0.45s cubic-bezier(0.2, 0.7, 0.3, 1),
              border-color 0.3s ease,
              box-shadow 0.45s cubic-bezier(0.2, 0.7, 0.3, 1);
}

.showcase-card:hover {
  transform: translateY(-3px);
  border-color: rgba(124, 92, 255, 0.5);
  box-shadow: 0 16px 36px -16px rgba(124, 92, 255, 0.35);
}

.showcase-image {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0,0,0,0.35);
}

.showcase-image img {
  display: block;
  width: 100%;
  height: auto;
  transition: transform 0.6s cubic-bezier(0.2, 0.7, 0.3, 1);
}

.showcase-card:hover .showcase-image img {
  transform: scale(1.015);
}

.showcase-meta {
  padding: 0 6px;
}

.showcase-meta h3 {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.012em;
}

.showcase-meta p {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
}

/* ── PDF / Documents module ───────────────────────────────── */

.pdf-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.pdf-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pdf-meta {
  display: flex;
  gap: 18px;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
}

.pdf-meta-text {
  flex: 1 1 280px;
  min-width: 0;
}

.pdf-meta-text h3 {
  margin: 0 0 6px;
  font-size: 17px;
}

.pdf-meta-text p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
}

.pdf-chips {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.pdf-chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(124, 92, 255, 0.14);
  color: var(--text);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  border: 1px solid rgba(124, 92, 255, 0.28);
}

.pdf-meta-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.pdf-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--panel-border);
  color: var(--text);
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.18s, border-color 0.18s, transform 0.18s;
  white-space: nowrap;
}

.pdf-btn:hover {
  background: rgba(124, 92, 255, 0.16);
  border-color: rgba(124, 92, 255, 0.5);
  transform: translateY(-1px);
}

.pdf-btn-primary {
  background: linear-gradient(135deg, var(--accent), #5eead4);
  color: #04111f;
  border-color: transparent;
  font-weight: 700;
}

.pdf-btn-primary:hover {
  filter: brightness(1.06);
  background: linear-gradient(135deg, var(--accent), #5eead4);
}

.pdf-embed {
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0,0,0,0.4);
  border: 1px solid var(--panel-border);
}

.pdf-embed object,
.pdf-embed iframe {
  display: block;
  width: 100%;
  border: 0;
  min-height: 720px;
}

@media (max-width: 720px) {
  .pdf-meta {
    flex-direction: column;
  }
  .pdf-meta-actions {
    width: 100%;
  }
  .pdf-btn {
    flex: 1;
    justify-content: center;
  }
  .pdf-embed object,
  .pdf-embed iframe {
    min-height: 480px;
  }
}

/* ── Video module ─────────────────────────────────────────── */

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 18px;
}

.video-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease;
  position: relative;
}

.video-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.45);
}

.video-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.video-thumb {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #000;
  overflow: hidden;
}

.video-thumb img,
.video-thumb video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.video-thumb-shade {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(0,0,0,0.55) 100%);
  pointer-events: none;
  transition: background 160ms;
}

.video-card:hover .video-thumb-shade {
  background: linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.4) 100%);
}

.video-play-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(124, 92, 255, 0.85);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  pointer-events: none;
  box-shadow: 0 6px 20px rgba(0,0,0,0.5);
  transition: transform 160ms ease, background 160ms ease;
}

.video-card:hover .video-play-icon {
  transform: translate(-50%, -50%) scale(1.08);
  background: var(--accent);
}

.video-duration {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 2px 8px;
  background: rgba(0,0,0,0.7);
  color: #fff;
  font-size: 11px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}

.video-meta {
  padding: 14px 16px 16px;
}

.video-section {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-2);
  margin-bottom: 4px;
}

.video-meta h4 {
  margin: 0 0 4px;
  font-size: 15px;
}

.video-meta p {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
}

/* Video lightbox tweaks (sit on top of generic .lightbox-overlay rules) */
.video-lightbox-content {
  flex-direction: row;
}
.video-stage {
  background: #000;
}
.video-stage video {
  width: 100%;
  height: 100%;
  max-height: calc(100vh - 120px);
  object-fit: contain;
}

@media (max-width: 880px) {
  .video-lightbox-content {
    flex-direction: column;
  }
}

.screen-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  cursor: zoom-in;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.screen-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.4);
}

.screen-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.screen-zoom-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(11, 16, 32, 0.7);
  color: rgba(255, 255, 255, 0.92);
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  opacity: 0;
  transform: translateY(-4px);
  transition: opacity 0.18s ease, transform 0.18s ease;
  backdrop-filter: blur(4px);
  z-index: 3;
}

.screen-card:hover .screen-zoom-badge,
.screen-card:focus-visible .screen-zoom-badge {
  opacity: 1;
  transform: translateY(0);
}

.screen-variant-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 3;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(124, 92, 255, 0.85);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  pointer-events: none;
  backdrop-filter: blur(4px);
}

/* ── Lightbox variants strip ──────────────────────────────── */

.lightbox-stage {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.lightbox-variants {
  flex: 0 0 auto;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px;
  background: rgba(2, 6, 23, 0.65);
  border: 1px solid rgba(124, 92, 255, 0.18);
  border-radius: 10px;
}

.lightbox-variant-btn {
  flex: 0 0 110px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
  background: transparent;
  border: 2px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text);
  transition: border-color 120ms, background 120ms;
}

.lightbox-variant-btn img {
  width: 100%;
  height: 56px;
  object-fit: cover;
  border-radius: 4px;
  display: block;
}

.lightbox-variant-btn span {
  font-size: 11px;
  line-height: 1.3;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lightbox-variant-btn:hover {
  background: rgba(124, 92, 255, 0.12);
  border-color: rgba(124, 92, 255, 0.4);
}

.lightbox-variant-btn.active {
  border-color: var(--accent);
  background: rgba(124, 92, 255, 0.18);
}

.lightbox-group-counter {
  font-size: 12px;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
  margin-bottom: 4px;
}

/* Edit mode reserves clicks for inline editing — hide the badge there */
.app.edit-mode .screen-zoom-badge {
  display: none;
}

.app.edit-mode .screen-card {
  cursor: default;
}

/* ── Screen lightbox ───────────────────────────────────────── */

.lightbox-overlay {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.86);
  backdrop-filter: blur(6px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  animation: lightbox-fade-in 160ms ease;
}

@keyframes lightbox-fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.lightbox-content {
  display: flex;
  gap: 24px;
  width: min(1280px, 100%);
  max-height: calc(100vh - 64px);
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  padding: 24px;
  box-shadow: 0 32px 80px rgba(0,0,0,0.6);
}

.lightbox-image-wrap {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgba(0,0,0,0.5);
  border-radius: 12px;
}

.lightbox-image-wrap img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
}

.lightbox-info {
  flex: 0 0 360px;
  max-width: 360px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-right: 4px;
}

.lightbox-section {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-2);
  font-weight: 600;
}

.lightbox-title {
  margin: 0;
  font-size: 22px;
  line-height: 1.3;
}

.lightbox-subtitle {
  font-size: 13px;
  color: var(--text-soft);
  margin-top: -8px;
}

.lightbox-desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text);
}

.lightbox-block h4 {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-soft);
}

.lightbox-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.lightbox-notes {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-soft);
}

.lightbox-counter {
  margin-top: auto;
  text-align: right;
  font-size: 12px;
  color: var(--text-soft);
  font-variant-numeric: tabular-nums;
}

.lightbox-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 0;
  background: rgba(11, 16, 32, 0.7);
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  z-index: 1001;
  transition: background 0.15s;
}
.lightbox-close:hover { background: rgba(255, 80, 80, 0.6); }

.lightbox-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 44px;
  height: 64px;
  border: 0;
  border-radius: 10px;
  background: rgba(11, 16, 32, 0.55);
  color: #fff;
  font-size: 28px;
  cursor: pointer;
  z-index: 1001;
  transition: background 0.15s;
}
.lightbox-nav:hover { background: rgba(124, 92, 255, 0.6); }
.lightbox-nav-prev { left: 18px; }
.lightbox-nav-next { right: 18px; }

@media (max-width: 880px) {
  .lightbox-content {
    flex-direction: column;
    padding: 16px;
    gap: 16px;
  }
  .lightbox-info {
    flex: 1 1 auto;
    max-width: 100%;
  }
  .lightbox-stage {
    min-height: 50vh;
  }
  .lightbox-image-wrap {
    min-height: 40vh;
  }
}

.screen-image {
  flex-shrink: 0;
}

.screen-image img {
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: 0;
  box-shadow: none;
  display: block;
  width: 100%;
}

.screen-desc {
  padding: 14px 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.screen-desc h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
}

.screen-desc-section {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent, #7c5cff);
  opacity: 0.85;
}

.screen-desc-body {
  font-size: 13px;
  color: var(--text-soft);
  line-height: 1.55;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.screen-desc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 2px;
}

.screen-desc-chips .chip {
  font-size: 11px;
  padding: 3px 8px;
}

.screen-desc-notes {
  font-size: 12px;
  color: var(--text-soft);
  padding-left: 14px;
  margin: 2px 0 0;
  line-height: 1.6;
}

.screen-desc-notes li + li {
  margin-top: 3px;
}

/* ── Flow chart ──────────────────────────────────────────── */

.flow-wrap {
  position: relative;
  overflow-x: auto;
  padding-bottom: 8px;
}

.flow-container {
  position: relative;
  display: inline-grid;
  gap: 32px 72px;
  padding: 20px 32px 100px;
  min-width: 100%;
}

.flow-svg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: visible;
  z-index: 0;
}

.flow-node {
  position: relative;
  z-index: 1;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 12px;
  overflow: hidden;
  width: 180px;
  transition: box-shadow 160ms ease;
}

.flow-node:hover {
  box-shadow: 0 6px 24px rgba(0,0,0,0.35);
  border-color: rgba(124,92,255,0.4);
}

.flow-node img {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  display: block;
}

.flow-node-placeholder {
  width: 100%;
  aspect-ratio: 16 / 9;
  background: rgba(255,255,255,0.04);
}

.flow-node-label {
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.45;
  text-align: center;
  color: var(--text);
  white-space: pre-wrap;
}

.flow-arrow {
  fill: none;
  stroke: rgba(124, 92, 255, 0.75);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.flow-arrow-back {
  fill: none;
  stroke: rgba(94, 234, 212, 0.6);
  stroke-width: 1.8;
  stroke-dasharray: 6 4;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.flow-edge-label-bg {
  fill: rgba(11, 16, 32, 0.85);
  rx: 4;
  ry: 4;
}

.flow-edge-label {
  font-size: 11px;
  font-weight: 600;
  fill: rgba(255,255,255,0.75);
  text-anchor: middle;
  dominant-baseline: middle;
  letter-spacing: 0.02em;
}

/* ── Doc image collapse ───────────────── */

.doc-image-wrap {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
}

.doc-zoom-btn {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 5;
  padding: 8px 14px;
  border: 0;
  border-radius: 999px;
  background: rgba(11, 16, 32, 0.78);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  backdrop-filter: blur(6px);
  box-shadow: 0 4px 14px rgba(0,0,0,0.35);
  transition: transform 120ms, background 120ms;
}

.doc-zoom-btn:hover {
  background: var(--accent);
  transform: translateY(-1px);
}

.doc-image img {
  cursor: zoom-in;
}

/* ── Interaction doc lightbox (long image viewer) ─────────── */

.doc-lightbox {
  align-items: stretch;
  justify-content: stretch;
  padding: 0;
}

.doc-lb-toolbar {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1001;
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  background: rgba(11, 16, 32, 0.85);
  border-radius: 999px;
  backdrop-filter: blur(8px);
}

.doc-lb-btn {
  padding: 6px 12px;
  border: 0;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 120ms;
  min-width: 32px;
}

.doc-lb-btn:hover {
  background: var(--accent);
}

.doc-lb-zoom-pct {
  padding: 0 10px;
  font-size: 12px;
  color: var(--text-soft);
  font-variant-numeric: tabular-nums;
  min-width: 70px;
  text-align: center;
}

.doc-lb-hint {
  margin-left: 8px;
  padding-left: 12px;
  border-left: 1px solid rgba(255,255,255,0.12);
  font-size: 11px;
  color: var(--text-soft);
  letter-spacing: 0.02em;
}

.doc-lb-scroll {
  position: absolute;
  inset: 0;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.doc-lb-scroll.dragging {
  cursor: grabbing;
}

.doc-lb-scroll img {
  position: absolute;
  top: 0;
  left: 0;
  display: block;
  max-width: none;
  width: auto;
  height: auto;
  transform-origin: 0 0;
  user-select: none;
  -webkit-user-drag: none;
  pointer-events: none;            /* drag is handled by the stage */
  box-shadow: 0 24px 60px rgba(0,0,0,0.55);
  border-radius: 4px;
  will-change: transform;
}

.doc-image-wrap .doc-image {
  max-height: 480px;
  overflow: hidden;
  transition: max-height 0.4s ease;
}

.doc-image-wrap.expanded .doc-image {
  max-height: 6000px;
}

.doc-expand-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 140px;
  background: linear-gradient(to bottom, transparent, rgba(11,16,32,0.97) 65%);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 22px;
  pointer-events: none;
}

.doc-image-wrap.expanded .doc-expand-bar {
  display: none;
}

/* Collapse-bar shown only when expanded — gives a quick way back up */
.doc-collapse-bar {
  display: none;
}

.doc-image-wrap.expanded .doc-collapse-bar {
  display: flex;
  justify-content: center;
  padding: 18px 0 6px;
}

.doc-expand-btn {
  pointer-events: all;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: linear-gradient(135deg, var(--accent), #5eead4);
  border: 0;
  color: #04111f;
  padding: 12px 28px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  font-family: inherit;
  letter-spacing: 0.03em;
  box-shadow: 0 8px 24px rgba(124,92,255,0.35), 0 2px 6px rgba(0,0,0,0.25);
  transition: transform 0.15s, box-shadow 0.15s, filter 0.15s;
}

.doc-expand-btn:hover {
  transform: translateY(-1px);
  filter: brightness(1.06);
  box-shadow: 0 10px 28px rgba(124,92,255,0.5), 0 3px 8px rgba(0,0,0,0.3);
}

.doc-expand-icon {
  font-size: 11px;
  line-height: 1;
}

.doc-expand-label {
  line-height: 1;
}

.proto-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
  gap: 18px;
}

.proto-main,
.proto-side {
  padding: 18px;
}

.proto-stage {
  position: relative;
  margin-top: 16px;
}

.proto-hotspot {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 28px;
  height: 28px;
  border: 2px solid rgba(255, 255, 255, 0.95);
  border-radius: 999px;
  background: linear-gradient(135deg, var(--accent), #5eead4);
  color: #04111f;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: transform 0.15s, box-shadow 0.15s;
  z-index: 2;
}

/* Pulsing ripple — visual cue that this spot is interactive.
   Two staggered rings expand and fade outward. */
.proto-hotspot::before,
.proto-hotspot::after {
  content: "";
  position: absolute;
  inset: -4px;
  border-radius: inherit;
  border: 2px solid rgba(94, 234, 212, 0.6);
  pointer-events: none;
  z-index: -1;
  animation: proto-hotspot-pulse 2.4s cubic-bezier(0.2, 0.7, 0.4, 1) infinite;
}

.proto-hotspot::after {
  animation-delay: 1.2s;
}

.proto-hotspot:hover {
  transform: translate(-50%, -50%) scale(1.08);
  box-shadow: 0 4px 18px rgba(94,234,212,0.35);
}

/* Once a hotspot is selected (clicked), stop pulsing — it's been "discovered". */
.proto-hotspot.active::before,
.proto-hotspot.active::after,
.proto-hotspot.visited::before,
.proto-hotspot.visited::after {
  animation: none;
  opacity: 0;
}

.proto-hotspot.active {
  outline: 3px solid rgba(124, 92, 255, 0.28);
}

@keyframes proto-hotspot-pulse {
  0% {
    transform: scale(1);
    opacity: 0.85;
    border-width: 2px;
  }
  70% {
    transform: scale(2.1);
    opacity: 0;
    border-width: 1px;
  }
  100% {
    transform: scale(2.1);
    opacity: 0;
    border-width: 1px;
  }
}

/* Navigation hotspot – shows edge label + arrow */
.proto-hotspot-nav {
  width: auto;
  min-width: 40px;
  height: auto;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(11, 16, 32, 0.82);
  border: 1.5px solid rgba(94, 234, 212, 0.7);
  color: rgba(94, 234, 212, 0.95);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.03em;
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 12px rgba(0,0,0,0.4);
}

.proto-hotspot-nav::before,
.proto-hotspot-nav::after {
  /* Nav hotspots get a softer, color-matched glow */
  inset: -2px;
  border-color: rgba(94, 234, 212, 0.55);
}

.proto-hotspot-nav:hover {
  background: rgba(94, 234, 212, 0.18);
  transform: translate(-50%, -50%) scale(1.06);
  box-shadow: 0 4px 18px rgba(94,234,212,0.25);
}

.proto-panel {
  margin-top: 16px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.proto-nav {
  display: grid;
  gap: 10px;
}

.proto-nav button,
.proto-hotspot-list button {
  border: 0;
  border-radius: 16px;
  text-align: left;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  cursor: pointer;
}

.proto-nav button.active,
.proto-hotspot-list button.active {
  background: linear-gradient(135deg, var(--accent), #5eead4);
  color: #04111f;
  font-weight: 700;
}

.editor-toolbar {
  position: sticky;
  top: 12px;
  z-index: 50;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 0 auto 18px;
  padding: 12px 16px;
}

.editor-toolbar-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.editor-toolbar-title {
  font-size: 14px;
  font-weight: 700;
}

.editor-toolbar-note {
  color: var(--text-soft);
  font-size: 12px;
}

.editor-toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.editor-toolbar button {
  border: 0;
  border-radius: 999px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
  cursor: pointer;
}

.editor-toolbar button.primary {
  background: linear-gradient(135deg, var(--accent), #5eead4);
  color: #04111f;
  font-weight: 700;
}

.editor-toolbar-sep {
  width: 1px;
  align-self: stretch;
  background: rgba(255,255,255,0.1);
  margin: 0 4px;
}

/* ── Management UI ──────────────────────────────────────── */

.manage-delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 5;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 0;
  background: rgba(255,80,80,0.85);
  color: #fff;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.project-card:hover .manage-delete-btn,
.screen-card:hover .manage-delete-btn {
  opacity: 1;
}

.screen-card {
  position: relative;
}

/* ── Add-screen tile ──────────────────────────────────────── */

.screen-add-tile {
  border: 2px dashed rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}

.screen-add-tile:hover {
  border-color: var(--accent);
  background: rgba(124, 92, 255, 0.08);
  transform: translateY(-2px);
}

.screen-add-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--text-soft);
  text-align: center;
  padding: 20px;
}

.screen-add-plus {
  font-size: 42px;
  font-weight: 300;
  line-height: 1;
  color: var(--accent);
}

.screen-add-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.screen-add-hint {
  font-size: 12px;
}

/* ── Replace-image control ───────────────────────────────── */

.replace-image-btn {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 5;
  padding: 5px 12px;
  border-radius: 14px;
  border: 0;
  background: rgba(20,22,40,0.82);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s, background 0.2s;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.replace-image-btn:hover {
  background: rgba(108,99,255,0.92);
}

.replace-image-btn[disabled] {
  opacity: 0.6 !important;
  cursor: wait;
}

/* reveal on hover of the enclosing image container */
.screen-card:hover .replace-image-btn,
.doc-image-wrap:hover .replace-image-btn,
.hero-preview:hover .replace-image-btn,
.project-card:hover .replace-image-btn {
  opacity: 1;
}

/* ensure image wrappers can position the overlay button */
.screen-image { position: relative; }
.hero-preview { position: relative; }
.project-cover { position: relative; }

.manage-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0,0,0,0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.manage-panel {
  background: var(--surface, #0f2038);
  border-radius: 16px;
  width: min(560px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: 28px 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Flow Editor ──────────────────────────────────────────── */

.flow-editor-panel {
  width: min(880px, 100%);
}

.flow-editor-body {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-right: 4px;
}

.flow-editor-meta {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.flow-editor-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--panel-border);
  border-radius: 12px;
}

.flow-editor-section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.flow-editor-section-head h3 {
  margin: 0;
  font-size: 15px;
  color: var(--text);
}

.flow-editor-hint {
  font-size: 12px;
  color: var(--text-soft);
}

.flow-nodes-list,
.flow-edges-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.flow-editor-empty {
  text-align: center;
  padding: 16px;
  color: var(--text-soft);
  font-size: 13px;
  background: rgba(0,0,0,0.18);
  border-radius: 8px;
}

.flow-editor-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 8px;
  background: rgba(15, 23, 42, 0.45);
  border-radius: 8px;
}

.flow-editor-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.flow-editor-cell-narrow { flex: 0 0 64px; }
.flow-editor-cell-wide   { flex: 1.4; }

.flow-editor-cell-label {
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-soft);
}

.flow-editor-cell input,
.flow-editor-cell select {
  width: 100%;
  padding: 6px 8px;
  background: rgba(0,0,0,0.35);
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
}

.flow-editor-row-del {
  flex: 0 0 28px;
  height: 28px;
  border-radius: 50%;
  border: 0;
  background: rgba(255, 80, 80, 0.6);
  color: #fff;
  cursor: pointer;
  align-self: center;
  margin-bottom: 2px;
}

.flow-editor-foot {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--panel-border);
}

.flow-editor-foot .manage-status {
  margin-right: auto;
  font-size: 12px;
  color: var(--text-soft);
}

.manage-panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.manage-panel-head h2 {
  margin: 0;
  font-size: 20px;
}

.manage-panel-head button {
  background: transparent;
  border: 0;
  color: var(--text-soft);
  font-size: 20px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}

.manage-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.manage-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.manage-label {
  font-size: 13px;
  font-weight: 600;
}

.manage-label em {
  color: #f87171;
  font-style: normal;
}

.manage-field input,
.manage-field textarea {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 8px;
  color: var(--text);
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.manage-field input:focus,
.manage-field textarea:focus {
  outline: none;
  border-color: var(--accent, #6c63ff);
}

.manage-hint {
  font-size: 12px;
  color: var(--text-soft);
  margin: 0;
}

.manage-upload-zone {
  border: 2px dashed rgba(255,255,255,0.2);
  border-radius: 12px;
  padding: 28px 20px;
  text-align: center;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-soft);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  transition: border-color 0.2s, background 0.2s;
}

.manage-upload-zone:hover,
.manage-upload-zone.drag-over {
  border-color: var(--accent, #6c63ff);
  background: rgba(108,99,255,0.08);
}

.manage-upload-icon {
  font-size: 28px;
}

.manage-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}

.manage-file-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  padding: 4px 8px;
}

.manage-form-actions {
  display: flex;
  gap: 10px;
}

.manage-form-actions button {
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  border: 0;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.manage-form-actions button.primary {
  background: linear-gradient(135deg, var(--accent), #5eead4);
  color: #04111f;
}

.manage-form-actions button:not(.primary) {
  background: rgba(255,255,255,0.08);
  color: var(--text);
}

.manage-status {
  font-size: 13px;
  color: var(--text-soft);
  min-height: 20px;
}

/* ── Section Manager ──────────────────────────────────────── */

.section-mgr-overlay {
  position: fixed;
  inset: 0;
  z-index: 210;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  padding: 72px 24px 24px;
}

.section-mgr-panel {
  background: var(--surface, #0f2038);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  width: min(400px, 92vw);
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0;
  box-shadow: 0 24px 64px rgba(0,0,0,0.55);
}

.section-mgr-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 20px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.07);
}

.section-mgr-head h3 {
  margin: 0;
  font-size: 16px;
}

.section-mgr-head button {
  background: transparent;
  border: 0;
  color: var(--text-soft);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}

.section-mgr-group {
  padding: 14px 20px;
}

.section-mgr-group + .section-mgr-group {
  border-top: 1px solid rgba(255,255,255,0.06);
}

.section-mgr-group-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-soft);
  margin-bottom: 10px;
}

.section-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  gap: 10px;
}

.section-toggle-row + .section-toggle-row {
  border-top: 1px solid rgba(255,255,255,0.05);
}

.section-toggle-label {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}

.section-toggle-icon {
  font-size: 16px;
  width: 24px;
  text-align: center;
  opacity: 0.8;
}

.section-toggle-name {
  font-weight: 500;
}

.section-toggle-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.toggle-eye-btn {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 13px;
  cursor: pointer;
  color: var(--text);
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}

.toggle-eye-btn:hover {
  background: rgba(255,255,255,0.08);
}

.toggle-eye-btn.hidden-section {
  opacity: 0.45;
  border-style: dashed;
}

.section-del-btn {
  background: transparent;
  border: 1px solid rgba(248,113,113,0.3);
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 12px;
  cursor: pointer;
  color: #f87171;
  transition: background 0.15s;
}

.section-del-btn:hover {
  background: rgba(248,113,113,0.1);
}

.section-mgr-add {
  padding: 14px 20px;
  border-top: 1px solid rgba(255,255,255,0.06);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-mgr-add input,
.section-mgr-add textarea {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  color: var(--text);
  padding: 9px 12px;
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
}

.section-mgr-add input:focus,
.section-mgr-add textarea:focus {
  outline: none;
  border-color: var(--accent, #7c5cff);
}

.section-mgr-add-btn {
  border: 1px dashed rgba(255,255,255,0.2);
  border-radius: 8px;
  background: transparent;
  color: var(--text-soft);
  padding: 9px 14px;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, color 0.15s;
  width: 100%;
}

.section-mgr-add-btn:hover {
  border-color: var(--accent, #7c5cff);
  color: var(--text);
}

.section-mgr-add-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-mgr-add-form-actions {
  display: flex;
  gap: 8px;
}

.section-mgr-add-form-actions button {
  flex: 1;
  padding: 9px;
  border-radius: 8px;
  border: 0;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.section-mgr-add-form-actions button.primary {
  background: linear-gradient(135deg, var(--accent), #5eead4);
  color: #04111f;
}

.section-mgr-add-form-actions button:not(.primary) {
  background: rgba(255,255,255,0.07);
  color: var(--text);
}

/* custom section card */
.custom-section-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.custom-section-card .section-kicker {
  color: var(--accent);
}

.custom-section-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-soft);
  white-space: pre-wrap;
}

.edit-mode [data-edit-path],
.edit-mode [data-image-path] {
  cursor: pointer;
}

.edit-mode [data-edit-path] {
  outline: 1px dashed rgba(94, 234, 212, 0.7);
  outline-offset: 4px;
}

.edit-mode [data-image-path] {
  outline: 2px dashed rgba(124, 92, 255, 0.65);
  outline-offset: 6px;
}

@media (max-width: 1080px) {
  .hero,
  .doc-layout,
  .proto-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .app {
    padding: 18px;
  }

  .hero-copy,
  .hero-preview,
  .section,
  .proto-main,
  .proto-side {
    padding: 16px;
  }
}

/* ── Editorial portfolio refresh ────────────────────────────────────── */
.skip-link {
  position: fixed;
  z-index: 10000;
  top: 16px;
  left: 20px;
  padding: 10px 16px;
  border-radius: 999px;
  background: #fff;
  color: #0b1020;
  font-weight: 700;
  transform: translateY(-160%);
  transition: transform 160ms ease;
}

.skip-link:focus { transform: translateY(0); }

body {
  background:
    radial-gradient(circle at 12% -8%, rgba(124, 92, 255, .22), transparent 32%),
    radial-gradient(circle at 92% 10%, rgba(45, 212, 191, .12), transparent 27%),
    #080b14;
}

.app { padding-top: 20px; }

.portfolio-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding: 8px 4px;
}

.portfolio-mark {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.portfolio-mark::before {
  content: "";
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--accent-2);
  box-shadow: 0 0 18px rgba(45, 212, 191, .8);
}

.portfolio-nav-meta {
  color: var(--text-soft);
  font-size: 12px;
}

.portfolio-nav-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.portfolio-nav-link,
.portfolio-mark-button {
  border: 0;
  background: transparent;
  color: var(--text-soft);
  font: inherit;
  cursor: pointer;
}

.portfolio-nav-link {
  padding: 7px 0;
  font-size: 12px;
}

.portfolio-nav-link:hover,
.portfolio-nav-link.is-active {
  color: #fff;
}

.portfolio-mark-button {
  padding: 0;
  text-align: left;
}

.portfolio-about-button {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 9px 13px;
  border: 1px solid rgba(45,212,191,.38);
  border-radius: 999px;
  background: rgba(45,212,191,.08);
  color: #d8fff8;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: 180ms ease;
}

.portfolio-about-button:hover {
  border-color: var(--accent-2);
  background: rgba(45,212,191,.16);
  transform: translateY(-1px);
}

.portfolio-project-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 13px;
  border: 1px solid rgba(45,212,191,.38);
  border-radius: 999px;
  background: rgba(45,212,191,.1);
  color: #d8fff8;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: 180ms ease;
}

.portfolio-project-button:hover {
  border-color: var(--accent-2);
  background: var(--accent-2);
  color: #07120f;
}

.hub-hero.editorial-hero {
  position: relative;
  min-height: min(72vh, 720px);
  align-items: flex-end;
  overflow: hidden;
  padding: clamp(34px, 6vw, 82px);
  border-radius: 34px;
  background:
    linear-gradient(105deg, rgba(8, 11, 20, .98) 4%, rgba(8, 11, 20, .8) 52%, rgba(8, 11, 20, .18) 100%),
    linear-gradient(145deg, rgba(124, 92, 255, .2), rgba(45, 212, 191, .08));
}

.editorial-hero::after {
  content: "UX";
  position: absolute;
  right: -2vw;
  top: -6vw;
  color: transparent;
  font-size: clamp(180px, 28vw, 430px);
  font-weight: 800;
  letter-spacing: -.1em;
  line-height: 1;
  -webkit-text-stroke: 1px rgba(255, 255, 255, .065);
  pointer-events: none;
}

.editorial-hero .hub-hero-left {
  position: relative;
  z-index: 1;
  max-width: 920px;
}

.hero-intro {
  margin: 0 0 22px;
  color: var(--accent-2);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .15em;
  text-transform: uppercase;
}

.hero-statement {
  max-width: 900px;
  margin: 0;
  color: #f7f8fc;
  font-size: clamp(46px, 7vw, 102px);
  font-weight: 800;
  letter-spacing: -.055em;
  line-height: .96;
}

.hero-statement em {
  color: var(--accent-2);
  font-style: normal;
}

.editorial-hero .hub-bio {
  max-width: 650px;
  margin: 30px 0 0;
  color: rgba(229, 238, 252, .68);
  font-size: 16px;
}

.hero-footer {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: 34px;
}

.hero-primary-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 10px;
}

.hero-cta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 13px 18px;
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 999px;
  color: #fff;
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
  transition: 180ms ease;
}

.hero-cta:hover { background: #fff; color: #0b1020; transform: translateY(-2px); }

.hero-about-cta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 13px 18px;
  border: 1px solid rgba(45,212,191,.38);
  border-radius: 999px;
  background: rgba(45,212,191,.08);
  color: #d8fff8;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: 180ms ease;
}

.hero-about-cta:hover {
  border-color: var(--accent-2);
  background: var(--accent-2);
  color: #07120f;
  transform: translateY(-2px);
}

.editorial-section {
  margin-top: 22px;
  padding: clamp(24px, 4vw, 54px);
  border-radius: 34px;
  background: rgba(12, 17, 30, .82);
}

.editorial-section .section-head { margin-bottom: 42px; }
.editorial-section .section-title { font-size: clamp(34px, 5vw, 68px); letter-spacing: -.045em; }
.editorial-section .section-kicker { color: var(--accent-2); }

.project-category { margin-top: 70px; }
.project-category:first-child { margin-top: 0; }
.project-category-head { align-items: flex-end; justify-content: space-between; margin-bottom: 22px; }
.project-category-label { font-size: 20px; }
.project-category-desc { max-width: 640px; font-size: 13px; line-height: 1.7; text-align: right; }

.project-grid {
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 18px;
}

.project-card { grid-column: span 4; min-width: 0; border-radius: 22px; background: #101725; }
.project-card:nth-child(1) { grid-column: span 7; }
.project-card:nth-child(2) { grid-column: span 5; }
.project-card .project-cover { padding: 0; }
.project-card .project-cover img { border-radius: 0; aspect-ratio: 16 / 9; }
.project-card:nth-child(1) .project-cover img,
.project-card:nth-child(2) .project-cover img { aspect-ratio: 16 / 9; }
.project-card .project-meta { padding: 22px; }

.case-overline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: var(--accent-2);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.case-view { color: var(--text-soft); transition: 160ms ease; }
.project-card:hover .case-view,
.project-card:focus-visible .case-view { color: #fff; transform: translateX(3px); }
.project-card:focus-visible { outline: 3px solid var(--accent-2); outline-offset: 4px; }
.project-meta h3 { font-size: clamp(20px, 2vw, 30px); }
.project-meta .muted + .muted { font-size: 13px; }

@media (max-width: 900px) {
  .project-card,
  .project-card:nth-child(1),
  .project-card:nth-child(2) { grid-column: span 6; }
  .editorial-hero { min-height: 620px; }
}

@media (max-width: 620px) {
  .app { padding: 12px; }
  .portfolio-nav-meta { display: none; }
  .hub-hero.editorial-hero { min-height: 600px; padding: 30px 22px; border-radius: 26px; }
  .hero-statement { font-size: clamp(43px, 14vw, 66px); }
  .hero-footer { align-items: flex-start; flex-direction: column; }
  .hero-primary-actions { align-items: flex-start; flex-direction: column; }
  .hub-tags { display: none; }
  .editorial-section { padding: 30px 18px; border-radius: 26px; }
  .project-category-head { display: block; }
  .project-category-desc { margin: 10px 0 0 12px; text-align: left; }
  .project-grid { grid-template-columns: 1fr; }
  .project-card,
  .project-card:nth-child(1),
  .project-card:nth-child(2) { grid-column: 1; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}

/* Equal-weight continuous project index */
.hub-hero.editorial-hero {
  min-height: 410px;
  align-items: center;
  padding: clamp(52px, 8vw, 110px) 4px;
  border: 0;
  border-bottom: 1px solid rgba(255,255,255,.13);
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  backdrop-filter: none;
}
.editorial-hero::after { right: 0; top: 8%; font-size: clamp(140px, 22vw, 320px); opacity: .7; }
.hero-statement { max-width: 900px; font-size: clamp(36px, 3.7vw, 52px); line-height: 1.1; letter-spacing: -.04em; }
.editorial-hero .hub-bio { max-width: 720px; }
.hero-footer { margin-top: 28px; }
.editorial-section {
  margin-top: 0;
  padding: clamp(70px, 9vw, 130px) 4px 40px;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  backdrop-filter: none;
}
.editorial-section .section-head {
  margin-bottom: 46px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255,255,255,.14);
}
.editorial-section .section-title { font-size: clamp(28px, 3.4vw, 44px); }
.project-list { display: block; }
.project-card.project-row,
.project-card.project-row:nth-child(1),
.project-card.project-row:nth-child(2) {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(300px, .88fr);
  grid-column: auto;
  align-items: center;
  gap: clamp(34px, 6vw, 94px);
  min-height: 440px;
  padding: clamp(34px, 5vw, 72px) 0;
  overflow: visible;
  border: 0;
  border-bottom: 1px solid rgba(255,255,255,.14);
  border-radius: 0;
  box-shadow: none;
  background: transparent;
}
.project-card.project-row:hover { transform: none; border-color: rgba(255,255,255,.28); box-shadow: none; }
.project-card.project-row::after { display: none; }
.project-card.project-row:nth-child(even) .project-cover { grid-column: 2; }
.project-card.project-row:nth-child(even) .project-meta { grid-column: 1; grid-row: 1; }
.project-card.project-row .project-cover {
  padding: 0;
  overflow: hidden;
  border-radius: 22px;
  background: #111827;
  box-shadow: 0 24px 60px rgba(0,0,0,.28);
}
.project-card.project-row .project-cover img,
.project-card.project-row:nth-child(1) .project-cover img,
.project-card.project-row:nth-child(2) .project-cover img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 0;
  object-fit: cover;
  transition: transform .65s cubic-bezier(.2,.7,.3,1), filter .4s ease;
}
.project-card.project-row:hover .project-cover img { transform: scale(1.025); filter: brightness(1.04); }
.project-card.project-row .project-meta { padding: 0; }
.project-card.project-row .project-meta h3 {
  margin-bottom: 14px;
  font-size: clamp(29px, 3.5vw, 50px);
  letter-spacing: -.045em;
}
.project-card.project-row .project-subtitle { margin: 0 0 18px; color: #d6def0; font-size: 15px; line-height: 1.65; }
.project-card.project-row .project-summary { max-width: 580px; margin: 0; color: var(--text-soft); font-size: 14px; line-height: 1.8; }
.project-card.project-row .case-overline { margin-bottom: 22px; }
.project-card.project-row .chips { margin-top: 24px; }
.project-card.project-row .chip { background: transparent; border: 1px solid rgba(255,255,255,.13); color: #aeb9cc; }
@media (max-width: 820px) {
  .project-card.project-row,
  .project-card.project-row:nth-child(1),
  .project-card.project-row:nth-child(2) { grid-template-columns: 1fr; gap: 28px; min-height: 0; padding: 50px 0; }
  .project-card.project-row:nth-child(even) .project-cover,
  .project-card.project-row:nth-child(even) .project-meta { grid-column: 1; }
  .project-card.project-row:nth-child(even) .project-cover { grid-row: 1; }
  .project-card.project-row:nth-child(even) .project-meta { grid-row: 2; }
}
@media (max-width: 620px) {
  .hub-hero.editorial-hero { min-height: 430px; padding: 46px 2px; border-radius: 0; }
  .editorial-section { padding: 74px 2px 24px; border-radius: 0; }
  .editorial-section .section-head { margin-bottom: 10px; }
  .project-card.project-row .project-meta h3 { font-size: 32px; }
  .project-card.project-row .project-cover { border-radius: 15px; }
}

/* Pixel-game accents and category tabs */
.pixel-cluster {
  position: absolute;
  z-index: 1;
  right: clamp(22px, 5vw, 76px);
  bottom: clamp(34px, 6vw, 82px);
  width: 82px;
  height: 62px;
  opacity: .72;
  pointer-events: none;
}
.pixel-cluster i { position: absolute; display: block; width: 8px; height: 8px; background: var(--accent-2); image-rendering: pixelated; }
.pixel-cluster i:nth-child(1) { left: 0; top: 16px; box-shadow: 8px 0 var(--accent-2), 16px 0 var(--accent-2), 16px 8px var(--accent-2); }
.pixel-cluster i:nth-child(2) { right: 0; top: 0; background: var(--accent); box-shadow: -8px 8px var(--accent), -16px 16px var(--accent); }
.pixel-cluster i:nth-child(3) { right: 24px; bottom: 0; background: #fff; box-shadow: 8px 0 #fff, 0 -8px #fff, 8px -8px #fff; opacity: .48; }
.pixel-cluster i:nth-child(n+4) { display: none; }

.pixel-avatar {
  position: absolute;
  z-index: 2;
  right: clamp(18px, 5vw, 72px);
  bottom: clamp(108px, 10vw, 138px);
  width: 174px;
  height: 104px;
  padding: 0;
  background: transparent;
  border: 0;
  clip-path: none;
  box-shadow: none;
  image-rendering: pixelated;
  animation: pixel-avatar-idle 2.8s steps(2, end) infinite;
}

@media (min-width: 761px) and (max-width: 1100px) {
  .pixel-avatar {
    right: 14px;
    top: 70px;
    bottom: auto;
    transform: scale(.76);
    transform-origin: right top;
    animation: none;
  }
}

@media (max-width: 760px) {
  .pixel-avatar { display: none; }
}
.pixel-girl { position: relative; float: left; width: 76px; height: 76px; image-rendering: pixelated; }
.pixel-girl i { position: absolute; display: block; }
.pg-hair {
  left: 7px;
  top: 3px;
  width: 62px;
  height: 63px;
  background: #28223f;
  box-shadow: -4px 8px 0 #28223f, 4px 8px 0 #28223f, 0 8px 0 #28223f;
}
.pg-face {
  left: 15px;
  top: 18px;
  width: 46px;
  height: 43px;
  background: #ffd6bd;
  box-shadow: 0 4px 0 #ffd6bd, 4px 0 0 #ffd6bd, -4px 0 0 #ffd6bd;
}
.pg-bangs {
  left: 11px;
  top: 9px;
  width: 54px;
  height: 16px;
  background: #28223f;
  box-shadow: 0 4px 0 #28223f, 8px 8px 0 #28223f, 26px 8px 0 #28223f, 42px 8px 0 #28223f;
}
.pg-eye { top: 34px; width: 5px; height: 7px; background: #332f48; box-shadow: 0 -1px 0 #fff; }
.pg-eye-left { left: 25px; }
.pg-eye-right { right: 25px; }
.pg-blush { top: 45px; width: 6px; height: 3px; background: #f49aaa; opacity: .9; }
.pg-blush-left { left: 19px; }
.pg-blush-right { right: 19px; }
.pg-mouth { left: 35px; top: 49px; width: 7px; height: 3px; background: #b85b70; box-shadow: 2px 2px 0 #b85b70; }
.pg-neck { left: 31px; top: 60px; width: 14px; height: 8px; background: #f2bda6; }
.pg-shirt {
  left: 17px;
  bottom: 0;
  width: 42px;
  height: 12px;
  background: var(--accent);
  box-shadow: -7px 5px 0 var(--accent), 7px 5px 0 var(--accent);
}
.pixel-gamepad {
  position: absolute;
  right: 12px;
  top: 28px;
  width: 66px;
  height: 48px;
  image-rendering: pixelated;
  transform: rotate(2deg);
}
.pixel-gamepad i { position: absolute; display: block; }
.pad-body {
  left: 6px;
  top: 6px;
  width: 54px;
  height: 32px;
  background: #e9ecf8;
  box-shadow: -4px 4px 0 #e9ecf8, 4px 4px 0 #e9ecf8, 0 -4px 0 #e9ecf8, 4px 0 0 #aeb5d1, 0 4px 0 #aeb5d1;
}
.pad-grip { top: 30px; width: 14px; height: 15px; background: #aeb5d1; }
.pad-grip-left { left: 8px; box-shadow: 4px 4px 0 #aeb5d1; }
.pad-grip-right { right: 8px; box-shadow: -4px 4px 0 #aeb5d1; }
.pad-cross {
  left: 16px;
  top: 16px;
  width: 14px;
  height: 5px;
  background: #28223f;
  box-shadow: 4px -4px 0 #28223f, 4px 4px 0 #28223f;
}
.pad-button { width: 6px; height: 6px; background: var(--accent); }
.pad-button-a { right: 15px; top: 14px; }
.pad-button-b { right: 23px; top: 22px; background: var(--accent-2); }
.pad-light { left: 31px; top: 28px; width: 5px; height: 3px; background: var(--accent-2); box-shadow: 0 0 8px var(--accent-2); }
.pixel-avatar:hover .pixel-gamepad { animation: gamepad-nudge .42s steps(2, end); }
.pixel-avatar:hover .pg-eye { height: 2px; top: 38px; box-shadow: none; }
@keyframes pixel-avatar-idle {
  0%, 88%, 100% { transform: translateY(0); }
  92%, 96% { transform: translateY(-3px); }
}
@keyframes gamepad-nudge {
  0%, 100% { transform: rotate(2deg) translateY(0); }
  50% { transform: rotate(-3deg) translateY(-3px); }
}

.category-switcher {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0 0 18px;
}
.category-tab {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 68px;
  padding: 16px 20px;
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 4px;
  background: rgba(255,255,255,.025);
  color: var(--text-soft);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
}
.category-tab::before {
  content: "";
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  background: currentColor;
  box-shadow: 8px 0 currentColor;
  opacity: .55;
}
.category-tab span { flex: 1; font-size: 14px; font-weight: 700; }
.category-tab b { font-size: 11px; letter-spacing: .12em; }
.category-tab:hover { color: #fff; border-color: rgba(255,255,255,.28); transform: translateY(-2px); }
.category-tab.is-active {
  border-color: var(--accent-2);
  background: rgba(45,212,191,.1);
  color: #fff;
  box-shadow: 4px 4px 0 rgba(45,212,191,.22);
}
.category-tab.is-active::after {
  content: "PLAY";
  position: absolute;
  right: 18px;
  bottom: 5px;
  color: var(--accent-2);
  font-size: 7px;
  font-weight: 800;
  letter-spacing: .16em;
}
.category-tab:focus-visible { outline: 3px solid var(--accent-2); outline-offset: 3px; }

/* About page */
.about-page { padding-bottom: 50px; }
.about-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, .55fr);
  gap: clamp(34px, 7vw, 110px);
  align-items: end;
  min-height: 560px;
  padding: clamp(64px, 9vw, 130px) 4px 80px;
  border-bottom: 1px solid rgba(255,255,255,.14);
}
.about-hero-copy { max-width: 900px; }
.about-hero h1 {
  max-width: 850px;
  margin: 18px 0 24px;
  font-size: clamp(38px, 4.5vw, 58px);
  line-height: 1.04;
  letter-spacing: -.05em;
}
.about-hero-copy > p {
  max-width: 720px;
  margin: 0;
  color: #c5cede;
  font-size: clamp(15px, 1.35vw, 18px);
  line-height: 1.8;
}
.about-hero-actions { margin-top: 26px; }
.about-project-cta {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 13px 19px;
  border: 1px solid var(--accent-2);
  border-radius: 999px;
  background: var(--accent-2);
  color: #07120f;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 10px 28px rgba(45,212,191,.16);
  transition: 180ms ease;
}
.about-project-cta:hover { transform: translateY(-2px); box-shadow: 0 14px 34px rgba(45,212,191,.24); }
.about-focus { display: flex; flex-wrap: wrap; gap: 9px; margin-top: 22px; }
.about-focus span,
.about-tool-cloud span {
  padding: 8px 11px;
  border: 1px solid rgba(255,255,255,.13);
  border-radius: 999px;
  color: #cbd5e1;
  font-size: 11px;
}
.about-identity-card {
  position: relative;
  overflow: hidden;
  min-height: 360px;
  padding: 28px;
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 24px;
  background: linear-gradient(155deg, rgba(124,92,255,.15), rgba(45,212,191,.04));
}
.about-monogram {
  margin-bottom: 62px;
  color: transparent;
  font-size: clamp(54px, 6vw, 86px);
  font-weight: 800;
  letter-spacing: -.07em;
  line-height: .8;
  white-space: nowrap;
  -webkit-text-stroke: 1px rgba(255,255,255,.22);
}
.about-name-cn { margin: 0; color: #fff; font-size: 24px; font-weight: 760; }
.about-name-en { margin: 4px 0 0; color: var(--text-soft); font-size: 13px; }
.about-role { margin-top: 24px; color: var(--accent-2); font-size: 13px; font-weight: 700; letter-spacing: .05em; }
.about-privacy-note { margin: 22px 0 0; color: #768196; font-size: 10px; line-height: 1.6; }
.about-section { padding: clamp(70px, 9vw, 124px) 4px; border-bottom: 1px solid rgba(255,255,255,.14); }
.about-section-heading { margin-bottom: 42px; }
.about-section-heading.compact { margin-bottom: 28px; }
.about-section-heading h2 { margin: 9px 0 0; font-size: clamp(28px, 3.4vw, 44px); letter-spacing: -.04em; }
.about-section-heading.compact h2 { font-size: clamp(27px, 3vw, 40px); }
.about-capability-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }
.about-capability-card {
  min-height: 245px;
  padding: 24px;
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 20px;
  background: rgba(255,255,255,.025);
}
.about-capability-card > span { color: var(--accent-2); font-size: 10px; font-weight: 800; letter-spacing: .13em; }
.about-capability-card h3 { margin: 52px 0 12px; font-size: 19px; }
.about-capability-card p { margin: 0; color: var(--text-soft); font-size: 13px; line-height: 1.75; }
.about-timeline { border-top: 1px solid rgba(255,255,255,.12); }
.about-timeline-item {
  display: grid;
  grid-template-columns: minmax(210px,.35fr) minmax(0,1fr);
  gap: clamp(30px, 7vw, 110px);
  padding: 42px 0;
  border-bottom: 1px solid rgba(255,255,255,.12);
}
.about-timeline-meta { display: flex; flex-direction: column; gap: 9px; }
.about-timeline-meta span { color: var(--accent-2); font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.about-timeline-meta strong { color: #fff; font-size: 18px; }
.about-product { margin: 0 0 6px; color: var(--text-soft); font-size: 12px; }
.about-timeline-content h3 { margin: 0 0 14px; font-size: clamp(22px,2.5vw,32px); }
.about-timeline-content > p:last-of-type { margin: 0; color: #c0cada; line-height: 1.8; }
.about-timeline-content ul { display: grid; gap: 9px; margin: 22px 0 0; padding-left: 18px; color: var(--text-soft); font-size: 13px; line-height: 1.7; }
.about-bottom-grid { display: grid; grid-template-columns: .9fr 1.1fr; gap: clamp(46px, 9vw, 130px); }
.about-education-list { display: grid; gap: 14px; }
.about-education-section .about-education-list { grid-template-columns: repeat(2, minmax(0,1fr)); }
.about-education-card { padding: 24px; border: 1px solid rgba(255,255,255,.12); border-radius: 18px; background: rgba(255,255,255,.025); }
.about-education-card span { color: var(--accent-2); font-size: 10px; }
.about-education-card h3 { margin: 20px 0 7px; font-size: 20px; }
.about-education-card p { margin: 0; color: var(--text-soft); font-size: 13px; line-height: 1.6; }
.about-tool-group + .about-tool-group { margin-top: 30px; }
.about-toolkit-layout { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: clamp(34px, 7vw, 90px); }
.about-toolkit-layout .about-tool-group + .about-tool-group { margin-top: 0; }
.about-tool-group h3 { margin: 0 0 13px; font-size: 14px; }
.about-tool-cloud { display: flex; flex-wrap: wrap; gap: 8px; }
.about-tool-cloud.accent span { border-color: rgba(45,212,191,.28); color: #c9fff5; background: rgba(45,212,191,.06); }
.about-language { margin: 32px 0 0; color: var(--text-soft); font-size: 12px; }
.about-footer { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 50px 4px 10px; }
.about-footer p { margin: 0; color: #d7deeb; font-size: 16px; }
.about-footer .hero-cta {
  border: 1px solid rgba(255,255,255,.18);
  background: transparent;
  cursor: pointer;
}

@media (max-width: 980px) {
  .about-capability-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .about-bottom-grid { grid-template-columns: 1fr; }
  .about-education-section .about-education-list,
  .about-toolkit-layout { grid-template-columns: 1fr; }
}
 
@media (max-width: 620px) {
  .pixel-cluster { right: 10px; bottom: 28px; transform: scale(.75); transform-origin: right bottom; }
  .pixel-avatar { right: 4px; bottom: 22px; transform: scale(.72); transform-origin: right bottom; animation: none; }
  .category-switcher { grid-template-columns: 1fr; gap: 8px; margin-top: 24px; }
  .category-tab { min-height: 60px; padding: 13px 16px; }
  .portfolio-nav-actions { gap: 10px; }
  .portfolio-nav-meta { display: none; }
  .about-page .portfolio-nav-link.is-active { display: none; }
  .portfolio-project-button { padding: 8px 11px; }
  .about-hero { grid-template-columns: 1fr; min-height: 0; padding: 58px 2px; }
  .about-hero h1 { font-size: clamp(38px, 11vw, 50px); }
  .about-identity-card { min-height: 300px; }
  .about-capability-grid { grid-template-columns: 1fr; }
  .about-capability-card { min-height: 0; }
  .about-capability-card h3 { margin-top: 28px; }
  .about-timeline-item { grid-template-columns: 1fr; gap: 24px; }
  .about-bottom-grid { grid-template-columns: 1fr; }
  .about-footer { align-items: flex-start; flex-direction: column; }
}
"""


JS_TEMPLATE = """const state = {
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
    const nextIsIndex = /^\\d+$/.test(nextPart || "");
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
          <h1>${escapeHtml(about.headline || "把设计思考推进到可运行的游戏界面。")}</h1>
          <p>${escapeHtml(about.intro || "")}</p>
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
  const res = await fetch("./site-data.json", { cache: "no-store" });
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
        const projMatch = /^projects\\.(\\d+)\\b/.exec(parentPath || "");
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
    alert(`保存部分成功 — ${summary.join(", ") || "无变更"} 已写入。失败项:\\n${errors.join("\\n")}`);
  } else if (summary.length) {
    alert(`✓ ${summary.join(" + ")} 已写回源文件, 站点已重建。\\n现在可在 Fork 里 commit + push。`);
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
  if (!confirm(`确认删除界面"${relativePath}"？\\n只从项目配置中移除, 源文件保留在磁盘上。`)) return;
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
    const response = await fetch("./site-data.json", { cache: "no-store" });
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
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a multi-project hub or a single-project detail site."
    )
    parser.add_argument("--input-dir", required=True, help="Folder containing one project or a projects index.")
    parser.add_argument("--title", help="Optional site title override.")
    parser.add_argument("--subtitle", default="", help="Optional site subtitle override.")
    parser.add_argument("--description", default="", help="Optional site description override.")
    parser.add_argument("--manifest", help="Optional manifest path. For multi-project mode, this should point to projects.index.json.")
    parser.add_argument("--output-dir", help="Optional output directory.")
    parser.add_argument("--serve", action="store_true", help="Start a local preview server.")
    parser.add_argument("--manage", action="store_true", help="Start a management server with project add/remove API.")
    parser.add_argument("--port", type=int, default=8123, help="Preview server port.")
    parser.add_argument("--open-browser", action="store_true", help="Open the preview URL in the system browser.")
    parser.add_argument(
        "--enable-prototype",
        action="store_true",
        help="Enable the interactive prototype module, including prototype scenes, steps, and hotspots.",
    )
    parser.add_argument(
        "--mode",
        default="auto",
        choices=("auto", "portfolio", "demo", "hybrid"),
        help="Legacy compatibility flag. The new layout always renders project overview plus project detail sections.",
    )
    return parser.parse_args()


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {path} ({exc})") from exc


def slugify(value: str) -> str:
    normalized = re.sub(r"[^\w\s-]", "", value).strip().lower()
    normalized = re.sub(r"[-\s]+", "-", normalized)
    return normalized or "project"


def normalize_text(value: str) -> str:
    return re.sub(r"[_-]+", " ", value).strip()


def title_from_stem(stem: str) -> str:
    cleaned = re.sub(r"^[\W_]*\d+[\W_]*", "", stem).strip()
    return normalize_text(cleaned or stem) or stem


def is_hidden_or_ignored(path: Path) -> bool:
    return any(part.startswith(".") or part in IGNORE_DIR_NAMES for part in path.parts)


def discover_images(input_dir: Path) -> list[Path]:
    images: list[Path] = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        rel = path.relative_to(input_dir)
        if is_hidden_or_ignored(rel):
            continue
        images.append(path)
    return sorted(images, key=lambda item: str(item.relative_to(input_dir)).lower())


def locate_site_manifest(project_dir: Path) -> Path | None:
    for name in ("site.meta.json", "portfolio.meta.json"):
        candidate = project_dir / name
        if candidate.exists():
            return candidate
    return None


def locate_index_manifest(input_dir: Path, manifest_arg: str | None) -> Path | None:
    if manifest_arg:
        return Path(manifest_arg).expanduser().resolve()
    candidate = input_dir / "projects.index.json"
    if candidate.exists():
        return candidate
    return None


def resolve_output_dir(input_dir: Path, output_dir_arg: str | None) -> Path:
    if output_dir_arg:
        return Path(output_dir_arg).expanduser().resolve()
    return (input_dir / "_portfolio_site" / input_dir.name).resolve()


def prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    for file_name in ("index.html", "styles.css", "app.js", "site-data.json"):
        file_path = output_dir / file_name
        if file_path.exists():
            file_path.unlink()


def copy_asset(
    source_path: Path,
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
) -> str:
    cache_key = str(source_path.resolve())
    if cache_key in cache:
        return cache[cache_key]

    try:
        rel = source_path.relative_to(project_dir)
    except ValueError:
        rel = Path(source_path.name)
    target = output_dir / "assets" / asset_prefix / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    public_path = target.relative_to(output_dir).as_posix()
    cache[cache_key] = public_path
    return public_path


def make_thumb_asset(
    source_path: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
    max_width: int = 760,
    quality: int = 82,
) -> str | None:
    """Generate a downscaled JPEG thumbnail next to the full asset and return
    its public path. Used for home-page card covers so the grid doesn't pull
    full 1920px+ images for a ~300px thumbnail. Falls back to None (caller
    then uses the full src) if Pillow is unavailable or the image can't be
    opened."""
    cache_key = "thumb::" + str(source_path.resolve())
    if cache_key in cache:
        return cache[cache_key]
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
    except Exception:
        return None
    try:
        with Image.open(source_path) as im:
            if im.width <= max_width:
                # Already small enough — no separate thumb needed
                return None
            ratio = max_width / im.width
            new_size = (max_width, max(1, round(im.height * ratio)))
            if im.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", im.size, (11, 16, 32))
                im_rgb = im.convert("RGBA")
                bg.paste(im_rgb, mask=im_rgb.split()[3] if im_rgb.mode == "RGBA" else None)
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")
            thumb = im.resize(new_size, Image.LANCZOS)
            stem = source_path.stem
            target = output_dir / "assets" / asset_prefix / f"{stem}-thumb.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            thumb.save(target, "JPEG", quality=quality, optimize=True, progressive=True)
            public_path = target.relative_to(output_dir).as_posix()
            cache[cache_key] = public_path
            return public_path
    except Exception:
        return None


def resolve_source_path(project_dir: Path, file_value: str) -> tuple[Path, str]:
    candidate = Path(file_value)
    source_path = (
        candidate.expanduser().resolve()
        if candidate.is_absolute()
        else (project_dir / candidate).resolve()
    )
    if not source_path.exists():
        raise SystemExit(f"Referenced file not found: {file_value}")
    try:
        relative_path = source_path.relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        relative_path = source_path.name
    return source_path, relative_path


def listify(values: Any) -> list[Any]:
    return values if isinstance(values, list) else []


def merge_labels(*label_sets: Any) -> dict[str, str]:
    merged = dict(DEFAULT_LABELS)
    for label_set in label_sets:
        if isinstance(label_set, dict):
            for key, value in label_set.items():
                if value is not None:
                    merged[str(key)] = str(value)
    return merged


def build_item(
    entry: dict[str, Any],
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
) -> dict[str, Any]:
    source_path, relative_path = resolve_source_path(project_dir, entry["file"])
    return {
        "id": entry.get("id") or Path(relative_path).stem,
        "relative_path": relative_path,
        "title": entry.get("title") or title_from_stem(source_path.stem),
        "caption": entry.get("caption", ""),
        "section": entry.get("section", ""),
        "tags": listify(entry.get("tags")),
        "summary": entry.get("summary", ""),
        "notes": listify(entry.get("notes")),
        "states": listify(entry.get("states")),
        "doc_refs": listify(entry.get("doc_refs")),
        "hover_title": entry.get("hover_title", ""),
        "hover_description": entry.get("hover_description", ""),
        "parent": entry.get("parent") or None,
        "src": copy_asset(source_path, project_dir, output_dir, asset_prefix, cache),
    }


def build_media_asset(
    file_value: str | None,
    title: str,
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
    make_thumb: bool = False,
) -> dict[str, Any] | None:
    if not file_value:
        return None
    source_path, relative_path = resolve_source_path(project_dir, file_value)
    asset: dict[str, Any] = {
        "id": Path(relative_path).stem,
        "relative_path": relative_path,
        "title": title,
        "src": copy_asset(source_path, project_dir, output_dir, asset_prefix, cache),
    }
    if make_thumb:
        thumb = make_thumb_asset(source_path, output_dir, asset_prefix, cache)
        if thumb:
            asset["thumb"] = thumb
    return asset


_VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}


def build_showcase_item(
    entry: dict[str, Any],
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
) -> dict[str, Any] | None:
    """Build a single 作品展示 item. Same image-handling as build_item but
    intentionally minimal metadata — these are "show the artwork, say a
    sentence" entries, not state-tagged UI screenshots."""
    if not isinstance(entry, dict) or not entry.get("file"):
        return None
    try:
        source_path, relative_path = resolve_source_path(project_dir, entry["file"])
    except SystemExit:
        return None
    if source_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    return {
        "id": entry.get("id") or Path(relative_path).stem,
        "relative_path": relative_path,
        "title": entry.get("title") or "",
        "description": entry.get("description", ""),
        "src": copy_asset(source_path, project_dir, output_dir, asset_prefix, cache),
    }


def build_pdf_item(
    entry: dict[str, Any] | str,
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
) -> dict[str, Any] | None:
    """Build a single PDF entry. `entry` can be a plain string (filename)
    or an object {file, title, description, page_count?}."""
    if isinstance(entry, str):
        entry = {"file": entry}
    if not isinstance(entry, dict):
        return None
    file_value = entry.get("file")
    if not file_value:
        return None
    try:
        source_path, relative_path = resolve_source_path(project_dir, file_value)
    except SystemExit:
        return None
    if source_path.suffix.lower() not in DOCUMENT_EXTENSIONS:
        return None
    size_bytes = source_path.stat().st_size
    return {
        "id": entry.get("id") or Path(relative_path).stem,
        "relative_path": relative_path,
        "title": entry.get("title") or title_from_stem(source_path.stem),
        "description": entry.get("description", ""),
        "page_count": entry.get("page_count") or None,
        "size_bytes": size_bytes,
        "size_label": _format_size(size_bytes),
        "src": copy_asset(source_path, project_dir, output_dir, asset_prefix, cache),
    }


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def build_video_item(
    entry: dict[str, Any],
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
) -> dict[str, Any] | None:
    """Build a single video entry. `entry` shape:
       { "file": "videos/x.mp4", "title": "...", "caption": "...", "poster": "..." }
    """
    file_value = entry.get("file") if isinstance(entry, dict) else None
    if not file_value:
        return None
    try:
        source_path, relative_path = resolve_source_path(project_dir, file_value)
    except SystemExit:
        return None
    if source_path.suffix.lower() not in VIDEO_EXTENSIONS:
        return None
    poster_value = entry.get("poster")
    poster_data: dict[str, Any] | None = None
    if poster_value:
        try:
            p_src, p_rel = resolve_source_path(project_dir, poster_value)
            poster_data = {
                "relative_path": p_rel,
                "src": copy_asset(p_src, project_dir, output_dir, asset_prefix, cache),
            }
        except SystemExit:
            poster_data = None
    return {
        "id": entry.get("id") or Path(relative_path).stem,
        "relative_path": relative_path,
        "title": entry.get("title") or title_from_stem(source_path.stem),
        "caption": entry.get("caption", ""),
        "section": entry.get("section", ""),
        "duration": entry.get("duration", ""),
        "mime": _VIDEO_MIME.get(source_path.suffix.lower(), "video/mp4"),
        "poster": poster_data,
        "src": copy_asset(source_path, project_dir, output_dir, asset_prefix, cache),
    }


def build_proto_hotspots(hotspots: Any) -> list[dict[str, Any]]:
    if not isinstance(hotspots, list):
        return []
    results: list[dict[str, Any]] = []
    for index, hotspot in enumerate(hotspots):
        if not isinstance(hotspot, dict):
            continue
        results.append(
            {
                "id": hotspot.get("id") or f"hotspot-{index + 1}",
                "x": float(hotspot.get("x", 0)),
                "y": float(hotspot.get("y", 0)),
                "title": hotspot.get("title") or hotspot.get("label", ""),
                "label": hotspot.get("label", ""),
                "content": hotspot.get("content") or hotspot.get("description", ""),
            }
        )
    return results


def build_prototype_scene(
    entry: dict[str, Any],
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
) -> dict[str, Any]:
    source_path, relative_path = resolve_source_path(project_dir, entry["file"])
    return {
        "id": entry.get("id") or Path(relative_path).stem,
        "relative_path": relative_path,
        "title": entry.get("title") or title_from_stem(source_path.stem),
        "caption": entry.get("caption", ""),
        "summary": entry.get("summary", ""),
        "steps": listify(entry.get("steps")),
        "hotspots": build_proto_hotspots(entry.get("hotspots")),
        "src": copy_asset(source_path, project_dir, output_dir, asset_prefix, cache),
    }


def detect_cover_entry(
    cover_value: str | None,
    screens: list[dict[str, Any]],
    interaction_doc: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if cover_value:
        normalized = str(cover_value).replace("\\", "/")
        for item in screens:
            if item["relative_path"] == normalized:
                return item
        if interaction_doc and interaction_doc["relative_path"] == normalized:
            return interaction_doc
    return screens[0] if screens else interaction_doc


_DOC_STEM_KEYWORDS = (
    "交互", "总览", "流程", "文档",
    "doc", "document", "flow", "board", "mockup", "overview", "wireframe",
)


def _auto_detect_interaction_doc_from_screens(screens: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first screen whose filename contains interaction-doc keywords."""
    for item in screens:
        stem = Path(item["relative_path"]).stem.lower()
        if any(k in stem for k in _DOC_STEM_KEYWORDS):
            return item
    return None


def detect_interaction_doc(
    meta: dict[str, Any],
    project_dir: Path,
    output_dir: Path,
    asset_prefix: str,
    cache: dict[str, str],
) -> dict[str, Any] | None:
    value = meta.get("interaction_doc")
    if isinstance(value, dict) and value.get("file"):
        item = build_item(value, project_dir, output_dir, asset_prefix, cache)
        source_path, _ = resolve_source_path(project_dir, value["file"])
        preview = make_thumb_asset(
            source_path, output_dir, asset_prefix, cache, max_width=2400, quality=86
        )
        if preview:
            item["preview"] = preview
        return item
    if isinstance(value, str):
        item = build_item({"file": value, "title": "交互文档"}, project_dir, output_dir, asset_prefix, cache)
        source_path, _ = resolve_source_path(project_dir, value)
        preview = make_thumb_asset(
            source_path, output_dir, asset_prefix, cache, max_width=2400, quality=86
        )
        if preview:
            item["preview"] = preview
        return item
    return None


def _build_flow(
    flow_meta: Any,
    screens: list[dict[str, Any]],
    interaction_doc: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Parse the `flow` block from site.meta.json into a clean data structure."""
    if not isinstance(flow_meta, dict):
        return None
    nodes_raw = flow_meta.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        return None

    all_items = {s["id"]: s for s in screens}
    if interaction_doc:
        all_items[interaction_doc["id"]] = interaction_doc

    nodes = []
    for node in nodes_raw:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        nodes.append({
            "id": str(node["id"]),
            "label": str(node.get("label", node["id"])),
            "screen_id": str(node["screen_id"]) if node.get("screen_id") else None,
            "col": int(node.get("col", 0)),
            "row": int(node.get("row", 0)),
        })

    edges = []
    for edge in flow_meta.get("edges", []):
        if not isinstance(edge, dict) or not edge.get("from") or not edge.get("to"):
            continue
        edges.append({
            "from": str(edge["from"]),
            "to": str(edge["to"]),
            "label": str(edge.get("label", "")),
            "type": str(edge.get("type", "forward")),
        })

    return {
        "title": str(flow_meta.get("title", "交互流程图")),
        "description": str(flow_meta.get("description", "")),
        "nodes": nodes,
        "edges": edges,
    }


def _auto_build_prototype_from_flow(
    flow: dict[str, Any],
    screens: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Derive prototype scenes + nav-hotspots automatically from flow data."""
    nodes = flow.get("nodes", [])
    edges = flow.get("edges", [])
    if not nodes or not edges:
        return None

    screen_map = {s["id"]: s for s in screens}

    # collect only nodes that have a matching screen image
    valid_nodes = [n for n in nodes if n.get("screen_id") and n["screen_id"] in screen_map]
    if not valid_nodes:
        return None

    # node_id → future scene list index
    node_id_to_idx: dict[str, int] = {n["id"]: i for i, n in enumerate(valid_nodes)}

    # outgoing edges per node
    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        outgoing.setdefault(edge["from"], []).append(edge)

    scenes: list[dict[str, Any]] = []
    for node in valid_nodes:
        screen = screen_map[node["screen_id"]]
        edges_out = outgoing.get(node["id"], [])
        n = len(edges_out)

        hotspots: list[dict[str, Any]] = []
        for i, edge in enumerate(edges_out):
            tgt_idx = node_id_to_idx.get(edge["to"])
            if tgt_idx is None:
                continue
            # Distribute hotspots evenly along the bottom 20% of the screen
            if n == 1:
                x = 50.0
            else:
                margin = max(15.0, 40.0 - n * 3)
                x = round(margin + i * (100.0 - 2 * margin) / (n - 1), 1)
            hotspots.append({
                "id": f"hs-{node['id']}-{edge['to']}",
                "x": x,
                "y": 84.0,
                "title": edge.get("label") or f"→ {edge['to']}",
                "label": edge.get("label", ""),
                "content": "",
                "goto_scene_index": tgt_idx,
            })

        label = node.get("label", "").replace("\n", " ")
        scenes.append({
            **screen,
            "id": node["id"],
            "title": label or screen["title"],
            "summary": "",
            "steps": [],
            "hotspots": hotspots,
        })

    return {
        "intro": "点击画面中的热区按钮，可切换到对应交互场景。",
        "scenes": scenes,
        "auto_generated": True,
    }


def build_project(
    project_dir: Path,
    output_dir: Path,
    prototype_enabled: bool,
    index_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = read_json(locate_site_manifest(project_dir))
    project_id = (
        str((index_entry or {}).get("id", "")).strip()
        or str(manifest.get("id", "")).strip()
        or slugify(project_dir.name)
    )
    asset_prefix = project_id
    cache: dict[str, str] = {}

    items_meta = manifest.get("items")
    if isinstance(items_meta, list) and items_meta:
        screens = [build_item(entry, project_dir, output_dir, asset_prefix, cache) for entry in items_meta if isinstance(entry, dict) and entry.get("file")]
    else:
        screens = []
        for source_path in discover_images(project_dir):
            rel = source_path.relative_to(project_dir).as_posix()
            screens.append(
                {
                    "id": Path(rel).stem,
                    "relative_path": rel,
                    "title": title_from_stem(source_path.stem),
                    "caption": "",
                    "section": "",
                    "tags": [],
                    "summary": "",
                    "notes": [],
                    "states": [],
                    "doc_refs": [],
                    "hover_title": "",
                    "hover_description": "",
                    "src": copy_asset(source_path, project_dir, output_dir, asset_prefix, cache),
                }
            )

    interaction_doc = detect_interaction_doc(manifest, project_dir, output_dir, asset_prefix, cache)
    if interaction_doc:
        screens = [item for item in screens if item["relative_path"] != interaction_doc["relative_path"]]
    elif not manifest.get("interaction_doc"):
        # Auto-detect from filename when no explicit interaction_doc is configured
        interaction_doc = _auto_detect_interaction_doc_from_screens(screens)
        if interaction_doc:
            screens = [item for item in screens if item["relative_path"] != interaction_doc["relative_path"]]

    explicit_detail_cover = (
        (index_entry or {}).get("detail_cover")
        or manifest.get("detail_cover")
        or manifest.get("cover")
        or manifest.get("hero")
    )
    # First, see if the explicit cover value matches a screen / interaction_doc
    cover = detect_cover_entry(explicit_detail_cover, screens, interaction_doc)
    # If it doesn't match (e.g. user set `cover: "cover.png"` for a standalone
    # cover image that isn't in items[]), fall back to building a fresh media
    # asset so any file inside the project folder can be used as the detail
    # cover — same flexibility card_cover already has.
    cover_matched_item = (
        explicit_detail_cover
        and cover
        and str(cover.get("relative_path") or "").replace("\\", "/")
            == str(explicit_detail_cover).replace("\\", "/")
    )
    if explicit_detail_cover and not cover_matched_item:
        standalone_cover = build_media_asset(
            explicit_detail_cover,
            f"{title_from_stem(project_dir.name)} cover",
            project_dir,
            output_dir,
            asset_prefix,
            cache,
        )
        if standalone_cover:
            cover = standalone_cover
    card_cover = build_media_asset(
        (index_entry or {}).get("card_cover") or manifest.get("card_cover"),
        f"{title_from_stem(project_dir.name)} card cover",
        project_dir,
        output_dir,
        asset_prefix,
        cache,
        make_thumb=True,
    ) or cover
    prototype_meta = manifest.get("prototype")
    if not isinstance(prototype_meta, dict):
        prototype_meta = manifest.get("demo") if isinstance(manifest.get("demo"), dict) else {}

    scenes_meta = prototype_meta.get("scenes", [])
    proto_scenes = [
        build_prototype_scene(entry, project_dir, output_dir, asset_prefix, cache)
        for entry in scenes_meta
        if isinstance(entry, dict) and entry.get("file")
    ]

    # Auto-generate prototype from flow when no explicit scenes are configured
    proto_intro = prototype_meta.get("intro", "")
    auto_proto_generated = False
    flow_data = _build_flow(manifest.get("flow"), screens, interaction_doc)
    if not proto_scenes and flow_data:
        auto_proto = _auto_build_prototype_from_flow(flow_data, screens)
        if auto_proto:
            proto_scenes = auto_proto["scenes"]
            proto_intro = auto_proto["intro"]
            auto_proto_generated = True

    # Auto-enable prototype when scenes were successfully derived from flow
    effective_prototype_enabled = prototype_enabled or (auto_proto_generated and bool(proto_scenes))

    tags = listify((index_entry or {}).get("tags")) or listify(manifest.get("tags"))
    title = (index_entry or {}).get("title") or manifest.get("title") or project_dir.name
    subtitle = (index_entry or {}).get("subtitle") or manifest.get("subtitle", "")
    summary = (index_entry or {}).get("summary") or manifest.get("description") or manifest.get("summary", "")
    labels = merge_labels(manifest.get("labels"), (index_entry or {}).get("labels"))

    # Build videos[] (new module replacing prototype)
    videos_meta = manifest.get("videos")
    videos: list[dict[str, Any]] = []
    if isinstance(videos_meta, list):
        for v_entry in videos_meta:
            built = build_video_item(v_entry, project_dir, output_dir, asset_prefix, cache)
            if built:
                videos.append(built)

    # Build pdfs[] — supports either a single `pdf` field (most common)
    # or a `pdfs` array for projects that include multiple downloadable docs
    pdfs: list[dict[str, Any]] = []
    single_pdf_meta = manifest.get("pdf")
    if single_pdf_meta:
        built = build_pdf_item(single_pdf_meta, project_dir, output_dir, asset_prefix, cache)
        if built:
            pdfs.append(built)
    pdfs_meta = manifest.get("pdfs")
    if isinstance(pdfs_meta, list):
        for entry in pdfs_meta:
            built = build_pdf_item(entry, project_dir, output_dir, asset_prefix, cache)
            if built:
                pdfs.append(built)

    # Build showcase[] — extra "作品展示" gallery for projects whose primary
    # deliverable is an artwork series rather than UI screens
    showcase: list[dict[str, Any]] = []
    showcase_meta = manifest.get("showcase")
    if isinstance(showcase_meta, list):
        for entry in showcase_meta:
            built = build_showcase_item(entry, project_dir, output_dir, asset_prefix, cache)
            if built:
                showcase.append(built)

    contribution = manifest.get("contribution") if isinstance(manifest.get("contribution"), dict) else None

    # Pass per-project display config (hide_sections / screens_layout etc.)
    # straight through to site-data.json so the client can read it
    display_meta = manifest.get("display") if isinstance(manifest.get("display"), dict) else {}

    category = (
        str((index_entry or {}).get("category") or "").strip()
        or str(manifest.get("category") or "").strip()
        or None
    )

    return {
        "id": project_id,
        "category": category,
        "title": title,
        "subtitle": subtitle,
        "summary": summary,
        "tags": tags,
        "labels": labels,
        "contribution": contribution,
        "cover": cover,
        "card_cover": card_cover,
        "interaction_doc": interaction_doc,
        "screens": screens,
        "videos": videos,
        "pdfs": pdfs,
        "showcase": showcase,
        "display": display_meta,
        "flow": flow_data,
        "prototype": {
            "enabled": effective_prototype_enabled,
            "intro": proto_intro,
            "scenes": proto_scenes,
        },
    }


def build_site_data(args: argparse.Namespace, input_dir: Path, output_dir: Path) -> dict[str, Any]:
    index_manifest_path = locate_index_manifest(input_dir, args.manifest)
    index_manifest = read_json(index_manifest_path)

    site_asset_cache: dict[str, str] = {}
    if index_manifest.get("projects"):
        projects: list[dict[str, Any]] = []
        for entry in index_manifest["projects"]:
            if not isinstance(entry, dict) or not entry.get("path"):
                continue
            project_dir = (input_dir / entry["path"]).resolve()
            if not project_dir.exists():
                raise SystemExit(f"Project path not found: {entry['path']}")
            projects.append(
                build_project(project_dir, output_dir, args.enable_prototype, entry)
            )
        if not projects:
            raise SystemExit("No valid projects found in projects.index.json")

        site_hero_image = build_media_asset(
            index_manifest.get("hero_image"),
            "site hero image",
            input_dir,
            output_dir,
            "__site",
            site_asset_cache,
        )
        all_tags: list[str] = []
        for p in projects:
            for t in (p.get("tags") or []):
                if t and t not in all_tags:
                    all_tags.append(t)
        # Categories are optional. Pass through as-is; if absent, frontend
        # renders all projects in a single ungrouped grid.
        categories_meta = index_manifest.get("categories")
        categories_clean: list[dict[str, Any]] = []
        if isinstance(categories_meta, list):
            for c in categories_meta:
                if isinstance(c, dict) and c.get("id"):
                    categories_clean.append({
                        "id": str(c["id"]),
                        "label": str(c.get("label") or c["id"]),
                        "description": str(c.get("description") or ""),
                    })
        return {
            "site": {
                "title": args.title or index_manifest.get("title") or input_dir.name,
                "subtitle": args.subtitle or index_manifest.get("subtitle", ""),
                "description": args.description or index_manifest.get("description", ""),
                "owner": index_manifest.get("owner", ""),
                "role": index_manifest.get("role", ""),
                "bio": index_manifest.get("bio", ""),
                "about": index_manifest.get("about") if isinstance(index_manifest.get("about"), dict) else None,
                "all_tags": index_manifest.get("all_tags") or all_tags,
                "prototype_enabled": args.enable_prototype,
                "labels": merge_labels(index_manifest.get("labels")),
                "hero_image": site_hero_image,
                "categories": categories_clean,
                "analytics": index_manifest.get("analytics") if isinstance(index_manifest.get("analytics"), dict) else None,
                "theme": {
                    "accent": index_manifest.get("theme", {}).get("accent", "#7c5cff"),
                    "background": index_manifest.get("theme", {}).get("background", "#0b1020"),
                },
            },
            "projects": projects,
        }

    project = build_project(input_dir, output_dir, args.enable_prototype)
    site_title = args.title or project["title"] or input_dir.name
    single_manifest = read_json(locate_site_manifest(input_dir))
    site_hero_image = build_media_asset(
        single_manifest.get("hero_image"),
        "site hero image",
        input_dir,
        output_dir,
        "__site",
        site_asset_cache,
    )
    all_tags: list[str] = []
    for t in (project.get("tags") or []):
        if t and t not in all_tags:
            all_tags.append(t)
    return {
        "site": {
            "title": site_title,
            "subtitle": args.subtitle or single_manifest.get("subtitle", ""),
            "description": args.description or single_manifest.get("description", ""),
            "owner": single_manifest.get("owner", ""),
            "role": single_manifest.get("role", ""),
            "bio": single_manifest.get("bio", ""),
            "about": single_manifest.get("about") if isinstance(single_manifest.get("about"), dict) else None,
            "all_tags": single_manifest.get("all_tags") or all_tags,
            "prototype_enabled": args.enable_prototype,
            "labels": merge_labels(single_manifest.get("labels")),
            "hero_image": site_hero_image,
            "theme": {
                "accent": single_manifest.get("theme", {}).get("accent", "#7c5cff"),
                "background": single_manifest.get("theme", {}).get("background", "#0b1020"),
            },
        },
        "projects": [project],
    }


def _build_analytics_snippet(analytics_cfg: dict[str, Any] | None) -> str:
    """Translate an `analytics` config block into HTML <script> tags.

    Supported providers (all optional; missing config -> empty snippet):
      - cloudflare: { "cloudflare": { "token": "<beacon-token>" } }
      - google_analytics: { "google_analytics": { "id": "G-XXXXXX" } }
      - goatcounter: { "goatcounter": { "code": "<your-code>" } }
      - custom_html: a raw HTML string spliced verbatim (escape hatch)
    """
    if not isinstance(analytics_cfg, dict):
        return ""
    parts: list[str] = []

    cf = analytics_cfg.get("cloudflare")
    if isinstance(cf, dict) and cf.get("token"):
        token = str(cf["token"]).replace('"', "")
        parts.append(
            "  <!-- Cloudflare Web Analytics -->\n"
            f"  <script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
            f"data-cf-beacon='{{\"token\": \"{token}\"}}'></script>\n"
            "  <!-- End Cloudflare Web Analytics -->"
        )

    ga = analytics_cfg.get("google_analytics")
    if isinstance(ga, dict) and ga.get("id"):
        ga_id = str(ga["id"]).strip()
        parts.append(
            "  <!-- Google Analytics 4 -->\n"
            f"  <script async src=\"https://www.googletagmanager.com/gtag/js?id={ga_id}\"></script>\n"
            "  <script>window.dataLayer = window.dataLayer || [];"
            "function gtag(){dataLayer.push(arguments);}gtag('js', new Date());"
            f"gtag('config', '{ga_id}');</script>"
        )

    gc = analytics_cfg.get("goatcounter")
    if isinstance(gc, dict) and gc.get("code"):
        code = str(gc["code"]).strip()
        parts.append(
            "  <!-- GoatCounter -->\n"
            f"  <script data-goatcounter=\"https://{code}.goatcounter.com/count\" "
            "async src=\"//gc.zgo.at/count.js\"></script>"
        )

    custom = analytics_cfg.get("custom_html")
    if isinstance(custom, str) and custom.strip():
        parts.append("  " + custom.strip())

    return "\n".join(parts)


def write_site_files(output_dir: Path, data: dict[str, Any]) -> None:
    analytics_snippet = _build_analytics_snippet(data.get("site", {}).get("analytics"))
    # Cache-bust app.js / styles.css / site-data.json with a short content hash
    # so a fresh HTML pull always pulls fresh assets. GitHub Pages serves these
    # with Cache-Control: max-age=600 (Fastly), and without a versioned URL the
    # user has to hard-refresh after every deploy. The hash changes with content,
    # so unchanged builds keep the same URL (browser cache stays warm).
    css_hash = hashlib.sha1(CSS_TEMPLATE.encode("utf-8")).hexdigest()[:8]
    js_hash = hashlib.sha1(JS_TEMPLATE.encode("utf-8")).hexdigest()[:8]
    data_blob = json.dumps(data, ensure_ascii=False, indent=2)
    data_hash = hashlib.sha1(data_blob.encode("utf-8")).hexdigest()[:8]
    html = (
        HTML_TEMPLATE
        .replace("__ANALYTICS_PLACEHOLDER__", analytics_snippet)
        .replace('href="./styles.css"', f'href="./styles.css?v={css_hash}"')
        .replace('src="./app.js"', f'src="./app.js?v={js_hash}"')
    )
    # Bake the data hash into app.js so its fetch("./site-data.json") is also versioned.
    js = JS_TEMPLATE.replace('fetch("./site-data.json"', f'fetch("./site-data.json?v={data_hash}"')
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / "styles.css").write_text(CSS_TEMPLATE, encoding="utf-8")
    (output_dir / "app.js").write_text(js, encoding="utf-8")
    (output_dir / "site-data.json").write_text(data_blob, encoding="utf-8")


def start_server(output_dir: Path, port: int, open_browser: bool) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(output_dir))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), handler) as server:
        url = f"http://127.0.0.1:{port}"
        print(f"Preview URL: {url}")
        print("Press Ctrl+C to stop the server.")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\\nServer stopped.")


def build_site(args: argparse.Namespace) -> Path:
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input folder not found: {input_dir}")

    output_dir = resolve_output_dir(input_dir, args.output_dir)
    if output_dir == input_dir:
        raise SystemExit("Output directory cannot be the same as the input directory.")

    prepare_output_dir(output_dir)
    data = build_site_data(args, input_dir, output_dir)
    write_site_files(output_dir, data)
    return output_dir


def main() -> int:
    args = parse_args()
    output_dir = build_site(args)
    print(f"Generated site: {output_dir}")
    if getattr(args, "manage", False):
        from manage_server import start_management_server  # noqa: PLC0415
        input_dir = Path(args.input_dir).expanduser().resolve()
        start_management_server(input_dir, output_dir, args, args.port, args.open_browser)
    elif args.serve:
        start_server(output_dir, args.port, args.open_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
