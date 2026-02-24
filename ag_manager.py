import sys
import os
import re
import shutil
import json
import time
import subprocess

# --- 环境自检 (Self-Inspect) ---
try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, filedialog, ttk
except ImportError:
    print("\n❌ 错误: 未检测到 Tkinter 模块 (GUI 基础库)")
    sys.exit(1)

# --- 常量配置 ---
DEFAULT_BASE_DIR = os.path.expanduser("~/Antigravity_Avatars")
CONFIG_FILE = os.path.join(DEFAULT_BASE_DIR, "config.json")

# 默认路径
# 优先尝试 Antigravity.app (用户报告的实际名称)
DEFAULT_ORIGINAL_APP_CANDIDATES = [
    "/Applications/Antigravity.app",
    os.path.expanduser("~/Applications/Antigravity.app")
]
DEFAULT_APPS_DIR = os.path.join(DEFAULT_BASE_DIR, "apps")
DEFAULT_DATA_DIR = os.path.join(DEFAULT_BASE_DIR, "data") 

class ConfigManager:
    """配置管理 (包含账号列表 & 路径设置)"""
    def __init__(self):
        # 自动探测最佳初始路径
        self.detected_app_path = None
        for path in DEFAULT_ORIGINAL_APP_CANDIDATES:
            if os.path.exists(path):
                self.detected_app_path = path
                break

        self.config = {
            "original_app_path": self.detected_app_path or DEFAULT_ORIGINAL_APP_CANDIDATES[0],
            "apps_dir": DEFAULT_APPS_DIR,
            "data_dir": DEFAULT_DATA_DIR,
            "accounts": [], 
            "column_widths": {"name": 200, "note": 200, "last_used": 150}
        }
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    self.config.update(saved)
                
                # [Cleaned Request] 移除了之前针对 data_source 的自动清理逻辑，保持代码整洁。
                
                # 自动自愈：如果配置文件里的路径都不存在，但我们刚才探测到了有效路径，则覆盖
                current_path = self.config.get("original_app_path")
                # 兼容性检查
                if (not current_path or not os.path.exists(current_path)) and self.detected_app_path:
                    print(f"Config path invalid/missing, auto-updating to: {self.detected_app_path}")
                    self.config["original_app_path"] = self.detected_app_path
                    self.save()

            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key):
        return self.config.get(key)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def get_accounts(self):
        return self.config.get("accounts", [])

    def add_account(self, name, note="", proxy_url=""):
        accounts = self.get_accounts()
        if any(a["name"] == name for a in accounts):
            return False
        accounts.append({
            "name": name,
            "note": note,
            "proxy_url": proxy_url,
            "created_at": time.time(),
            "last_used": 0
        })
        self.config["accounts"] = accounts
        self.save()
        return True

    def delete_account(self, name):
        accounts = [a for a in self.get_accounts() if a["name"] != name]
        self.config["accounts"] = accounts
        self.save()

    def update_account(self, name, **kwargs):
        for acc in self.config["accounts"]:
            if acc["name"] == name:
                acc.update(kwargs)
                self.save()
                return True
        return False

