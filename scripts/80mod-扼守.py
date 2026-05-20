import cv2
import sys
import time
from datetime import datetime
from utils.tools import (
    ensure_adb_connection, list_devices, click, wait_until_match,
    JoystickController, StopScriptException, TimeoutException, status_notifier
)
from utils.scripts import spiral, ult
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


def combat_prep(connector, device, joystick, run_count, total_round):
    """封装：确认选择 -> 进场 -> 移动 -> 开大"""
    status_notifier.update(run_count, "正在确认选择...", total_round)
    click(*COORDS["confirm_btn"], connector, device)

    status_notifier.update(run_count, "正在等待加载中 (15s)...", total_round)
    time.sleep(15)

    status_notifier.update(run_count, "执行螺旋绕怪突进...", total_round)
    spiral(connector, device, 7)
    time.sleep(1)

    status_notifier.update(run_count, "释放轰击技能大招...", total_round)
    ult(connector, device)


def run(device_id=None):
    run_count = 1
    total_round = "∞"

    try:
        connector = ensure_adb_connection()
        if device_id:
            dev = device_id
        else:
            devices = list_devices(connector)
            if not devices: return
            dev = devices[0]

        joystick = JoystickController(connector, 450, 1440, 150, dev)

        # 1. 初始检测进入
        status_notifier.update(run_count, "正在检查设备初始状态...", total_round)
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if not res_start:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
        else:
            res_restart = None

        if res_start:
            status_notifier.update(run_count, "点击开始按钮...", total_round)
            click(*COORDS["start_btn"], connector, dev)
            combat_prep(connector, dev, joystick, run_count, total_round)
        elif res_restart:
            status_notifier.update(run_count, "点击再次挑战...", total_round)
            click(*COORDS["restart_btn"], connector, dev)
            time.sleep(1)
            combat_prep(connector, dev, joystick, run_count, total_round)
        else:
            status_notifier.update(run_count, "监控中：直接进入战斗...", total_round)

        # 2. 主逻辑循环
        while True:
            print(f"\n[第 {run_count} 轮] 战斗进行中，等待结算...")
            status_notifier.update(run_count, "⚔️ 战斗进行中，等待结算...", total_round)

            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=360, raise_err=True)

            print(f"===== 第 {run_count} 次运行完成 ===== || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            run_count += 1
            status_notifier.update(run_count, "点击重开，准备下一轮...", total_round)
            click(*COORDS["restart_btn"], connector, dev)
            time.sleep(1)
            combat_prep(connector, dev, joystick, run_count, total_round)

    except StopScriptException:
        status_notifier.update(run_count, "🛑 脚本已成功停止", total_round)
        print("\n[系统提示] 用户手动停止脚本，任务安全终止。")

    except TimeoutException as e:
        error_msg = f"运行出错: {e}"
        status_notifier.update(run_count, "❌ 等待超时 / 发生异常", total_round)
        print(f"\n❌ {error_msg}")
        try:
            notification.send_failure(error_msg)
        except Exception:
            pass

    except KeyboardInterrupt:
        print("\n脚本已停止")
    except Exception as e:
        error_msg = f"未知错误: {e}"
        status_notifier.update(run_count, "❌ 脚本遭遇未知错误", total_round)
        print(f"\n❌ {error_msg}")
        try:
            notification.send_failure(error_msg)
        except Exception:
            pass
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()