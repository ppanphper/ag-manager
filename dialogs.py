import os
import tkinter as tk
from tkinter import messagebox, filedialog, ttk

from theme import COLORS, center_window


class SettingsDialog:
    def __init__(self, parent, cfg):
        self.top = tk.Toplevel(parent)
        self.top.title("⚙️ 全局设置")
        self.top.configure(bg=COLORS["root_bg"])
        center_window(self.top, 650, 450)
        self.cfg = cfg
        self.setup_ui()

    def setup_ui(self):
        self.create_path_entry("原始 Antigravity.app 路径 (Source):", "original_app_path", is_app_bundle=True)
        self.create_path_entry("实例(App) 存储位置 (Target, 可选外接磁盘):", "apps_dir", is_app_bundle=False)
        self.create_path_entry("用户数据(Data) 存储位置:", "data_dir", is_app_bundle=False)

        btn_frame = ttk.Frame(self.top, padding=(0, 20))
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="保存并关闭", command=self.top.destroy, style="TButton", width=15).pack()

    def create_path_entry(self, label, key, is_app_bundle):
        frame = ttk.Frame(self.top, padding=10)
        frame.pack(fill=tk.X)

        lbl_frame = ttk.Frame(frame)
        lbl_frame.pack(fill=tk.X)
        ttk.Label(lbl_frame, text=label, font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        path_var = tk.StringVar(value=self.cfg.get(key))

        status_lbl = ttk.Label(lbl_frame, text="", font=("Arial", 9))
        status_lbl.pack(side=tk.RIGHT)

        entry_frame = ttk.Frame(frame)
        entry_frame.pack(fill=tk.X, pady=2)

        entry = ttk.Entry(entry_frame, textvariable=path_var, style="TEntry")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def check_path(*args):
            p = path_var.get()
            is_valid = os.path.exists(p)
            status_lbl.config(text="✅ 有效" if is_valid else "❌ 无效", foreground="green" if is_valid else "red")

            if key == "apps_dir":
                orig = self.cfg.get("original_app_path")
                if orig and p and os.path.abspath(p).startswith(os.path.abspath(orig)):
                    status_lbl.config(text="❌ 错误: 不能在源App内部", foreground="red")

            self.cfg.set(key, p)

        path_var.trace_add("write", check_path)
        check_path()

        def browse():
            if is_app_bundle:
                path = filedialog.askdirectory(title="选择 Antigravity.app (它是一个文件夹)")
            else:
                path = filedialog.askdirectory(title="选择文件夹")

            if path:
                if is_app_bundle and not path.endswith(".app"):
                    messagebox.showwarning("提示", "你选择的似乎不是 .app 应用包")
                path_var.set(path)

        ttk.Button(entry_frame, text="📂", command=browse, style="TButton").pack(side=tk.RIGHT, padx=5)


class InstanceEditorDialog:
    """新建/编辑实例弹窗"""
    def __init__(self, parent, existing_data=None):
        self.top = tk.Toplevel(parent)
        self.top.title("新建实例" if not existing_data else "编辑实例")
        self.top.configure(bg=COLORS["root_bg"])
        center_window(self.top, 400, 350)
        self.result = None

        ttk.Label(self.top, text="实例名称 (例如: US-Project-01):").pack(anchor="w", padx=20, pady=(20, 5))
        self.name_var = tk.StringVar(value=existing_data["name"] if existing_data else "")
        self.name_entry = ttk.Entry(self.top, textvariable=self.name_var, style="TEntry")
        self.name_entry.pack(fill=tk.X, padx=20)
        if existing_data:
            self.name_entry.config(state="disabled")

        ttk.Label(self.top, text="备注信息 (可选):").pack(anchor="w", padx=20, pady=(15, 5))
        self.note_var = tk.StringVar(value=existing_data.get("note", "") if existing_data else "")
        ttk.Entry(self.top, textvariable=self.note_var, style="TEntry").pack(fill=tk.X, padx=20)

        ttk.Label(self.top, text="代理地址 (可选, 推荐 SOCKS5):").pack(anchor="w", padx=20, pady=(15, 5))
        self.proxy_var = tk.StringVar(value=existing_data.get("proxy_url", "") if existing_data else "")
        ttk.Entry(self.top, textvariable=self.proxy_var, style="TEntry").pack(fill=tk.X, padx=20)
        ttk.Label(self.top, text="例如: socks5://127.0.0.1:7890\n若填写，启动时会自动注入代理参数。",
                 foreground="gray", font=("Arial", 9), justify=tk.LEFT).pack(anchor="w", padx=20)

        btn_frame = ttk.Frame(self.top, padding=(0, 20))
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="确定", command=self.on_ok,
                 style="TButton", width=10).pack(pady=10)

        # Modal
        self.top.transient(parent)
        self.top.grab_set()
        parent.wait_window(self.top)

    def on_ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("错误", "名称不能为空")
            return
        self.result = {
            "name": name,
            "note": self.note_var.get().strip(),
            "proxy_url": self.proxy_var.get().strip()
        }
        self.top.destroy()
