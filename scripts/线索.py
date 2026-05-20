import cv2
import sys
import time
from utils.tools import (
    ensure_adb_connection, list_devices, click, execute_screenshot_and_match,
    StopScriptException, TimeoutException, status_notifier
)
import utils.notification as notification

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


def combat_prep(connector, device, run_count, total_round):
    status_notifier.update(run_count, "正在点击继续挑战按钮...", total_round)
    click(*COORDS["continue"], connector, device)
    time.sleep(0.5)
    status_notifier.update(run_count, "正在点击开始按钮...", total_round)
    click(*COORDS["start"], connector, device)


def run(device_id=None):
    run_count = 1
    total_round = 99  # 线索脚本特定触发上限阈值

    try:
        connector = ensure_adb_connection()
        if device_id:
            dev = device_id
        else:
            devices = list_devices(connector)
            if not devices: return
            dev = devices[0]

        status_notifier.update(run_count, "正在检查设备初始状态...", total_round)

        while True:
            res_continue = execute_screenshot_and_match(dev, connector, TEMPLATES["continue"], debug=False)

            if res_continue['is_match']:
                print(f"\n===== 第 {run_count} 次运行完成 =====")

                if run_count == 99:
                    print("!!! 已达 99 次，发送成功通知 !!!")
                    try:
                        notification.send_success(run_count)
                    except Exception:
                        pass
                    status_notifier.update(run_count, "🎉 已成功刷满 99 次线索！", total_round)
                    break

                combat_prep(connector, dev, run_count, total_round)

                run_count += 1
                status_notifier.update(run_count, "⏳ 已经重开，等待本轮战斗结束...", total_round)
                time.sleep(2)

            # 看板静默监控检测中
            time.sleep(3)

    except StopScriptException:
        status_notifier.update(run_count, "🛑 脚本已成功停止", total_round)
        print("\n[系统提示] 用户手动停止脚本，任务安全终止。")
    except Exception as e:
        error_msg = f"未知错误: {e}"
        status_notifier.update(run_count, "❌ 脚本遭遇未知错误", total_round)
        print(f"\n❌ {error_msg}")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()