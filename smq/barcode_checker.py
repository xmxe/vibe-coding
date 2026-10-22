# -*- coding: utf-8 -*-
"""
扫码顺序比对工具
================
原理：扫码枪在出厂默认的 "HID 键盘模拟" 模式下等同于一个键盘，
扫一下 = 自动输入一串字符 + 回车。因此程序不需要任何驱动或 SDK，
只要让界面上的输入框保持焦点，有线 USB / 2.4G 无线 / 蓝牙扫码枪都能直接用。

比对逻辑：
    Excel 中某一列按行号构成"期望顺序表"。
    第 1 次扫码必须与第 1 条一致，第 2 次必须与第 2 条一致……
    任意一次不一致立即红色提示 + 声音报警，并且【不推进序号】，可重新扫描。
"""

import csv
import json
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

try:
    import winsound  # Windows 自带，用于报警音
except ImportError:  # 非 Windows 平台退化处理
    winsound = None

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None  # 运行时在界面上提示 pip install openpyxl

# ---------------- 路径与常量 ----------------
if getattr(sys, "frozen", False):  # PyInstaller 打包后
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
ALARM_WAV = os.path.join(BASE_DIR, "alarm.wav")  # 可选：自定义报警音，放程序同目录即可
DUP_INTERVAL = 0.5  # 0.5 秒内扫到相同码视为扫码枪误触发，忽略


def norm(v):
    """Excel 单元格 -> 规整字符串：去首尾空白；12.0 -> '12'"""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


# ---------------- 声音 ----------------
def _alarm_worker():
    if winsound is None:
        print("\a[ALARM]")
        return
    if os.path.exists(ALARM_WAV):
        winsound.PlaySound(ALARM_WAV, winsound.SND_FILENAME | winsound.SND_SYNC)
    else:  # 无自定义音频时：三短促蜂鸣
        for _ in range(3):
            winsound.Beep(1600, 120)
            winsound.Beep(800, 120)


def _ok_worker():
    if winsound:
        winsound.Beep(1200, 80)


def alarm_async():
    threading.Thread(target=_alarm_worker, daemon=True).start()


def ok_beep_async():
    threading.Thread(target=_ok_worker, daemon=True).start()


