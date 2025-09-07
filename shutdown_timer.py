#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时关机 / 睡眠 小工具（修正版）
- 只保留 '关机' 和 '睡眠'
- 启动计时后锁定 UI
- 双重确认（启动前确认 + 睡眠前 10s 最终可取消倒计时）
- 使用 ctypes 直接调用系统 API（避免不可靠的 rundll32 调用）
作者  : XXbq567（修改版）
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
from datetime import datetime, timedelta
import webbrowser
import os
import sys

# --- 辅助：在 Windows 上尝试提升并调用 SetSuspendState ---
def enable_shutdown_privilege():
    """
    尝试为当前进程启用 SeShutdownPrivilege（SetSuspendState 可能需要）。
    返回 True/False 表示是否成功或调用链路无错误。
    （如果失败仍继续执行，但可能导致 API 调用失败）
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    try:
        advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        OpenProcessToken = advapi32.OpenProcessToken
        LookupPrivilegeValueW = advapi32.LookupPrivilegeValueW
        AdjustTokenPrivileges = advapi32.AdjustTokenPrivileges

        GetCurrentProcess = kernel32.GetCurrentProcess
        CloseHandle = kernel32.CloseHandle

        TOKEN_ADJUST_PRIVILEGES = 0x0020
        TOKEN_QUERY = 0x0008
        SE_PRIVILEGE_ENABLED = 0x00000002

        class LUID(ctypes.Structure):
            _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', wintypes.LONG)]

        class LUID_AND_ATTRIBUTES(ctypes.Structure):
            _fields_ = [('Luid', LUID), ('Attributes', wintypes.DWORD)]

        class TOKEN_PRIVILEGES(ctypes.Structure):
            _fields_ = [('PrivilegeCount', wintypes.DWORD),
                        ('Privileges', LUID_AND_ATTRIBUTES * 1)]

        hProc = GetCurrentProcess()
        hToken = wintypes.HANDLE()
        if not OpenProcessToken(hProc, TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(hToken)):
            return False

        luid = LUID()
        # SeShutdownPrivilege 对应的名称在 Windows API 文档中是 "SeShutdownPrivilege"
        if not LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid)):
            CloseHandle(hToken)
            return False

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        # 调整令牌
        if not AdjustTokenPrivileges(hToken, False, ctypes.byref(tp), ctypes.sizeof(tp), None, None):
            CloseHandle(hToken)
            return False

        CloseHandle(hToken)
        return True
    except Exception:
        return False


def sleep_via_api():
    """
    优先使用 ctypes 直接调用 powrprof.SetSuspendState(False,...)
    如果失败，回退到 PowerShell 的 SetSuspendState 方法（.NET）。
    返回 True/False 表示是否调用成功（注意：某些设备/固件不支持 S3）
    """
    # 在非常少见的情况下，现代设备使用 Modern Standby（S0）并不支持传统 S3。
    # 这里尽力而为，失败时返回 False。
    try:
        import ctypes
        # 尝试提升权限（静默进行）
        try:
            enable_shutdown_privilege()
        except Exception:
            pass

        # SetSuspendState(bHibernate=False, bForce=True, bWakeupEventsDisabled=False)
        # 传 False/True/False 或 0/1/0 都可以
        res = ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        # 如果 API 成功通常返回非 0（但不同环境差异较大），我们把异常视为失败
        return bool(res)
    except Exception:
        # 回退：使用 PowerShell 的托管方法
        try:
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $true)"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
            return True
        except Exception:
            return False


class ShutdownTimer:
    def __init__(self, root):
        if sys.platform != "win32":
            messagebox.showerror("错误", "本工具仅支持 Windows 系统。")
            root.destroy()
            return

        self.root = root
        self.root.title("定时关机工具")
        self.root.geometry("360x260")
        self.root.resizable(False, False)

        self.running = False
        self.task = None
        self.lock_ui = False

        # ---------------- 模式变量 ----------------
        self.mode_var = tk.StringVar(value="countdown")
        self.action_var = tk.StringVar(value="shutdown")

        # ---------------- 模式选择 ----------------
        self.mode_frame = ttk.LabelFrame(root, text="模式选择")
        self.mode_frame.pack(fill="x", padx=10, pady=5)

        self.rb_clock = ttk.Radiobutton(self.mode_frame, text="指定时间", value="clock",
                                        variable=self.mode_var, command=self.switch_mode)
        self.rb_clock.pack(side="left", padx=5)

        self.rb_count = ttk.Radiobutton(self.mode_frame, text="倒计时", value="countdown",
                                        variable=self.mode_var, command=self.switch_mode)
        self.rb_count.pack(side="left", padx=5)

        # ---------------- 时间输入区 ----------------
        self.time_frame = ttk.Frame(root)
        self.time_frame.pack(fill="x", padx=10, pady=5)

        # 倒计时
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

        # 指定时间
        self.clock_frame = ttk.Frame(self.time_frame)
        self.clock_frame.pack_forget()
        ttk.Label(self.clock_frame, text="目标时间 (HH:MM):").pack(side="left")
        self.clock_entry = ttk.Entry(self.clock_frame, width=8)
        self.clock_entry.insert(0, "23:30")
        self.clock_entry.pack(side="left", padx=5)

        # ---------------- 操作选择 ----------------
        self.action_frame = ttk.LabelFrame(root, text="执行操作")
        self.action_frame.pack(fill="x", padx=10, pady=5)

        self.action_rbs = []
        action_map = [("关机", "shutdown"), ("睡眠", "sleep")]  # 只保留关机 + 睡眠
        for txt, val in action_map:
            rb = ttk.Radiobutton(self.action_frame, text=txt, value=val, variable=self.action_var)
            rb.pack(side="left", padx=20)
            self.action_rbs.append(rb)

        # ---------------- 按钮区 ----------------
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=5)
        self.start_btn = ttk.Button(btn_frame, text="启动", command=self.start_timer)
        self.start_btn.pack(side="left", padx=10)
        self.cancel_btn = ttk.Button(btn_frame, text="取消", command=self.cancel_timer)
        self.cancel_btn.pack(side="left", padx=10)

        # ---------------- 状态标签 ----------------
        self.status_lbl = ttk.Label(root, text="未启动", foreground="blue")
        self.status_lbl.pack(pady=2)

        # ---------------- 更新链接（最底部居中，小字） ----------------
        self.update_lbl = tk.Label(
            root, text="更新", fg="blue", cursor="hand2",
            font=("Segoe UI", 9)
        )
        self.update_lbl.pack(side="bottom", pady=2)
        self.update_lbl.bind("<Button-1>", lambda e: self.open_update())

    # --------------- 跳转action ---------------
    def open_update(self):
        if not self.lock_ui:
            webbrowser.open("https://github.com/XXbq567/shutdown_timer/actions")

    def switch_mode(self):
        if self.mode_var.get() == "clock":
            self.countdown_frame.pack_forget()
            self.clock_frame.pack(side="left", padx=20)
        else:
            self.clock_frame.pack_forget()
            self.countdown_frame.pack(side="left")

    def start_timer(self):
        if self.lock_ui:
            messagebox.showinfo("提示", "请先取消当前任务后再修改。")
            return

        mode = self.mode_var.get()
        action = self.action_var.get()
        action_name = {"shutdown": "关机", "sleep": "睡眠"}[action]

        if mode == "clock":
            try:
                target_str = self.clock_entry.get().strip()
                target_time = datetime.strptime(target_str, "%H:%M").time()
                now = datetime.now()
                target_dt = datetime.combine(now.date(), target_time)
                if target_dt <= now:
                    target_dt += timedelta(days=1)
                seconds = int((target_dt - now).total_seconds())
                confirm_text = f"确定在 {target_str} 执行吗？"
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
                confirm_text = f"确定在 {h}小时{m}分钟后执行吗？"
            except ValueError:
                messagebox.showerror("错误", "请输入有效数字")
                return

        # 双重确认（第一次）
        if not self.ask_yes_no(confirm_text):
            return

        # 锁定 UI、启动线程
        self.lock_ui = True
        self.set_widgets_state("disabled")
        self.running = True
        self.status_lbl.config(text="等待中…", foreground="green")

        self.task = threading.Thread(target=self.countdown_and_execute, args=(seconds, action))
        self.task.daemon = True
        self.task.start()

    def ask_yes_no(self, message):
        top = tk.Toplevel(self.root)
        top.title("请确认")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()
        top.lift()

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

        top.protocol("WM_DELETE_WINDOW", no)

        top.update_idletasks()
        w, h = top.winfo_width(), top.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        top.geometry(f"+{x}+{y}")
        top.wait_window()
        return result.get()

    def cancel_timer(self):
        self.running = False
        self.lock_ui = False
        self.set_widgets_state("normal")
        self.status_lbl.config(text="已取消", foreground="red")

    def countdown_and_execute(self, seconds, action):
        while seconds > 0 and self.running:
            mins, secs = divmod(seconds, 60)
            # 更新为 mm:ss（小时也会按分钟累计）
            self.status_lbl.config(text=f"剩余 {mins:02d}:{secs:02d}")
            time.sleep(1)
            seconds -= 1
        if not self.running:
            return
        # 到点后执行（主线程外）
        self.root.after(0, lambda: self.execute_action(action))

    def final_sleep_countdown(self, seconds=10):
        """
        在主线程中弹出一个可取消的 10s 倒计时对话框。
        返回 True 表示继续执行睡眠，False 表示用户取消。
        """
        top = tk.Toplevel(self.root)
        top.title("即将睡眠 — 最终确认")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()
        label = ttk.Label(top, text=f"将在 {seconds} 秒后进入睡眠，点击“取消”可停止。", wraplength=320)
        label.pack(padx=10, pady=10)

        canceled = tk.BooleanVar(False)

        def do_cancel():
            canceled.set(True)
            top.destroy()

        btn = ttk.Button(top, text="取消", command=do_cancel)
        btn.pack(pady=(0, 8))

        def tick(s):
            if canceled.get():
                return
            if s <= 0:
                top.destroy()
                return
            label.config(text=f"将在 {s} 秒后进入睡眠，点击“取消”可停止。")
            top.after(1000, lambda: tick(s - 1))

        top.update_idletasks()
        w, h = top.winfo_width(), top.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        top.geometry(f"+{x}+{y}")

        tick(seconds)
        top.wait_window()
        return not canceled.get()

    def execute_action(self, action):
        """
        在主线程中执行具体操作（睡眠/关机）。
        对于睡眠：执行最终 10s 可取消倒计时 -> 尝试用 API 睡眠（ctypes），
        若系统启用了休眠且无法直接进入睡眠，会尝试暂时关闭休眠（需要管理员权限）。
        """
        action_name = {"shutdown": "关机", "sleep": "睡眠"}[action]

        if action == "sleep":
            # 检查系统是否启用了休眠（输出中有 Hibernate / 休眠 字样）
            try:
                result = subprocess.run("powercfg -query", shell=True, capture_output=True, text=True, timeout=5)
                stdout = result.stdout or ""
            except Exception:
                stdout = ""

            hibernate_enabled = ("Hibernate" in stdout) or ("休眠" in stdout)
            disabled_hibernate = False

            # 如果启用了休眠，我们尝试临时关闭（以确保调用 SetSuspendState 时进入真正的睡眠）
            # 这个操作需要管理员权限，若失败则会继续尝试 API（但可能会进入休眠）
            if hibernate_enabled:
                try:
                    subprocess.run("powercfg -hibernate off", shell=True, check=True)
                    disabled_hibernate = True
                except Exception:
                    # 不能临时关闭休眠（普通用户或权限不足），继续但告知用户
                    self.status_lbl.config(text="注意：无法禁用休眠，睡眠行为可能为休眠。", foreground="orange")

            # 最后的 10s 提示（用户可以取消）
            proceed = self.final_sleep_countdown(10)
            if not proceed:
                # 用户取消：恢复 hibernate（如果我们曾经关闭过）
                if disabled_hibernate:
                    try:
                        subprocess.run("powercfg -hibernate on", shell=True, check=True)
                    except Exception:
                        pass
                self.cancel_timer()
                return

            # 尝试使用 API 睡眠
            ok = sleep_via_api()

            # 恢复休眠设置（如果我们之前临时关闭过）
            if disabled_hibernate:
                try:
                    subprocess.run("powercfg -hibernate on", shell=True, check=True)
                except Exception:
                    pass

            if not ok:
                messagebox.showerror("错误", "尝试进入睡眠失败。你的设备可能不支持传统 S3 睡眠或权限不足。")
                self.cancel_timer()
                return

            # 成功后退出（应用无需继续运行）
            os._exit(0)

        elif action == "shutdown":
            # 直接关机
            try:
                subprocess.Popen("shutdown /s /f /t 0", shell=True)
            except Exception:
                messagebox.showerror("错误", "执行关机时出现错误。")
                self.cancel_timer()
                return
            os._exit(0)

    def set_widgets_state(self, state):
        self.rb_clock.config(state=state)
        self.rb_count.config(state=state)
        for rb in self.action_rbs:
            rb.config(state=state)
        try:
            self.clock_entry.config(state=state)
            self.hour_spin.config(state=state)
            self.min_spin.config(state=state)
            self.start_btn.config(state=state)
            # update_lbl 用 label，不支持 state 直接设置，使用 fg 改变视觉提示
            self.update_lbl.config(fg=("blue" if state == "normal" else "gray"))
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    ShutdownTimer(root)
    root.mainloop()