class AppPowerManager:
    """负责物理文件操作"""
    
    def __init__(self, config_mgr):
        self.cfg = config_mgr

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
            return target_app, False # Already exists

        # 检查源是否存在 (支持软链)
        if not os.path.exists(source_app):
            # 再次尝试 resolve 软链
            if os.path.islink(source_app):
                source_app = os.path.realpath(source_app)
                if not os.path.exists(source_app):
                    raise FileNotFoundError(f"源 App 软链指向无效: {source_app}")
            else:
                raise FileNotFoundError(f"未找到原始应用: {source_app}\n请在设置中指定正确的 Antigravity.app 路径")

        try:
            apps_dir = self.cfg.get("apps_dir")
            os.makedirs(apps_dir, exist_ok=True)
            
            # 使用 copytree 复制内容
            # symlinks=True 是关键，因为它保留了 .app 包内部的软连接结构
            shutil.copytree(source_app, target_app, symlinks=True)
            return target_app, True # Created new
        except Exception as e:
            raise Exception(f"克隆 App 失败: {e}")

    def install_process_shim(self, name):
        """
        [Plan D: Process Shim]
        替换 language_server 二进制为 Shell 脚本，使其在运行时动态重命名。
        解决 Proxifier 无法通过路径区分同名进程的问题。
        """
        app_path = self.get_app_path(name)
        # 目标二进制路径 (Hardcoded based on Antigravity structure)
        bin_dir = os.path.join(app_path, "Contents/Resources/app/extensions/antigravity/bin")
        target_bin = os.path.join(bin_dir, "language_server_macos_arm")
        original_bin = os.path.join(bin_dir, "language_server_macos_arm.original")
        
        if not os.path.exists(bin_dir):
            print(f"Warning: Binary directory not found: {bin_dir}")
            return

        # 1. 备份原文件 (如果还没备份)
        if os.path.exists(target_bin) and not os.path.exists(original_bin):
            # 确认 target_bin 是二进制不是脚本 (简单读个头或者根据扩展名，这里假设通过是否已存在 .original 判断)
            # 或者强制覆盖
            subprocess.run(["mv", target_bin, original_bin], check=True)
            print(f"Backed up original binary to {original_bin}")
        
        # 如果原文件不存在但备份也不存在，说明路径可能不对，跳过
        if not os.path.exists(original_bin):
            print(f"Error: Original binary not found at {original_bin}")
            return

        # 2. 写入 Shim 脚本
        shim_content = f"""#!/bin/bash
# Antigravity Process Shim (Created by AG Manager)
# This script wraps the original binary to enable dynamic renaming for Proxifier Identity.

DIR=$(cd "$(dirname "$0")"; pwd)
ORIGINAL="$DIR/language_server_macos_arm.original"
INSTANCE_NAME="${{AG_INSTANCE_NAME}}"

# Fallback: If no instance name provided (manual run), run original directly
if [ -z "$INSTANCE_NAME" ]; then
    exec "$ORIGINAL" "$@"
fi

# Sanitize instance name
SAFE_NAME=$(echo "$INSTANCE_NAME" | tr -cd '[:alnum:]_-')
TARGET="$DIR/language_server_macos_arm_${{SAFE_NAME}}"

# Create a copy if it doesn't exist.
# We copy instead of symlink because some tools resolve symlinks to raw binary path.
if [ ! -f "$TARGET" ]; then
    cp "$ORIGINAL" "$TARGET"
    # [Plan F Critical] Strip signature to avoid SIGKILL (Code Signature Invalid)
    # Renaming a signed binary invalidates its signature on macOS
    codesign --remove-signature "$TARGET" 2>/dev/null
    chmod +x "$TARGET"
fi

# Execute the renamed binary with all original arguments
# exec replaces the current shell process, preserving PID (mostly) and memory
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
        解决 Proxifier 无法区分不同实例主进程(及其子进程如 Updater)的问题。
        """
        app_path = self.get_app_path(name)
        macos_dir = os.path.join(app_path, "Contents/MacOS")
        target_bin = os.path.join(macos_dir, "Electron")
        original_bin = os.path.join(macos_dir, "Electron.original")
        
        if not os.path.exists(macos_dir):
            return

        # 1. 备份 (First run)
        if os.path.exists(target_bin) and not os.path.exists(original_bin):
            # Check if it's already a script? We assume if .original missing, target is binary
            subprocess.run(["mv", target_bin, original_bin], check=True)
            print(f"Backed up Electron binary to {original_bin}")
            
        # If original_bin doesn't exist after backup attempt, something is wrong
        if not os.path.exists(original_bin):
            print(f"Error: Original Electron binary not found at {original_bin}")
            return

        # 2. 写入 Shim 脚本
        # 注意: Electron 对 argv[0] 比较敏感，但通常只影响 crash reporter 等
        # 关键是 exec 后的进程名变了，Proxifier 就能抓到了
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

