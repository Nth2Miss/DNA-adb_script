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
    "start_btn": (2400, 1740),  # 开始按钮
    "confirm_btn": (1475, 1210),  # 确认选择
    "restart_btn": (1882, 1745),  # 再次挑战
}

# 技能/摇杆参数
JOYSTICK_CENTER = (450, 1440)  # 摇杆中心点
# =================================================================

run_count = 0


def combat_prep(connector, device, joystick):
    """封装：确认选择 -> 进场 -> 移动 -> 开大"""
    print("-> 确认开始...")
    click(*COORDS["confirm_btn"], connector, device)

    print("-> 等待加载中(15s)...")
    time.sleep(15)

    print("-> 执行入场移动与技能...")
    joystick.move('w', 3.8)
    joystick.move('a', 10)
    joystick.move('w', 8)
    joystick.move('a', 23)

    fuwei(connector, device)
    time.sleep(1)
    ult(connector, device)
    print("-> 等待结算")


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

        # 1. 初始状态检测与分流
        print("正在检查初始状态...")
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if res_start:
            print("-> 检测到初始界面，开始挑战...")
            click(*COORDS["start_btn"], connector, dev)
            combat_prep(connector, dev, joystick)
        else:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
            if res_restart:
                print("-> 检测到再次挑战界面，直接重开...")
                click(*COORDS["restart_btn"], connector, dev)
                time.sleep(1)
                combat_prep(connector, dev, joystick)
            else:
                print("未检测到开始或再次挑战按钮，尝试直接进入结算监控...")

        # 2. 主逻辑循环
        while True:
            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=300, raise_err=True)

            run_count += 1
            print(f"\n===== 第 {run_count} 次运行完成 =====")

            # 使用预设坐标点击
            click(*COORDS["restart_btn"], connector, dev)

            time.sleep(1)  # 等待界面切换
            combat_prep(connector, dev, joystick)

    except Exception as e:
        print(f"运行出错: {e}")
        notification.send_failure(e)
    except KeyboardInterrupt:
        print("\n脚本已手动停止。")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()