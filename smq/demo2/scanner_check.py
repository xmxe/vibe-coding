# -*- coding: utf-8 -*-

"""
扫码顺序比对工具

功能：
1. 读取 Excel / CSV 文件中的条码顺序；
2. 扫码枪扫一次条码，立刻比对一次；
3. 条码正确：记录日志，进入下一个；
4. 条码错误：记录日志，并发出报警声；
5. 支持跳过当前、回退一个、重置进度；
6. 每次扫码结果写入 scan_log.csv 日志。

依赖：
    pip install openpyxl

说明：
    扫码枪需要配置为 USB HID 键盘模式，并且扫码结束后发送回车键。
"""

import csv
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import winsound
except ImportError:
    winsound = None


LOG_FILE = "scan_log.csv"


def cell_to_str(value):
    """
    将 Excel 单元格内容转换为字符串。
    特别注意：
    如果 Excel 把条码识别成数字，可能丢失前导零或精度。
    所以条码列最好在 Excel 中设置为文本格式。
    """
    if value is None:
        return ""

    if isinstance(value, bool):
        return str(value).strip()

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    return str(value).strip()


def load_barcodes_from_excel(path, header_row=True, barcode_col=1):
    """
    从 xlsx / xlsm 文件读取条码列。
    barcode_col 从 1 开始，即：
    1 表示第一列；
    2 表示第二列。
    """
    if openpyxl is None:
        raise RuntimeError("缺少 openpyxl，请先执行：pip install openpyxl")

    if barcode_col < 1:
        raise ValueError("条码列必须大于等于 1")

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    start_row = 2 if header_row else 1

    barcodes = []
    for row in ws.iter_rows(
        min_row=start_row,
        min_col=barcode_col,
        max_col=barcode_col,
        values_only=True
    ):
        text = cell_to_str(row[0])
        if text:
            barcodes.append(text)

    wb.close()
    return barcodes


def load_barcodes_from_csv(path, header_row=True, barcode_col=1):
    """
    从 csv / txt 文件读取条码列。
    barcode_col 从 1 开始。
    """
    if barcode_col < 1:
        raise ValueError("条码列必须大于等于 1")

    encodings = ["utf-8-sig", "gbk", "latin-1"]
    last_error = None

    for encoding in encodings:
        try:
            with open(path, "r", newline="", encoding=encoding) as f:
                reader = csv.reader(f)
                rows = list(reader)

            start_index = 1 if header_row else 0
            barcodes = []

            for row in rows[start_index:]:
                if not row:
                    continue

                col_index = barcode_col - 1
                if col_index < len(row):
                    text = row[col_index].strip()
                    if text:
                        barcodes.append(text)

            return barcodes

        except UnicodeDecodeError as e:
            last_error = e
            continue

    raise last_error if last_error else RuntimeError("无法读取 CSV 文件")


def load_barcodes_from_file(path, header_row=True, barcode_col=1):
    """
    根据文件后缀自动选择读取方式。
    支持：
        .xlsx
        .xlsm
        .csv
        .txt
    """
    ext = os.path.splitext(path)[1].lower()

    if ext in [".csv", ".txt"]:
        return load_barcodes_from_csv(path, header_row, barcode_col)

    if ext in [".xlsx", ".xlsm"]:
        return load_barcodes_from_excel(path, header_row, barcode_col)

    raise RuntimeError(
        "暂不支持该文件格式。\n"
        "请将文件另存为 .xlsx、.xlsm、.csv 或 .txt。"
    )


def append_scan_log(seq, expected, actual, result):
    """
    写入扫码日志。
    日志文件：scan_log.csv
    """
    try:
        file_exists = os.path.exists(LOG_FILE)

        with open(LOG_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow([
                    "时间",
                    "当前序号",
                    "期望条码",
                    "实际条码",
                    "结果"
                ])

            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                seq,
                expected,
                actual,
                result
            ])
    except Exception:
        # 日志写入失败不影响主流程
        pass


