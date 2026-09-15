"""Render I6 course diagrams in the industry-slide style."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
I5_REF = ROOT.parent / "I5" / "I5-01-async-read.png"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

W, H = 1280, 720
MARGIN_X = 48
HEADER_Y = 52
CONTENT_TOP = 118
FOOTER_TOP = 640

C_TEXT = (27, 31, 36, 255)
C_SUB = (107, 114, 128, 255)
C_LINE = (229, 231, 235, 255)
C_WHITE = (255, 255, 255, 255)
C_TAG = (75, 85, 99, 255)

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
GRAY = (100, 116, 139, 255)
GRAY_SOFT = (248, 250, 252, 255)
GRAY_BD = (203, 213, 225, 255)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=0)


def F_TITLE() -> ImageFont.FreeTypeFont:
    return font(FONT_BOLD, 34)


def F_SUB() -> ImageFont.FreeTypeFont:
    return font(FONT_REG, 16)


def F_TAG() -> ImageFont.FreeTypeFont:
    return font(FONT_REG, 15)


def F_H() -> ImageFont.FreeTypeFont:
    return font(FONT_BOLD, 18)


def F_B() -> ImageFont.FreeTypeFont:
    return font(FONT_REG, 14)


def F_S() -> ImageFont.FreeTypeFont:
    return font(FONT_REG, 12)


def F_EN() -> ImageFont.FreeTypeFont:
    return font(FONT_BOLD, 13)


def measure(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def new_slide(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGBA", (W, H), C_WHITE)
    draw = ImageDraw.Draw(canvas)
    draw.text((MARGIN_X, HEADER_Y), title, font=F_TITLE(), fill=C_TEXT)
    draw.text((MARGIN_X, HEADER_Y + 48), subtitle, font=F_SUB(), fill=C_SUB)
    tag = "# 2026 OceanBase 数据库大赛 #"
    tw, _ = measure(draw, tag, F_TAG())
    draw.text((W - MARGIN_X - tw, HEADER_Y + 8), tag, font=F_TAG(), fill=C_TAG)
    footer = Image.open(I5_REF).convert("RGBA").crop((0, FOOTER_TOP, W, H))
    canvas.paste(footer, (0, FOOTER_TOP), footer)
    return canvas, draw


def card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    border: tuple[int, int, int, int],
    radius: int = 16,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=border, width=width)


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
    cx = (box[0] + box[2]) // 2
    block = lines_height(draw, lines, gap)
    top = box[1] + (box[3] - box[1] - block) // 2 + y_offset
    center_lines(draw, cx, top, lines, gap)


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
        draw.text(((x1 + x2) // 2 - tw // 2, y - th - 8), label, font=F_S(), fill=color)


def arrow_down(
    draw: ImageDraw.ImageDraw,
    x: int,
    y1: int,
    y2: int,
    color: tuple[int, int, int, int] = GRAY,
) -> None:
    draw.line((x, y1, x, y2 - 10), fill=color, width=3)
    draw.polygon([(x, y2), (x - 6, y2 - 12), (x + 6, y2 - 12)], fill=color)


def badge(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    text: str,
    fill: tuple[int, int, int, int],
) -> None:
    draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=fill)
    tw, th = measure(draw, text, F_EN())
    draw.text((cx - tw // 2, cy - th // 2 - 1), text, font=F_EN(), fill=C_WHITE)


def draw_role_stack(draw: ImageDraw.ImageDraw) -> None:
    roles = [
        ((308, 150, 558, 258), "来源 Source", "记录发生了什么"),
        ((308, 278, 558, 386), "记忆 Memory", "留下长期知识"),
        ((308, 406, 558, 520), "任务状态 / 交接", "进行到哪里"),
    ]
    for box, title, sub in roles:
        card(draw, box, BLUE_SOFT, BLUE_BD)
        draw.rounded_rectangle((box[0], box[1], box[0] + 6, box[3]), radius=3, fill=BLUE)
        box_lines(draw, box, [(title, F_H(), C_TEXT), (sub, F_B(), C_SUB)], gap=8)


def render_assembly() -> Image.Image:
    img, draw = new_slide("从项目数据到单次决策视图", "选择、装配与引用标注之后，模型只面对这一次决策的有界视图")

    g1 = (48, 150, 268, 520)
    card(draw, g1, GRAY_SOFT, GRAY_BD)
    box_lines(
        draw,
        g1,
        [
            ("项目数据", F_H(), C_TEXT),
            ("长期材料，不是本次输入", F_S(), C_SUB),
            ("文档 / 对话 / 规范", F_B(), GRAY),
            ("代码库 / 工具结果", F_B(), GRAY),
        ],
        gap=12,
    )
    draw_role_stack(draw)

    g3 = (598, 170, 858, 500)
    card(draw, g3, ORANGE_SOFT, ORANGE_BD)
    box_lines(
        draw,
        g3,
        [
            ("上下文准备", F_H(), C_TEXT),
            ("PreparedContext", F_EN(), ORANGE),
            ("选择 / 排序 / 裁剪", F_B(), C_SUB),
            ("引用标注后交付", F_B(), C_SUB),
            ("一次性视图，不长期存储", F_S(), ORANGE),
        ],
        gap=12,
    )

    g4a = (898, 150, 1232, 318)
    g4b = (898, 352, 1232, 520)
    card(draw, g4a, GREEN_SOFT, GREEN_BD)
    box_lines(draw, g4a, [("本次视图", F_H(), C_TEXT), ("有界注入 · 可追溯", F_B(), C_SUB)], gap=10)
    card(draw, g4b, PURPLE_SOFT, PURPLE_BD)
    box_lines(draw, g4b, [("模型", F_H(), C_TEXT), ("只看这一次决策视图", F_B(), C_SUB)], gap=10)

    arrow_right(draw, 268, 335, 308, GRAY)
    arrow_right(draw, 558, 335, 598, BLUE, "召回候选")
    arrow_right(draw, 858, 234, 898, ORANGE, "装配")
    arrow_down(draw, 1065, 318, 352, GREEN)

    bar = (48, 548, 1232, 612)
    card(draw, bar, GRAY_SOFT, GRAY_BD, radius=12)
    box_lines(
        draw,
        bar,
        [("执行与回写    新证据进入来源 · 结论可沉淀为记忆 · 进度写回任务状态", F_B(), GRAY)],
        gap=0,
    )
    return img


def budget_stages() -> list[tuple]:
    return [
        ("01", "全部可引用", "文档 / 对话记录", "规范 / 历史版本", BLUE_SOFT, BLUE_BD, BLUE),
        ("02", "检索相关候选", "混合检索 / 重排", "排序靠前不等于可注入", BLUE_SOFT, BLUE_BD, BLUE),
        ("03", "通过准入", "完整性 / 相关性基线", "信任层级过滤", ORANGE_SOFT, ORANGE_BD, ORANGE),
        ("04", "预算内注入", "默认 8000 字节", "单条 ≤2000 · 至多 8 条", ORANGE_SOFT, ORANGE_BD, ORANGE),
        ("05", "进入本次视图", "ready / 引用标注", "字节核对后交付", GREEN_SOFT, GREEN_BD, GREEN),
    ]


def render_budget() -> Image.Image:
    img, draw = new_slide("预算裁剪决定放得下什么", "相关候选先过准入，再按确定性字节规则裁剪，只有一部分进入本次视图")

    left, gap, card_w, top, bottom = 64, 18, 216, 168, 488
    for i, (num, title, l1, l2, fill, bd, accent) in enumerate(budget_stages()):
        x = left + i * (card_w + gap)
        box = (x, top, x + card_w, bottom)
        card(draw, box, fill, bd)
        badge(draw, x + card_w // 2, top + 28, num, accent)
        box_lines(
            draw,
            box,
            [(title, F_H(), C_TEXT), (l1, F_B(), C_SUB), (l2, F_B(), C_SUB)],
            gap=14,
            y_offset=12,
        )
        if i < 4:
            arrow_right(draw, x + card_w, (top + bottom) // 2, x + card_w + gap, accent)

    bar = (48, 528, 1232, 612)
    card(draw, bar, GREEN_SOFT, GREEN_BD, radius=12)
    box_lines(
        draw,
        bar,
        [
            ("规则可复现：512–32768 字节，默认 8000 · 超限先截断，仍放不下则跳过 · ready / empty", F_B(), GREEN),
            ("排序负责谁靠前，准入负责谁能进视图，预算负责最终放得下多少", F_S(), C_SUB),
        ],
        gap=8,
    )
    return img


def revision_versions() -> list[tuple]:
    return [
        ("memory/entry@1", "已停用", "退出检索面 · 仍可读", BLUE_SOFT, BLUE_BD, BLUE),
        ("memory/entry@2", "历史版本", "被视图精确引用", ORANGE_SOFT, ORANGE_BD, ORANGE),
        ("memory/entry@3", "当前头", "参与检索与默认注入", GREEN_SOFT, GREEN_BD, GREEN),
    ]


def render_revision() -> Image.Image:
    img, draw = new_slide("修订链与精确引用", "修订产生新版本，旧版本保持可读，引用始终锚定具体版本，不会悄悄漂移")

    left, top, card_w, card_h, gap = 64, 148, 300, 196, 86
    centers = []
    for i, (name, state, desc, fill, bd, accent) in enumerate(revision_versions()):
        x = left + i * (card_w + gap)
        box = (x, top, x + card_w, top + card_h)
        card(draw, box, fill, bd)
        box_lines(draw, box, [(name, F_EN(), accent), (state, F_H(), C_TEXT), (desc, F_B(), C_SUB)], gap=12)
        centers.append(x + card_w // 2)
        if i < 2:
            arrow_right(draw, x + card_w, top + card_h // 2, x + card_w + gap, GRAY, "revise")

    cite = (left + card_w + gap, 396, left + 2 * card_w + gap, 548)
    card(draw, cite, PURPLE_SOFT, PURPLE_BD)
    box_lines(
        draw,
        cite,
        [
            ("精确引用", F_H(), PURPLE),
            ("某次请求的视图锚定 @2", F_B(), C_TEXT),
            ("读取该版本全文即可核验", F_S(), C_SUB),
        ],
        gap=8,
    )
    arrow_down(draw, centers[1], top + 196, 396, ORANGE)

    note_l = (64, 396, 340, 548)
    note_r = (940, 396, 1216, 548)
    card(draw, note_l, GRAY_SOFT, GRAY_BD)
    box_lines(draw, note_l, [("停用 ≠ 删除", F_H(), C_TEXT), ("历史保留，审计可回看", F_B(), C_SUB)], gap=10)
    card(draw, note_r, GRAY_SOFT, GRAY_BD)
    box_lines(draw, note_r, [("引用不会漂移", F_H(), C_TEXT), ("冲突可见，解决过程可回滚", F_B(), C_SUB)], gap=10)
    return img


def save(image: Image.Image, name: str) -> Path:
    path = ROOT / name
    image.convert("RGBA").save(path, "PNG", optimize=True)
    return path


def main() -> None:
    save(render_assembly(), "I6-01-context-assembly.png")
    save(render_budget(), "I6-02-budget-funnel.png")
    save(render_revision(), "I6-03-revision-citation.png")


if __name__ == "__main__":
    main()
