from io import BytesIO
from pathlib import Path
import random
import textwrap

import streamlit as st
from PIL import Image, ImageDraw, ImageFont


PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
LEFT_MARGIN = 120
RIGHT_MARGIN = 100
TOP_MARGIN = 130
BOTTOM_MARGIN = 110


def find_font() -> Path | None:
    """Find the first .ttf or .otf font placed in the fonts folder."""
    font_dir = Path(__file__).parent / "fonts"
    font_files = list(font_dir.glob("*.ttf")) + list(font_dir.glob("*.otf"))
    return font_files[0] if font_files else None


def load_font(font_size: int) -> ImageFont.FreeTypeFont:
    font_path = find_font()

    if font_path is None:
        raise FileNotFoundError(
            "没有找到字体。请把支持俄语的 .ttf 或 .otf 手写字体放进 fonts 文件夹。"
        )

    return ImageFont.truetype(str(font_path), font_size)


def draw_paper_background(draw: ImageDraw.ImageDraw, paper_type: str) -> None:
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

            # Very long unbroken words are split character by character.
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


def render_page(
    text: str,
    font_size: int,
    line_spacing: int,
    paper_type: str,
    ink_color: str,
    randomness: int,
) -> Image.Image:
    image = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), (250, 249, 245))
    draw = ImageDraw.Draw(image)
    draw_paper_background(draw, paper_type)

    font = load_font(font_size)
    max_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    lines = wrap_text(text, draw, font, max_width)

    line_height = font_size + line_spacing
    y = TOP_MARGIN

    for line in lines:
        if y + line_height > PAGE_HEIGHT - BOTTOM_MARGIN:
            break

        if line:
            x_shift = random.randint(-randomness, randomness)
            y_shift = random.randint(-randomness, randomness)

            draw.text(
                (LEFT_MARGIN + x_shift, y + y_shift),
                line,
                font=font,
                fill=ink_color,
            )

        y += line_height + random.randint(-randomness, randomness)

    return image


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


st.set_page_config(page_title="俄语手写图片生成器", page_icon="✍️", layout="wide")

st.title("✍️ 俄语手写图片生成器")
st.caption("第一版：粘贴俄语文字，生成一页手写 PNG 图片。")

with st.sidebar:
    st.header("页面设置")
    font_size = st.slider("字体大小", 35, 90, 58)
    line_spacing = st.slider("行距", 5, 55, 22)
    paper_type = st.selectbox("纸张", ["横线纸", "白纸", "方格纸"])
    ink_name = st.selectbox("墨水", ["蓝色", "黑色"])
    randomness = st.slider("自然随机程度", 0, 5, 2)

ink_color = "#243A73" if ink_name == "蓝色" else "#202020"

default_text = """Привет! Это мой первый текст.

Сегодня я создаю приложение, которое превращает русский текст в рукописное изображение."""

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
                ink_color=ink_color,
                randomness=randomness,
            )

            png_data = image_to_png_bytes(result)

            st.success("生成成功。")
            st.image(result, caption="预览", use_container_width=True)
            st.download_button(
                "下载 PNG 图片",
                data=png_data,
                file_name="russian_handwriting.png",
                mime="image/png",
            )

            st.info("当前版本只生成一页。超出页面的文字会在以后加入自动分页。")

        except FileNotFoundError as error:
            st.error(str(error))
        except OSError:
            st.error(
                "字体无法打开。请确认 fonts 文件夹中的字体是有效的 TTF/OTF，"
                "并且支持西里尔字母。"
            )
        except Exception as error:
            st.exception(error)
