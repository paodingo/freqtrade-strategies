"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const PROJECT_DIR = path.resolve(__dirname, "..");
const SCRIPT = path.join(PROJECT_DIR, "scripts", "notify_trades.sh");
const WEIXIN_RENDERER = path.join(PROJECT_DIR, "scripts", "render_weixin_alert_image.py");

test("trade notification script records delivery audit for Telegram and OpenClaw", () => {
  const content = fs.readFileSync(SCRIPT, "utf8");

  assert.match(content, /DELIVERY_LOG=/);
  assert.match(content, /LC_ALL=.*UTF-8/);
  assert.match(content, /LANG=.*UTF-8/);
  assert.match(content, /log_delivery\(\)/);
  assert.match(content, /telegram\s+ok/);
  assert.match(content, /telegram\s+failed/);
  assert.match(content, /openclaw\s+ok/);
  assert.match(content, /openclaw\s+failed/);
  assert.match(content, /openclaw_output=/);
  assert.match(content, /Message ID/);
  assert.match(content, /WEIXIN_IMAGE_RENDERER=/);
  assert.match(content, /is_weixin_channel\(\)/);
  assert.match(content, /mktemp -d/);
  assert.match(content, /--media "\$media_path"/);
  assert.match(content, /Trade alert image/);
});

test("Weixin image renderer uses a CJK-capable font fallback chain", () => {
  const content = fs.readFileSync(WEIXIN_RENDERER, "utf8");

  assert.match(content, /from PIL import Image, ImageDraw, ImageFont/);
  assert.match(content, /NotoSansCJK/);
  assert.match(content, /wqy-microhei/);
  assert.match(content, /textbbox/);
  assert.match(content, /wrap_visual_lines/);
});
