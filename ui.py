import os
import re
import time
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from theme import COLORS, IS_DARK, center_window
from config import ConfigManager
from power_manager import AppPowerManager
from dialogs import SettingsDialog, InstanceEditorDialog


class AGManagerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity 启动器 (外部存储适配版)")
        self.root.configure(bg=COLORS["root_bg"])
        center_window(self.root, 650, 500)

        self.cfg = ConfigManager()
        self.mgr = AppPowerManager(self.cfg)

        self.setup_ui()
        self.check_env()
        self.refresh_list()
        self.root.update_idletasks()

    def check_env(self):
        """检查环境，如果配置不对自动弹出设置"""
        src = self.cfg.get("original_app_path")
        if not os.path.exists(src) and not os.path.islink(src):
            self.root.after(500, lambda: self.prompt_inital_setup(src))

    def prompt_inital_setup(self, path):
        if messagebox.askyesno("初始化配置", f"未检测到原始应用路径：\n{path}\n\nAntigravity.app 未安装或路径不正确。\n是否现在手动指定？"):
            SettingsDialog(self.root, self.cfg)

    def configure_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        bg = COLORS["root_bg"]
        fg = COLORS["fg"]
        btn_bg = COLORS["btn_bg"]
        btn_fg = COLORS["btn_fg"]

        style.configure(".", background=bg, foreground=fg, font=("Arial", 11))
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TEntry", fieldbackground=COLORS["entry_bg"], foreground=COLORS["entry_fg"])

        style.configure("TButton", background=btn_bg, foreground=btn_fg, borderwidth=1, focuscolor="none")
        style.map("TButton", background=[('active', btn_bg)])

        btn_colors = {
            "Green": "#4CAF50",
            "Blue": "#2196F3",
            "Orange": "#FF9800",
            "Red": "#f44336",
            "Gray": "#555555"
        }
        for name, color in btn_colors.items():
            sname = f"{name}.TButton"
            style.configure(sname, background=color, foreground="white", font=("Arial", 12, "bold"))
            style.map(sname, background=[('active', color)])

        heading_bg = "#333333" if IS_DARK else "#e1e1e1"
        heading_fg = "#ffffff" if IS_DARK else "#000000"
        style.configure("Treeview",
                        background=COLORS["tree_bg"],
                        foreground=COLORS["tree_fg"],
                        fieldbackground=COLORS["tree_bg"],
                        borderwidth=0,
                        font=("Arial", 11))
        style.map('Treeview', background=[('selected', COLORS["select_bg"])])

        style.configure("Treeview.Heading",
                        background=heading_bg,
                        foreground=heading_fg,
                        relief="flat",
                        font=("Arial", 11, "bold"))
        style.map("Treeview.Heading", background=[('active', heading_bg)])

    def setup_ui(self):
        self.configure_styles()

        # 顶部工具栏
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="➕ 新建实例", command=self.add_instance, style="TButton").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="⚙️ 设置路径", command=lambda: SettingsDialog(self.root, self.cfg), style="TButton").pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="📖 使用说明", command=self.show_instructions, style="TButton").pack(side=tk.RIGHT, padx=5)

        # 列表
        cols = ("name", "note", "last_used")
        self.tree = ttk.Treeview(self.root, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("name", text="实例名称")
        self.tree.column("name", width=200)
        self.tree.heading("note", text="备注 / 代理规则")
        self.tree.column("note", width=200)
        self.tree.heading("last_used", text="Apps 状态")
        self.tree.column("last_used", width=150)

        scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tree.bind("<Double-1>", lambda e: self.launch_current())

        # 底部操作
        self.action_frame = ttk.Frame(self.root, padding=(0, 15))
        self.action_frame.pack(fill=tk.X)

        ttk.Button(self.action_frame, text="🚀 启动", command=self.launch_current,
                 style="Green.TButton", width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.action_frame, text="📡 代理规则", command=self.view_rules,
                 style="Blue.TButton", width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.action_frame, text="♻️ 同步内核", command=self.sync_kernel_ui,
                 style="Orange.TButton", width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(self.action_frame, text="", width=2).pack(side=tk.LEFT)
        ttk.Button(self.action_frame, text="🗑️ 删除", command=self.delete_current,
                 style="Red.TButton", width=8).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.action_frame, text="⚙️ 设置", command=self.edit_instance,
                 style="Gray.TButton", width=8).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.action_frame, text="⏹ 强制退出", command=self.force_quit_current,
                 style="Gray.TButton", width=10).pack(side=tk.RIGHT, padx=5)

        # 底部状态栏
        self.status_var = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status_var, font=("Arial", 10)).pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.update_status()

    def update_status(self):
        apps_dir = self.cfg.get("apps_dir")
        self.status_var.set(f"当前存储: {apps_dir}")
        self.root.after(2000, self.update_status)

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        accounts = self.cfg.get_accounts()
        accounts.sort(key=lambda x: x.get("last_used", 0), reverse=True)

        for acc in accounts:
            name = acc["name"]
            app_path = self.mgr.get_app_path(name)
            status = "✅ 正常" if os.path.exists(app_path) else "⚠️ 未创建"
            self.tree.insert("", tk.END, values=(name, f"{acc.get('note', '')} {('[Proxy]' if acc.get('proxy_url') else '')}", status), iid=name)

    def add_instance(self):
        dialog = InstanceEditorDialog(self.root)
        if not dialog.result: return

        data = dialog.result
        name = data["name"]
        note = data["note"]
        proxy = data["proxy_url"]

        if self.cfg.add_account(name, note, proxy):
            try:
                app_path, created = self.mgr.ensure_app_created(name)
                self.refresh_list()
                self.tree.selection_set(name)
                # 新建实例后询问是否同步配置
                if messagebox.askyesno("同步配置", f"是否将原版 Antigravity 的扩展和配置同步到新实例【{name}】？\n\n这将复制：\n  • 已安装的扩展\n  • 编辑器设置 (settings.json)\n  • 快捷键 (keybindings.json)\n  • 代码片段 (snippets)\n\n不会复制登录信息和工作区数据。"):
                    try:
                        synced = self.mgr.sync_config(name, source_name=None)
                        messagebox.showinfo("同步完成", f"已同步: {', '.join(synced)}")
                    except Exception as ex:
                        messagebox.showerror("同步失败", str(ex))
                self.show_proxifier_guide(name, app_path)
            except Exception as e:
                msg = str(e)
                if "在源 App 内部创建实例" in msg:
                    msg = "您当前的【实例存储位置】被设置在了 Antigravity.app 内部！\n这是不被允许的。\n请去设置页面修改存储路径为其他任何文件夹。"
                messagebox.showerror("创建失败", msg)
                self.cfg.delete_account(name)
                self.refresh_list()
        else:
            messagebox.showerror("错误", "实例名称已存在")

    def show_instructions(self):
        """显示全局使用说明"""
        win = tk.Toplevel(self.root)
        win.title("📖 核心机制与使用说明")
        win.configure(bg=COLORS["root_bg"])
        center_window(win, 600, 480)

        content = (
            "🚀 核心机制:\n"
            "1. 物理隔离: 每个实例拥有独立的 .app 文件和数据目录，从根源上防止 IP 串联。\n"
            "2. 零空间克隆: 使用 macOS APFS 技术，克隆 App 不占用物理硬盘空间。\n\n"
            "⚠️ 关键操作 (登录防冲突):\n"
            "因 macOS 机制限制，所有分身共享同一个登录回调。\n"
            "【初次登录新账号时】请务必：\n"
            "   (1) 关闭所有其他 Antigravity 窗口。\n"
            "   (2) 只运行你要登录的那个实例。\n"
            "   (3) 登录成功保存 Token 后，即可正常多开。\n\n"
            "📡 Proxifier 配置:\n"
            "请点击主界面下方的【代理规则】按钮，获取针对每个实例的精确分流规则。\n"
            "每个实例会生成三条规则：\n"
            "   A. 主进程名 (Electron_{name})\n"
            "   B. 语言服务器名 (language_server_macos_arm_{name})\n"
            "   C. 插件宿主 Bundle ID (com.google.antigravity.helper.{name})\n\n"
            "💡 关于更新与同步内核:\n"
            "因为修改了签名，隔离版 App 将无法【自动更新】。\n"
            "   (1) 更新方法：先在系统正常下载安装新版 Antigravity.app\n"
            "   (2) 然后在管理器选中旧实例，点击底部的【♻️ 同步内核】\n"
            "   (3) 它会将新版核心安全覆盖过来，同时完整保留该实例所有的本地 Cookie 和登录数据。\n"
        )

        text_area = tk.Text(win, wrap=tk.WORD, font=("Arial", 11), padx=10, pady=10,
                           bg=COLORS["root_bg"], fg=COLORS["fg"],
                           selectbackground=COLORS["text_select"], relief=tk.FLAT)
        text_area.insert(tk.END, content)

        hl_bold = "#007AFF" if not IS_DARK else "#4FC3F7"
        hl_red = "#FF3B30" if not IS_DARK else "#FFAB91"

        text_area.tag_config("bold", font=("Arial", 11, "bold"), foreground=hl_bold)
        text_area.tag_config("red", foreground=hl_red)

        text_area.tag_add("bold", "1.0", "1.7")
        text_area.tag_add("bold", "6.0", "6.18")
        text_area.tag_add("red", "6.0", "6.18")

        text_area.config(state="disabled")
        text_area.pack(fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(win, pady=10, bg=COLORS["root_bg"])
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(btn_frame, text="明白", command=win.destroy,
                 bg=COLORS["btn_bg"], fg=COLORS["btn_fg"], highlightbackground=COLORS["root_bg"], width=15).pack()

    def view_rules(self):
        """查看现有实例的代理规则"""
        sel = self.tree.selection()
        if not sel: return
        name = sel[0]
        app_path = self.mgr.get_app_path(name)
        if not os.path.exists(app_path):
            messagebox.showwarning("提示", "该实例尚未创建物理 App，无法生成规则。")
            return
        self.show_proxifier_guide(name, app_path)

    def show_proxifier_guide(self, name, app_path):
        win = tk.Toplevel(self.root)
        win.title("📡 Proxifier 配置指南")
        win.configure(bg=COLORS["root_bg"])
        center_window(win, 650, 560)

        tk.Label(win, text=f"为实例 [{name}] 配置分流", font=("Arial", 14, "bold"),
                fg=COLORS["select_bg"], bg=COLORS["root_bg"]).pack(pady=10)

        info_frame = tk.Frame(win, padx=10, pady=5, bg=COLORS["root_bg"])
        info_frame.pack(fill=tk.BOTH, expand=True)

        # 规则生成
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '', name)

        # 进程名规则（已验证生效的 shim 进程）
        elec_rule = f'"Electron_{safe_name}"'
        ls_rule = f'"language_server_macos_arm_{safe_name}"'

        # Plugin Helper Bundle ID 规则（通过 ad-hoc 重签注入自定义 identifier）
        plugin_bundle_id = f'"com.google.antigravity.helper.{safe_name}"'

        all_rules = [elec_rule, ls_rule, plugin_bundle_id]
        full_rule = "; ".join(all_rules)

        # 一键复制区
        tk.Label(info_frame, text="✨ 一键配置 (进程名 + Bundle ID 精准分流)", font=("Arial", 12, "bold"),
                fg=COLORS["select_bg"], bg=COLORS["root_bg"]).pack(anchor="w", pady=(5,5))

        all_frame = tk.Frame(info_frame, pady=5, bg=COLORS["root_bg"])
        all_frame.pack(fill=tk.X)

        e_all = tk.Entry(all_frame, font=("Arial", 10), bg=COLORS["entry_bg"], fg=COLORS["entry_fg"], insertbackground=COLORS["fg"])
        e_all.insert(0, full_rule)
        e_all.config(state="readonly")
        e_all.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        tk.Button(all_frame, text="复制完整规则", command=lambda: self.copy_to_clip(full_rule),
                 bg=COLORS["btn_bg"], fg=COLORS["btn_fg"], highlightbackground=COLORS["root_bg"]).pack(side=tk.RIGHT)

        tk.Label(info_frame, text="👆 将上方内容粘贴到 Proxifier 规则的 Applications 字段。\n前两项按进程名匹配主程序和语言服务器；第三项按 Bundle ID 匹配 Plugin Helper（扩展宿主进程）。",
                 fg="gray", bg=COLORS["root_bg"], justify=tk.LEFT, wraplength=600).pack(anchor="w", pady=(0, 15))

        # 规则详情
        tk.Frame(info_frame, height=1, bg="gray").pack(fill=tk.X, pady=10)
        tk.Label(info_frame, text="🔍 规则详情", font=("Arial", 10, "bold"), fg="gray", bg=COLORS["root_bg"]).pack(anchor="w")

        tk.Label(info_frame, text="主进程 (Electron Shim):", fg="gray", bg=COLORS["root_bg"]).pack(anchor="w")
        self.create_copy_row(info_frame, elec_rule)

        tk.Label(info_frame, text="语言服务器 (LS Shim):", fg="gray", bg=COLORS["root_bg"]).pack(anchor="w")
        self.create_copy_row(info_frame, ls_rule)

        tk.Label(info_frame, text="插件宿主 (Plugin Helper, ad-hoc 重签 Bundle ID):", fg="gray", bg=COLORS["root_bg"]).pack(anchor="w")
        self.create_copy_row(info_frame, plugin_bundle_id)

        # 登录提示
        warning_frame = tk.LabelFrame(win, text="⚠️ 登录必读", padx=10, pady=5, bg=COLORS["root_bg"], fg=COLORS["fg"])
        warning_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(warning_frame, text="因 macOS 机制限制，多实例同时运行时，登录回调可能会乱序。\n【初次登录时】请务必关闭所有其他 Antigravity 窗口，仅保留当前这一个。\n登录成功保存 Token 后，即可正常多开。",
                 justify=tk.LEFT, wraplength=500, bg=COLORS["root_bg"], fg=COLORS["fg"]).pack(anchor="w")

        tk.Button(win, text="我已配置完成", command=win.destroy,
                 bg="#4CAF50", fg="white", highlightbackground=COLORS["root_bg"], width=20).pack(side=tk.BOTTOM, pady=20)

    def create_copy_row(self, parent, text):
        row = tk.Frame(parent, bg=COLORS["root_bg"])
        row.pack(fill=tk.X, pady=2)
        e = tk.Entry(row, font=("Arial", 9), bg=COLORS["entry_bg"], fg=COLORS["entry_fg"], insertbackground=COLORS["fg"])
        e.insert(0, text)
        e.config(state="readonly")
        e.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="复制", command=lambda: self.copy_to_clip(text), width=4,
                 bg=COLORS["btn_bg"], fg=COLORS["btn_fg"], highlightbackground=COLORS["root_bg"]).pack(side=tk.RIGHT, padx=5)

    def launch_current(self):
        sel = self.tree.selection()
        if not sel: return
        name = sel[0]
        try:
            self.mgr.launch(name)
            self.cfg.update_account(name, last_used=time.time())
            self.refresh_list()
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def sync_kernel_ui(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个实例")
            return
        name = sel[0]
        if not messagebox.askyesno("同步内核", f"确定要同步【{name}】的内核吗？\n这会将原始 App 的代码覆盖到此实例，您的配置和数据会被保留。"):
            return

        # 询问是否同步配置和扩展
        sync_config = messagebox.askyesno("同步配置", f"是否同时同步扩展和配置？\n\n这将从原版 Antigravity 复制：\n  • 新增的扩展（已有的不会覆盖）\n  • 编辑器设置 (settings.json)\n  • 快捷键和代码片段\n\n选择【否】则只同步应用程序代码。")

        # 禁用所有按钮防止重复操作
        for child in self.action_frame.winfo_children():
            if isinstance(child, ttk.Button):
                child.config(state="disabled")

        # 创建进度提示窗口
        progress_win = tk.Toplevel(self.root)
        progress_win.title("同步内核")
        progress_win.configure(bg=COLORS["root_bg"])
        progress_win.resizable(False, False)
        center_window(progress_win, 350, 120)
        progress_win.transient(self.root)
        progress_win.grab_set()
        progress_win.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(progress_win, text=f"正在同步【{name}】的内核...",
                font=("Arial", 12), bg=COLORS["root_bg"], fg=COLORS["fg"]).pack(pady=(20, 5))

        status_var = tk.StringVar(value="正在复制文件，请稍候...")
        tk.Label(progress_win, textvariable=status_var,
                font=("Arial", 10), fg="gray", bg=COLORS["root_bg"]).pack(pady=5)

        # 后台线程执行同步
        result = {"error": None}
        def do_sync():
            try:
                self.mgr.sync_kernel(name)
                if sync_config:
                    self.mgr.sync_config(name, source_name=None)
            except Exception as e:
                result["error"] = str(e)

        t = threading.Thread(target=do_sync, daemon=True)
        t.start()

        # 轮询线程状态
        dots = [0]
        def check_progress():
            if t.is_alive():
                dots[0] = (dots[0] % 3) + 1
                status_var.set("正在复制文件" + "." * dots[0])
                self.root.after(500, check_progress)
            else:
                progress_win.destroy()
                for child in self.action_frame.winfo_children():
                    if isinstance(child, ttk.Button):
                        child.config(state="normal")
                self.refresh_list()
                if result["error"]:
                    messagebox.showerror("同步失败", result["error"])
                else:
                    messagebox.showinfo("成功", f"实例【{name}】内核同步完成！")

        self.root.after(300, check_progress)

    def edit_instance(self):
        sel = self.tree.selection()
        if not sel: return
        name = sel[0]
        acc = next((a for a in self.cfg.get_accounts() if a["name"] == name), {})

        dialog = InstanceEditorDialog(self.root, existing_data=acc)
        if not dialog.result: return

        data = dialog.result
        self.cfg.update_account(name, note=data["note"], proxy_url=data["proxy_url"])
        self.refresh_list()

    def force_quit_current(self):
        sel = self.tree.selection()
        if not sel: return
        name = sel[0]
        if messagebox.askyesno("强制退出", f"确定要强制退出实例【{name}】的所有进程吗？"):
            clean = self.mgr.force_quit(name)
            if clean:
                messagebox.showinfo("完成", f"实例【{name}】的所有进程已强制终止。")
            else:
                messagebox.showwarning("警告", f"可能仍有残留进程，请手动检查。")

    def copy_to_clip(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        messagebox.showinfo("已复制", "规则已复制到剪贴板！")

    def delete_current(self):
        sel = self.tree.selection()
        if not sel: return
        name = sel[0]
        if messagebox.askyesno("删除", f"删除实例 {name}？\n这会删除 App 和 数据目录。"):
            try:
                self.mgr.delete_resources(name, delete_data=True)
                self.cfg.delete_account(name)
                self.refresh_list()
            except Exception as e:
                messagebox.showerror("错误", str(e))
