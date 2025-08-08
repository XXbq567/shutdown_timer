import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
from datetime import datetime, timedelta

class ShutdownTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("定时关机工具")
        self.root.geometry("360x260")
        self.root.resizable(False, False)

        self.running = False
        self.task = None
        self.lock_ui = False

        # ---------------- 模式变量 ----------------
        self.mode_var = tk.StringVar(value="countdown")  # 默认倒计时
        self.action_var = tk.StringVar(value="shutdown")

        # ---------------- 模式选择 ----------------
        mode_frame = ttk.LabelFrame(root, text="模式选择")
        mode_frame.pack(fill="x", padx=10, pady=5)

        ttk.Radiobutton(mode_frame, text="倒计时", value="countdown",
                        variable=self.mode_var, command=self.switch_mode).pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="指定时间", value="clock",
                        variable=self.mode_var, command=self.switch_mode).pack(side="left", padx=5)

        # ---------------- 时间输入区 ----------------
        self.time_frame = ttk.Frame(root)
        self.time_frame.pack(fill="x", padx=10, pady=5)

        # 倒计时（默认显示）
        self.countdown_frame = ttk.Frame(self.time_frame)
        self.countdown_frame.pack(side="left")
        ttk.Label(self.countdown_frame, text="倒计时 时").pack(side="left")
        self.hour_spin = ttk.Spinbox(self.countdown_frame, from_=0, to=99, width=3)
        self.hour_spin.insert(0, "1")
        self.hour_spin.pack(side="left")
        ttk.Label(self.countdown_frame, text="分").pack(side="left")
        self.min_spin = ttk.Spinbox(self.countdown_frame, from_=0, to=59, width=3)
        self.min_spin.insert(0, "0")
        self.min_spin.pack(side="left")

        # 指定时间（默认隐藏，放右边）
        self.clock_frame = ttk.Frame(self.time_frame)
        self.clock_frame.pack_forget()
        ttk.Label(self.clock_frame, text="目标时间 (HH:MM):").pack(side="left")
        self.clock_entry = ttk.Entry(self.clock_frame, width=8)
        self.clock_entry.insert(0, "23:30")
        self.clock_entry.pack(side="left", padx=5)

        # ---------------- 操作选择 ----------------
        action_frame = ttk.LabelFrame(root, text="执行操作")
        action_frame.pack(fill="x", padx=10, pady=5)
        action_map = [("关机", "shutdown"), ("重启", "restart"), ("睡眠", "sleep"), ("休眠", "hibernate")]
        for txt, val in action_map:
            ttk.Radiobutton(action_frame, text=txt, value=val,
                            variable=self.action_var).pack(side="left", padx=5)

        # ---------------- 按钮 ----------------
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=10)
        self.start_btn = ttk.Button(btn_frame, text="启动", command=self.start_timer)
        self.start_btn.pack(side="left", padx=10)
        self.cancel_btn = ttk.Button(btn_frame, text="取消", command=self.cancel_timer)
        self.cancel_btn.pack(side="left")

        # ---------------- 状态标签 ----------------
        self.status_lbl = ttk.Label(root, text="未启动", foreground="blue")
        self.status_lbl.pack(pady=5)

    # --------------- 界面切换 ---------------
    def switch_mode(self):
        if self.mode_var.get() == "clock":
            self.countdown_frame.pack_forget()
            self.clock_frame.pack(side="left", padx=20)
        else:
            self.clock_frame.pack_forget()
            self.countdown_frame.pack(side="left")

    # --------------- 启动 ---------------
    def start_timer(self):
        if self.lock_ui:
            messagebox.showinfo("提示", "请先取消当前任务后再修改。")
            return

        mode = self.mode_var.get()
        action = self.action_var.get()
        action_name = {"shutdown": "关机", "restart": "重启", "sleep": "睡眠", "hibernate": "休眠"}[action]

        if mode == "clock":
            try:
                target_str = self.clock_entry.get().strip()
                target_time = datetime.strptime(target_str, "%H:%M").time()
                now = datetime.now()
                target_dt = datetime.combine(now.date(), target_time)
                if target_dt <= now:
                    target_dt += timedelta(days=1)
                delta = target_dt - now
                seconds = int(delta.total_seconds())
                confirm_text = f"确定要在 {target_str} 执行【{action_name}】吗？"
            except ValueError:
                messagebox.showerror("错误", "时间格式应为 HH:MM")
                return
        else:
            try:
                h = int(self.hour_spin.get())
                m = int(self.min_spin.get())
                if h == 0 and m == 0:
                    messagebox.showerror("错误", "倒计时不能为 0")
                    return
                seconds = h * 3600 + m * 60
                confirm_text = f"确定在 {h}小时{m}分钟后执行【{action_name}】吗？"
            except ValueError:
                messagebox.showerror("错误", "请输入有效数字")
                return

        # 自定义二次确认框，右上角 × 视为取消
        if not self.ask_yes_no(confirm_text):
            return

        # 锁定界面
        self.lock_ui = True
        self.set_widgets_state("disabled")
        self.running = True
        self.status_lbl.config(text="等待中…", foreground="green")

        self.task = threading.Thread(target=self.countdown_and_execute, args=(seconds, action))
        self.task.daemon = True
        self.task.start()

    # --------------- 二次确认框（主窗口居中） ---------------
    def ask_yes_no(self, message):
        top = tk.Toplevel(self.root)
        top.title("请确认")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()

        # 内容
        ttk.Label(top, text=message, wraplength=300).pack(pady=10)
        result = tk.BooleanVar(value=False)

        def yes():
            result.set(True)
            top.destroy()

        def no():
            result.set(False)
            top.destroy()

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="确定", command=yes).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="取消", command=no).pack(side="left", padx=10)

        # 右上角 × 视为取消
        top.protocol("WM_DELETE_WINDOW", no)

        # 计算居中位置
        top.update_idletasks()
        w, h = top.winfo_width(), top.winfo_height()
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        top.geometry(f"+{x}+{y}")

        top.wait_window()
        return result.get()

        # 右上角 × 视为取消
        top.protocol("WM_DELETE_WINDOW", no)
        top.wait_window()
        return result.get()

    # --------------- 取消 ---------------
    def cancel_timer(self):
        self.running = False
        self.lock_ui = False
        self.set_widgets_state("normal")
        self.status_lbl.config(text="已取消", foreground="red")
        if self.task and self.task.is_alive():
            self.task.join(timeout=0.1)

    # --------------- 线程倒计时 ---------------
    def countdown_and_execute(self, seconds, action):
        while seconds > 0 and self.running:
            mins, secs = divmod(seconds, 60)
            self.status_lbl.config(text=f"剩余 {mins:02d}:{secs:02d}")
            time.sleep(1)
            seconds -= 1

        if not self.running:
            return

        cmd_map = {
            "shutdown": "shutdown /s /f /t 0",
            "restart": "shutdown /r /f /t 0",
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "hibernate": "shutdown /h"
        }
        subprocess.Popen(cmd_map[action], shell=True)
        self.root.quit()

    # --------------- 统一启用/禁用控件 ---------------
    def set_widgets_state(self, state):
        for w in (self.clock_entry, self.hour_spin, self.min_spin,
                  self.start_btn):
            w.config(state=state)
        # 模式单选框也禁用
        for rb in self.root.nametowidget(".!labelframe").winfo_children():
            if isinstance(rb, ttk.Radiobutton):
                rb.config(state=state)

if __name__ == "__main__":
    root = tk.Tk()
    ShutdownTimer(root)
    root.mainloop()

