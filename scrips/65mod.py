import cv2
import sys
import time
from utils.tools import *
from utils.scripts import *


# --- 配置区：集中管理坐标和路径，方便修改 ---
TEMPLATES = {
    "start": "../templates/start_1.png",
    "restart": "../templates/restart.png"
}

# 坐标配置 (x1, y1)
POS_START_BTN = (2400, 1740)   # 开始按钮
POS_SELECT_CONF = (1475, 1210)   # 确认选择
POS_RESTART_BTN = (1882, 1745)   # 再次挑战
POS_ULT_POS = (2050, 1650)    # 开大招坐标

# 技能/摇杆参数
JOYSTICK_CENTER = (450, 1440)  # 摇杆中心点
# =================================================================

run_count = 0

def combat_prep(connector, device, joystick):
    """封装：确认选择 -> 进场 -> 移动 -> 开大"""
    print("-> 确认开始...")
    click(*POS_SELECT_CONF, connector, device)

    print("-> 等待加载中(15s)...")
    time.sleep(15)

    print("-> 执行入场移动与技能...")
    joystick.move('w', 10)
    joystick.move('a', 10)
    joystick.move('w', 3)
    joystick.move('a', 25)

    fuwei(connector, device)
    time.sleep(1)
    ult(connector, device)


def main():
    global run_count
    try:
        # 1. 环境初始化
        connector = ensure_adb_connection()
        devices = list_devices(connector)
        if not devices:
            print("错误：未找到任何ADB设备")
            sys.exit(1)
        dev = devices[0]

        # 初始化摇杆
        joystick = JoystickController(
            connector=connector,
            center_x=JOYSTICK_CENTER[0],
            center_y=JOYSTICK_CENTER[1],
            radius=150,
            device_id=dev
        )


        # 1. 初始检测进入
        print("正在检查初始状态...")
        res = execute_screenshot_and_match(dev, connector, TEMPLATES["start"], debug=False)
        if res['is_match']:
            print("-> 开始挑战...")
            click(*POS_START_BTN, connector, dev)
            combat_prep(connector, dev, joystick)
        else:
            print("未检测到开始按钮，尝试直接进入结算监控...")

        # 2. 主逻辑循环：监控结算与重开
        while True:
            res_restart = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)

            if res_restart['is_match']:
                run_count += 1
                print(f"\n===== 第 {run_count} 次运行完成 =====")

                click(*POS_RESTART_BTN, connector, dev)

                time.sleep(1)  # 等待界面切换
                combat_prep(connector, dev, joystick)

            # 轮询间隔，避免截图过快导致占用高
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n脚本已手动停止。")

    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n脚本已停止")
    finally:
        cv2.destroyAllWindows()