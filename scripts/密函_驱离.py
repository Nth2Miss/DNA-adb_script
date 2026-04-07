import cv2
import sys
import time
from datetime import datetime
from utils.tools import *
import utils.notification as notification

# --- 配置区：集中管理坐标和路径 ---
TEMPLATES = {
    "start": "templates/xzmh.png",
    "confirm": "templates/confirm.png",
    "restart": "templates/restart.png"
}

# 格式: (x1, y1)
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
    print("    -> 正在选择密函...")
    click(*COORDS["secret_1"], connector, device, show_log=False)
    time.sleep(0.5)
    click(*COORDS["confirm_sel"], connector, device, show_log=False)

    print("    -> 等待加载中(15s)...")
    time.sleep(15)

    print("    -> 执行入场移动与技能...")
    joystick.move('w', 15)
    click(*COORDS["ult_pos"], connector, device, show_log=False)


def main():
    connector = ADBConnector()
    devices = connector.list_devices()
    if not devices:
        print("未找到设备")
        return

    dev = devices[0]
    joystick = JoystickController(connector, 450, 1440, 150, dev)
    run_count = 1

    print("=== √ 脚本启动 ===")

    try:
        # 1. 初始检测进入
        print("正在检查初始状态...")
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if not res_start:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
        else:
            res_restart = None

        print(f"\n=== 第 {run_count} 轮 开始 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

        if res_start:
            click(*COORDS["start_btn"], connector, dev, show_log=False)
            combat_prep(connector, dev, joystick)
        elif res_restart:
            click(*COORDS["restart_btn"], connector, dev, show_log=False)
            time.sleep(1)
            combat_prep(connector, dev, joystick)
        else:
            print("    -> 未检测到开始或再次挑战按钮，默认认为在战斗中，进入监控...")
        # 2. 主逻辑循环
        while True:
            # --- 等待战斗结束（结算界面） ---
            print("    -> 战斗进行中，等待结算...")
            wait_until_match(dev, connector, TEMPLATES["confirm"], timeout=300, raise_err=True)

            # 点击结算确认
            click(*COORDS["confirm_btn"], connector, dev, show_log=False)
            print("    -> 等待结算动画...")
            time.sleep(3)

            # --- 等待再次挑战 ---
            print("    -> 等待【再次挑战】按钮...")
            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=30, raise_err=True)

            # 点击重开
            click(*COORDS["restart_btn"], connector, dev, show_log=False)
            print("    -> 重开战斗")

            # 【在重开战斗后，结算并打印这一轮的结束】
            print(f"=== 第 {run_count} 轮 结束 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

            run_count += 1

            print(f"=== 第 {run_count} 轮 开始 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

            time.sleep(1)
            combat_prep(connector, dev, joystick)

    except TimeoutException as e:
        error_msg = f"运行出错: {e}"
        print(f"\n❌ {error_msg}")
        try:
            notification.send_failure(error_msg)
        except Exception:
            pass

    except StopScriptException:
        print("\n用户手动停止脚本")

    except KeyboardInterrupt:
        print("\n脚本已停止")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()