"""Сборка открытки 9:16 и надёжный текст поверх (кириллица)."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bot.config import get_card_output_size

logger = logging.getLogger(__name__)

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    preferred = _FONT_CANDIDATES if bold else (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        *_FONT_CANDIDATES,
    )
    for path in preferred:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    logger.warning("Не найден TTF с кириллицей — используем шрифт по умолчанию Pillow")
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = (text or "").replace("\r", "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def fit_to_portrait_9_16(src: Image.Image, width: int, height: int) -> Image.Image:
    """Вписывает картинку в 9:16 без обрезки (поля + размытый фон)."""
    canvas = Image.new("RGB", (width, height), (28, 24, 36))
    blurred = src.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    blurred = blurred.filter(ImageFilter.GaussianBlur(28))
    canvas.paste(blurred, (0, 0))

    src_ratio = src.width / src.height
    target_ratio = width / height
    if src_ratio > target_ratio:
        new_w = width
        new_h = max(1, int(width / src_ratio))
    else:
        new_h = height
        new_w = max(1, int(height * src_ratio))
    fitted = src.convert("RGB").resize((new_w, new_h), Image.Resampling.LANCZOS)
    offset = ((width - new_w) // 2, (height - new_h) // 2)
    canvas.paste(fitted, offset)
    return canvas


def compose_greeting_card_image(
    background_bytes: bytes,
    name: str,
    wish: str,
) -> bytes:
    width, height = get_card_output_size()
    with Image.open(io.BytesIO(background_bytes)) as raw:
        base = fit_to_portrait_9_16(raw, width, height)

    panel_top = int(height * 0.62)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        (int(width * 0.06), panel_top, int(width * 0.94), int(height * 0.94)),
        radius=36,
        fill=(18, 16, 28, 170),
    )
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    title_font = _load_font(max(42, width // 18), bold=True)
    body_font = _load_font(max(30, width // 26), bold=False)
    max_text_width = int(width * 0.78)
    text_left = int(width * 0.11)
    y = panel_top + int(height * 0.04)

    title_size = int(getattr(title_font, "size", max(42, width // 18)))
    body_size = int(getattr(body_font, "size", max(30, width // 26)))

    name_text = (name or "Дорогой друг").strip()[:60]
    for line in _wrap_text(draw, name_text, title_font, max_text_width):
        draw.text((text_left, y), line, font=title_font, fill=(255, 245, 230))
        y += int(title_size * 1.25)

    y += int(height * 0.015)
    wish_text = (wish or "С теплом и лучшими пожеланиями!").strip()[:280]
    for line in _wrap_text(draw, wish_text, body_font, max_text_width):
        draw.text((text_left, y), line, font=body_font, fill=(240, 236, 255))
        y += int(body_size * 1.35)
        if y > int(height * 0.92):
            break

    out = io.BytesIO()
    base.save(out, format="PNG", optimize=True)
    return out.getvalue()
