import cv2
import sys
import time
from utils.tools import *

# ================= 配置区：修改这里即可适配不同设备 =================
# 图像模板路径
TMPL_START = "../templates/xzmh.png"
TMPL_CONFIRM = "../templates/confirm.png"
TMPL_RESTART = "../templates/restart.png"

# 坐标配置 (x1, y1)
POS_START_BTN = (2400, 1740)   # 开始按钮
POS_SECRET_ONE = (1600, 930)   # 第一个密函
POS_SELECT_CONF = (2100, 1165)   # 确认选择
POS_RESULT_CONF = (1330, 1645)   # 结算确认
POS_RESTART_BTN = (1882, 1745)   # 再次挑战

# 技能/摇杆参数
POS_ULTIMATE = (2050, 1650)  # 开大招坐标
JOYSTICK_CENTER = (450, 1440)  # 摇杆中心点
# =================================================================

run_count = 0


def enter_combat(connector, device, joystick):
    """直观的入场流水账逻辑"""
    print("  -> 点击：第一个密函")
    click(*POS_SECRET_ONE, connector, device)
    time.sleep(0.5)

    print("  -> 点击：确认选择")
    click(*POS_SELECT_CONF, connector, device)

    print("  -> 等待加载入场 (15s)...")
    time.sleep(15)

    print("  -> 操作：摇杆向前移动 15s")
    joystick.move('w', 15)

    print("  -> 操作：释放大招")
    connector.click_screen(*POS_ULTIMATE, device)


def main():
    global run_count
    try:
        # 1. 环境初始化
        connector = ensure_adb_connection()
        devices = list_devices(connector)
        if not devices:
            print("错误：未找到任何ADB设备")
            sys.exit(1)
        first_device = devices[0]

        # 初始化摇杆
        joystick = JoystickController(
            connector=connector,
            center_x=JOYSTICK_CENTER[0],
            center_y=JOYSTICK_CENTER[1],
            radius=150,
            device_id=first_device
        )

        # 2. 初始检查
        print("正在检查初始界面...")
        res = execute_screenshot_and_match(first_device, connector, TMPL_START, debug=False)
        if res['is_match']:
            print("检测到开始按钮，准备进入第一次战斗...")
            click(*POS_START_BTN, connector, first_device)
            time.sleep(0.5)
            enter_combat(connector, first_device, joystick)

        # 3. 主监控循环
        while True:
            # 检查战斗是否结束
            res_confirm = execute_screenshot_and_match(first_device, connector, TMPL_CONFIRM, debug=False)

            if res_confirm['is_match']:
                run_count += 1
                print(f"\n========== 第 {run_count} 次运行完成 ==========")

                print("点击：结算确认按钮")
                click(*POS_RESULT_CONF, connector, first_device)

                # 等待“再次挑战”按钮出现 (带有超时逻辑)
                print("等待再次挑战按钮...")
                retry_start_time = time.time()
                found_restart = False

                while time.time() - retry_start_time < 60:
                    res_restart = execute_screenshot_and_match(first_device, connector, TMPL_RESTART, debug=False)
                    if res_restart['is_match']:
                        found_restart = True
                        break
                    time.sleep(2)

                if found_restart:
                    print("点击：再次挑战")
                    click(*POS_RESTART_BTN, connector, first_device)
                    time.sleep(1)
                    enter_combat(connector, first_device, joystick)
                else:
                    print("超时：未能跳转到再次挑战界面。")

            time.sleep(8)  # 轮询间隔

    except KeyboardInterrupt:
        print("\n脚本已手动停止。")
    except Exception as e:
        print(f"运行异常: {e}")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()