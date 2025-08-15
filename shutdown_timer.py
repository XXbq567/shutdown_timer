#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时关机 / 重启 / 睡眠 / 休眠 小工具
作者  : XXbq567
仓库  : https://github.com/XXbq567/shutdown_timer
说明  : 开源、轻量级、无依赖，Windows 11 单文件 EXE
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import subprocess

class ShutdownTimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("定时关机工具")
        self.root.geometry("400x300")
        self.root.resizable(False, False)

        # 保存用户设置
        self.selected_action = tk.StringVar(value="shutdown")
        self.hours = tk.IntVar(value=0)
        self.minutes = tk.IntVar(value=0)
        self.seconds = tk.IntVar(value=0)
        self.remaining_time = 0
        self.timer_running = False
        self.stop_event = threading.Event()

        # ===== GUI 元素 =====
        # 动作选择
        action_frame = ttk.LabelFrame(root, text="选择动作", padding=10)
        action_frame.pack(padx=10, pady=10, fill="x")

        actions = [("关机", "shutdown"),
                   ("重启", "restart"),
                   ("睡眠", "sleep"),
                   ("休眠", "hibernate")]

        for text, value in actions:
            ttk.Radiobutton(action_frame, text=text, variable=self.selected_action, value=value).pack(side="left", padx=5)

        # 时间输入
        time_frame = ttk.LabelFrame(root, text="设置时间", padding=10)
        time_frame.pack(padx=10, pady=10, fill="x")

        ttk.Label(time_frame, text="小时:").pack(side="left")
        ttk.Entry(time_frame, textvariable=self.hours, width=5).pack(side="left", padx=5)

        ttk.Label(time_frame, text="分钟:").pack(side="left")
        ttk.Entry(time_frame, textvariable=self.minutes, width=5).pack(side="left", padx=5)

        ttk.Label(time_frame, text="秒:").pack(side="left")
        ttk.Entry(time_frame, textvariable=self.seconds, width=5).pack(side="left", padx=5)

        # 倒计时显示
        self.label_time = ttk.Label(root, text="剩余时间: 00:00:00", font=("Arial", 14))
        self.label_time.pack(pady=20)

        # 按钮
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="启动", command=self.start_timer).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="取消", command=self.cancel_timer).pack(side="left", padx=10)

    # 启动定时器
    def start_timer(self):
        total_seconds = self.hours.get() * 3600 + self.minutes.get() * 60 + self.seconds.get()
        if total_seconds <= 0:
            messagebox.showerror("错误", "请输入一个大于 0 的时间！")
            return

        self.remaining_time = total_seconds
        self.stop_event.clear()
        self.timer_running = True
        threading.Thread(target=self.countdown).start()

    # 倒计时
    def countdown(self):
        while self.remaining_time > 0 and not self.stop_event.is_set():
            mins, secs = divmod(self.remaining_time, 60)
            hrs, mins = divmod(mins, 60)
            self.label_time.config(text=f"剩余时间: {hrs:02}:{mins:02}:{secs:02}")
            time.sleep(1)
            self.remaining_time -= 1

        if not self.stop_event.is_set():
            self.execute_action(self.selected_action.get())

    # 执行动作
    def execute_action(self, action):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        psshutdown = os.path.join(base_dir, "psshutdown.exe")

        if action == "sleep":
            # 使用 psshutdown 强制睡眠
            if os.path.exists(psshutdown):
                subprocess.Popen(f'"{psshutdown}" -d -t 0', shell=True)
            else:
                messagebox.showerror("错误", "未找到 psshutdown.exe，请将其放在程序目录下！")

        elif action == "hibernate":
            subprocess.Popen("shutdown /h", shell=True)
        elif action == "shutdown":
            subprocess.Popen("shutdown /s /f /t 0", shell=True)
        elif action == "restart":
            subprocess.Popen("shutdown /r /f /t 0", shell=True)

        os._exit(0)

    # 取消定时器
    def cancel_timer(self):
        self.stop_event.set()
        self.timer_running = False
        self.label_time.config(text="剩余时间: 00:00:00")

# 运行程序
if __name__ == "__main__":
    root = tk.Tk()
    app = ShutdownTimerApp(root)
    root.mainloop()
