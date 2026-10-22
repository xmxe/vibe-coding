# -*- coding: utf-8 -*-
"""
# 运行前请确保安装依赖：
#     pip install playwright pypdf
#     playwright install chromium
#
主程序入口：输入天数 N，自动完成「生成 N 份 HTML -> 合并成一个完整 PDF」。
"""

import os
from math_generator import DayData
from html_template import build_html

# 让控制台稳定输出中文/特殊符号（Windows 默认 GBK 会报错）
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(OUTPUT_DIR, "html")


def generate(day: int, out_dir: str = OUTPUT_DIR) -> str:
    data = DayData(day_num=day)
    html = build_html(data)
    os.makedirs(HTML_DIR, exist_ok=True)
    path = os.path.join(HTML_DIR, f"worksheet_{day:02d}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def export_to_pdf(num_days: int, out_dir: str = OUTPUT_DIR,
                 pdf_name: str = "三年级口算练习册_全册.pdf") -> str:
    """用 Playwright 把所有 HTML 逐个渲染并合并成一个完整的 PDF。

    步骤：
      1. 启动 Chromium；
      2. 遍历 1..num_days，打开本地 worksheet_XX.html；
      3. 调用 page.pdf() 得到当前页的 PDF 字节流；
      4. 用 pypdf 把每个字节流追加到全局 PDF 文件中；
      5. 保存为 三年级口算练习册_全册.pdf。
    """
    from playwright.sync_api import sync_playwright
    from pypdf import PdfWriter, PdfReader
    import io
    import tempfile
    import os as _os

    writer = PdfWriter()
    tmp_dir = tempfile.mkdtemp(prefix="ws_pdf_")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        for day in range(1, num_days + 1):
            html_path = os.path.join(HTML_DIR, f"worksheet_{day:02d}.html")
            if not os.path.exists(html_path):
                print(f"  [跳过] 未找到 {os.path.basename(html_path)}，请先运行生成流程")
                continue

            page.goto("file://" + os.path.abspath(html_path))
            page.wait_for_load_state("networkidle")

            temp_pdf_path = _os.path.join(tmp_dir, f"_day_{day:02d}.pdf")
            page.pdf(
                path=temp_pdf_path,
                format="A4",
                print_background=True,
                display_header_footer=False,
                prefer_css_page_size=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )

            # 追加当前页到全局 PDF
            page_pdf = PdfReader(temp_pdf_path)
            for src_page in page_pdf.pages:
                writer.add_page(src_page)

            print(f"  [完成] 第 {day:02d} 天 -> {len(page_pdf.pages)} 页")
            _os.remove(temp_pdf_path)

            # 页数校验：0 页 = 报错；>1 页 = 仅提示（不影响合并）
            if len(page_pdf.pages) == 0:
                print(f"  [错误] 第 {day:02d} 天生成 0 页，请检查 HTML 是否完整。")
            elif len(page_pdf.pages) > 1:
                print(f"  [提示] 第 {day:02d} 天内容较多，占用 {len(page_pdf.pages)} 页。")

        browser.close()

    # 清理临时文件
    for f in _os.listdir(tmp_dir):
        _os.remove(_os.path.join(tmp_dir, f))
    _os.rmdir(tmp_dir)

    out_path = os.path.join(out_dir, pdf_name)
    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"成功合并 {num_days} 天为 {pdf_name}，共 {len(writer.pages)} 页。")
    return out_path


def main():
    print("=== 三年级上册数学计算思维每日一练 · 一键生成 ===")
    raw = input("请输入需要生成的练习册天数：").strip()
    try:
        n = int(raw)
    except ValueError:
        print("请输入一个正整数天数。")
        return
    if n <= 0:
        print("天数必须大于 0。")
        return

    # 1. 自动生成 N 份 HTML
    print(f"\n[1/2] 正在生成 {n} 份 HTML 练习册 ...")
    for day in range(1, n + 1):
        path = generate(day)
        print(f"  已生成：{os.path.basename(path)}")
    print(f"HTML 全部生成完毕。")

    # 2. 无缝自动调用 PDF 导出（无需用户确认）
    print(f"\n[2/2] 正在自动合并 PDF ...")
    try:
        pdf_path = export_to_pdf(n)
        print(f"\n[完成] 全流程成功！最终文件：{pdf_path}")
    except ModuleNotFoundError as e:
        missing = str(e).split("'")[-1]
        print(f"\n[错误] 缺少依赖库：{missing}")
        print("   请先在终端安装依赖再运行：")
        print("       pip install playwright pypdf")
        print("       playwright install chromium")
    except Exception as e:
        print(f"\n[错误] PDF 生成失败：{e}")
        print("   常见原因：未执行 'playwright install chromium' 下载浏览器内核。")
        print("   请在终端运行：")
        print("       playwright install chromium")
        print("   然后再重新运行本程序。")


if __name__ == "__main__":
    main()
