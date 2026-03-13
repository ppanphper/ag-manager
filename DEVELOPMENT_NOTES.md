# AGManager 开发规范与已知问题记录

## ❌ 已知 Bug：macOS 暗色模式下 `tk.Button` 文字不可见

### 问题现象
弹窗内的按钮显示为**白色方块，文字不可见**（白底白字）。

### 根因
macOS 暗色模式（Dark Mode）下，`tkinter` 的原生 `tk.Button` 组件对 `bg` / `fg` / `highlightbackground` 等属性的渲染**由系统接管**，自定义颜色参数会被忽略或覆盖，导致系统用纯白渲染按钮背景与文字，视觉上不可见。

### 修复方式

**✅ 统一使用 `ttk.Button` + 已预设的 Style，禁止使用 `tk.Button`**

| 按钮语义 | Style 名称 | 颜色效果 |
|---|---|---|
| 普通操作（复制、确认等） | `"TButton"` | 深色背景 + 白字 |
| 确认 / 完成（绿色） | `"Green.TButton"` | 绿色背景 + 白字 |
| 主要操作（蓝色） | `"Blue.TButton"` | 蓝色背景 + 白字 |
| 警告操作（橙色） | `"Orange.TButton"` | 橙色背景 + 白字 |
| 危险操作（红色） | `"Red.TButton"` | 红色背景 + 白字 |
| 次要操作（灰色） | `"Gray.TButton"` | 灰色背景 + 白字 |

Style 在 `ui.py` 的 `configure_styles()` 方法中统一定义。

### 错误写法 ❌
```python
tk.Button(frame, text="确认", bg="#4CAF50", fg="white",
          highlightbackground=COLORS["root_bg"]).pack()
```

### 正确写法 ✅
```python
ttk.Button(frame, text="确认", style="Green.TButton").pack()
```

### 受影响并已修复的位置（2026-03-12）
- `ui.py` → `sync_login_ui()` — 「确认同步」和「取消」按钮
- `ui.py` → `show_proxifier_guide()` — 「复制完整规则」和「我已配置完成」按钮
- `ui.py` → `create_copy_row()` — 「复制」按钮