# ---------------- 主程序 ----------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("扫码顺序比对工具")
        self.geometry("820x640")
        self.minsize(720, 520)

        self.expected = []   # 期望顺序表（来自 Excel）
        self.index = 0       # 当前应扫位置（0 起）
        self._last_code = ""
        self._last_time = 0.0
        self._dialog_open = False
        self._refocus_job = None
        self._log_file = None
        self._csv = None
        # CTkComboBox 不支持 ["values"] 下标取值，用 Python 列表记录当前可选值
        self._sheet_values = []
        self._col_values = []

        self._build_ui()
        self._load_config()
        self.scan_entry.focus_set()

    # ---------- 界面（customtkinter 现代组件） ----------
    def _build_ui(self):
        # 顶栏：文件选择
        top = ctk.CTkFrame(self, corner_radius=8)
        top.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(top, text="Excel 文件：", width=90, anchor="w").pack(side="left", padx=(8, 4))
        self.path_var = tk.StringVar()
        ctk.CTkEntry(top, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(top, text="浏览…", width=100, command=self.choose_file).pack(side="left", padx=(4, 8))

        # 参数栏：工作表 / 比对列 / 加载 / 提示音
        mid = ctk.CTkFrame(self, corner_radius=8)
        mid.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(mid, text="工作表：", width=50, anchor="w").pack(side="left", padx=(8, 4))
        self.sheet_var = tk.StringVar()
        self.sheet_box = ctk.CTkComboBox(mid, variable=self.sheet_var, width=180,
                                         command=lambda v: self._on_sheet_selected())
        self.sheet_box.pack(side="left", padx=4)

        ctk.CTkLabel(mid, text="比对列：", width=50, anchor="w").pack(side="left", padx=(8, 4))
        self.col_var = tk.StringVar()
        self.col_box = ctk.CTkComboBox(mid, variable=self.col_var, width=220,
                                       command=lambda v: self._on_col_selected())
        self.col_box.pack(side="left", padx=4)

        ctk.CTkButton(mid, text="加载数据", width=110, command=self.load_data).pack(side="left", padx=6)
        self.ok_beep_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(mid, text="正确时提示音", variable=self.ok_beep_var).pack(side="left", padx=8)

        # 全局点击后回收焦点（保留之前的焦点守护逻辑）
        self.bind_all("<Button-1>", lambda e: self.after(150, self._post_click_refocus))

        # 扫码输入框
        self.scan_var = tk.StringVar()
        self.scan_entry = ctk.CTkEntry(self, textvariable=self.scan_var,
                                       font=ctk.CTkFont(family="Consolas", size=24))
        self.scan_entry.pack(fill="x", padx=12, pady=(12, 4))
        self.scan_entry.bind("<Return>", self.on_scan)
        self.scan_entry.bind("<FocusOut>", self._on_focus_out)

        # 状态横幅（tk.Label 换成 CTkLabel，颜色由 _set_status 动态设置）
        self.status_lbl = ctk.CTkLabel(self, text="请先选择 Excel 并加载数据",
                                       font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold"),
                                       fg_color="#D4DCE7", height=50, corner_radius=8)
        self.status_lbl.pack(fill="x", padx=12, pady=8)

        # 进度 / 当前应扫
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(fill="x", padx=12, pady=4)
        self.progress_var = tk.StringVar(value="进度: 0 / 0")
        ctk.CTkLabel(info, textvariable=self.progress_var,
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold")).pack(side="left")
        self.expect_var = tk.StringVar(value="当前应扫: -")
        ctk.CTkLabel(info, textvariable=self.expect_var,
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=11)).pack(side="left", padx=24)

        # 日志区（CTkTextbox 内置垂直滚动条）
        logf = ctk.CTkFrame(self, corner_radius=8)
        logf.pack(fill="both", expand=True, padx=12, pady=6)
        self.log_box = ctk.CTkTextbox(logf, font=ctk.CTkFont(family="Consolas", size=10),
                                       state="disabled", wrap="none", corner_radius=8)
        self.log_box.pack(fill="both", expand=True)

        # 底部操作按钮
        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="x", padx=12, pady=6)
        ctk.CTkButton(bot, text="跳过当前(慎用)", width=130, command=self.skip_current).pack(side="left")
        ctk.CTkButton(bot, text="重置进度", width=100, command=self.reset_progress).pack(side="left", padx=6)
        ctk.CTkButton(bot, text="打开日志目录", width=110, command=self.open_log_dir).pack(side="left", padx=6)

    # ---------- Excel 加载 ----------
    def choose_file(self):
        if load_workbook is None:
            messagebox.showerror("缺少依赖", "未安装 openpyxl，请先执行:\n\npip install openpyxl")
            return
        self._dialog_open = True
        try:
            path = filedialog.askopenfilename(
                title="选择 Excel 文件",
                filetypes=[("Excel 文件", "*.xlsx *.xlsm *.xltx *.xltm")])
        finally:
            self._dialog_open = False
        if path:
            self.path_var.set(path)
            self._load_sheets(path)
            self.after(50, self._refocus_entry)  # 选完文件后焦点还给输入框

    def _open_wb(self, path):
        return load_workbook(path, read_only=True, data_only=True)

    def _load_sheets(self, path):
        try:
            wb = self._open_wb(path)
            names = wb.sheetnames
            wb.close()
        except Exception as e:
            messagebox.showerror("打开失败", f"无法读取 Excel:\n{e}")
            return
        self.sheet_box.configure(values=names)
        self._sheet_values = names
        if names:
            self.sheet_var.set(names[0])
            self._load_columns()

    def _load_columns(self):
        """读取所选工作表第一行作为列名，填入比对列下拉框"""
        try:
            wb = self._open_wb(self.path_var.get())
            ws = wb[self.sheet_var.get()]
            headers = []
            for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
                headers = [norm(v) for v in row]
            wb.close()
        except Exception as e:
            messagebox.showerror("读取失败", str(e))
            return
        headers = [h if h else f"第{i + 1}列" for i, h in enumerate(headers)]
        self.col_box.configure(values=headers)
        self._col_values = headers
        if headers:
            self.col_var.set(headers[0])

    def load_data(self):
        path, sheet, colname = self.path_var.get(), self.sheet_var.get(), self.col_var.get()
        if not (path and sheet and colname):
            messagebox.showwarning("提示", "请选择 Excel 文件、工作表和比对列")
            return
        try:
            wb = self._open_wb(path)
            ws = wb[sheet]
            row_iter = ws.iter_rows(values_only=True)
            header_row = next(row_iter, None)
            if header_row is None:
                wb.close()
                messagebox.showwarning("提示", "该工作表为空，没有表头行")
                return
            headers = [norm(v) for v in header_row]
            headers = [h if h else f"第{i + 1}列" for i, h in enumerate(headers)]
            col_idx = headers.index(colname)
            data = []
            num_warnings = 0  # 加载过程中超长数字码警告次数
            for rno, row in enumerate(row_iter, start=2):
                if col_idx < len(row):
                    cell = row[col_idx]
                    v = norm(cell)
                    if v:
                        # 检测到单元格为数字且位数 >=16，提醒精度可能丢失
                        if isinstance(cell, float) and cell != int(cell):
                            pass  # 小数直接当字符串处理
                        elif isinstance(cell, (int, float)):
                            if len(str(int(float(cell)))) >= 16:
                                num_warnings += 1
                                if num_warnings <= 3:  # 最多报 3 次
                                    self.log(f"[警告] 第{rno}行条码以数值存储「{v}」，≥16位可能失真，建议设为文本格式")
                        data.append(v)
            wb.close()
        except Exception as e:
            messagebox.showerror("加载失败", str(e))
            return
        if not data:
            messagebox.showwarning("提示", "该列没有可用数据")
            return

        self.expected = data
        self.index = 0
        self._last_code = ""
        self._last_time = 0.0
        self._open_log()
        self._save_config()
        self.log_box.delete("1.0", tk.END)
        self._set_status("数据已加载，等待扫描…", "#1e88e5")
        self._update_progress()
        self.log(f"已加载 {len(data)} 条数据（{os.path.basename(path)} / {sheet} / {colname}）", to_file=False)
        self.scan_entry.focus_set()

    # ---------- 扫码处理（核心逻辑） ----------
    def on_scan(self, event=None):
        code = self.scan_var.get().strip()
        self.scan_var.set("")  # 立即清空，准备下一枪
        if not code:
            return
        if not self.expected:
            self._set_status("尚未加载 Excel 数据！", "#e53935")
            return

        now = time.time()
        if code == self._last_code and now - self._last_time < DUP_INTERVAL:
            self.log(f"[忽略] 重复触发: {code}")
            return
        self._last_code, self._last_time = code, now

        if self.index >= len(self.expected):
            self._set_status(f"清单已全部完成，多扫: {code}", "#fb8c00")
            self.log(f"[超额] {code}（清单已完成）")
            alarm_async()
            return

        expected = self.expected[self.index]
        if code == expected:
            self.index += 1
            self.log(f"[OK] 第{self.index}项 {code}")
            if self.ok_beep_var.get():
                ok_beep_async()
            if self.index >= len(self.expected):
                self._set_status("✔ 全部比对完成！", "#43a047")
            else:
                self._set_status(f"✔ 正确 (第{self.index}项)", "#43a047")
            self._update_progress()
        else:
            hint = self._find_hint(code)
            self._set_status(f"✘ 不一致！应扫[{expected}] 实扫[{code}]", "#e53935")
            self.log(f"[错误] 第{self.index + 1}项 期望[{expected}] 实扫[{code}]{hint}")
            alarm_async()
            # 注意：不一致时【不推进序号】，操作员重新扫正确的码即可

    def _find_hint(self, code):
        """提示这个码在清单里的位置，便于排查是拿错货还是顺序错"""
        pos = [i + 1 for i, v in enumerate(self.expected) if v == code]
        if not pos:
            return "；该码不在清单中"
        shown = pos[:5]
        suffix = "…" if len(pos) > 5 else ""
        return f"；该码在清单第{','.join(map(str, shown))}位{suffix}"

    # ---------- 辅助操作 ----------
    def skip_current(self):
        if self.expected and self.index < len(self.expected):
            skipped = self.expected[self.index]
            self.index += 1
            self.log(f"[跳过] 第{self.index}项 {skipped}")
            self._update_progress()
            self._set_status(f"已跳过第{self.index}项", "#fb8c00")
        self.scan_entry.focus_set()

    def reset_progress(self):
        if not self.expected:
            return
        self._dialog_open = True
        try:
            yes = messagebox.askyesno("确认", "将比对进度清零，从头开始？")
        finally:
            self._dialog_open = False
        if yes:
            self.index = 0
            self._last_code, self._last_time = "", 0.0  # 清防连发状态，避免重置后立即重扫被误忽略
            self._update_progress()
            self._set_status("已重置，等待扫描…", "#1e88e5")
            self.log("---- 进度已重置 ----")
        self.scan_entry.focus_set()

    def open_log_dir(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        try:
            os.startfile(LOG_DIR)  # Windows
        except AttributeError:
            pass
        self.scan_entry.focus_set()

    # ---------- 状态与日志 ----------
    def _set_status(self, text, color):
        self.status_lbl.configure(text=text, fg_color=color)

    def _update_progress(self):
        self.progress_var.set(f"进度: {self.index} / {len(self.expected)}")
        nxt = self.expected[self.index] if self.index < len(self.expected) else "-"
        self.expect_var.set(f"当前应扫: {nxt}")

    def log(self, msg, to_file=True):
        # CTkTextbox 是只读状态，写入前需临时解锁
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, f"{datetime.now():%H:%M:%S}  {msg}\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")
        # 落盘（原逻辑保留，不删减）
        if to_file and self._csv:
            self._csv.writerow([f"{datetime.now():%Y-%m-%d %H:%M:%S}", msg])
            self._log_file.flush()

    def _open_log(self):
        self._close_log()
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(LOG_DIR, f"scan_{datetime.now():%Y%m%d_%H%M%S}.csv")
        # utf-8-sig 让 Excel 直接双击打开不乱码
        self._log_file = open(path, "a", newline="", encoding="utf-8-sig")
        self._csv = csv.writer(self._log_file)
        self._csv.writerow(["时间", "结果"])

    def _close_log(self):
        if self._log_file:
            try:
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None
            self._csv = None

    # ---------- 焦点保持 ----------
    # 不能一失焦就立刻抢回焦点：点工作表/比对列下拉框时，弹出的列表会因焦点被
    # 强行夺走而瞬间收起，导致没法选择。改为 200ms 后检查鼠标位置：
    # 鼠标停在下拉框/按钮/日志列表/下拉弹窗上 = 用户正在操作界面，不抢焦点；
    # 否则才把焦点还给输入框，保证扫码枪随时能"打"进来。
    _INTERACTIVE = (ctk.CTkComboBox, ctk.CTkButton, ctk.CTkCheckBox)

    def _on_focus_out(self, event=None):
        if self._dialog_open:
            return
        if self._refocus_job:
            self.after_cancel(self._refocus_job)
        self._refocus_job = self.after(200, self._try_refocus)

    def _safe_focus_check(self):
        """安全地尝试夺回焦点（带异常保护）"""
        if self._dialog_open:
            return
        try:
            x, y = self.winfo_pointerx(), self.winfo_pointery()
            w = self.winfo_containing(x, y)
        except Exception:
            return
        if w is not None:
            try:
                # 鼠标在下拉弹窗（独立 Toplevel）或其它窗口上：不抢焦点
                if w.winfo_toplevel() is not self:
                    return
            except Exception:
                return
            if isinstance(w, self._INTERACTIVE):
                return            # 还在按钮/下拉框上，先放过
        self.scan_entry.focus_set()

    def _try_refocus(self):
        self._refocus_job = None
        self._safe_focus_check()

    def _post_click_refocus(self):
        """150ms 后安全地尝试夺回焦点——此时 ComboBox 弹窗应已关闭"""
        self._safe_focus_check()

    def _refocus_entry(self):
        """延迟把焦点还给输入框（下拉框选择完成、选完文件等场景用）"""
        if not self._dialog_open:
            self.scan_entry.focus_set()

    def _on_sheet_selected(self):
        self._load_columns()
        self.after(50, self._refocus_entry)

    def _on_col_selected(self, event=None):
        """选择比对列后：立即用新列重新加载数据，使选择立即生效"""
        if self.path_var.get() and self.sheet_var.get():
            # 用下拉框当前值同步 textvariable，避免事件先后导致读到旧列
            self.col_var.set(self.col_box.get())
            self.load_data()
        self.after(50, self._refocus_entry)

    # ---------- 配置记忆 ----------
    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"excel": self.path_var.get(),
                           "sheet": self.sheet_var.get(),
                           "column": self.col_var.get()}, f, ensure_ascii=False)
        except OSError:
            pass

    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            return
        path = cfg.get("excel", "")
        if path and os.path.exists(path) and load_workbook:
            self.path_var.set(path)
            self._load_sheets(path)
            if cfg.get("sheet") in (self._sheet_values or []):
                self.sheet_var.set(cfg["sheet"])
                self._load_columns()
            if cfg.get("column") in (self._col_values or []):
                self.col_var.set(cfg["column"])

    def on_close(self):
        self._close_log()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
