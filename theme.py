import sys
import subprocess

# --- 主题检测 (Theme Detection) ---
def is_dark_mode():
    """检测 macOS 是否为深色模式"""
    try:
        if sys.platform != 'darwin':
            return False
            
        res = subprocess.run(
            ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
            capture_output=True, text=True
        )
        val = res.stdout.strip()
        return 'Dark' in val
    except Exception:
        return False

IS_DARK = is_dark_mode()

# --- 色彩方案 ---
THEME = {
    "dark": {
        "root_bg": "#2b2b2b",
        "fg": "#ffffff",
        "entry_bg": "#444444",
        "entry_fg": "#ffffff",
        "btn_bg": "#2196F3",
        "btn_fg": "#ffffff",
        "tree_bg": "#444444",
        "tree_fg": "#ffffff",
        "select_bg": "#2196F3",
        "text_select": "#555555"
    },
    "light": {
        "root_bg": "#ececec",
        "fg": "#000000",
        "entry_bg": "#ffffff",
        "entry_fg": "#000000",
        "btn_bg": "#e1e1e1",
        "btn_fg": "#000000",
        "tree_bg": "#ffffff",
        "tree_fg": "#000000",
        "select_bg": "#3a86ff",
        "text_select": "#bce0fd"
    }
}

COLORS = THEME["dark"] if IS_DARK else THEME["light"]

# --- 环境自检 ---
try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, filedialog, ttk
except ImportError:
    print("\n❌ 错误: 未检测到 Tkinter 模块 (GUI 基础库)")
    sys.exit(1)


def center_window(win, w, h):
    """将窗口居中显示在屏幕上"""
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")
