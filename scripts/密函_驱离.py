import cv2
import sys
import time
from datetime import datetime
# 核心：引入全局状态分发器 status_notifier
from utils.tools import (
    ADBConnector, JoystickController, click, wait_until_match,
    TimeoutException, StopScriptException, status_notifier
)
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
    "secret_3": (1805, 880),
    "confirm_sel": (2010, 1210),
    "confirm_btn": (1330, 1650),
    "restart_btn": (1882, 1735),
    "ult_pos": (2050, 1650)
}


def combat_prep(connector, device, joystick, run_count):
    """封装：选密函 -> 进场 -> 移动 -> 开大"""
    # 表格更新当前操作步骤
    status_notifier.update(run_count, "正在选择密函...")
    click(*COORDS["secret_1"], connector, device, show_log=False)
    # click(*COORDS["secret_3"], connector, device, show_log=False)  # 暂时设置第三个
    time.sleep(0.5)
    click(*COORDS["confirm_sel"], connector, device, show_log=False)

    status_notifier.update(run_count, "正在等待加载中(15s)...")
    time.sleep(15)

    status_notifier.update(run_count, "执行入场移动与技能...")
    joystick.move('w', 10)
    click(*COORDS["ult_pos"], connector, device, show_log=False)


def run(device_id=None):
    connector = ADBConnector()

    # 优先获取 GUI 传进来的当前选中的设备
    if device_id:
        dev = device_id
    else:
        devices = connector.list_devices()
        if not devices:
            print("❌ 未找到有效设备，脚本退出")
            return
        dev = devices[0]

    joystick = JoystickController(connector, 450, 1440, 150, dev)
    run_count = 1

    print("=== √ 脚本成功启动 ===")

    try:
        # 1. 初始检测进入
        status_notifier.update(run_count, "正在检查设备初始状态...", "∞")
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if not res_start:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
        else:
            res_restart = None

        print(f"\n=== 第 {run_count} 轮 开始 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

        if res_start:
            status_notifier.update(run_count, "点击开始按钮...")
            click(*COORDS["start_btn"], connector, dev, show_log=False)
            combat_prep(connector, dev, joystick, run_count)
        elif res_restart:
            status_notifier.update(run_count, "点击再次挑战...")
            click(*COORDS["restart_btn"], connector, dev, show_log=False)
            time.sleep(1)
            combat_prep(connector, dev, joystick, run_count)
        else:
            status_notifier.update(run_count, "监控中：直接进入战斗...")

        # 2. 主逻辑循环
        while True:
            # --- 等待战斗结束（结算界面） ---
            status_notifier.update(run_count, "⚔️ 战斗进行中，等待结算...")
            wait_until_match(dev, connector, TEMPLATES["confirm"], timeout=300, raise_err=True)

            # 点击结算确认
            status_notifier.update(run_count, "✅ 战斗结束，点击结算确认")
            click(*COORDS["confirm_btn"], connector, dev, show_log=False)
            time.sleep(3)

            # --- 等待再次挑战 ---
            status_notifier.update(run_count, "正在等待【再次挑战】按钮...")
            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=30, raise_err=True)

            # 点击重开
            status_notifier.update(run_count, "点击重开，准备下一轮...")
            click(*COORDS["restart_btn"], connector, dev, show_log=False)

            print(f"=== 第 {run_count} 轮 结束 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

            # 轮次递增
            run_count += 1

            print(f"=== 第 {run_count} 轮 开始 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            time.sleep(1)
            combat_prep(connector, dev, joystick, run_count)


    except StopScriptException:
        status_notifier.update(run_count, "🛑 脚本已成功停止")
        print("\n[系统提示] 用户手动停止脚本，任务安全终止。")

    except TimeoutException as e:
        error_msg = f"运行出错: {e}"
        status_notifier.update(run_count, "❌ 等待超时 / 发生异常")
        print(f"\n❌ {error_msg}")
        try:
            notification.send_failure(error_msg)
        except Exception:
            pass

    except Exception as e:
        error_msg = f"未知错误: {e}"
        status_notifier.update(run_count, "❌ 脚本遭遇未知错误")
        print(f"\n❌ {error_msg}")
        try:
            notification.send_failure(error_msg)
        except Exception:
            pass

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()