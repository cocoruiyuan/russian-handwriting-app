from io import BytesIO
from pathlib import Path
import random

import streamlit as st
from PIL import Image, ImageDraw, ImageFont


PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
LEFT_MARGIN = 120
RIGHT_MARGIN = 100
TOP_MARGIN = 130
BOTTOM_MARGIN = 110


def clamp(value: int) -> int:
    return max(0, min(255, value))


def find_font() -> Path | None:
    base_dir = Path(__file__).resolve().parent

    font_files = (
        list(base_dir.rglob("*.ttf"))
        + list(base_dir.rglob("*.otf"))
        + list(base_dir.rglob("*.TTF"))
        + list(base_dir.rglob("*.OTF"))
    )

    return font_files[0] if font_files else None


def load_font(font_size: int) -> ImageFont.FreeTypeFont:
    font_path = find_font()

    if font_path is None:
        raise FileNotFoundError(
            "没有找到字体。请把支持俄语的 .ttf 或 .otf 手写字体放进项目里。"
        )

    return ImageFont.truetype(str(font_path), font_size)


def add_paper_texture(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)

    for _ in range(4500):
        x = random.randint(0, PAGE_WIDTH - 1)
        y = random.randint(0, PAGE_HEIGHT - 1)
        shade = random.randint(-7, 7)

        color = (
            clamp(248 + shade),
            clamp(246 + shade),
            clamp(240 + shade),
        )
        draw.point((x, y), fill=color)

    for _ in range(180):
        x1 = random.randint(0, PAGE_WIDTH - 1)
        y1 = random.randint(0, PAGE_HEIGHT - 1)
        x2 = x1 + random.randint(-18, 18)
        y2 = y1 + random.randint(-18, 18)

        draw.line(
            (x1, y1, x2, y2),
            fill=(240, 237, 231),
            width=1,
        )


def draw_paper_background(image: Image.Image, paper_type: str) -> None:
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, PAGE_WIDTH, PAGE_HEIGHT), fill=(248, 246, 240))

    add_paper_texture(image)

    if paper_type == "横线纸":
        for y in range(TOP_MARGIN, PAGE_HEIGHT - BOTTOM_MARGIN, 62):
            draw.line((80, y, PAGE_WIDTH - 80, y), fill=(208, 220, 235), width=2)

        draw.line(
            (LEFT_MARGIN - 25, 70, LEFT_MARGIN - 25, PAGE_HEIGHT - 70),
            fill=(235, 175, 175),
            width=2,
        )

    elif paper_type == "方格纸":
        spacing = 55

        for x in range(60, PAGE_WIDTH - 60, spacing):
            draw.line((x, 60, x, PAGE_HEIGHT - 60), fill=(220, 227, 235), width=1)

        for y in range(60, PAGE_HEIGHT - 60, spacing):
            draw.line((60, y, PAGE_WIDTH - 60, y), fill=(220, 227, 235), width=1)


def wrap_paragraph(
    paragraph: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    if not paragraph.strip():
        return [""]

    words = paragraph.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"

        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)

            if draw.textlength(word, font=font) > max_width:
                part = ""
                for char in word:
                    candidate_part = part + char
                    if draw.textlength(candidate_part, font=font) <= max_width:
                        part = candidate_part
                    else:
                        if part:
                            lines.append(part)
                        part = char
                current = part
            else:
                current = word

    if current:
        lines.append(current)

    return lines


