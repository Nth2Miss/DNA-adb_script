import datetime
import cv2
import sys
from utils.tools import *
from utils.scripts import *


# --- 配置区：集中管理坐标和模板路径 ---
TEMPLATES = {
    "start": "templates/start_1.png",
    "restart": "templates/restart.png"
}

# 坐标配置 (x1, y1)
COORDS = {
    "start_btn": (2400, 1740),   # 开始按钮
    "confirm_btn": (1475, 1210),   # 确认选择
    "restart_btn": (1882, 1745),   # 再次挑战
}

# 技能/摇杆参数
JOYSTICK_CENTER = (450, 1440)  # 摇杆中心点
# =================================================================

run_count = 0


def combat_prep(connector, dev):
    """封装：确认 -> 加载 -> 开大"""
    print("-> 确认选择并进入...")
    click(*COORDS["confirm_btn"], connector, dev)

    print("-> 等待加载 (15s)...")
    time.sleep(15)

    ult(connector, dev)
    time.sleep(10)


def main():
    global run_count
    try:
        connector = ensure_adb_connection()
        devices = list_devices(connector)
        if not devices: sys.exit(1)
        dev = devices[0]

        # 1. 初始检测分流
        print("正在检查初始状态...")
        res_start = execute_screenshot_and_match(dev, connector, TEMPLATES["start"], debug=False)
        res_restart = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)

        if res_start['is_match']:
            print("✓ 检测到开始界面")
            click(*COORDS["start_btn"], connector, dev)
            time.sleep(0.5)
            combat_prep(connector, dev)
        elif res_restart['is_match']:
            print("✓ 检测到再次挑战界面")
            click(*COORDS["restart_btn"], connector, dev)
            time.sleep(0.5)
            combat_prep(connector, dev)
        else:
            print("未检测到开始或再次挑战按钮，尝试直接进入结算监控...")

        # 2. 主循环
        while True:
            res = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)
            if res['is_match']:
                run_count += 1
                print(f"\n第 {run_count} 次运行 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                click(*COORDS["restart_btn"], connector, dev)
                time.sleep(0.5)
                combat_prep(connector, dev)

            time.sleep(2)

    except Exception as e:
        print(f"错误: {e}")
    finally:
        pass


if __name__ == "__main__":
    main()