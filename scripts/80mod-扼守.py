import cv2
import sys
import time
from utils.tools import *
from utils.scripts import *

# --- 配置区：集中管理坐标和模板路径 ---
TEMPLATES = {
    "start": "templates/start.png",
    "restart": "templates/restart.png"
}

# 坐标配置 (x1, y1)
RECT_RESTART = (1682, 1700, 2147, 1778)
RECT_CONFIRM = (1440, 1190, 1980, 1250)
RECT_START = (2315, 1705, 2770, 1775)
POS_SPIRAL = (2290, 980, 2400, 1090)  # 螺旋点击区域
# =================================================================

run_count = 0


def combat_prep(connector, dev):
    """封装：确认选择 -> 加载 -> 螺旋操作"""
    print("-> 点击确认选择...")
    random_click(*RECT_CONFIRM, connector, dev)

    print("-> 等待加载动画...")
    random_sleep_extended(12, 18)

    spiral(connector, dev, 7)


def main():
    global run_count
    try:
        connector = ensure_adb_connection()
        devices = list_devices(connector)
        if not devices: sys.exit(1)
        dev = devices[0]

        # 1. 初始检测
        res_start = execute_screenshot_and_match(dev, connector, TEMPLATES["start"], debug=False)
        res_restart = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)

        if res_start['is_match']:
            random_click(*RECT_START, connector, dev)
            random_sleep(1)
            combat_prep(connector, dev)
        elif res_restart['is_match']:
            random_click(*RECT_RESTART, connector, dev)
            random_sleep(1)
            combat_prep(connector, dev)

        # 2. 主循环
        while True:
            res = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)
            if res['is_match']:
                run_count += 1
                print(f"\n--- 第 {run_count} 轮开始 ---")
                random_click(*RECT_RESTART, connector, dev)
                random_sleep(2)
                combat_prep(connector, dev)

            time.sleep(2)
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()