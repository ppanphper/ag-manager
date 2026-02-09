# Antigravity 启动器 (Launcher) 使用说明

这个工具是一个用来管理多个 Google Antigravity 账号分身的启动器。
它的核心功能是**接管你现有的账号数据**，并为每个账号创建一个独立的物理 App，以便配合 **Proxifier** 实现精准的分流隔离。

## 🚀 快速开始

1.  **运行程序**:
    ```bash
    python3 ag_manager.py
    ```

2.  **设置数据源**:
    - 程序启动后，默认数据源是 `~/Antigravity_Avatars/data`。
    - 如果你之前使用 `antigravity-manager` 或其他工具生成了账号数据，请点击右上角的 **【📂 切换】** 按钮。
    - 选择包含你所有账号子文件夹的**父目录**。
    - *例如：如果你的账号数据在 `~/.config/antigravity-storage/user1`，请选择 `~/.config/antigravity-storage`。*

3.  **启动分身**:
    - 列表会自动刷新，显示数据源下的所有账号。
    - **双击** 列表项，或者选中后点击 **【🚀 启动环境】**。
    - **首次启动时**：工具会自动在 `~/Antigravity_Avatars/apps/` 下克隆一个名为 `Antigravity-{账号名}.app` 的物理应用。这是为了让 Proxifier 能区分不同账号。

## 🌐 Proxifier 配置指南

为了实现不同账号走不同代理，请在 Proxifier 中按以下方式配置 Rules：

1.  打开 Proxifier -> Rules。
2.  添加规则 (Add Rule)：
    - **Applications**: 点击浏览，找到 `~/Antigravity_Avatars/apps/Antigravity-{账号名}.app`。
    - **Action**: 选择对应的 Proxy 节点 (例如 Proxy US, Proxy JP)。
    - **Name**: 随便起个名字 (例如 "AG - Account US")。

## 📝 备注功能
- 在列表中选中账号，点击 **【📝 编辑备注】**。
- 你可以备注该账号对应的地区（如 "🇺🇸 美西"），方便记忆。

## 🧹 清理功能
- 如果某个分身不再使用，或者 App 文件损坏，可以点击 **【🗑️ 清理App】**。
- **注意**：这只会删除 `~/Antigravity_Avatars/apps/` 下的物理 App 文件，**绝对不会** 删除你的账号数据。下次启动时会自动重建 App。

---
**提示**: 需要安装 `tkinter` (Python 默认自带) 和 `Antigravity` 主程序。
