import os
import re
import shutil
import json
import subprocess
import threading


class AppPowerManager:
    """负责物理文件操作"""

    def __init__(self, config_mgr):
        self.cfg = config_mgr
        self._running_procs = {}  # {实例名: Popen对象}

    def sanitize_filename(self, name):
        return re.sub(r'[^\w\-\.\u4e00-\u9fa5]', '_', name).strip()

    def get_app_path(self, name):
        safe_name = self.sanitize_filename(name)
        base = self.cfg.get("apps_dir")
        return os.path.join(base, f"Antigravity-{safe_name}.app")

    def get_data_path(self, name):
        safe_name = self.sanitize_filename(name)
        base = self.cfg.get("data_dir")
        return os.path.join(base, safe_name)

    def ensure_app_created(self, name):
        """创建物理 App"""
        target_app = self.get_app_path(name)
        source_app = self.cfg.get("original_app_path")

        # 防止递归创建：如果目标路径在源路径内部，这是绝对错误的
        if os.path.abspath(target_app).startswith(os.path.abspath(source_app)):
            raise ValueError(f"错误：不能在源 App 内部创建实例！\n源: {source_app}\n目标: {target_app}\n请在设置中修改 '实例存储位置' 到其他文件夹。")

        if os.path.exists(target_app):
            return target_app, False

        # 检查源是否存在 (支持软链)
        if not os.path.exists(source_app):
            if os.path.islink(source_app):
                source_app = os.path.realpath(source_app)
                if not os.path.exists(source_app):
                    raise FileNotFoundError(f"源 App 软链指向无效: {source_app}")
            else:
                raise FileNotFoundError(f"未找到原始应用: {source_app}\n请在设置中指定正确的 Antigravity.app 路径")

        try:
            apps_dir = self.cfg.get("apps_dir")
            os.makedirs(apps_dir, exist_ok=True)
            shutil.copytree(source_app, target_app, symlinks=True)
            return target_app, True
        except Exception as e:
            raise Exception(f"克隆 App 失败: {e}")

    def install_process_shim(self, name):
        """
        [Plan D: Process Shim]
        替换 language_server 二进制为 Shell 脚本，使其在运行时动态重命名。
        解决 Proxifier 无法通过路径区分同名进程的问题。
        """
        app_path = self.get_app_path(name)
        bin_dir = os.path.join(app_path, "Contents/Resources/app/extensions/antigravity/bin")
        target_bin = os.path.join(bin_dir, "language_server_macos_arm")
        original_bin = os.path.join(bin_dir, "language_server_macos_arm.original")

        if not os.path.exists(bin_dir):
            print(f"Warning: Binary directory not found: {bin_dir}")
            return

        if os.path.exists(target_bin) and not os.path.exists(original_bin):
            subprocess.run(["mv", target_bin, original_bin], check=True)
            print(f"Backed up original binary to {original_bin}")

        if not os.path.exists(original_bin):
            print(f"Error: Original binary not found at {original_bin}")
            return

        shim_content = f"""#!/bin/bash
# Antigravity Process Shim (Created by AG Manager)

DIR=$(cd "$(dirname "$0")"; pwd)
ORIGINAL="$DIR/language_server_macos_arm.original"
INSTANCE_NAME="${{AG_INSTANCE_NAME}}"

if [ -z "$INSTANCE_NAME" ]; then
    exec "$ORIGINAL" "$@"
fi

SAFE_NAME=$(echo "$INSTANCE_NAME" | tr -cd '[:alnum:]_-')
TARGET="$DIR/language_server_macos_arm_${{SAFE_NAME}}"

if [ ! -f "$TARGET" ]; then
    cp "$ORIGINAL" "$TARGET"
    codesign --remove-signature "$TARGET" 2>/dev/null
    chmod +x "$TARGET"
fi

exec "$TARGET" "$@"
"""
        try:
            with open(target_bin, 'w') as f:
                f.write(shim_content)
            os.chmod(target_bin, 0o755)
            print(f"Installed Shim at {target_bin}")
        except Exception as e:
            print(f"Failed to install shim: {e}")

    def install_electron_shim(self, name):
        """
        [Plan F: Main Process Shim]
        替换 Contents/MacOS/Electron 主程序为 Shell 脚本。
        运行时将 Electron 复制为 Electron_{InstanceName} 并执行。
        """
        app_path = self.get_app_path(name)
        macos_dir = os.path.join(app_path, "Contents/MacOS")
        target_bin = os.path.join(macos_dir, "Electron")
        original_bin = os.path.join(macos_dir, "Electron.original")

        if not os.path.exists(macos_dir):
            return

        if os.path.exists(target_bin) and not os.path.exists(original_bin):
            subprocess.run(["mv", target_bin, original_bin], check=True)
            print(f"Backed up Electron binary to {original_bin}")

        if not os.path.exists(original_bin):
            print(f"Error: Original Electron binary not found at {original_bin}")
            return

        shim_content = f"""#!/bin/bash
# Antigravity Electron Shim (Plan F)
DIR=$(cd "$(dirname "$0")"; pwd)
ORIGINAL="$DIR/Electron.original"
INSTANCE_NAME="${{AG_INSTANCE_NAME}}"

if [ -z "$INSTANCE_NAME" ]; then
    exec "$ORIGINAL" "$@"
fi

SAFE_NAME=$(echo "$INSTANCE_NAME" | tr -cd '[:alnum:]_-')
TARGET="$DIR/Electron_${{SAFE_NAME}}"

if [ ! -f "$TARGET" ] || [ "$ORIGINAL" -nt "$TARGET" ]; then
    cp "$ORIGINAL" "$TARGET"
    codesign --remove-signature "$TARGET" 2>/dev/null
    chmod +x "$TARGET"
fi

exec "$TARGET" "$@"
"""
        try:
            with open(target_bin, 'w') as f:
                f.write(shim_content)
            os.chmod(target_bin, 0o755)
            print(f"Installed Electron Shim at {target_bin}")
        except Exception as e:
            print(f"Failed to install Electron shim: {e}")

    # [废弃方案记录]
    # Plan G (bash 垫片): posix_spawn 无法执行脚本，Plugin 进程静默启动失败
    # Plan H (二进制改名 + plist): Chromium 内部硬编码路径，应用崩溃
    # Plan I (Bundle ID + codesign 重签): ad-hoc 重签破坏 Google 原始签名信任链，AI 请求被拒绝
    # 最终方案：Plugin Helper 不做任何修改，依靠 Proxifier 路径通配符 *Antigravity-{instance}.app* 兜底分流

    def get_default_data_paths(self):
        """
        获取原版 Antigravity 的默认数据路径。
        - user_data: ~/Library/Application Support/Antigravity/
        - extensions: ~/.antigravity/extensions/
        """
        home = os.path.expanduser("~")
        return {
            "user_data": os.path.join(home, "Library/Application Support/Antigravity"),
            "extensions": os.path.join(home, ".antigravity/extensions"),
        }

    def sync_config(self, target_name, source_name=None):
        """
        从源复制扩展和核心配置到目标实例。
        
        source_name: 
            None = 原版 Antigravity（默认数据目录）
            str  = 已有实例名称
        
        复制内容：
            ✅ extensions/          — 已安装的扩展（最大痛点）
            ✅ User/settings.json   — 编辑器设置
            ✅ User/keybindings.json — 快捷键
            ✅ User/snippets/       — 代码片段
        排除内容：
            ❌ User/globalStorage/  — 登录 Token 等敏感数据
            ❌ User/workspaceStorage/ — 工作区状态
            ❌ User/History/        — 编辑历史
        """
        # 确定源路径
        if source_name is None:
            paths = self.get_default_data_paths()
            src_user_data = paths["user_data"]
            src_extensions = paths["extensions"]
            source_label = "原版 Antigravity"
        else:
            src_base = self.get_data_path(source_name)
            src_user_data = os.path.join(src_base, "user_data")
            src_extensions = os.path.join(src_base, "extensions")
            source_label = f"实例 [{source_name}]"

        # 确定目标路径
        tgt_base = self.get_data_path(target_name)
        tgt_user_data = os.path.join(tgt_base, "user_data")
        tgt_extensions = os.path.join(tgt_base, "extensions")

        synced = []

        # 1. 同步扩展
        if os.path.exists(src_extensions):
            os.makedirs(tgt_extensions, exist_ok=True)
            src_ext_items = [d for d in os.listdir(src_extensions) 
                          if os.path.isdir(os.path.join(src_extensions, d))]
            copied_ext = 0
            for ext_dir in src_ext_items:
                src_ext = os.path.join(src_extensions, ext_dir)
                tgt_ext = os.path.join(tgt_extensions, ext_dir)
                if not os.path.exists(tgt_ext):
                    shutil.copytree(src_ext, tgt_ext, symlinks=True)
                    copied_ext += 1
            # 同步 extensions.json（扩展元数据）
            for meta_file in ["extensions.json"]:
                src_meta = os.path.join(src_extensions, meta_file)
                tgt_meta = os.path.join(tgt_extensions, meta_file)
                if os.path.exists(src_meta):
                    shutil.copy2(src_meta, tgt_meta)
            synced.append(f"扩展: {copied_ext} 个新扩展")
            print(f"Synced {copied_ext} extensions from {source_label}")
        else:
            print(f"Warning: Source extensions not found: {src_extensions}")

        # 2. 同步核心配置文件
        src_user_dir = os.path.join(src_user_data, "User")
        tgt_user_dir = os.path.join(tgt_user_data, "User")
        os.makedirs(tgt_user_dir, exist_ok=True)

        # 单文件复制
        for config_file in ["settings.json", "keybindings.json"]:
            src_file = os.path.join(src_user_dir, config_file)
            tgt_file = os.path.join(tgt_user_dir, config_file)
            if os.path.exists(src_file):
                shutil.copy2(src_file, tgt_file)
                synced.append(config_file)
                print(f"Synced {config_file}")

        # 目录复制
        for config_dir in ["snippets"]:
            src_dir = os.path.join(src_user_dir, config_dir)
            tgt_dir = os.path.join(tgt_user_dir, config_dir)
            if os.path.exists(src_dir):
                if os.path.exists(tgt_dir):
                    shutil.rmtree(tgt_dir)
                shutil.copytree(src_dir, tgt_dir, symlinks=True)
                synced.append(config_dir)
                print(f"Synced {config_dir}/")

        return synced

    def get_available_sources(self):
        """获取可用的配置同步源列表（原版 + 已有实例）"""
        sources = [("📦 原版 Antigravity (默认)", None)]
        for acc in self.cfg.get_accounts():
            name = acc["name"]
            data_path = self.get_data_path(name)
            if os.path.exists(os.path.join(data_path, "user_data")):
                sources.append((f"🔄 实例: {name}", name))
        return sources

    def sync_kernel(self, name):
        """
        [Maintenance Feature]
        同步内核: 使用源 App 覆盖实例 App，保留用户数据。
        """
        source_app = self.cfg.get("original_app_path")
        if not source_app or not os.path.exists(source_app):
            raise FileNotFoundError(f"源应用程序未找到: {source_app}\n请在设置中指定正确的 Antigravity.app 路径")

        app_path = self.get_app_path(name)

        apps_dir = self.cfg.get("apps_dir")
        if not os.path.abspath(app_path).startswith(os.path.abspath(apps_dir)) or not app_path.endswith(".app"):
            raise ValueError(f"安全拒绝: 试图删除非托管目录 {app_path}")

        print(f"Removing old app kernel: {app_path}")
        if os.path.exists(app_path):
            shutil.rmtree(app_path)

        print(f"Cloning new kernel from: {source_app}")
        shutil.copytree(source_app, app_path, symlinks=True)

        print("Re-applying isolation shims...")
        self.install_process_shim(name)
        self.install_electron_shim(name)

        print(f"Kernel sync completed for {name}")

    def launch(self, name):
        app_path = self.get_app_path(name)
        base_data_path = self.get_data_path(name)

        user_data_dir = os.path.join(base_data_path, "user_data")
        extensions_dir = os.path.join(base_data_path, "extensions")

        if not os.path.exists(app_path):
            self.ensure_app_created(name)

        self.install_process_shim(name)
        self.install_electron_shim(name)


        for p in [user_data_dir, extensions_dir]:
            if not os.path.exists(p):
                os.makedirs(p, exist_ok=True)

        # [Critical] 必须直接执行二进制，不能用 `open -n -a`
        # 因为 macOS LaunchServices 不继承环境变量，会导致 AG_INSTANCE_NAME 丢失，
        # 进而使所有垫片脚本走 fallback 分支（exec 原始二进制而非带后缀的副本）。
        macos_dir = os.path.join(app_path, "Contents", "MacOS")
        executable_path = None
        
        if os.path.exists(macos_dir):
            candidates = ["Electron", "Antigravity"]
            for f_name in os.listdir(macos_dir):
                fp = os.path.join(macos_dir, f_name)
                if os.path.isfile(fp) and os.access(fp, os.X_OK):
                    if f_name in candidates:
                        executable_path = fp
                        break
                    if not executable_path:
                        executable_path = fp

        if executable_path:
            cmd = [
                executable_path,
                f"--user-data-dir={user_data_dir}",
                f"--extensions-dir={extensions_dir}"
            ]
        else:
            # Fallback: 直接 exec 找不到时退回 open（此情况下环境变量会丢失）
            print("Warning: Could not find executable in Contents/MacOS, falling back to open -n -a (env vars will be lost)")
            cmd = [
                "open", "-n",
                "-a", app_path,
                "--args",
                f"--user-data-dir={user_data_dir}",
                f"--extensions-dir={extensions_dir}"
            ]

        account_config = next((a for a in self.cfg.get_accounts() if a["name"] == name), None)
        env = os.environ.copy()

        if account_config and account_config.get("proxy_url"):
            proxy_url = account_config["proxy_url"]
            print(f"Bypassing internal proxy injection, relying on Proxifier for {proxy_url}")
            no_proxy = "localhost,127.0.0.1"
            env["NO_PROXY"] = no_proxy
            env["no_proxy"] = no_proxy

        env["AG_INSTANCE_NAME"] = name
        print(f"Injected AG_INSTANCE_NAME={name}")

        print(f"Launching with isolation: {' '.join(cmd)}")

        self.clear_vscode_proxy_settings(user_data_dir)

        proc = subprocess.Popen(cmd, env=env, start_new_session=True, stdout=None, stderr=None)
        self._running_procs[name] = proc

        # 启动守护线程：主进程退出后自动清理残留子进程
        t = threading.Thread(target=self._watchdog, args=(name, proc), daemon=True)
        t.start()

    def clear_vscode_proxy_settings(self, user_data_dir):
        """清除 VS Code 旧版残留的代理配置避免引发 Electron 协议解析异常"""
        try:
            settings_dir = os.path.join(user_data_dir, "User")
            settings_path = os.path.join(settings_dir, "settings.json")

            if not os.path.exists(settings_path):
                return

            content = {}
            try:
                with open(settings_path, 'r') as f:
                    content = json.load(f)
            except:
                print("Warning: Failed to parse existing settings.json during proxy cleanup.")
                return

            keys_to_remove = ["http.proxy", "http.proxyStrictSSL", "http.proxySupport"]
            modified = False
            for k in keys_to_remove:
                if k in content:
                    del content[k]
                    modified = True

            if modified:
                with open(settings_path, 'w') as f:
                    json.dump(content, f, indent=4)
                    print(f"Cleared legacy proxy settings in {settings_path}")

        except Exception as e:
            print(f"Failed to clear settings.json proxy configuration: {e}")

    def delete_resources(self, name, delete_data=False):
        app_path = self.get_app_path(name)
        data_path = self.get_data_path(name)

        deleted_app = False
        deleted_data = False

        if os.path.exists(app_path):
            shutil.rmtree(app_path)
            deleted_app = True

        if delete_data and os.path.exists(data_path):
            shutil.rmtree(data_path)
            deleted_data = True

        return deleted_app, deleted_data

    def _watchdog(self, name, proc):
        """
        守护线程：等待 Electron 主进程退出后，自动清理所有残留子进程。
        解决 IDE 关闭后 language_server、crashpad_handler 等进程残留的问题。
        """
        try:
            proc.wait()  # 阻塞直到主进程退出
            print(f"[Watchdog] 实例 [{name}] 主进程已退出 (PID={proc.pid}, code={proc.returncode})，开始清理残留进程...")
            import time
            time.sleep(1)  # 等待子进程自然退出
            self.force_quit(name)
            print(f"[Watchdog] 实例 [{name}] 清理完成。")
        except Exception as e:
            print(f"[Watchdog] 实例 [{name}] 清理异常: {e}")
        finally:
            self._running_procs.pop(name, None)

    def cleanup_all(self):
        """清理所有已跟踪实例的残留进程（AG Manager 退出时调用）"""
        for name in list(self._running_procs.keys()):
            try:
                self.force_quit(name)
            except Exception as e:
                print(f"cleanup_all: 清理 [{name}] 失败: {e}")
        self._running_procs.clear()

    def force_quit(self, name):
        """
        强制退出指定实例的所有进程（含 Helper 子进程）。
        通过匹配 App 路径来精确杀死与此实例相关的全部进程。
        """
        safe_name = self.sanitize_filename(name)
        app_path = self.get_app_path(name)
        
        killed = 0
        try:
            # 1. 通过 App 路径匹配杀死所有进程
            result = subprocess.run(
                ["pkill", "-9", "-f", f"Antigravity-{safe_name}.app"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                killed += 1
            
            # 2. 同时杀死可能漏网的 Electron 改名进程
            subprocess.run(
                ["pkill", "-9", "-f", f"Electron_{safe_name}"],
                capture_output=True, text=True
            )
            
            # 3. 杀死 language_server 改名进程
            subprocess.run(
                ["pkill", "-9", "-f", f"language_server_macos_arm_{safe_name}"],
                capture_output=True, text=True
            )
        except Exception as e:
            print(f"Error during force quit: {e}")
        
        # 验证是否全部清理干净
        import time
        time.sleep(0.5)
        check = subprocess.run(
            ["pgrep", "-f", f"Antigravity-{safe_name}.app"],
            capture_output=True, text=True
        )
        remaining = len(check.stdout.strip().split('\n')) if check.stdout.strip() else 0
        
        return remaining == 0
