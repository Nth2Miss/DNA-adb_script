import cv2
import sys
import time
from utils.tools import *
import utils.notification as notification

# --- 配置区：集中管理坐标和路径 ---
TEMPLATES = {
    "start": "templates/xzmh.png",
    "confirm": "templates/confirm.png",
    "restart": "templates/restart.png"
}

# 格式: (x1, y1, x2, y2)
COORDS = {
    "start_btn": (2400, 1740),
    "secret_1": (1425, 885),
    "confirm_sel": (2010, 1210),
    "confirm_btn": (1330, 1650),
    "restart_btn": (1882, 1735),
    "ult_pos": (2050, 1650)
}


def combat_prep(connector, device, joystick):
    """封装：选密函 -> 进场 -> 移动 -> 开大"""
    print("-> 正在选择密函...")
    click(*COORDS["secret_1"], connector, device)
    time.sleep(0.5)
    click(*COORDS["confirm_sel"], connector, device)

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

    # 1. 初始检测进入（添加双重入口判断）
    print("正在检查初始状态...")
    res_start = execute_screenshot_and_match(dev, connector, TEMPLATES["start"], debug=False)
    res_restart = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)

    if res_start['is_match']:
        print("-> 检测到初始【选择密函】界面，开始流程...")
        click(*COORDS["start_btn"], connector, dev)
        combat_prep(connector, dev, joystick)
    elif res_restart['is_match']:
        print("-> 检测到【再次挑战】界面，直接跳转...")
        click(*COORDS["restart_btn"], connector, dev)
        time.sleep(1)
        combat_prep(connector, dev, joystick)
    else:
        print("未检测到开始或再次挑战按钮，尝试直接进入结算监控...")

    # 2. 主逻辑循环：监控结算与重开
    while True:
        # 监控“确认”按钮（战斗结束）
        res_confirm = execute_screenshot_and_match(dev, connector, TEMPLATES["confirm"], debug=False)

        if res_confirm['is_match']:
            run_count += 1
            print(f"\n===== 第 {run_count} 次运行完成 =====")

            # 点击结算确认
            click(*COORDS["confirm_btn"], connector, dev)

            # 优化：移除冗余的 wait_until_match，直接在循环中检测下一阶段
            print("正在等待结算动画结束...")
            time.sleep(2)

            # 监控“再次挑战”按钮
        res_restart_loop = execute_screenshot_and_match(dev, connector, TEMPLATES["restart"], debug=False)
        if res_restart_loop['is_match']:
            click(*COORDS["restart_btn"], connector, dev)
            time.sleep(1)  # 等待界面切换
            combat_prep(connector, dev, joystick)

        time.sleep(3)  # 轮询间隔


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n脚本已停止")
    finally:
        cv2.destroyAllWindows()