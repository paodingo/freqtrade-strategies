#!/usr/bin/env python3
"""Render a trade alert as a PNG for Weixin delivery."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - exercised on the server path.
    raise SystemExit("Pillow is required: install python3-pil") from exc


FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

BOLD_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
    return right - left


def wrap_visual_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue

        current = ""
        for char in paragraph:
            candidate = current + char
            if current and text_width(draw, candidate, font) > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def choose_accent(message: str) -> tuple[int, int, int]:
    if "+" in message or "盈利" in message or "赚" in message:
        return (28, 126, 68)
    if "-" in message or "亏损" in message or "亏" in message:
        return (188, 51, 46)
    return (37, 99, 235)


def render(message: str, output: Path) -> None:
    title_font = load_font(BOLD_FONT_CANDIDATES, 34)
    body_font = load_font(FONT_CANDIDATES, 28)
    meta_font = load_font(FONT_CANDIDATES, 20)

    width = 960
    padding = 44
    max_text_width = width - padding * 2
    probe = Image.new("RGB", (width, 400), "white")
    draw = ImageDraw.Draw(probe)

    parts = message.split("\n\n", 1)
    title = parts[0].strip() if parts else "交易提醒"
    body = parts[1].strip() if len(parts) > 1 else message.strip()
    body_lines = wrap_visual_lines(draw, body, body_font, max_text_width)

    line_height = 40
    body_height = max(1, len(body_lines)) * line_height
    height = padding * 2 + 54 + 24 + body_height + 32
    image = Image.new("RGB", (width, max(300, height)), (248, 250, 252))
    draw = ImageDraw.Draw(image)

    accent = choose_accent(message)
    draw.rounded_rectangle((20, 20, width - 20, image.height - 20), radius=22, fill=(255, 255, 255))
    draw.rounded_rectangle((20, 20, 34, image.height - 20), radius=7, fill=accent)

    y = padding
    draw.text((padding, y), title, font=title_font, fill=(15, 23, 42))
    y += 58
    draw.line((padding, y, width - padding, y), fill=(226, 232, 240), width=2)
    y += 24

    for line in body_lines:
        draw.text((padding, y), line, font=body_font, fill=(30, 41, 59))
        y += line_height

    footer = "Weixin image fallback"
    draw.text((padding, image.height - padding - 4), footer, font=meta_font, fill=(148, 163, 184))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
        epilog=textwrap.dedent(
            """\
            Example:
              printf '交易 / 运行提醒\\n\\n[V6.5] 已平仓' | render_weixin_alert_image.py --output alert.png
            """
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    message = sys.stdin.read().strip()
    if not message:
        raise SystemExit("message stdin is empty")
    render(message, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
