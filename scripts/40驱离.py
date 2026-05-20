import cv2
import sys
import time
from datetime import datetime
from utils.tools import (
    ensure_adb_connection, list_devices, click, wait_until_match,
    StopScriptException, TimeoutException, status_notifier
)
from utils.scripts import select_commission_multiplier, ult
import utils.notification as notification

# --- 配置区：集中管理坐标和模板路径 ---
TEMPLATES = {
    "start": "templates/start.png",
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


def combat_prep(connector, dev, run_count, total_round):
    """封装：选择倍率 -> 确认 -> 加载 -> 开大"""
    status_notifier.update(run_count, "正在选择佣兵倍率...", total_round)
    select_commission_multiplier(connector, dev)

    status_notifier.update(run_count, "确认选择并进入战斗...", total_round)
    click(*COORDS["confirm_btn"], connector, dev)

    status_notifier.update(run_count, "正在等待加载中 (20s)...", total_round)
    time.sleep(20)

    status_notifier.update(run_count, "执行释放终极技能...", total_round)
    ult(connector, dev)
    time.sleep(10)


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
            status_notifier.update(run_count, "⚔️ 战斗进行中，等待结算...", total_round)
            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=300, raise_err=True)

            print(f"===== 第 {run_count} 次运行完成 ===== || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            run_count += 1
            status_notifier.update(run_count, "点击重开，准备下一轮...", total_round)
            click(*COORDS["restart_btn"], connector, dev)
            time.sleep(0.5)
            combat_prep(connector, dev, run_count, total_round)

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