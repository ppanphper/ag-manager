import sys
import time
from config import ConfigManager
from power_manager import AppPowerManager

def main():
    try:
        cfg = ConfigManager()
        mgr = AppPowerManager(cfg)
        
        # 强制执行一次 Launch
        instance_name = "lijiao-US-San-Jose-01"
        print(f"Testing launch for {instance_name}...")
        
        # 因为 launch 会直接跑 subprocess.Popen 后返回，我们等个10秒看有没有崩溃即可
        mgr.launch(instance_name)
        print("Launch executed. Waiting 5s to observe any errors in background...")
        time.sleep(5)
        print("Done.")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    main()
