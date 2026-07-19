from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import random
import zipfile

import streamlit as st
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754

LEFT_MARGIN = 120
RIGHT_MARGIN = 100
TOP_MARGIN = 130
BOTTOM_MARGIN = 110

FONT_DIR = Path(__file__).resolve().parent / "fonts"


@dataclass(frozen=True)
class RenderSettings:
    font_path: str
    font_size: int
    line_spacing: int
    paper_type: str
    ink_name: str
    randomness: int
    seed: int
    quality_scale: int = 2


def clamp(value: int) -> int:
    return max(0, min(255, value))


def get_font_files() -> dict[str, Path]:
    """
    只扫描 fonts 文件夹，比扫描整个项目更快。
    """
    FONT_DIR.mkdir(exist_ok=True)

    files = sorted(
        [
            *FONT_DIR.glob("*.ttf"),
            *FONT_DIR.glob("*.otf"),
            *FONT_DIR.glob("*.TTF"),
            *FONT_DIR.glob("*.OTF"),
        ],
        key=lambda path: path.name.lower(),
    )

    return {path.name: path for path in files}


@st.cache_resource(show_spinner=False)
def load_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont:
    """
    缓存字体，避免 Streamlit 每次刷新都重新读取。
    """
    return ImageFont.truetype(font_path, font_size)


