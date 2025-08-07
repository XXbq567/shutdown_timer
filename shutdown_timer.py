import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import threading
import time
from datetime import datetime

class ShutdownTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("定时关机工具")
        self.root.geometry("320x220")
        self.root.resizable(False, False)

        self.task = None
        self.running = False

        # 操作选项
        self.action_var = tk.StringVar(value="shutdown")
        actions = [("关机", "shutdown"), ("重启", "restart"), ("睡眠", "sleep"), ("休眠", "hibernate")]

        ttk.Label(root, text="选择操作：").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        for i, (label, value) in enumerate(actions):
            ttk.Radiobutton(root, text=label, value=value, variable=self.action_var).grid(
                row=0, column=i + 1, padx=5, pady=10
            )

        # 时间输入
        ttk.Label(root, text="目标时间：").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.time_entry = ttk.Entry(root, width=12)
        self.time_entry.insert(0, "23:30")
        self.time_entry.grid(row=1, column=1, columnspan=3, padx=10, pady=5)

        # 按钮
        self.start_btn = ttk.Button(root, text="启动", command=self.start_timer)
        self.start_btn.grid(row=2, column=1, pady=10)

        self.cancel_btn = ttk.Button(root, text="取消", command=self.cancel_timer)
        self.cancel_btn.grid(row=2, column=2, pady=10)

        self.status_label = ttk.Label(root, text="未启动")
        self.status_label.grid(row=3, column=0, columnspan=4, pady=5)

    def start_timer(self):
        try:
            target_time = datetime.strptime(self.time_entry.get(), "%H:%M").time()
        except ValueError:
            messagebox.showerror("错误", "时间格式错误，请输入 HH:MM")
            return

        self.running = True
        self.start_btn.config(state="disabled")
        self.status_label.config(text="等待中...")
        self.task = threading.Thread(target=self.wait_and_execute, args=(target_time,))
        self.task.daemon = True
        self.task.start()

    def cancel_timer(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.status_label.config(text="已取消")

    def wait_and_execute(self, target_time):
        while self.running:
            now = datetime.now().time()
            if now >= target_time:
                self.execute_action()
                break
            time.sleep(10)

    def execute_action(self):
        action = self.action_var.get()
        cmd_map = {
            "shutdown": "shutdown /s /f /t 0",
            "restart": "shutdown /r /f /t 0",
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "hibernate": "shutdown /h"
        }
        subprocess.Popen(cmd_map[action], shell=True)
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = ShutdownTimer(root)
    root.mainloop()