def wrap_text(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    all_lines: list[str] = []

    for paragraph in text.splitlines():
        all_lines.extend(wrap_paragraph(paragraph, draw, font, max_width))

    return all_lines


def varied_ink_color(ink_name: str) -> tuple[int, int, int]:
    if ink_name == "蓝色":
        base = (36, 58, 115)
        variation = 12
    else:
        base = (32, 32, 32)
        variation = 10

    return (
        clamp(base[0] + random.randint(-variation, variation)),
        clamp(base[1] + random.randint(-variation, variation)),
        clamp(base[2] + random.randint(-variation, variation)),
    )


def draw_handwritten_line(
    page: Image.Image,
    text: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    ink_name: str,
    randomness: int,
) -> None:
    temp_draw = ImageDraw.Draw(page)
    text_width = int(temp_draw.textlength(text, font=font)) + 60
    text_height = font.size * 2 + 40

    line_image = Image.new("RGBA", (max(1, text_width), max(1, text_height)), (0, 0, 0, 0))
    line_draw = ImageDraw.Draw(line_image)

    current_x = 12

    for char in text:
        char_color = varied_ink_color(ink_name)
        char_y_shift = random.randint(-1 - randomness, 1 + randomness)

        line_draw.text(
            (current_x, 12 + char_y_shift),
            char,
            font=font,
            fill=char_color,
        )

        char_width = line_draw.textlength(char, font=font)
        current_x += int(char_width) + random.randint(0, 1)

    angle = random.uniform(-0.6 - randomness * 0.2, 0.6 + randomness * 0.2)
    rotated = line_image.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    paste_x = max(0, x)
    paste_y = max(0, y)

    page.alpha_composite(rotated, (paste_x, paste_y))


def render_page(
    text: str,
    font_size: int,
    line_spacing: int,
    paper_type: str,
    ink_name: str,
    randomness: int,
) -> Image.Image:
    image = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), (248, 246, 240, 255))
    draw_paper_background(image, paper_type)

    measure_draw = ImageDraw.Draw(image)
    font = load_font(font_size)

    max_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    lines = wrap_text(text, measure_draw, font, max_width)

    line_height = font_size + line_spacing + 8
    y = TOP_MARGIN
    previous_was_blank = True

    for line in lines:
        if y + line_height > PAGE_HEIGHT - BOTTOM_MARGIN:
            break

        if not line.strip():
            y += line_height // 2 + 10
            previous_was_blank = True
            continue

        paragraph_indent = random.randint(18, 42) if previous_was_blank else 0

        x = (
            LEFT_MARGIN
            + paragraph_indent
            + random.randint(-randomness * 2, randomness * 3)
        )

        y_offset = random.randint(-randomness, randomness + 1)

        draw_handwritten_line(
            page=image,
            text=line,
            x=x,
            y=y + y_offset,
            font=font,
            ink_name=ink_name,
            randomness=randomness,
        )

        y += line_height + random.randint(-randomness, randomness + 2)
        previous_was_blank = False

    return image.convert("RGB")


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


st.set_page_config(page_title="俄语手写图片生成器", page_icon="✍️", layout="wide")

st.title("✍️ 俄语手写图片生成器")
st.caption("增强版：更自然的纸张纹理、墨水变化和手写抖动。")

with st.sidebar:
    st.header("页面设置")
    font_size = st.slider("字体大小", 35, 90, 58)
    line_spacing = st.slider("行距", 5, 55, 22)
    paper_type = st.selectbox("纸张", ["横线纸", "白纸", "方格纸"])
    ink_name = st.selectbox("墨水", ["蓝色", "黑色"])
    randomness = st.slider("自然随机程度", 0, 6, 3)

default_text = """Привет! Это мой первый текст.

Сегодня я создаю приложение, которое превращает русский текст в рукописное изображение.

Я хочу, чтобы это выглядело намного более естественно и похоже на настоящий почерк."""

text = st.text_area(
    "输入或粘贴俄语文字",
    value=default_text,
    height=260,
)

if st.button("生成手写图片", type="primary"):
    if not text.strip():
        st.warning("请先输入文字。")
    else:
        try:
            result = render_page(
                text=text,
                font_size=font_size,
                line_spacing=line_spacing,
                paper_type=paper_type,
                ink_name=ink_name,
                randomness=randomness,
            )

            png_data = image_to_png_bytes(result)

            st.success("生成成功。")
            st.image(result, caption="预览", width="stretch")
            st.download_button(
                "下载 PNG 图片",
                data=png_data,
                file_name="russian_handwriting.png",
                mime="image/png",
            )

            st.info("当前版本仍然只生成一页，下一步我们可以继续升级为自动分页。")

        except FileNotFoundError as error:
            st.error(str(error))
        except OSError:
            st.error(
                "字体无法打开。请确认字体文件有效，并且支持西里尔字母。"
            )
        except Exception as error:
            st.exception(error)
