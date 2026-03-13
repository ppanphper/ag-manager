# Antigravity Manager (AGM)

**专为 Google Antigravity 设计的极致多开与流量隔离管理器。**

AGM 是一个开源的 Python 工具，通过独特的 **Process Shim (进程垫片)** + **Bundle ID 重签** 技术，为每个 Antigravity 实例赋予独立的进程身份，从而配合 **Proxifier** 实现 100% 精准的 IP/流量隔离。

## 🌟 核心特性

- **🛡️ 三层流量隔离**:
    - 主程序垫片: `Electron` → `Electron_{InstanceName}`
    - 语言服务器垫片: `language_server` → `language_server_..._{InstanceName}`
    - Plugin Helper 重签: Bundle ID `com.google.antigravity.helper` → `com.google.antigravity.helper.{InstanceName}`
    - **效果**: Proxifier 可通过进程名 + Bundle ID 精准匹配每个实例的全部网络流量。

- **📡 一键分流规则**:
    - 点击「代理规则」按钮，一键复制包含进程名和 Bundle ID 的完整 Proxifier 规则。
    - 三条规则覆盖实例的所有网络进程：Electron、language_server、Plugin Helper。

- **📋 配置与扩展同步**:
    - 新建实例时自动询问是否从原版 Antigravity 同步扩展和配置。
    - 同步内核时可选择同时同步（增量复制扩展，不覆盖已有）。
    - 精确排除登录 Token 和工作区数据，避免账号串联。

- **♻️ 内核同步 (Sync Core)**:
    - 由于修改了签名，自动更新被禁用。
    - 提供「一键同步内核」功能：当 Antigravity 发布新版时，一键将新版核心同步到所有实例，同时保留用户数据。

- **🔑 同步登录 (Sync Login)**:
    - 解决 Antigravity **1.18.4+ 版本修改了 OAuth 回调验证逻辑**，导致典型 Shim 方案在新实例中无法正常完成登录回调的问题。
    - 操作方式：用**任意已登录的来源**（原版 App 或已有实例）登录账号后，通过此功能将 Token （`globalStorage`）直接复制到目标实例，不依赖任何版本的 OAuth 回调机制。
    - 任何 Antigravity 版本均可用。

- **⏹ 强制退出**:
    - 一键强杀实例的所有进程（含 Helper 子进程），确保彻底退出。

- **💾 外部存储支持**:
    - 支持将 App 实例存储在外接硬盘，节省本机空间。
    - 用户数据 (Cookies, LocalStorage) 保存在本机，确保速度。

## 🚀 快速开始

### 1. 环境准备
- macOS (Intel / Apple Silicon)
- Python 3.9+ (`brew install python3`)
- **Proxifier** (或 Surge 等支持进程规则的网关)

### 2. 安装与运行
```bash
git clone https://github.com/ppanphper/ag-manager.git
cd ag-manager
python3 ag_manager.py
```

### 3. 初次设置
程序启动后，点击 **⚙️ 设置**：
1.  **源 App 路径**: 选择你安装的原始 `Antigravity.app`。
2.  **实例存储位置**: 选择文件夹（推荐外接硬盘）用于存放克隆的分身 APP。
3.  **数据存储位置**: 选择本机文件夹用于存放用户数据。

### 4. 创建与启动
1.  点击 **➕ 新建实例**，输入名称 (如 `US-Project-A`)。
2.  填写 **SOCKS5 代理** (可选): `socks5://127.0.0.1:7890`。
3.  创建后自动询问是否从原版同步扩展和配置。
4.  选中实例，点击 **📡 代理规则** → **复制完整规则**。
5.  在 Proxifier 中添加规则，Action 指向对应的代理节点。
6.  点击 **🚀 启动**。

## ⚠️ 重要提示

### Keychain 弹窗
由于修改了二进制签名（实现进程伪装），首次启动时 macOS 会弹出 **"Antigravity wants to access key..."**。
- 请输入密码并点击 **[始终允许 (Always Allow)]**。

### 登录新实例（1.18.4+ 推荐方式）
Antigravity 1.18.4+ 版本修改了 OAuth 回调验证逻辑，导致 Shim 实例无法在新实例中直接完成登录。**推荐使用【🔑 同步登录】功能**：

1. 用原版 Antigravity（或任意已登录的实例）登录目标账号。
2. 回到 AGM 选中目标实例，点击 **🔑 同步登录**。
3. 选择来源（原版 / 已登录实例），点击「确认同步」。
4. 启动目标实例，无需重新登录，直接进入已登录状态。

> **考古步骤**（1.18.4 以下版本仳用）: macOS 限制了同一 App ID 的并发登录回调。初次登录新账号时，请关闭其他所有 Antigravity 窗口，仅保留当前实例。

### 如何更新 Antigravity？
1.  下载最新版 Antigravity，安装到 Applications。
2.  在 AGM 中选中实例，点击 **♻️ 同步内核**。
3.  选择是否同时同步扩展和配置。
4.  完成！数据自动保留。

## 🏗️ 项目结构
```
ag-manager/
├── ag_manager.py      # 主入口
├── config.py          # 配置管理
├── power_manager.py   # 核心逻辑（启动、同步、垫片、Bundle ID 重签）
├── ui.py              # GUI 界面
├── theme.py           # 主题样式
├── dialogs.py         # 对话框组件
├── CHANGELOG.md       # 版本更新日志
├── DEVELOPMENT_NOTES.md # 开发注意事项与已知问题记录
└── README.md
```

## 🛠️ 技术原理

AGM 使用 APFS clone 克隆 App Bundle，通过三层技术实现进程隔离：

1. **Shell Shim**: 用脚本替换 `Electron` 和 `language_server` 二进制，运行时动态复制为带实例名的副本并执行。
2. **Bundle ID 重签**: 通过 `codesign --sign - --identifier` 给 Plugin Helper 注入包含实例名的自定义标识符（ad-hoc 签名），使 Proxifier 能通过 macOS 内核级的代码签名 Identifier 精确区分不同实例的 Plugin 流量。
3. **环境变量注入**: 直接执行 Electron 二进制（而非 `open -n -a`），确保 `AG_INSTANCE_NAME` 等环境变量正确传播到所有子进程。

## 📄 License
MIT License. 本工具仅供学习与安全研究使用。
