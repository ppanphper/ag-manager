# Changelog

## [0.3.0] - 2026-02-27

### 新增
- **Plugin Helper 流量隔离 (Plan I)**
  - ~~通过 `codesign --sign - --identifier` 给每个实例的 Plugin Helper 注入独立的 Bundle ID~~ (已废弃，破坏 AI 请求)
  - 改用 Proxifier 路径通配符 `*Antigravity-{instance}.app*` 兜底匹配 Plugin Helper 流量
  - 三层隔离：Electron 进程名 + language_server 进程名 + Plugin Bundle ID
- **配置和扩展同步**
  - 新建实例时自动询问是否从原版 Antigravity 同步扩展和配置
  - 同步内核时可选择同时同步扩展和配置
  - 增量同步扩展（已有的不覆盖），精确排除登录 Token 和工作区数据
- **强制退出功能**
  - 新增「⏹ 强制退出」按钮，通过 `pkill -9` 彻底终止实例的所有进程
  - 覆盖 Electron 主进程、所有 Helper 子进程、language_server

### 变更
- Proxifier 规则从路径通配符改为 Bundle ID 精准匹配
- 使用说明同步更新，反映三条规则的匹配方式

### 废弃方案记录
- Plan G (bash 垫片): `posix_spawn` 无法执行脚本，Plugin 进程静默启动失败
- Plan H (二进制改名 + plist CFBundleExecutable): Chromium 内部硬编码路径，应用崩溃
- Plan I (Bundle ID + codesign 重签): ad-hoc 重签破坏 Google 原始代码签名信任链，AI 请求报错 `Agent execution terminated due to error`

---

## [0.2.0] - 2026-02-26

### 新增
- **代码重构**: 将单体 `ag_manager.py` 拆分为模块化架构
  - `config.py` — 配置管理
  - `power_manager.py` — 核心逻辑（启动、同步、垫片安装）
  - `ui.py` — GUI 界面
  - `theme.py` — 主题样式
  - `dialogs.py` — 对话框组件
- **Electron 主进程垫片**: `Electron` → `Electron_{InstanceName}`
- **language_server 垫片**: `language_server_macos_arm` → `language_server_macos_arm_{InstanceName}`
- **直接执行模式**: 改用直接执行 Electron 二进制而非 `open -n -a`，确保环境变量传播

---

## [0.1.0] - 2026-02-25

### 初始版本
- APFS 零空间克隆 App Bundle
- 多实例独立 `--user-data-dir` 和 `--extensions-dir`
- 外部存储支持
- Proxifier 分流规则一键复制
- 内核同步功能
