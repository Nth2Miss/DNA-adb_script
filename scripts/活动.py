import sys
import time
from utils.scripts import *
import utils.notification as notification
import threading


# --- 配置区：集中管理坐标和路径 ---
TEMPLATES = {
    "start": "templates/Activity/start.png",
    "restart": "templates/Activity/restart.png"
}

# 坐标配置 (x1, y1)
COORDS = {
    "start_btn": (2150, 1740),  # 开始按钮
    "restart_btn": (930, 1725),  # 再次挑战
}

# 技能/摇杆参数
JOYSTICK_CENTER = (450, 1440)  # 摇杆中心点
# =================================================================

run_count = 0

# 定义一个全局变量用于控制后台动作的开关
stop_action_event = threading.Event()

def background_combat_task(connector, dev):
    """
    后台循环执行的任务
    """
    print("-> 后台动作线程启动")
    while not stop_action_event.is_set():
        try:
                reg(connector, dev, show_log=False)
        except Exception as e:
            print(f"后台动作异常: {e}")
            break
        time.sleep(0.2)


def combat_prep(connector, dev):
    """封装：进场 -> 移动 -> 开大"""
    print("-> 等待加载 (15s)...")
    time.sleep(15)

    print("-> 执行入场移动与技能...")
    ult(connector, dev)
    time.sleep(1)
    spiral(connector, dev, 4)

    # 2. 启动后台持续动作
    stop_action_event.clear()  # 重置停止信号
    action_thread = threading.Thread(target=background_combat_task, args=(connector, dev))
    action_thread.daemon = True  # 设置为守护线程
    action_thread.start()

    print("-> 动作已转入后台，开始实时监控结算界面...")


def main():
    global run_count
    try:
        connector = ensure_adb_connection()
        devices = list_devices(connector)
        if not devices: sys.exit(1)
        dev = devices[0]

        # 1. 初始检测分流
        print("正在检查初始状态...")
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if res_start:
            print("✓ 检测到开始界面")
            click(*COORDS["start_btn"], connector, dev)
            time.sleep(0.5)
            combat_prep(connector, dev)
        else:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
            if res_restart:
                print("✓ 检测到再次挑战界面")
                click(*COORDS["restart_btn"], connector, dev)
                time.sleep(0.5)
                combat_prep(connector, dev)
            else:
                print("未检测到开始或再次挑战按钮，尝试直接进入结算监控...")

        # 2. 主循环
        while True:
            res = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=300, raise_err=True)

            if res:
                # 一旦检测到结算，立即停止后台动作
                stop_action_event.set()

                run_count += 1
                print(f"\n===== 第 {run_count} 次运行完成 =====")

                # 点击结算，准备下一轮
                click(*COORDS["restart_btn"], connector, dev)
                time.sleep(2)  # 等待界面转换
                combat_prep(connector, dev)

    except Exception as e:
        print(e)
        notification.send_failure(e)
    finally:
        # 主脚本退出时停止后台线程
        stop_action_event.set()
        print("-> 脚本已停止，正在关闭后台战斗任务...")


if __name__ == "__main__":
    main()