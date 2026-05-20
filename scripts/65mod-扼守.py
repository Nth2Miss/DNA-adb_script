import cv2
import sys
import time
from datetime import datetime
from utils.tools import (
    ensure_adb_connection, list_devices, click, wait_until_match,
    JoystickController, StopScriptException, TimeoutException, status_notifier
)
from utils.scripts import fuwei, ult, timeout
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


def combat_prep(connector, device, joystick, run_count, total_round):
    """封装：确认选择 -> 进场 -> 移动 -> 开大"""
    status_notifier.update(run_count, "正在确认选择...", total_round)
    click(*COORDS["confirm_btn"], connector, device)

    status_notifier.update(run_count, "正在等待加载中 (20s)...", total_round)
    time.sleep(20)

    status_notifier.update(run_count, "正在执行入场移动跑位...", total_round)
    joystick.move('w', 3.5)
    joystick.move('a', 8.5)
    joystick.move('w', 6.5)
    joystick.move('a', 22)

    status_notifier.update(run_count, "技能就绪，释放大招...", total_round)
    fuwei(connector, device)
    time.sleep(1)
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

        joystick = JoystickController(
            connector=connector,
            center_x=JOYSTICK_CENTER[0],
            center_y=JOYSTICK_CENTER[1],
            radius=150,
            device_id=dev
        )

        # 1. 初始状态检测与分流
        status_notifier.update(run_count, "正在检查设备初始状态...", total_round)
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if res_start:
            status_notifier.update(run_count, "点击开始按钮...", total_round)
            click(*COORDS["start_btn"], connector, dev)
            combat_prep(connector, dev, joystick, run_count, total_round)
        else:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
            if res_restart:
                status_notifier.update(run_count, "点击再次挑战...", total_round)
                click(*COORDS["restart_btn"], connector, dev)
                time.sleep(1)
                combat_prep(connector, dev, joystick, run_count, total_round)
            else:
                status_notifier.update(run_count, "监控中：直接进入结算监控...", total_round)

        # 2. 主逻辑循环
        while True:
            retry_limit = 2
            retry_count = 0
            found_restart = False

            while retry_count < retry_limit:
                try:
                    status_notifier.update(run_count, "⚔️ 战斗进行中，等待结算...", total_round)
                    wait_until_match(dev, connector, TEMPLATES["restart"], timeout=300, raise_err=True)
                    found_restart = True
                    break  # 匹配成功，跳出重试
                except StopScriptException:
                    raise StopScriptException  # 如果是手动停止抛出的超时，必须往上层抛
                except Exception:
                    retry_count += 1
                    status_notifier.update(run_count, f"⚠️ 超时重试 ({retry_count}/{retry_limit})...", total_round)
                    timeout(connector, dev)
                    time.sleep(2)

            if not found_restart:
                status_notifier.update(run_count, "❌ 连续超时且重试失败，脚本已终止", total_round)
                notification.send_failure("战斗连续超时，已停止。")
                break

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
        print("\n脚本已手动停止。")
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