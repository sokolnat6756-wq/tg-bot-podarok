"""Сборка цельной открытки 9:16: фон без текста + кириллические надписи."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from bot.config import get_card_output_size

logger = logging.getLogger(__name__)

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_TITLE = _FONTS_DIR / "CormorantGaramond-Bold.ttf"
_FONT_SCRIPT = _FONTS_DIR / "MarckScript-Regular.ttf"
_FONT_BODY = _FONTS_DIR / "Manrope-Medium.ttf"

_FALLBACK_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _load_font(path: Path, size: int, weight: int | None = None) -> ImageFont.ImageFont:
    candidates = [path, *[Path(p) for p in _FALLBACK_FONTS]]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            font = ImageFont.truetype(str(candidate), size=size)
            if weight is not None and hasattr(font, "set_variation_by_axes"):
                try:
                    font.set_variation_by_axes([weight])
                except Exception:
                    pass
            return font
        except OSError:
            continue
    logger.warning("Шрифт %s недоступен — fallback Pillow default", path.name)
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
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


def _fit_font_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    path: Path,
    max_width: int,
    start_size: int,
    min_size: int,
    weight: int | None = None,
    max_lines: int = 4,
) -> tuple[ImageFont.ImageFont, list[str], int]:
    size = start_size
    while size >= min_size:
        font = _load_font(path, size, weight=weight)
        lines = _wrap_text(draw, text, font, max_width)
        widest = max((draw.textlength(line, font=font) for line in lines), default=0)
        if widest <= max_width and len(lines) <= max_lines:
            return font, lines, size
        size -= 2
    font = _load_font(path, min_size, weight=weight)
    return font, _wrap_text(draw, text, font, max_width), min_size


def cover_to_portrait_9_16(src: Image.Image, width: int, height: int) -> Image.Image:
    """Заполняет холст 9:16 без полос и без искажения (cover + center crop)."""
    src = src.convert("RGB")
    src_ratio = src.width / src.height
    target_ratio = width / height
    if src_ratio > target_ratio:
        new_h = height
        new_w = max(1, int(height * src_ratio))
    else:
        new_w = width
        new_h = max(1, int(width / src_ratio))
    scaled = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return scaled.crop((left, top, left + width, top + height))


def _soft_vignette(base: Image.Image) -> Image.Image:
    """Мягкие градиенты сверху и снизу для читаемости (без непрозрачной плашки)."""
    width, height = base.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = overlay.load()
    top_h = int(height * 0.30)
    bottom_h = int(height * 0.32)
    for y in range(top_h):
        t = 1.0 - (y / max(top_h, 1))
        alpha = int(150 * (t ** 1.4))
        for x in range(width):
            pixels[x, y] = (12, 10, 18, alpha)
    for i in range(bottom_h):
        y = height - 1 - i
        t = 1.0 - (i / max(bottom_h, 1))
        alpha = int(165 * (t ** 1.25))
        for x in range(width):
            pixels[x, y] = (10, 8, 16, alpha)
    return Image.alpha_composite(base.convert("RGBA"), overlay)


def build_headline(
    *,
    name: str,
    occasion_key: str,
    birthday_years: str = "",
) -> str:
    who = (name or "").strip() or "Друг"
    if occasion_key == "birthday":
        return f"{who}, с днём рождения!"
    mapping = {
        "ny": f"{who}, с Новым годом!",
        "valentine": f"{who}, с 14 февраля!",
        "mar8": f"{who}, с 8 Марта!",
        "feb23": f"{who}, с 23 Февраля!",
        "wedding": f"{who}, с праздником любви!",
        "colleague": f"{who}, с праздником!",
        "no_reason": f"{who}, для тебя!",
    }
    return mapping.get(occasion_key, f"{who}, с праздником!")


def build_script_accent(
    *,
    occasion_key: str,
    birthday_years: str = "",
    recipient_key: str = "",
) -> str:
    if occasion_key == "birthday" and birthday_years:
        return f"{birthday_years}!"
    if occasion_key == "birthday":
        return "С праздником!"
    if recipient_key == "child":
        return "Ура!"
    short = {
        "ny": "Волшебства!",
        "valentine": "С любовью",
        "mar8": "Для тебя",
        "feb23": "С уважением",
        "wedding": "На счастье",
    }
    return short.get(occasion_key, "С теплом")


def _sanitize_wish(wish: str, name: str) -> str:
    text = (wish or "Желаю тепла, радости и всего самого светлого.").strip()
    who = (name or "").strip()
    if who and text.lower().startswith(who.lower()):
        text = text[len(who) :].lstrip(" ,!—-:;")
        if text:
            text = text[:1].upper() + text[1:]
    return text[:320]


def _text_color_for_scene(base: Image.Image) -> tuple[int, int, int]:
    sample = base.resize((32, 32), Image.Resampling.BOX)
    pixels = list(sample.getdata())
    avg = sum(sum(p[:3]) for p in pixels) / (len(pixels) * 3)
    if avg > 155:
        return (40, 30, 24)
    return (255, 246, 230)


def compose_greeting_card_image(
    background_bytes: bytes,
    *,
    name: str,
    wish: str,
    occasion_key: str = "no_reason",
    recipient_key: str = "",
    age_key: str = "",
    birthday_years: str = "",
    interest_key: str = "",
    selected_gift: str = "",
) -> bytes:
    del age_key, interest_key, selected_gift  # учтены в промпте фона / пожелании
    width, height = get_card_output_size()
    with Image.open(io.BytesIO(background_bytes)) as raw:
        base = cover_to_portrait_9_16(raw, width, height)

    base = ImageEnhance.Brightness(base).enhance(0.93)
    composed = _soft_vignette(base)
    draw = ImageDraw.Draw(composed, "RGBA")

    color = _text_color_for_scene(base)
    max_text_width = int(width * 0.84)

    headline = build_headline(
        name=name,
        occasion_key=occasion_key,
        birthday_years=birthday_years,
    )
    accent = build_script_accent(
        occasion_key=occasion_key,
        birthday_years=birthday_years,
        recipient_key=recipient_key,
    )
    wish_text = _sanitize_wish(wish, name)

    title_font, title_lines, title_size = _fit_font_to_width(
        draw,
        headline,
        _FONT_TITLE,
        max_text_width,
        start_size=max(56, width // 13),
        min_size=32,
        weight=700,
        max_lines=3,
    )
    script_size = max(46, width // 15)
    if recipient_key == "child":
        script_size = max(52, width // 14)
    script_font = _load_font(_FONT_SCRIPT, script_size)
    body_font, body_lines, body_size = _fit_font_to_width(
        draw,
        wish_text,
        _FONT_BODY,
        max_text_width,
        start_size=max(34, width // 22),
        min_size=22,
        weight=500,
        max_lines=5,
    )

    def _draw_centered_lines(
        lines: list[str],
        font: ImageFont.ImageFont,
        y_start: int,
        line_gap: float,
        fill: tuple[int, int, int],
        size_hint: int,
    ) -> int:
        y = y_start
        for line in lines:
            w = draw.textlength(line, font=font)
            x = int((width - w) / 2)
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 120))
            draw.text((x, y), line, font=font, fill=fill)
            y += int(size_hint * line_gap)
        return y

    y = int(height * 0.055)
    y = _draw_centered_lines(title_lines, title_font, y, 1.12, color, title_size)

    y += int(height * 0.01)
    gold = (255, 224, 170) if color[0] > 200 else (236, 196, 120)
    accent_w = draw.textlength(accent, font=script_font)
    ax = int((width - accent_w) / 2)
    draw.text((ax + 2, y + 2), accent, font=script_font, fill=(0, 0, 0, 100))
    draw.text((ax, y), accent, font=script_font, fill=gold)

    body_block_h = len(body_lines) * int(body_size * 1.35)
    y_body = int(height * 0.76)
    if y_body + body_block_h > height - int(height * 0.045):
        y_body = height - int(height * 0.045) - body_block_h
    _draw_centered_lines(body_lines, body_font, y_body, 1.35, color, body_size)

    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