def play_error_sound(times=3):
    """
    播放错误报警声。
    Windows 下使用 winsound.Beep。
    非 Windows 下使用系统终端响铃。
    """
    for _ in range(times):
        if winsound is not None:
            try:
                winsound.Beep(1200, 250)
            except Exception:
                print("\a", end="", flush=True)
        else:
            print("\a", end="", flush=True)

        time.sleep(0.08)


def play_finish_sound():
    """
    全部完成提示音。
    """
    if winsound is not None:
        try:
            winsound.Beep(800, 200)
            time.sleep(0.05)
            winsound.Beep(1000, 200)
            time.sleep(0.05)
            winsound.Beep(1200, 300)
        except Exception:
            print("\a", end="", flush=True)
    else:
        print("\a", end="", flush=True)


class ScannerApp:
    def __init__(self, root):
        self.root = root
        root.title("扫码顺序比对工具")
        root.geometry("980x620")

        # 条码列表
        self.barcodes = []

        # 当前应该扫第几个，从 0 开始
        self.index = 0

        # 统计
        self.ok_count = 0
        self.err_count = 0

        # 焦点守护 / 防连发 状态
        self._dialog_open = False
        self._refocus_job = None
        self._last_code = ""
        self._last_time = 0.0

        # 界面变量
        self.file_path = tk.StringVar()
        self.col_var = tk.IntVar(value=1)
        self.header_var = tk.BooleanVar(value=True)
        self.ignore_case_var = tk.BooleanVar(value=False)
        self.sound_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="请先选择并加载条码清单")

        self.build_ui()

        # 扫码枪通常最后会发送回车，因此绑定回车事件
        self.scan_entry.bind("<Return>", self.on_scan)
        self.scan_entry.bind("<KP_Enter>", self.on_scan)
        self.scan_entry.bind("<FocusOut>", self._on_focus_out)

        # 启动后焦点放到扫码输入框
        self.scan_entry.focus_set()

        if openpyxl is None:
            self.log("警告：未检测到 openpyxl，.xlsx 文件将无法读取。")
            self.log("请先执行：pip install openpyxl")

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # =========================
        # 文件选择区
        # =========================
        file_frame = ttk.Frame(main)
        file_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(file_frame, text="条码文件：").pack(side=tk.LEFT)

        ttk.Entry(
            file_frame,
            textvariable=self.file_path
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        ttk.Button(
            file_frame,
            text="浏览...",
            command=self.choose_file
        ).pack(side=tk.LEFT)

        # =========================
        # 参数设置区
        # =========================
        config_frame = ttk.Frame(main)
        config_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(config_frame, text="条码列：").pack(side=tk.LEFT)

        ttk.Spinbox(
            config_frame,
            from_=1,
            to=100,
            width=5,
            textvariable=self.col_var
        ).pack(side=tk.LEFT, padx=(2, 12))

        ttk.Checkbutton(
            config_frame,
            text="首行是表头",
            variable=self.header_var
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Checkbutton(
            config_frame,
            text="忽略大小写",
            variable=self.ignore_case_var
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Checkbutton(
            config_frame,
            text="启用报警声",
            variable=self.sound_var
        ).pack(side=tk.LEFT)

        # =========================
        # 操作按钮区
        # =========================
        button_frame = ttk.Frame(main)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            button_frame,
            text="加载清单",
            command=self.load_list
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            button_frame,
            text="重置进度",
            command=self.reset_progress
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            button_frame,
            text="跳过当前",
            command=self.skip_current
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            button_frame,
            text="回退一个",
            command=self.back_one
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            button_frame,
            text="清空日志",
            command=self.clear_log
        ).pack(side=tk.LEFT)

        # =========================
        # 扫码输入区
        # =========================
        ttk.Label(
            main,
            text="扫码输入框（请保持光标在这里，扫码枪扫码后会自动比对）："
        ).pack(anchor=tk.W)

        self.scan_var = tk.StringVar()
        self.scan_entry = ttk.Entry(
            main,
            textvariable=self.scan_var,
            font=("Consolas", 14)
        )
        self.scan_entry.pack(fill=tk.X, pady=(4, 8))

        # =========================
        # 状态区
        # =========================
        ttk.Label(
            main,
            textvariable=self.status_var,
            foreground="blue"
        ).pack(anchor=tk.W, pady=(0, 8))

        # =========================
        # 日志区
        # =========================
        self.log_text = ScrolledText(
            main,
            height=18,
            state="disabled",
            font=("Consolas", 10)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 全局点击后尝试回收焦点（日志区/滚动条/勾选框点击后不会把焦点永久带走）
        self.root.bind_all("<Button-1>", lambda e: self.root.after(150, self._post_click_refocus))

    def choose_file(self):
        self._dialog_open = True
        try:
            path = filedialog.askopenfilename(
                title="选择条码文件",
                filetypes=[
                    ("表格文件", "*.xlsx *.xlsm *.csv *.txt"),
                    ("Excel 文件", "*.xlsx *.xlsm"),
                    ("CSV 文件", "*.csv *.txt"),
                    ("所有文件", "*.*")
                ]
            )
        finally:
            self._dialog_open = False

        if path:
            self.file_path.set(path)
            self.log(f"已选择文件：{path}")

        self.scan_entry.focus_set()

    def load_list(self):
        path = self.file_path.get().strip()

        if not path:
            messagebox.showwarning("提示", "请先选择条码文件。")
            return

        if not os.path.exists(path):
            messagebox.showerror("错误", "文件不存在，请重新选择。")
            return

        try:
            barcode_col = int(self.col_var.get())
        except Exception:
            messagebox.showerror("错误", "条码列必须是数字。")
            return

        self._dialog_open = True
        try:
            self.barcodes = load_barcodes_from_file(
                path=path,
                header_row=self.header_var.get(),
                barcode_col=barcode_col
            )
        except Exception as e:
            self._dialog_open = False
            messagebox.showerror("加载失败", str(e))
            return
        finally:
            self._dialog_open = False

        self.index = 0
        self.ok_count = 0
        self.err_count = 0
        self.scan_var.set("")
        self._last_code = ""
        self._last_time = 0.0

        self.log("-" * 60)
        self.log(f"加载成功：{os.path.basename(path)}")
        self.log(f"共读取条码数量：{len(self.barcodes)}")

        if len(self.barcodes) == 0:
            self.log("警告：没有读取到条码，请检查条码列和表头设置。")

        self.update_status()
        self.scan_entry.focus_set()

    def reset_progress(self):
        if not self.barcodes:
            self.log("尚未加载条码清单，无法重置。")
            return

        if not messagebox.askyesno("确认", "确定要重置扫码进度吗？"):
            return

        self.index = 0
        self.ok_count = 0
        self.err_count = 0
        self.scan_var.set("")
        self._last_code = ""
        self._last_time = 0.0
        self.log("已重置扫码进度。")
        self.update_status()
        self.scan_entry.focus_set()

    def skip_current(self):
        if not self.barcodes:
            self.log("尚未加载条码清单，无法跳过。")
            return

        if self.index >= len(self.barcodes):
            self.log("当前清单已完成，无需跳过。")
            return

        seq = self.index + 1
        expected = self.barcodes[self.index]

        append_scan_log(seq, expected, "", "SKIP")

        self.index += 1
        self.log(f"[跳过] 第 {seq}/{len(self.barcodes)} 个，原期望条码：{expected}")

        self.update_status()
        self.scan_entry.focus_set()

    def back_one(self):
        if not self.barcodes:
            self.log("尚未加载条码清单，无法回退。")
            return

        if self.index <= 0:
            self.log("已经是第一个，无法回退。")
            return

        self.index -= 1
        # 清除防连发记录，否则回退后立即重扫同一码会被误判为重复
        self._last_code = ""
        self._last_time = 0.0
        self.log(f"[回退] 当前回到第 {self.index + 1}/{len(self.barcodes)} 个。")

        self.update_status()
        self.scan_entry.focus_set()

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def log(self, message):
        self.log_text.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"{timestamp} {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def update_status(self):
        total = len(self.barcodes)

        if total == 0:
            self.status_var.set("未加载条码清单")
        elif self.index >= total:
            self.status_var.set(
                f"已完成 {total}/{total}，OK：{self.ok_count}，NG：{self.err_count}"
            )
        else:
            expected = self.barcodes[self.index]
            self.status_var.set(
                f"等待扫第 {self.index + 1}/{total} 个，"
                f"期望条码：{expected} | OK：{self.ok_count}，NG：{self.err_count}"
            )

        # 保持焦点在扫码输入框
        self.scan_entry.focus_set()

    def on_scan(self, event=None):
        """
        扫码枪输入完成，通常以回车结束。
        每次回车触发一次比对。
        """
        raw = self.scan_var.get().strip()
        self.scan_var.set("")

        if not raw:
            return "break"

        # 去掉不可打印字符，避免扫码枪附加控制字符影响比对
        actual = "".join(ch for ch in raw if ch.isprintable()).strip()

        if not actual:
            return "break"

        # 防连发：0.5 秒内相同内容视为扫码枪误触发，忽略
        now = time.time()
        if actual == self._last_code and now - self._last_time < 0.5:
            return "break"
        self._last_code, self._last_time = actual, now

        if not self.barcodes:
            self.log(f"尚未加载条码清单，但扫到：{actual}")
            if self.sound_var.get():
                threading.Thread(
                    target=play_error_sound,
                    args=(1,),
                    daemon=True
                ).start()
            return "break"

        if self.index >= len(self.barcodes):
            self.log(f"清单已完成，但仍扫到：{actual}")
            if self.sound_var.get():
                threading.Thread(
                    target=play_error_sound,
                    args=(1,),
                    daemon=True
                ).start()
            return "break"

        expected = self.barcodes[self.index]
        seq = self.index + 1

        if self.ignore_case_var.get():
            cmp_actual = actual.upper()
            cmp_expected = expected.upper()
        else:
            cmp_actual = actual
            cmp_expected = expected

        if cmp_actual == cmp_expected:
            append_scan_log(seq, expected, actual, "OK")

            self.index += 1
            self.ok_count += 1

            self.log(f"[OK] 第 {seq}/{len(self.barcodes)} 个：{actual}")

            if self.index >= len(self.barcodes):
                self.log("全部条码扫码完成。")
                threading.Thread(
                    target=play_finish_sound,
                    daemon=True
                ).start()

        else:
            append_scan_log(seq, expected, actual, "NG")

            self.err_count += 1

            self.log(
                f"[NG] 第 {seq}/{len(self.barcodes)} 个顺序不一致！"
                f"期望：{expected}，实际：{actual}"
            )

            if self.sound_var.get():
                threading.Thread(
                    target=play_error_sound,
                    args=(3,),
                    daemon=True
                ).start()

        self.update_status()

        # 阻止回车默认行为
        return "break"

    # ---------- 焦点守护：防止点击日志/滚动条/勾选框后焦点永久离开扫码输入框 ----------
    _INTERACTIVE = (ttk.Button, ttk.Checkbutton, ttk.Spinbox, tk.Spinbox)

    def _on_focus_out(self, event=None):
        if self._dialog_open:
            return
        if self._refocus_job:
            self.root.after_cancel(self._refocus_job)
        self._refocus_job = self.root.after(200, self._try_refocus)

    def _safe_focus_check(self):
        if self._dialog_open:
            return
        try:
            x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        except Exception:
            return
        w = self.root.winfo_containing(x, y)
        if w is not None:
            if w.winfo_toplevel() is not self.root:
                return
            if isinstance(w, self._INTERACTIVE):
                return
        self.scan_entry.focus_set()

    def _try_refocus(self):
        self._refocus_job = None
        self._safe_focus_check()

    def _post_click_refocus(self):
        self._safe_focus_check()


def main():
    root = tk.Tk()
    app = ScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()