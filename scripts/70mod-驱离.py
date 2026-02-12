import cv2
import sys
import time
from utils.tools import *
from utils.scripts import *
import utils.notification as notification


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
# =================================================================

run_count = 0


def combat_prep(connector, dev):
    """封装：确认选择 -> 进场"""
    print("-> 点击确认选择...")
    click(*COORDS["confirm_btn"], connector, dev)
    # 根据原代码逻辑，此处不需要额外操作，直接等待下一轮检测


def main():
    global run_count
    try:
        connector = ensure_adb_connection()
        devices = list_devices(connector)
        if not devices:
            sys.exit(1)
        dev = devices[0]

        # 1. 初始检测
        print("正在检查初始状态...")
        res_start = execute_screenshot_and_match(dev, connector, TEMPLATES["start"], debug=False)
        res_restart = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)

        if res_start['is_match']:
            print("✓ 检测到开始界面")
            click(*COORDS["start_btn"], connector, dev)
            random_sleep(1)
            combat_prep(connector, dev)
        elif res_restart['is_match']:
            print("✓ 检测到再次进行界面")
            click(*COORDS["restart_btn"], connector, dev)
            random_sleep(1)
            combat_prep(connector, dev)

        # 2. 主循环
        while True:
            res = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)
            if res['is_match']:
                run_count += 1
                print(f"\n===== 第 {run_count} 次运行完成 =====")
                click(*COORDS["restart_btn"], connector, dev)
                random_sleep(2)
                combat_prep(connector, dev)

            time.sleep(2)

    except Exception as e:
        print(f"❌ 错误: {e}")
        notification.send_failure(e)
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()