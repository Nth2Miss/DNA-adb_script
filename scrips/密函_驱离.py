import cv2
import sys
import time
from utils.tools import *

# --- 配置区：集中管理坐标和路径，方便修改 ---
TEMPLATES = {
    "start": "../templates/xzmh.png",
    "confirm": "../templates/confirm.png",
    "restart": "../templates/restart.png"
}

# 格式: (x1, y1, x2, y2)
COORDS = {
    "start_btn": (2315, 1705, 2770, 1775),
    "secret_1": (1540, 830, 1690, 1050),
    "confirm_sel": (1974, 1141, 2462, 1195),
    "confirm_btn": (1130, 1630, 1670, 1670),
    "restart_btn": (1682, 1700, 2147, 1778),
    "ult_pos": (2050, 1650)
}



def combat_prep(connector, device, joystick):
    """封装：选密函 -> 进场 -> 移动 -> 开大"""
    print("-> 正在选择密函...")
    random_click(*COORDS["secret_1"], connector, device)
    time.sleep(0.5)
    random_click(*COORDS["confirm_sel"], connector, device)

    print("-> 等待加载中(15s)...")
    time.sleep(15)

    print("-> 执行入场移动与技能...")
    joystick.move('w', 15)
    connector.click_screen(*COORDS["ult_pos"], device)


def main():
    connector = ensure_adb_connection()
    devices = list_devices(connector)
    if not devices:
        print("未找到设备")
        return

    dev = devices[0]
    joystick = JoystickController(connector, 450, 1440, 150, dev)
    run_count = 0

    # 1. 初始检测进入
    print("正在检查初始状态...")
    res = execute_screenshot_and_match(dev, connector, TEMPLATES["start"], debug=False)
    if res['is_match']:
        random_click(*COORDS["start_btn"], connector, dev)
        combat_prep(connector, dev, joystick)
    else:
        print("未检测到开始按钮，尝试直接进入结算监控...")

    # 2. 主逻辑循环：监控结算与重开
    while True:
        # 监控“确认”按钮（战斗结束）
        res_confirm = execute_screenshot_and_match(dev, connector, TEMPLATES["confirm"], debug=False)

        if res_confirm['is_match']:
            run_count += 1
            print(f"\n===== 第 {run_count} 次运行完成 =====")

            # 点击结算确认
            random_click(*COORDS["confirm_btn"], connector, dev)

            # 等待“再次挑战”按钮出现
            print("正在等待再次挑战按钮...")
            if wait_until_match(dev, connector, TEMPLATES["restart"], timeout=60):
                random_click(*COORDS["restart_btn"], connector, dev)
                time.sleep(1)  # 等待界面切换
                combat_prep(connector, dev, joystick)
            else:
                print("错误：长时间未找到再次挑战按钮，脚本停止")
                break

        time.sleep(5)  # 轮询间隔，避免截图过快导致占用高


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n脚本已停止")
    finally:
        cv2.destroyAllWindows()