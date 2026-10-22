# -*- coding: utf-8 -*-
"""HTML/CSS 渲染模板：把 DayData 渲染成可打印的 A4 练习册"""

from math_generator import DayData

# 自适应排版：根据题量动态计算留白（min-height）
A4_HEIGHT_MM = 297
PAD_TOP_MM = 10
PAD_BOTTOM_MM = 10
MM_TO_PX = 96 / 25.4

def _usable_px():
    return (A4_HEIGHT_MM - PAD_TOP_MM - PAD_BOTTOM_MM) * MM_TO_PX

def _fixed_content_px(data):
    row = 1.8 * 15
    gap = 4
    h = 4 * (8 + 6 + row)
    k_rows = (len(data.kousan) + 3) // 4
    h += k_rows * row + (k_rows - 1) * gap
    s_rows = (len(data.shiki) + 3) // 4
    h += s_rows * row
    t_rows = (len(data.tuoshi) + 1) // 2
    h += t_rows * row
    h += len(data.solving) * (row + row)
    return h

def _compute_spacing(data):
    budget = max(_usable_px() - _fixed_content_px(data), 0)
    w = {'shiki': 3.0, 'tuoshi': 2.0, 'solve': 1.5}
    tot_w = sum(w.values())
    space = {k: budget * weight / tot_w for k, weight in w.items()}
    # 上限收紧，保证固定内容+留白总高 ≤ A4 可用高度(约1047px)
    clamp = {'shiki': (36, 72), 'tuoshi': (24, 56), 'solve': (30, 60)}
    for k in space:
        lo, hi = clamp[k]
        space[k] = int(round(max(lo, min(hi, space[k]))))
    return space



# ---- 行辅助：口算/竖式/脱式/应用 各部分转成 HTML 行 ----
def _render_kousan(kousan):
    items = []
    for i, q in enumerate(kousan, 1):
        items.append(f'<div class="cell">{q}</div>')
    return "\n".join(items)


def _render_shiki(shiki):
    items = []
    for i, q in enumerate(shiki, 1):
        items.append(
            f'<div class="cell"><div class="q">{i}. {q}</div>'
            f'<div class="space-shiki"></div></div>'
        )
    return "\n".join(items)


def _render_tuoshi(tuoshi):
    items = []
    for i, q in enumerate(tuoshi, 1):
        items.append(
            f'<div class="cell"><div class="q">{q}</div>'
            f'<div class="space-tuoshi"></div></div>'
        )
    return "\n".join(items)


def _render_solving(solving):
    items = []
    for i, q in enumerate(solving, 1):
        items.append(
            f'<div class="solve-block">'
            f'<div class="q">{i}. {q}</div>'
            f'<div class="space-solve"></div>'
            f'<div class="ans-line">答：{"_" * 30}。</div>'
            f'</div>'
        )
    return "\n".join(items)


# ---- 完整页面 ----
def build_html(data: DayData) -> str:
    space = _compute_spacing(data)
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>新三年级上册数学计算思维每日一练(第 {data.day_num} 天)</title>
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Microsoft YaHei", "SimHei", sans-serif;
    font-size: 15px;
    color: #000;
    background: #f5f5f5;
    margin: 0;
  }}
  .page-container {{
    width: 210mm;
    min-height: 297mm;
    height: auto;
    overflow: visible;
    box-sizing: border-box;
    margin: 0 auto;
    background: #fff;
    padding: 10mm;
  }}

  .section-title {{
    font-size: 18px;
    font-weight: bold;
    border-left: 5px solid #000;
    padding-left: 8px;
    margin: 8px 0 6px;
  }}

  .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px 16px; }}
  .grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px 24px; }}

  .cell .num {{ display: inline-block; min-width: 24px; }}
  .cell {{ line-height: 1.8; }}

  .space-shiki {{ min-height: {space['shiki']}px; }}
  .space-tuoshi {{ min-height: {space['tuoshi']}px; }}
  .space-solve {{ min-height: {space['solve']}px; }}

  .solve-block {{ margin-bottom: 4px; }}
  .q {{ font-weight: bold; }}
  .ans-line {{ margin-top: 4px; letter-spacing: 1px; }}

  @media print {{
    body {{ background: #fff; margin: 0; padding: 0; }}
    .page-container {{
      page-break-after: always;
      page-break-inside: avoid;
    }}
  }}
</style>
</head>
<body>
<div class="page-container">
  <div class="section-title">一、口算题</div>
  <div class="grid-4">
{_render_kousan(data.kousan)}
  </div>

  <div class="section-title">二、列竖式计算</div>
  <div class="grid-4">
{_render_shiki(data.shiki)}
  </div>

  <div class="section-title">三、脱式计算</div>
  <div class="grid-2">
{_render_tuoshi(data.tuoshi)}
  </div>

  <div class="section-title">四、解决问题</div>
{_render_solving(data.solving)}
</div>
</body>
</html>
"""
    return page


def build_all_html(pages: list) -> str:
    """把多份 DayData 拼成带分页标记的完整 HTML"""
    body_parts = []
    for i, data in enumerate(pages, 1):
        page_html = build_html(data)
        # 抽出 .page-container 内的 body 内容
        import re
        m = re.search(r'(<div class="page-container">.*?</div>\n</body>)', page_html, re.DOTALL)
        inner = m.group(1).replace('</body>', '')
        # 每天一张独立 A4，.page-container 自身带 page-break-after:always，
        # 多份连排时每份都独立占一页
        body_parts.append(inner)
    css = _extract_css(pages[0])
    head = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>新三年级上册数学计算思维每日一练</title>
<style>
{css}
</style>
</head>
<body>
"""
    tail = "</body>\n</html>\n"
    return head + "\n".join(body_parts) + tail


def _extract_css(sample_page_html):
    import re
    m = re.search(r'<style>(.*?)</style>', sample_page_html, re.DOTALL)
    return m.group(1) if m else ""
