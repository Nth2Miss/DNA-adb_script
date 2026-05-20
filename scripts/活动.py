import cv2
import sys
import time
from datetime import datetime
import threading
from utils.tools import (
    ensure_adb_connection, list_devices, click, wait_until_match,
    StopScriptException, TimeoutException, status_notifier
)
from utils.scripts import ult, spiral, reg
import utils.notification as notification

# --- 配置区：集中管理坐标和路径 ---
TEMPLATES = {
    "start": "templates/Activity/start.png",
    "restart": "templates/Activity/restart.png"
}

COORDS = {
    "start_btn": (2150, 1740),  # 开始按钮
    "restart_btn": (930, 1725),  # 再次挑战
}

run_count = 1
stop_action_event = threading.Event()


def background_combat_task(connector, dev):
    """后台持续循环动作"""
    while not stop_action_event.is_set():
        try:
            reg(connector, dev, show_log=False)
        except Exception:
            break
        time.sleep(0.2)


def combat_prep(connector, dev, run_count, total_round):
    """封装：进场 -> 移动 -> 开大"""
    status_notifier.update(run_count, "正在等待加载中 (15s)...", total_round)
    time.sleep(15)

    status_notifier.update(run_count, "执行入场高燃身法技能...", total_round)
    ult(connector, dev)
    time.sleep(1)
    spiral(connector, dev, 4)

    # 启动异步后台打击
    stop_action_event.clear()
    action_thread = threading.Thread(target=background_combat_task, args=(connector, dev))
    action_thread.daemon = True
    action_thread.start()
    print("-> 战术动作切入后台，开启核心结算监控...")


def run(device_id=None):
    global run_count
    total_round = "∞"

    try:
        connector = ensure_adb_connection()
        if device_id:
            dev = device_id
        else:
            devices = list_devices(connector)
            if not devices: return
            dev = devices[0]

        # 1. 初始检测分流
        status_notifier.update(run_count, "正在检查设备初始状态...", total_round)
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if res_start:
            print("✓ 检测到开始界面")
            status_notifier.update(run_count, "点击开始按钮...", total_round)
            click(*COORDS["start_btn"], connector, dev)
            time.sleep(0.5)
            combat_prep(connector, dev, run_count, total_round)
        else:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
            if res_restart:
                print("✓ 检测到再次挑战界面")
                status_notifier.update(run_count, "点击再次挑战...", total_round)
                click(*COORDS["restart_btn"], connector, dev)
                time.sleep(0.5)
                combat_prep(connector, dev, run_count, total_round)
            else:
                status_notifier.update(run_count, "监控中：直接进入结算监控...", total_round)

        # 2. 主循环
        while True:
            status_notifier.update(run_count, "⚔️ 后台战斗轰击中，等待结算...", total_round)
            res = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=300, raise_err=True)

            if res:
                stop_action_event.set()
                print(f"\n===== 第 {run_count} 次运行完成 =====")

                run_count += 1
                status_notifier.update(run_count, "点击结算，准备下一轮...", total_round)
                click(*COORDS["restart_btn"], connector, dev)
                time.sleep(2)
                combat_prep(connector, dev, run_count, total_round)

    except StopScriptException:
        stop_action_event.set()
        status_notifier.update(run_count, "🛑 脚本已成功停止", total_round)
        print("\n[系统提示] 用户手动停止脚本，任务安全终止。")

    except TimeoutException as e:
        stop_action_event.set()
        error_msg = f"运行出错: {e}"
        status_notifier.update(run_count, "❌ 等待超时 / 发生异常", total_round)
        print(f"\n❌ {error_msg}")
        try:
            notification.send_failure(error_msg)
        except Exception:
            pass
    except Exception as e:
        stop_action_event.set()
        error_msg = f"未知错误: {e}"
        status_notifier.update(run_count, "❌ 脚本遭遇未知错误", total_round)
        print(f"\n❌ {error_msg}")
        try:
            notification.send_failure(error_msg)
        except Exception:
            pass
    finally:
        stop_action_event.set()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()