# Copy logic (Start fresh if binary changed)
if [ ! -f "$TARGET" ] || [ "$ORIGINAL" -nt "$TARGET" ]; then
    cp "$ORIGINAL" "$TARGET"
    # [Plan F Critical] Strip signature to avoid SIGKILL (Code Signature Invalid)
    # Renaming a signed binary invalidates its signature on macOS
    codesign --remove-signature "$TARGET" 2>/dev/null
    chmod +x "$TARGET"
fi

# Exec the renamed binary
exec "$TARGET" "$@"
"""
        try:
            with open(target_bin, 'w') as f:
                f.write(shim_content)
            os.chmod(target_bin, 0o755)
            print(f"Installed Electron Shim at {target_bin}")
        except Exception as e:
            print(f"Failed to install Electron shim: {e}")

    def sync_kernel(self, name):
        """
        [Maintenance Feature]
        同步内核 (Sync Kernel): 使用源 App 覆盖实例 App，保留用户数据。
        解决因签名剥离导致无法自动更新的问题。
        """
        source_app = self.cfg.get("original_app_path")
        if not source_app or not os.path.exists(source_app):
            raise FileNotFoundError(f"源应用程序未找到: {source_app}\n请在设置中指定正确的 Antigravity.app 路径")

        app_path = self.get_app_path(name)
        
        # Safety Check: Ensure we are deleting a valid app bundle inside apps_dir
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
        
        # [Plan D & F] Install Shims before launch
        self.install_process_shim(name)
        self.install_electron_shim(name)
        
        # [Extension Isolation] 物理隔离核心：分离 UserData 和 Extensions
        # 这样 language_server 等插件进程的路径也会是独立的，方便 Proxifier 抓取
        user_data_dir = os.path.join(base_data_path, "user_data")
        extensions_dir = os.path.join(base_data_path, "extensions")

        if not os.path.exists(app_path):
            self.ensure_app_created(name)
        
        for p in [user_data_dir, extensions_dir]:
            if not os.path.exists(p):
                os.makedirs(p, exist_ok=True)

        # [Critical Change] Use direct executable path instead of `open` command
        # `open` command on macOS does NOT pass environment variables to the launched app (SIP/LaunchServices restriction)
        # We must execute the binary directly to ensure HTTP_PROXY is inherited by child processes (language_server)
        
        # 1. Find the executable in Contents/MacOS
        macos_dir = os.path.join(app_path, "Contents", "MacOS")
        executable_path = None
        
        if os.path.exists(macos_dir):
            # Try to find 'Electron' or 'Antigravity' or any executable
            candidates = ["Electron", "Antigravity"]
            # Also search for any file that is executable
            for f in os.listdir(macos_dir):
                fp = os.path.join(macos_dir, f)
                if os.path.isfile(fp) and os.access(fp, os.X_OK):
                     # Prefer candidates if match
                     if f in candidates:
                         executable_path = fp
                         break
                     # Fallback to first executable found if not verified
                     if not executable_path:
                         executable_path = fp
        
        if not executable_path:
             # Fallback to open if binary triggers weird error (unlikely)
             print("Warning: Could not find executable in Contents/MacOS, falling back to open -n -a")
             cmd = [
                "open", "-n", 
                "-a", app_path, 
                "--args", 
                f"--user-data-dir={user_data_dir}",
                f"--extensions-dir={extensions_dir}" 
            ]
        else:
            cmd = [
                executable_path,
                f"--user-data-dir={user_data_dir}",
                f"--extensions-dir={extensions_dir}"
            ]

        # [Hybrid Proxy Injection]
        # 读取配置中的代理设置
        account_config = next((a for a in self.cfg.get_accounts() if a["name"] == name), None)
        env = os.environ.copy()
        
        if account_config and account_config.get("proxy_url"):
            proxy_url = account_config["proxy_url"]
            print(f"Injecting proxy: {proxy_url}")
            
            # 1. 注入 VS Code Settings (User/settings.json)
            # 这是最关键的一步，因为 VS Code 及其插件通常优先读取内部配置
            self.inject_vscode_settings(user_data_dir, proxy_url)
            
            # 2. 注入 Electron 启动参数 (管住主进程)
            cmd.append(f"--proxy-server={proxy_url}")
            
            # 3. 注入环境变量 (管住 language_server 等子进程)
            # 注意: 某些工具可能只认 http_proxy (小写) 或 HTTP_PROXY (大写)，为了保险起见全部设置
            env["HTTP_PROXY"] = proxy_url
            env["HTTPS_PROXY"] = proxy_url
            env["ALL_PROXY"] = proxy_url
            env["http_proxy"] = proxy_url
            env["https_proxy"] = proxy_url
            env["all_proxy"] = proxy_url
            env["GRPC_PROXY"] = proxy_url # Google tools use gRPC
            env["grpc_proxy"] = proxy_url
            
            # 4. NO_PROXY (Localhost bypass)
            no_proxy = "localhost,127.0.0.1"
            env["NO_PROXY"] = no_proxy
            env["no_proxy"] = no_proxy
            
        # [Plan D: Process Shim] Inject Instance Name
        env["AG_INSTANCE_NAME"] = name
        print(f"Injected AG_INSTANCE_NAME={name}")
        
        print(f"Launching with isolation: {' '.join(cmd)}")
        # Use Popen with start_new_session=True to detach process properly
        subprocess.Popen(cmd, env=env, start_new_session=True, stdout=None, stderr=None)

    def inject_vscode_settings(self, user_data_dir, proxy_url):
        """注入 VS Code 代理配置到 settings.json"""
        try:
            settings_dir = os.path.join(user_data_dir, "User")
            os.makedirs(settings_dir, exist_ok=True)
            settings_path = os.path.join(settings_dir, "settings.json")
            
            content = {}
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, 'r') as f:
                        # JSON allowed to have comments in VS Code but standard json lib might fail
                        # simple load for now
                        content = json.load(f)
                except:
                    # If failed to load (e.g. comments), start fresh or skip?
                    # Start fresh is safer for ensuring proxy works, but destructive.
                    # Given this is a managed instance, we prioritize functionality.
                    print("Warning: Failed to parse existing settings.json, overwriting.")
                    pass
            
            # Update Proxy Settings
            content["http.proxy"] = proxy_url
            content["http.proxyStrictSSL"] = False # Often needed for self-signed proxies
            content["http.proxySupport"] = "on" # Force on
            
            with open(settings_path, 'w') as f:
                json.dump(content, f, indent=4)
                print(f"Updated settings.json at {settings_path}")
                
        except Exception as e:
            print(f"Failed to inject settings.json: {e}")

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

class SettingsDialog:
    def __init__(self, parent, cfg):
        self.top = tk.Toplevel(parent)
        self.top.title("⚙️ 全局设置")
        self.top.geometry("650x450")
        self.cfg = cfg
        self.setup_ui()
        
    def setup_ui(self):
        # 1. 原始应用路径
        self.create_path_entry("原始 Antigravity.app 路径 (Source):", "original_app_path", is_app_bundle=True)
        # 2. 实例存储路径
        self.create_path_entry("实例(App) 存储位置 (Target, 可选外接磁盘):", "apps_dir", is_app_bundle=False)
        # 3. 数据存储路径
        self.create_path_entry("用户数据(Data) 存储位置:", "data_dir", is_app_bundle=False)
        
        btn_frame = tk.Frame(self.top, pady=20)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="保存并关闭", command=self.top.destroy, width=15).pack()

    def create_path_entry(self, label, key, is_app_bundle):
        frame = tk.Frame(self.top, pady=10, padx=10)
        frame.pack(fill=tk.X)
        
        lbl_frame = tk.Frame(frame)
        lbl_frame.pack(fill=tk.X)
        tk.Label(lbl_frame, text=label, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        path_var = tk.StringVar(value=self.cfg.get(key))
        
        # 状态指示灯
        status_lbl = tk.Label(lbl_frame, text="", font=("Arial", 9))
        status_lbl.pack(side=tk.RIGHT)
        
        entry_frame = tk.Frame(frame)
        entry_frame.pack(fill=tk.X, pady=2)
        
        entry = tk.Entry(entry_frame, textvariable=path_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def check_path(*args):
            p = path_var.get()
            # 宽容检查: 如果是 .app，只要也是文件夹就行
            is_valid = os.path.exists(p)
            status_lbl.config(text="✅ 有效" if is_valid else "❌ 无效", fg="green" if is_valid else "red")
            
            # 防呆检测：apps_dir 不能是 original_app_path 的子目录
            if key == "apps_dir":
                orig = self.cfg.get("original_app_path")
                if orig and p and os.path.abspath(p).startswith(os.path.abspath(orig)):
                    status_lbl.config(text="❌ 错误: 不能在源App内部", fg="red")
            
            self.cfg.set(key, p)
        
        path_var.trace_add("write", check_path)
        check_path() # Init check

        def browse():
            if is_app_bundle:
                # 关键修复：macOS 下 .app 是目录，必须用 askdirectory 才能选中
                path = filedialog.askdirectory(title="选择 Antigravity.app (它是一个文件夹)")
            else:
                path = filedialog.askdirectory(title="选择文件夹")
                
            if path:
                if is_app_bundle and not path.endswith(".app"):
                    messagebox.showwarning("提示", "你选择的似乎不是 .app 应用包")
                
                path_var.set(path)

        tk.Button(entry_frame, text="📂", command=browse).pack(side=tk.RIGHT, padx=5)


        tk.Button(entry_frame, text="📂", command=browse).pack(side=tk.RIGHT, padx=5)

class InstanceEditorDialog:
    """新建/编辑实例弹窗"""
    def __init__(self, parent, existing_data=None):
        self.top = tk.Toplevel(parent)
        self.top.title("新建实例" if not existing_data else "编辑实例")
        self.top.geometry("400x350")
        self.result = None
        
        # UI Elements
        tk.Label(self.top, text="实例名称 (例如: US-Project-01):").pack(anchor="w", padx=20, pady=(20, 5))
        self.name_var = tk.StringVar(value=existing_data["name"] if existing_data else "")
        self.name_entry = tk.Entry(self.top, textvariable=self.name_var)
        self.name_entry.pack(fill=tk.X, padx=20)
        if existing_data: # Name is key, disable editing for now (simplification)
            self.name_entry.config(state="disabled")

        tk.Label(self.top, text="备注信息 (可选):").pack(anchor="w", padx=20, pady=(15, 5))
        self.note_var = tk.StringVar(value=existing_data.get("note", "") if existing_data else "")
        tk.Entry(self.top, textvariable=self.note_var).pack(fill=tk.X, padx=20)

        tk.Label(self.top, text="代理地址 (可选, 推荐 SOCKS5):").pack(anchor="w", padx=20, pady=(15, 5))
        self.proxy_var = tk.StringVar(value=existing_data.get("proxy_url", "") if existing_data else "")
        tk.Entry(self.top, textvariable=self.proxy_var).pack(fill=tk.X, padx=20)
        tk.Label(self.top, text="例如: socks5://127.0.0.1:7890\n若填写，启动时会自动注入代理参数。", 
                 fg="gray", font=("Arial", 9), justify=tk.LEFT).pack(anchor="w", padx=20)

        btn_frame = tk.Frame(self.top, pady=20)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="确定", command=self.on_ok, width=10).pack(pady=10)
        
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

class AGManagerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity 启动器 (外部存储适配版)")
        self.root.geometry("650x500")
        
        self.cfg = ConfigManager()
        self.mgr = AppPowerManager(self.cfg)
        
        self.setup_ui()
        self.check_env()
        self.refresh_list()

    def check_env(self):
        """检查环境，如果配置不对自动弹出设置"""
        src = self.cfg.get("original_app_path")
        # 宽容检查: 只要原来的路径存在就行，不管是文件、目录还是软链
        if not os.path.exists(src) and not os.path.islink(src):
             # 延迟弹出，让主界面先画出来
             self.root.after(500, lambda: self.prompt_inital_setup(src))

    def prompt_inital_setup(self, path):
        if messagebox.askyesno("初始化配置", f"未检测到原始应用路径：\n{path}\n\nAntigravity.app 未安装或路径不正确。\n是否现在手动指定？"):
            SettingsDialog(self.root, self.cfg)

    def setup_ui(self):
        # 顶部工具栏
        toolbar = tk.Frame(self.root, pady=10)
        toolbar.pack(fill=tk.X, padx=10)
        
        tk.Button(toolbar, text="➕ 新建实例", command=self.add_instance, font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        
        # 设置按钮
        tk.Button(toolbar, text="⚙️ 设置路径", command=lambda: SettingsDialog(self.root, self.cfg)).pack(side=tk.RIGHT)
        tk.Button(toolbar, text="📖 使用说明", command=self.show_instructions).pack(side=tk.RIGHT, padx=5)

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
        self.action_frame = tk.Frame(self.root, pady=15) # Renamed from btn_frame to action_frame as per instruction
        self.action_frame.pack(fill=tk.X)
        
        # Define BG_DARK for consistency with instruction's button styles
        BG_DARK = "#2b2b2b" 

        tk.Button(self.action_frame, text="🚀 启动", command=self.launch_current, font=("Arial", 12, "bold"), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(self.action_frame, text="📡 代理规则", command=self.view_rules, font=("Arial", 12), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(self.action_frame, text="♻️ 同步内核", command=self.sync_kernel_ui, font=("Arial", 12), width=10).pack(side=tk.LEFT, padx=5)
        # Spacer
        tk.Label(self.action_frame, text="", bg=BG_DARK, width=2).pack(side=tk.LEFT)
        tk.Button(self.action_frame, text="🗑️ 删除", command=self.delete_current, font=("Arial", 12), width=8).pack(side=tk.RIGHT, padx=5)
        tk.Button(self.action_frame, text="⚙️ 设置", command=self.edit_instance, font=("Arial", 12), width=8).pack(side=tk.RIGHT, padx=5)
        
        # 底部状态栏显示当前存储路径
        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var, fg="gray", font=("Arial", 10), anchor="w").pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
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
            # 检查物理文件状态
            app_path = self.mgr.get_app_path(name)
            status = "✅ 正常" if os.path.exists(app_path) else "⚠️ 未创建"
            
            self.tree.insert("", tk.END, values=(name, f"{acc.get('note', '')} {('[Proxy]' if acc.get('proxy_url') else '')}", status), iid=name)

    def add_instance(self):
        # 使用自定义弹窗获取所有信息
        dialog = InstanceEditorDialog(self.root)
        if not dialog.result: return
        
        data = dialog.result
        name = data["name"]
        note = data["note"]
        proxy = data["proxy_url"]

        if self.cfg.add_account(name, note, proxy):
            try:
                # 立即生成物理 App
                app_path, created = self.mgr.ensure_app_created(name)
                self.refresh_list()
                self.tree.selection_set(name)
                self.show_proxifier_guide(name, app_path)
            except Exception as e:
                # 如果是递归错误，直接弹窗提示，不显示 Stack Trace
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
        win.geometry("600x480")
        
        # Dark Theme
        BG_DARK = "#2b2b2b"
        FG_LIGHT = "#ffffff"
        
        # Set window background
        try: win.configure(bg=BG_DARK)
        except: pass
        
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
            "务必添加两条规则：\n"
            "   A. 主程序路径 (App)\n"
            "   B. 插件路径 (.../extensions/*)\n\n"
            "💡关于原始实例 (Original App):\n"
            "如果你想代理【原始未隔离】的 Antigravity，规则通常是：\n"
            "   A. /Applications/Antigravity.app\n"
            "   B. ~/.antigravity/extensions/*\n"
            "   (建议尽量使用本工具创建隔离分身，管理更方便)\n"
        )
        
        text_area = tk.Text(win, wrap=tk.WORD, font=("Arial", 11), padx=10, pady=10, bg=BG_DARK, fg=FG_LIGHT, selectbackground="#555555", relief=tk.FLAT)
        text_area.insert(tk.END, content)
        
        # Highlight crucial parts
        text_area.tag_config("bold", font=("Arial", 11, "bold"), foreground="#4FC3F7") # Light Blue
        text_area.tag_config("red", foreground="#FFAB91") # Light Orange/Rust
        
        text_area.tag_add("bold", "1.0", "1.7") # 核心机制
        text_area.tag_add("bold", "6.0", "6.18") # 关键操作
        text_area.tag_add("red", "6.0", "6.18")
        
        text_area.config(state="disabled")
        text_area.pack(fill=tk.BOTH, expand=True)
        
        # Frame for OK button to match BG
        btn_frame = tk.Frame(win, bg=BG_DARK, pady=10)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(btn_frame, text="明白", command=win.destroy, bg="#2196F3", fg="white", highlightbackground=BG_DARK, width=15).pack()

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
        win.geometry("600x500")
        
        # Dark Theme Backgrounds
        BG_DARK = "#2b2b2b"
        FG_LIGHT = "#ffffff"
        ENTRY_BG = "#3c3c3c"
        
        # Set window background (if possible, though frames usually cover it)
        try: win.configure(bg=BG_DARK)
        except: pass
        
        # 获取隔离的数据目录
        data_path = self.mgr.get_data_path(name)
        extensions_path = os.path.join(data_path, "extensions")
        
        tk.Label(win, text=f"为实例 [{name}] 配置分流", font=("Arial", 14, "bold"), fg="#4FC3F7", bg=BG_DARK).pack(pady=10)
        
        info_frame = tk.Frame(win, padx=10, pady=5, bg=BG_DARK)
        info_frame.pack(fill=tk.BOTH, expand=True)

        # 规则 1: 主程序 (App & Internal Binaries)
        # [Critical Fix] Explicitly list embedded binaries because wildcards fail on deep paths
        # 显式列出 language_server_macos_arm 的完整路径
        info_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Process Shim Rules (Plan D & F - Level 3)
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '', name)
        
        # Shim 1: Language Server
        ls_rule = f'"language_server_macos_arm_{safe_name}"'
        # Shim 2: Main Electron Process (New in Plan F)
        elec_rule = f'"Electron_{safe_name}"'

        # 2. App Bundle Rule (Fallback)
        # 既然有了 Shim，主程序二进制路径 (MacOS/Electron) 就不需要显式列出了，
        # 因为它现在是脚本，最终跑的是 Electron_{Name}。
        # 保留 App Bundle 路径和 Extensions 通配符作为兜底。
        ls_path = os.path.join(app_path, "Contents/Resources/app/extensions/antigravity/bin/language_server_macos_arm")
        app_rule = f'"{app_path}"; "{ls_path}"; "{app_path}/*"'

        # 3. Extensions Wildcard Rule (Plan A - Level 1 - Fallback)
        ext_rule = f'"{extensions_path}/*"' 

        # Combine ALL (separated by ;)
        # 优先匹配 Shim 后的具体进程名
        full_rule = f"{elec_rule}; {ls_rule}; {app_rule}; {ext_rule}"

        # -------------------------------------------------------------------------
        # [UI - Simplified]
        # -------------------------------------------------------------------------
        
        # Headline
        tk.Label(info_frame, text="✨ 一键配置 (完美分流版)", font=("Arial", 12, "bold"), fg="#4FC3F7", bg=BG_DARK).pack(anchor="w", pady=(5,5))
        
        # Copy All Button + Entry
        all_frame = tk.Frame(info_frame, bg=BG_DARK, pady=5)
        all_frame.pack(fill=tk.X)
        
        e_all = tk.Entry(all_frame, bg="#444444", fg=FG_LIGHT, font=("Arial", 10), insertbackground="white")
        e_all.insert(0, full_rule)
        e_all.config(state="readonly")
        e_all.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        tk.Button(all_frame, text="复制完整规则", command=lambda: self.copy_to_clip(full_rule), 
                  bg="#2196F3", fg="white", font=("Arial", 10, "bold"), width=12).pack(side=tk.RIGHT)

        tk.Label(info_frame, text="👆 现在的规则包含主程序(Updater)和插件的独立进程伪装名。\n粘贴到 Proxifier 后，所有流量（含自动更新）都将精准分流。", 
                 fg="#aaaaaa", bg=BG_DARK, justify=tk.LEFT, wraplength=550).pack(anchor="w", pady=(0, 15))


        # Divider
        tk.Frame(info_frame, height=1, bg="#555555").pack(fill=tk.X, pady=10)
        
        # Detailed Breakdown (Collapsed/Secondary)
        tk.Label(info_frame, text="🔍 规则详情 (调试用)", font=("Arial", 10, "bold"), fg="#888888", bg=BG_DARK).pack(anchor="w")

        # R1: Electron Shim
        tk.Label(info_frame, text="主程序伪装 (Main & Updater):", fg="#aaaaaa", bg=BG_DARK).pack(anchor="w")
        self.create_copy_row(info_frame, elec_rule, BG_DARK, ENTRY_BG, FG_LIGHT)

        # R2: LS Shim
        tk.Label(info_frame, text="插件伪装 (LangServer):", fg="#aaaaaa", bg=BG_DARK).pack(anchor="w")
        self.create_copy_row(info_frame, ls_rule, BG_DARK, ENTRY_BG, FG_LIGHT)

        # R3: App Bundle
        tk.Label(info_frame, text="通用兜底 (Bundle Path):", fg="#aaaaaa", bg=BG_DARK).pack(anchor="w")
        self.create_copy_row(info_frame, app_rule, BG_DARK, ENTRY_BG, FG_LIGHT)

        # 登录提示 (Login Warning)
        warning_frame = tk.Frame(win, bg="#3E2723", padx=10, pady=5, relief=tk.RIDGE, borderwidth=1) # Dark Brown/Rust for warning
        warning_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(warning_frame, text="⚠️ 登录必读 (Login Note)", font=("Arial", 11, "bold"), bg="#3E2723", fg="#FF5722").pack(anchor="w")
        tk.Label(warning_frame, text="因 macOS 机制限制，多实例同时运行时，登录回调可能会乱序。\n【初次登录时】请务必关闭所有其他 Antigravity 窗口，仅保留当前这一个。\n登录成功保存 Token 后，即可正常多开。", 
                 bg="#3E2723", fg="#FFCCBC", justify=tk.LEFT, wraplength=500).pack(anchor="w")

        tk.Button(win, text="我已配置完成", command=win.destroy, bg="#4CAF50", width=20).pack(side=tk.BOTTOM, pady=20)

    def create_copy_row(self, parent, text, bg, entry_bg, fg):
        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, pady=2)
        e = tk.Entry(row, bg=entry_bg, fg=fg, insertbackground="white", font=("Arial", 9))
        e.insert(0, text)
        e.config(state="readonly")
        e.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="复制", command=lambda: self.copy_to_clip(text), bg="#555555", fg="white", width=4).pack(side=tk.RIGHT, padx=5)

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
        if messagebox.askyesno("同步内核", f"确定要同步【{name}】的内核吗？\n这会将原始 App 的代码覆盖到此实例，您的配置和数据会被保留。"):
            try:
                self.mgr.sync_kernel(name)
                self.refresh_list()
                messagebox.showinfo("成功", f"实例【{name}】内核同步完成！")
            except Exception as e:
                messagebox.showerror("同步失败", str(e))

    def edit_instance(self):
        sel = self.tree.selection()
        if not sel: return
        name = sel[0]
        acc = next((a for a in self.cfg.get_accounts() if a["name"] == name), {})
        
        # Reuse Dialog for editing
        dialog = InstanceEditorDialog(self.root, existing_data=acc)
        if not dialog.result: return
        
        # Update config
        data = dialog.result
        # Name cannot be changed easily because it's tied to folder names, so we only update note/proxy
        self.cfg.update_account(name, note=data["note"], proxy_url=data["proxy_url"])
        self.refresh_list()

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

if __name__ == "__main__":
    root = tk.Tk()
    app = AGManagerUI(root)
    root.mainloop()