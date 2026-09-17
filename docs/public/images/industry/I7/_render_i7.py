"""Render I7 course diagrams in the industry-slide style."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
I5_REF = ROOT.parent / "I5" / "I5-01-async-read.png"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

W, H = 1280, 720
MARGIN_X = 48
HEADER_Y = 36
BAR_TOP = 668
LOGO_END = 190

C_TEXT = (27, 31, 36, 255)
C_SUB = (107, 114, 128, 255)
C_WHITE = (255, 255, 255, 255)
BLUE = (6, 150, 254, 255)
BLUE_SOFT = (235, 246, 255, 255)
BLUE_BD = (147, 197, 253, 255)
ORANGE = (242, 140, 40, 255)
ORANGE_SOFT = (255, 244, 230, 255)
ORANGE_BD = (253, 186, 116, 255)
GREEN = (16, 163, 127, 255)
GREEN_SOFT = (236, 253, 245, 255)
GREEN_BD = (110, 231, 183, 255)
PURPLE = (139, 92, 246, 255)
PURPLE_SOFT = (245, 243, 255, 255)
PURPLE_BD = (196, 181, 253, 255)
ROSE = (225, 29, 72, 255)
ROSE_SOFT = (255, 241, 242, 255)
ROSE_BD = (253, 164, 175, 255)
GRAY = (100, 116, 139, 255)
GRAY_SOFT = (248, 250, 252, 255)
GRAY_BD = (203, 213, 225, 255)
BAR_LEFT = (0, 150, 254, 255)
BAR_RIGHT = (190, 157, 255, 255)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=0)


def F_TITLE() -> ImageFont.FreeTypeFont:
    return font(FONT_BOLD, 32)


def F_SUB() -> ImageFont.FreeTypeFont:
    return font(FONT_REG, 16)


def F_H() -> ImageFont.FreeTypeFont:
    return font(FONT_BOLD, 17)


def F_B() -> ImageFont.FreeTypeFont:
    return font(FONT_REG, 14)


def F_S() -> ImageFont.FreeTypeFont:
    return font(FONT_REG, 12)


def F_EN() -> ImageFont.FreeTypeFont:
    return font(FONT_BOLD, 13)


def measure(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def lines_height(
    draw: ImageDraw.ImageDraw,
    lines: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]],
    gap: int,
) -> int:
    total = 0
    for i, (text, fnt, _) in enumerate(lines):
        _, th = measure(draw, text, fnt)
        total += th
        if i < len(lines) - 1:
            total += gap
    return total


def center_lines(
    draw: ImageDraw.ImageDraw,
    cx: int,
    top: int,
    lines: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]],
    gap: int = 6,
) -> int:
    y = top
    for text, fnt, color in lines:
        tw, th = measure(draw, text, fnt)
        draw.text((cx - tw // 2, y), text, font=fnt, fill=color)
        y += th + gap
    return y


def box_lines(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    lines: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]],
    gap: int = 8,
    y_offset: int = 0,
) -> None:
    total = lines_height(draw, lines, gap)
    top = box[1] + (box[3] - box[1] - total) // 2 + y_offset
    center_lines(draw, (box[0] + box[2]) // 2, top, lines, gap)


def card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    border: tuple[int, int, int, int],
    radius: int = 16,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=border, width=width)


def accent_bar(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    color: tuple[int, int, int, int],
) -> None:
    draw.rounded_rectangle((box[0], box[1], box[0] + 6, box[3]), radius=3, fill=color)


def arrow_right(
    draw: ImageDraw.ImageDraw,
    x1: int,
    y: int,
    x2: int,
    color: tuple[int, int, int, int] = GRAY,
    label: str = "",
) -> None:
    draw.line((x1, y, x2 - 10, y), fill=color, width=3)
    draw.polygon([(x2, y), (x2 - 12, y - 6), (x2 - 12, y + 6)], fill=color)
    if label:
        tw, th = measure(draw, label, F_S())
        draw.text(((x1 + x2) // 2 - tw // 2, y - th - 6), label, font=F_S(), fill=color)


def arrow_down(
    draw: ImageDraw.ImageDraw,
    x: int,
    y1: int,
    y2: int,
    color: tuple[int, int, int, int] = GRAY,
    label: str = "",
) -> None:
    draw.line((x, y1, x, y2 - 10), fill=color, width=3)
    draw.polygon([(x, y2), (x - 6, y2 - 12), (x + 6, y2 - 12)], fill=color)
    if label:
        tw, th = measure(draw, label, F_S())
        draw.text((x + 8, (y1 + y2) // 2 - th // 2), label, font=F_S(), fill=color)


def lerp_color(
    start: tuple[int, int, int, int],
    end: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    return tuple(int(start[i] + (end[i] - start[i]) * t) for i in range(4))


def paint_footer(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    for x in range(W):
        color = lerp_color(BAR_LEFT, BAR_RIGHT, x / (W - 1))
        draw.line([(x, BAR_TOP), (x, H - 1)], fill=color)
    logo = Image.open(I5_REF).convert("RGBA").crop((0, BAR_TOP, LOGO_END, H))
    canvas.paste(logo, (0, BAR_TOP), logo)


def new_slide(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGBA", (W, H), C_WHITE)
    draw = ImageDraw.Draw(canvas)
    draw.text((MARGIN_X, HEADER_Y), title, font=F_TITLE(), fill=C_TEXT)
    draw.text((MARGIN_X, HEADER_Y + 46), subtitle, font=F_SUB(), fill=C_SUB)
    paint_footer(canvas)
    return canvas, ImageDraw.Draw(canvas)


def labeled_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    border: tuple[int, int, int, int],
    accent: tuple[int, int, int, int],
    lines: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]],
    gap: int = 7,
) -> None:
    card(draw, box, fill, border)
    accent_bar(draw, box, accent)
    box_lines(draw, box, lines, gap=gap)


def save(image: Image.Image, name: str) -> Path:
    path = ROOT / name
    image.convert("RGBA").save(path, "PNG", optimize=True)
    return path


def draw_scope_cards(draw: ImageDraw.ImageDraw) -> None:
    scope = (40, 122, 868, 648)
    card(draw, scope, GRAY_SOFT, GRAY_BD, radius=20)
    draw.text((58, 136), "Scope  数据归属边界", font=F_H(), fill=C_TEXT)
    draw.text((58, 162), "scope_id 由服务端生成，只负责隔离，不负责授权", font=F_S(), fill=C_SUB)

    source = (56, 192, 448, 348)
    artifact = (464, 192, 852, 348)
    contract = (56, 368, 448, 508)
    revision = (464, 368, 852, 508)
    candidate = (56, 524, 852, 632)

    labeled_card(
        draw, source, BLUE_SOFT, BLUE_BD, BLUE,
        [("Source 来源", F_H(), C_TEXT), ("不可变观察 + SourceRef", F_B(), C_SUB), ("captured / referenced", F_S(), GRAY)],
    )
    labeled_card(
        draw, artifact, BLUE_SOFT, BLUE_BD, BLUE,
        [("Artifact 资产层", F_H(), C_TEXT), ("Memory / Handoff", F_B(), C_SUB), ("Experience / Skill", F_B(), C_SUB)],
    )
    labeled_card(
        draw, contract, C_WHITE, GRAY_BD, GRAY,
        [("Work Contract / Task Outcome", F_H(), C_TEXT), ("委托基线与结果回写", F_B(), C_SUB), ("以来源形式保存", F_S(), GRAY)],
    )
    labeled_card(
        draw, revision, ORANGE_SOFT, ORANGE_BD, ORANGE,
        [("Revision 链", F_H(), C_TEXT), ("v1 → v2 → v3 不可变", F_B(), C_SUB), ("引用锚定具体版本", F_S(), ORANGE)],
    )
    labeled_card(
        draw, candidate, PURPLE_SOFT, PURPLE_BD, PURPLE,
        [
            ("Candidate 候选", F_H(), C_TEXT),
            ("Experience / Skill 先审核再发布", F_B(), C_SUB),
            ("候选本身不占 Artifact 身份", F_S(), PURPLE),
        ],
        gap=8,
    )
    arrow_right(draw, 448, 270, 464, GRAY)
    arrow_right(draw, 448, 438, 464, GRAY)
    arrow_down(draw, 252, 348, 368, GRAY)
    arrow_down(draw, 658, 348, 368, GRAY)


def render_domain() -> Image.Image:
    img, draw = new_slide(
        "领域模型：归属、证据与不可变资产",
        "Scope 划定归属，Source 与 Artifact 落位，PreparedContext 按请求装配",
    )
    draw_scope_cards(draw)
    prepared = (888, 192, 1240, 400)
    agent = (888, 430, 1240, 632)
    labeled_card(
        draw, prepared, GREEN_SOFT, GREEN_BD, GREEN,
        [
            ("PreparedContext", F_H(), C_TEXT),
            ("一次请求的有界视图", F_B(), C_SUB),
            ("信任包装 + 精确引用", F_B(), C_SUB),
            ("不落库，每次重新装配", F_S(), GREEN),
        ],
    )
    labeled_card(
        draw, agent, ROSE_SOFT, ROSE_BD, ROSE,
        [("Agent / 宿主", F_H(), C_TEXT), ("只消费本次视图", F_B(), C_SUB)],
    )
    arrow_right(draw, 852, 270, 888, GREEN, "装配")
    arrow_down(draw, 1064, 400, 430, ROSE)
    return img


def render_interfaces() -> Image.Image:
    img, draw = new_slide(
        "接入接口的设计边界",
        "同一套领域语义，通过 Core SDK、HTTP、Client、MCP、CLI 与 Web UI 分层暴露",
    )
    hosts = [
        (40, 124, 424, 218, "Agent 宿主", "Codex · Claude Code · DSH"),
        (448, 124, 832, 218, "应用代码与框架", "类型化 Client 调用 HTTP 语义"),
        (856, 124, 1240, 218, "人工操作", "审核候选 · 导出技能 · 配置观察"),
    ]
    access = (40, 246, 1240, 368)
    runtime = (40, 416, 1240, 516)
    storage = (40, 544, 1240, 640)
    for box in hosts:
        labeled_card(
            draw, box[:4], ROSE_SOFT, ROSE_BD, ROSE,
            [(box[4], F_H(), C_TEXT), (box[5], F_B(), C_SUB)],
        )
    labeled_card(
        draw, access, BLUE_SOFT, BLUE_BD, BLUE,
        [
            ("接入入口（共用领域语义）", F_H(), C_TEXT),
            ("MCP 精选子集  ·  HTTP OpenAPI 契约  ·  Python Client", F_B(), C_SUB),
            ("CLI 配置与诊断  ·  Web UI 只读  ·  Core SDK 进程内", F_B(), C_SUB),
        ],
    )
    labeled_card(
        draw, runtime, ORANGE_SOFT, ORANGE_BD, ORANGE,
        [("Server / Runtime", F_H(), C_TEXT), ("领域校验 · 调度 · 生命周期 · 装配", F_B(), C_SUB)],
    )
    labeled_card(
        draw, storage, GREEN_SOFT, GREEN_BD, GREEN,
        [("存储与检索（可替换）", F_H(), C_TEXT), ("SQLite  /  seekDB  /  OceanBase", F_B(), C_SUB)],
    )
    for box in hosts:
        arrow_down(draw, (box[0] + box[2]) // 2, 218, 246, ROSE)
    arrow_down(draw, 640, 368, 416, BLUE, "统一领域校验")
    arrow_down(draw, 640, 516, 544, ORANGE)
    return img


def render_storage() -> Image.Image:
    img, draw = new_slide(
        "存储后端与检索契约",
        "三个存储后端共享同一份检索契约，能力差异通过能力探测暴露",
    )
    request = (40, 128, 1240, 214)
    labeled_card(
        draw, request, BLUE_SOFT, BLUE_BD, BLUE,
        [
            ("检索请求", F_H(), C_TEXT),
            ("mode = auto / fts / vector / hybrid    ·    能力探测先行，缺失能力显式报错", F_B(), C_SUB),
        ],
    )
    backends = [
        (40, 248, 424, 500, GRAY_SOFT, GRAY_BD, GRAY,
         "SQLite（默认本地）", "个人与单机开发", "FTS5 全文 + sqlite-vec", "无模型时全文检索立即可用"),
        (448, 248, 832, 500, GREEN_SOFT, GREEN_BD, GREEN,
         "seekDB（嵌入式）", "嵌入式向量数据库", "向量与混合检索", "Linux / macOS 本地增强"),
        (856, 248, 1240, 500, PURPLE_SOFT, PURPLE_BD, PURPLE,
         "OceanBase（分布式）", "分布式数据库", "FULLTEXT + VECTOR HNSW", "团队共享与规模化部署"),
    ]
    for left, top, right, bottom, fill, bd, accent, title, line1, line2, line3 in backends:
        labeled_card(
            draw, (left, top, right, bottom), fill, bd, accent,
            [(title, F_H(), C_TEXT), (line1, F_B(), C_SUB), (line2, F_B(), C_SUB), (line3, F_S(), accent)],
            gap=10,
        )
        arrow_down(draw, (left + right) // 2, 214, 248, BLUE)

    contract = (40, 524, 1240, 640)
    labeled_card(
        draw, contract, ORANGE_SOFT, ORANGE_BD, ORANGE,
        [
            ("一致性契约", F_H(), C_TEXT),
            ("内容 Revision、当前头投影与检索索引同一事务提交", F_B(), C_SUB),
            ("投影可重建，检索只命中当前头且状态为活跃的内容", F_B(), C_SUB),
        ],
    )
    return img


def main() -> None:
    save(render_domain(), "I7-01-domain-model.png")
    save(render_interfaces(), "I7-02-interface-layers.png")
    save(render_storage(), "I7-03-storage-backends.png")


if __name__ == "__main__":
    main()