def make_texture(
    width: int,
    height: int,
    rng: random.Random,
) -> Image.Image:
    """
    使用低分辨率随机纹理放大，速度比逐个绘制几千个点更快。
    """
    small_width = max(40, width // 10)
    small_height = max(40, height // 10)

    pixels = bytes(
        rng.randint(235, 255)
        for _ in range(small_width * small_height)
    )

    texture = Image.frombytes(
        "L",
        (small_width, small_height),
        pixels,
    )

    return texture.resize(
        (width, height),
        Image.Resampling.BILINEAR,
    ).convert("RGB")


def create_paper_background(
    paper_type: str,
    rng: random.Random,
) -> Image.Image:
    """
    生成白纸、横线纸或方格纸背景。
    """
    base = Image.new(
        "RGB",
        (PAGE_WIDTH, PAGE_HEIGHT),
        (248, 246, 240),
    )

    texture = make_texture(PAGE_WIDTH, PAGE_HEIGHT, rng)
    image = Image.blend(base, texture, 0.12)
    draw = ImageDraw.Draw(image)

    # 少量纸张纤维
    for _ in range(90):
        x1 = rng.randint(0, PAGE_WIDTH - 1)
        y1 = rng.randint(0, PAGE_HEIGHT - 1)
        x2 = x1 + rng.randint(-15, 15)
        y2 = y1 + rng.randint(-15, 15)

        draw.line(
            (x1, y1, x2, y2),
            fill=(239, 236, 229),
            width=1,
        )

    if paper_type == "横线纸":
        for y in range(TOP_MARGIN, PAGE_HEIGHT - BOTTOM_MARGIN, 62):
            draw.line(
                (80, y, PAGE_WIDTH - 80, y),
                fill=(208, 220, 235),
                width=2,
            )

        draw.line(
            (
                LEFT_MARGIN - 25,
                70,
                LEFT_MARGIN - 25,
                PAGE_HEIGHT - 70,
            ),
            fill=(235, 175, 175),
            width=2,
        )

    elif paper_type == "方格纸":
        spacing = 55

        for x in range(60, PAGE_WIDTH - 60, spacing):
            draw.line(
                (x, 60, x, PAGE_HEIGHT - 60),
                fill=(220, 227, 235),
                width=1,
            )

        for y in range(60, PAGE_HEIGHT - 60, spacing):
            draw.line(
                (60, y, PAGE_WIDTH - 60, y),
                fill=(220, 227, 235),
                width=1,
            )

    return image.convert("RGBA")


def split_long_word(
    word: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """
    超长单词按字符拆分，避免超出页面。
    """
    parts: list[str] = []
    current = ""

    for char in word:
        candidate = current + char

        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = char

    if current:
        parts.append(current)

    return parts


def wrap_paragraph(
    paragraph: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """
    自动换行一个段落。
    """
    if not paragraph.strip():
        return [""]

    words = paragraph.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"

        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        if draw.textlength(word, font=font) <= max_width:
            current = word
            continue

        parts = split_long_word(
            word=word,
            draw=draw,
            font=font,
            max_width=max_width,
        )

        if parts:
            lines.extend(parts[:-1])
            current = parts[-1]

    if current:
        lines.append(current)

    return lines


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """
    对全文自动换行，并保留空行。
    """
    measuring_image = Image.new("RGB", (10, 10), "white")
    draw = ImageDraw.Draw(measuring_image)

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    all_lines: list[str] = []

    for paragraph in normalized_text.split("\n"):
        all_lines.extend(
            wrap_paragraph(
                paragraph=paragraph,
                draw=draw,
                font=font,
                max_width=max_width,
            )
        )

    return all_lines


def paginate_lines(
    lines: list[str],
    font_size: int,
    line_spacing: int,
    randomness: int,
) -> list[list[str]]:
    """
    把排好行的文字自动分成多页。
    """
    normal_height = font_size + line_spacing + 8 + randomness + 2
    blank_height = normal_height // 2 + 10
    available_height = PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN

    pages: list[list[str]] = []
    current_page: list[str] = []
    used_height = 0

    for line in lines:
        line_height = blank_height if not line.strip() else normal_height

        if current_page and used_height + line_height > available_height:
            pages.append(current_page)
            current_page = []
            used_height = 0

        current_page.append(line)
        used_height += line_height

    if current_page or not pages:
        pages.append(current_page)

    return pages


def varied_ink_color(
    ink_name: str,
    rng: random.Random,
) -> tuple[int, int, int]:
    """
    每一行的墨水颜色有轻微变化。
    """
    if ink_name == "蓝色":
        base = (36, 58, 115)
        variation = 10
    else:
        base = (32, 32, 32)
        variation = 8

    return (
        clamp(base[0] + rng.randint(-variation, variation)),
        clamp(base[1] + rng.randint(-variation, variation)),
        clamp(base[2] + rng.randint(-variation, variation)),
    )


def create_pressure_mask(
    text_mask: Image.Image,
    rng: random.Random,
) -> Image.Image:
    """
    模拟书写压力的轻微变化。
    """
    width, height = text_mask.size
    small_width = max(2, width // 30)
    small_height = max(2, height // 12)

    pressure_pixels = bytes(
        rng.randint(218, 255)
        for _ in range(small_width * small_height)
    )

    pressure = Image.frombytes(
        "L",
        (small_width, small_height),
        pressure_pixels,
    ).resize(
        (width, height),
        Image.Resampling.BILINEAR,
    )

    return ImageChops.multiply(text_mask, pressure)


def draw_handwritten_line(
    page: Image.Image,
    text: str,
    x: int,
    y: int,
    settings: RenderSettings,
    rng: random.Random,
) -> None:
    """
    绘制一整行文字，保留字体本身的连笔效果。
    """
    scale = settings.quality_scale

    high_font = load_font(
        settings.font_path,
        settings.font_size * scale,
    )

    measuring_image = Image.new("L", (1, 1), 0)
    measuring_draw = ImageDraw.Draw(measuring_image)

    bbox = measuring_draw.textbbox(
        (0, 0),
        text,
        font=high_font,
    )

    padding = 14 * scale
    text_width = max(1, bbox[2] - bbox[0])
    text_height = max(1, bbox[3] - bbox[1])

    mask = Image.new(
        "L",
        (
            text_width + padding * 2,
            text_height + padding * 2,
        ),
        0,
    )

    mask_draw = ImageDraw.Draw(mask)

    mask_draw.text(
        (
            padding - bbox[0],
            padding - bbox[1],
        ),
        text,
        font=high_font,
        fill=255,
    )

    # 轻微柔化边缘
    mask = mask.filter(
        ImageFilter.GaussianBlur(radius=0.12 * scale)
    )

    pressure_mask = create_pressure_mask(mask, rng)
    ink_color = varied_ink_color(settings.ink_name, rng)

    line_image = Image.new(
        "RGBA",
        mask.size,
        (
            ink_color[0],
            ink_color[1],
            ink_color[2],
            0,
        ),
    )

    line_image.putalpha(pressure_mask)

    # 每行轻微拉伸，避免每一行都完全相同
    width_change = rng.uniform(
        0.994 - settings.randomness * 0.0015,
        1.006 + settings.randomness * 0.0015,
    )

    height_change = rng.uniform(
        0.997 - settings.randomness * 0.0008,
        1.003 + settings.randomness * 0.0008,
    )

    new_width = max(
        1,
        int(line_image.width / scale * width_change),
    )

    new_height = max(
        1,
        int(line_image.height / scale * height_change),
    )

    line_image = line_image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )

    # 每行轻微倾斜
    angle = rng.uniform(
        -0.12 - settings.randomness * 0.025,
        0.12 + settings.randomness * 0.025,
    )

    line_image = line_image.rotate(
        angle,
        expand=True,
        resample=Image.Resampling.BICUBIC,
    )

    paste_x = max(0, x + rng.randint(-1, 1))
    paste_y = max(0, y + rng.randint(-1, 1))

    # 防止旋转后超出右边界
    max_allowed_width = PAGE_WIDTH - RIGHT_MARGIN - paste_x

    if line_image.width > max_allowed_width and max_allowed_width > 10:
        ratio = max_allowed_width / line_image.width

        line_image = line_image.resize(
            (
                max_allowed_width,
                max(1, int(line_image.height * ratio)),
            ),
            Image.Resampling.LANCZOS,
        )

    page.alpha_composite(
        line_image,
        (paste_x, paste_y),
    )


def render_single_page(
    page_lines: list[str],
    settings: RenderSettings,
    page_number: int,
) -> Image.Image:
    """
    渲染单独一页。
    """
    page_seed = settings.seed + page_number * 100_003
    rng = random.Random(page_seed)

    image = create_paper_background(
        settings.paper_type,
        rng,
    )

    line_height = settings.font_size + settings.line_spacing + 8
    y = TOP_MARGIN
    previous_was_blank = True

    for line in page_lines:
        if not line.strip():
            y += line_height // 2 + 10
            previous_was_blank = True
            continue

        paragraph_indent = (
            rng.randint(18, 42)
            if previous_was_blank
            else 0
        )

        x = (
            LEFT_MARGIN
            + paragraph_indent
            + rng.randint(
                -settings.randomness * 2,
                settings.randomness * 3,
            )
        )

        y_offset = rng.randint(
            -settings.randomness,
            settings.randomness + 1,
        )

        draw_handwritten_line(
            page=image,
            text=line,
            x=x,
            y=y + y_offset,
            settings=settings,
            rng=rng,
        )

        y += line_height + rng.randint(
            -settings.randomness,
            settings.randomness + 2,
        )

        previous_was_blank = False

    return image.convert("RGB")


def render_document(
    text: str,
    settings: RenderSettings,
) -> list[Image.Image]:
    """
    自动换行、自动分页并渲染全部页面。
    """
    normal_font = load_font(
        settings.font_path,
        settings.font_size,
    )

    # 给段落缩进和随机抖动预留安全空间
    max_text_width = (
        PAGE_WIDTH
        - LEFT_MARGIN
        - RIGHT_MARGIN
        - 90
    )

    lines = wrap_text(
        text=text,
        font=normal_font,
        max_width=max_text_width,
    )

    pages_lines = paginate_lines(
        lines=lines,
        font_size=settings.font_size,
        line_spacing=settings.line_spacing,
        randomness=settings.randomness,
    )

    return [
        render_single_page(
            page_lines=page_lines,
            settings=settings,
            page_number=index,
        )
        for index, page_lines in enumerate(pages_lines)
    ]


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
        optimize=True,
    )

    return buffer.getvalue()


def pages_to_zip_bytes(pages: list[Image.Image]) -> bytes:
    """
    把所有 PNG 页面放入 ZIP。
    """
    buffer = BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for index, page in enumerate(pages, start=1):
            archive.writestr(
                f"page_{index:03d}.png",
                image_to_png_bytes(page),
            )

    return buffer.getvalue()


def pages_to_pdf_bytes(pages: list[Image.Image]) -> bytes:
    """
    把全部页面合并为 PDF。
    """
    buffer = BytesIO()
    rgb_pages = [page.convert("RGB") for page in pages]

    rgb_pages[0].save(
        buffer,
        format="PDF",
        save_all=True,
        append_images=rgb_pages[1:],
        resolution=150.0,
    )

    return buffer.getvalue()


def save_result_to_session(pages: list[Image.Image]) -> None:
    """
    缓存生成结果，点击下载时不会重复生成。
    """
    st.session_state["generated_result"] = {
        "preview_pages": pages[:5],
        "page_count": len(pages),
        "first_png": image_to_png_bytes(pages[0]),
        "zip_bytes": pages_to_zip_bytes(pages),
        "pdf_bytes": pages_to_pdf_bytes(pages),
    }


st.set_page_config(
    page_title="俄语手写图片生成器",
    page_icon="✍️",
    layout="wide",
)

st.title("✍️ 俄语手写图片生成器")
st.caption("优化版：支持自动分页、多页 PNG、ZIP 和 PDF 导出。")

font_files = get_font_files()

if not font_files:
    st.error(
        "没有找到字体。请把支持俄语的 .ttf 或 .otf 手写字体，"
        "复制到项目的 fonts 文件夹后刷新页面。"
    )

    st.code(
        "项目文件夹\n"
        "├── app.py\n"
        "└── fonts\n"
        "    └── 你的俄语手写字体.ttf"
    )

    st.stop()


with st.sidebar:
    st.header("页面设置")

    selected_font_name = st.selectbox(
        "手写字体",
        options=list(font_files.keys()),
    )

    font_size = st.slider(
        "字体大小",
        min_value=35,
        max_value=90,
        value=58,
    )

    line_spacing = st.slider(
        "行距",
        min_value=5,
        max_value=55,
        value=22,
    )

    paper_type = st.selectbox(
        "纸张",
        ["横线纸", "白纸", "方格纸"],
    )

    ink_name = st.selectbox(
        "墨水",
        ["蓝色", "黑色"],
    )

    randomness = st.slider(
        "自然随机程度",
        min_value=0,
        max_value=6,
        value=3,
        help="建议选择 2～4。数值太高可能显得杂乱。",
    )

    seed = st.number_input(
        "随机种子",
        min_value=0,
        max_value=999_999,
        value=12_345,
        step=1,
        help="相同文字和种子会生成相同效果。修改数字可换一种排列。",
    )


default_text = """Привет! Это мой первый текст.

Сегодня я создаю приложение, которое превращает русский текст в рукописное изображение.

Я хочу, чтобы это выглядело естественно и было похоже на настоящий почерк."""

text = st.text_area(
    "输入或粘贴俄语文字",
    value=default_text,
    height=300,
)

generate_clicked = st.button(
    "生成手写文档",
    type="primary",
)

if generate_clicked:
    if not text.strip():
        st.warning("请先输入俄语文字。")
    else:
        settings = RenderSettings(
            font_path=str(font_files[selected_font_name]),
            font_size=font_size,
            line_spacing=line_spacing,
            paper_type=paper_type,
            ink_name=ink_name,
            randomness=randomness,
            seed=int(seed),
        )

        try:
            with st.spinner("正在生成手写页面……"):
                pages = render_document(
                    text=text,
                    settings=settings,
                )

                save_result_to_session(pages)

            st.success(
                f"生成成功，共 {len(pages)} 页。"
            )

        except FileNotFoundError as error:
            st.error(str(error))

        except OSError:
            st.error(
                "字体无法打开。请确认字体文件有效，并且支持西里尔字母。"
            )

        except MemoryError:
            st.error(
                "文字太多，电脑内存不足。请减少文字数量后分批生成。"
            )

        except Exception as error:
            st.exception(error)


result = st.session_state.get("generated_result")

if result:
    st.subheader("预览")

    preview_pages = result["preview_pages"]

    for index, page in enumerate(preview_pages, start=1):
        st.image(
            page,
            caption=f"第 {index} 页",
            width="stretch",
        )

    if result["page_count"] > len(preview_pages):
        st.info(
            f"为了保持网页流畅，只预览前 {len(preview_pages)} 页。"
            f"全部 {result['page_count']} 页可以下载为 ZIP 或 PDF。"
        )

    st.subheader("下载")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "下载第一页 PNG",
            data=result["first_png"],
            file_name="russian_handwriting_page_001.png",
            mime="image/png",
            width="stretch",
        )

    with col2:
        st.download_button(
            "下载全部 PNG（ZIP）",
            data=result["zip_bytes"],
            file_name="russian_handwriting_pages.zip",
            mime="application/zip",
            width="stretch",
        )

    with col3:
        st.download_button(
            "下载全部页面 PDF",
            data=result["pdf_bytes"],
            file_name="russian_handwriting_document.pdf",
            mime="application/pdf",
            width="stretch",
        )
