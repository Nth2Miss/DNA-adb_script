import cv2
import sys
import time
from plyer import notification  # 导入通知库
from utils.tools import *

# --- 配置区保持不变 ---
TEMPLATES = {
    "start": "templates/xzmh.png",
    "continue": "templates/continue.png",
    "restart": "templates/restart.png"
}

COORDS = {
    "continue": (1860, 1280),
    "start": (1160, 1220),
    "ult_pos": (2050, 1650)
}

def send_alert(count):
    """发送 Windows 系统通知"""
    notification.notify(
        title="二重螺旋 自动化脚本提示",
        message=f"运行次数已达到 {count} 次！",
        app_icon=None,  # 如果有 .ico 文件可以加上路径
        timeout=5,      # 通知显示时间（秒）
    )

def combat_prep(connector, device):
    print("-> 继续挑战...")
    click(*COORDS["continue"], connector, device)
    time.sleep(0.5)
    click(*COORDS["start"], connector, device)

def main():
    connector = ensure_adb_connection()
    devices = list_devices(connector)
    if not devices:
        print("未找到设备")
        return

    dev = devices[0]
    run_count = 0

    print("正在检查初始状态...")

    while True:
        res_continue = execute_screenshot_and_match(dev, connector, TEMPLATES["continue"], debug=False)

        if res_continue['is_match']:
            run_count += 1
            print(f"\n===== 第 {run_count} 次运行完成 =====")

            # --- 判断次数并报警 ---
            if run_count == 99:
                print("!!! 已达 99 次，发送通知 !!!")
                send_alert(run_count)
            # --------------------------

            combat_prep(connector, dev)
            print("等待本轮结束...")
            time.sleep(2)

        time.sleep(3)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n脚本已停止")
    finally:
        cv2.destroyAllWindows()