# Antigravity Manager (AGM)

**专为 Google Antigravity 设计的极致多开与流量隔离管理器。**

AGM 是一个开源的 Python 工具，通过独特的 **Process Shim (进程垫片)** 技术，为每个 Antigravity 实例赋予独立的进程身份，从而配合 **Proxifier** 实现 100% 精准的 IP/流量隔离。

## 🌟 核心特性

- **🛡️ 绝对隔离 (Plan F)**:
    - 自动修改 Application Bundle 的内核启动逻辑。
    - 主程序伪装: `Electron` -> `Electron_{InstanceName}`
    - 插件伪装: `language_server` -> `language_server_..._{InstanceName}`
    - **效果**: 无论是在 Activity Monitor 还是 Proxifier 中，每个账号都是完全独立的 APP。

- **� 一键分流规则**:
    - 再也不用手动配置复杂的 Proxifier 规则。
    - 点击「代理规则」按钮，一键复制包含所有伪装进程名的完整规则字符串。
    - *支持自动更新组件 (Updater) 的流量拦截。*

- **♻️ 内核同步 (Sync Core)**:
    - 由于剥离了签名，自动更新被禁用（为了安全）。
    - 提供「一键同步内核」功能：当 Antigravity 发布新版时，一键将新版核心同步到所有实例，同时保留用户数据。

- **💾 外部存储支持**:
    - 支持将庞大的 App 实例存储在外接硬盘，节省本机空间。
    - 只有用户数据 (Cookies, LocalStorage) 保存在本机，确保速度。

## 🚀 快速开始

### 1. 环境准备
- macOS (Intel / Apple Silicon)
- Python 3.9+ (`brew install python3`)
- **Proxifier** (或是 Surge 等支持进程规则的网关)

### 2. 安装与运行
```bash
git clone https://github.com/ppanphper/ag-manager.git
cd ag-manager
pip3 install -r requirements.txt  # (虽然目前主要只依赖标准库和 tkinter)
python3 ag_manager.py
```

### 3. 初次设置
程序启动后，点击 **⚙️ 设置**：
1.  **源 App 路径**: 选择你安装的原始 `Antigravity.app`。
2.  **实例存储位置**: 选择一个文件夹（推荐外接硬盘）用于存放克隆的分身 APP。
3.  **数据存储位置**: 选择一个本机文件夹用于存放用户数据。

### 4. 创建与启动
1.  点击 **➕ 新建实例**，输入名称 (如 `US-Project-A`)。
2.  填写 **SOCKS5 代理** (可选，推荐): `socks5://127.0.0.1:7890`。
    - *这会作为环境变量注入，作为 Proxifier 之外的第二道防线。*
3.  选中实例，点击 **� 代理规则** -> **复制完整规则**。
4.  在 Proxifier 中添加规则，Action 指向对应的代理节点。
5.  点击 **🚀 启动**。

## ⚠️ 重要提示

### Keychain 弹窗
由于我们修改了二进制文件的签名（为了实现进程伪装），首次启动时 macOS 会弹出 **"Antigravity wants to access key..."**。
- 请输入密码并点击 **[始终允许 (Always Allow)]**。
- 这是正常且必要的安全步骤。

### 登录冲突
macOS 限制了同一 App ID 的并发登录回调。
**初次登录新账号时**，请务必关闭其他所有 Antigravity 窗口，仅保留当前实例。登录成功后即可随意多开。

### 如何更新 Antigravity？
1.  下载最新版 Antigravity，安装到 Applications。
2.  在 AGM 中选中实例，点击 **♻️ 同步内核**。
3.  完成！数据自动保留。

## 🛠️ 技术原理
AGM 使用 `shutil.copytree` 克隆 App Bundle，并注入 Shell 脚本 (Shim) 替换 `Contents/MacOS/Electron` 和 `language_server`。Shim 脚本在运行时动态将二进制文件复制为带实例名的副本并执行，从而欺骗系统和网络工具，实现“影分身”效果。

## 📄 License
MIT License. 本工具仅供学习与安全研究使用。
