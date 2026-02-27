import os
import json
import time

# --- 常量配置 ---
DEFAULT_BASE_DIR = os.path.expanduser("~/Antigravity_Avatars")
CONFIG_FILE = os.path.join(DEFAULT_BASE_DIR, "config.json")

# 默认路径
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

                # 自动自愈：如果配置文件里的路径都不存在，但我们刚才探测到了有效路径，则覆盖
                current_path = self.config.get("original_app_path")
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
