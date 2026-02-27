#!/usr/bin/env python3
"""
Antigravity 启动器 - 多实例管理工具
入口文件，启动 GUI 主界面。
"""
import tkinter as tk
from ui import AGManagerUI

if __name__ == "__main__":
    root = tk.Tk()
    app = AGManagerUI(root)
    root.mainloop()