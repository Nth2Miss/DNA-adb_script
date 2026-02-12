import cv2
import sys
import time
from utils.tools import *
from utils.scripts import *
import utils.notification as notification


# --- 配置区：集中管理坐标和模板路径 ---
TEMPLATES = {
    "start": "templates/start_1.png",
    "restart": "templates/restart.png"
}

# 坐标配置 (x1, y1)
COORDS = {
    "start_btn": (2400, 1740),   # 开始按钮
    "confirm_btn": (1475, 1210),   # 确认选择
    "restart_btn": (1882, 1745),   # 再次挑战
}
# =================================================================


def combat_prep(connector, device):
    """封装：确认选择 -> 进场 -> 移动 -> 开大"""
    print("-> 确认开始...")
    click(*COORDS["confirm_btn"], connector, device)

    print("-> 等待加载中(15s)...")
    time.sleep(15)

    print("-> 执行入场移动与技能...")
    spiral(connector, device, 2)
    ult(connector, device)
    print("-> 等待结算")
    
    


def main():
    connector = ensure_adb_connection()
    devices = list_devices(connector)
    if not devices:
        print("未找到设备")
        return

    dev = devices[0]
    joystick = JoystickController(connector, 450, 1440, 150, dev)
    run_count = 0

    print("=== √ 脚本启动===")

    try:
        # 1. 初始检测进入
        # 使用 wait_until_match 进行非阻塞检测 (raise_err=False)
        # timeout=5 表示只检测5秒，没找到就返回 None
        print("正在检查初始状态...")
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        # 如果没在开始界面，再检查是不是在重开界面
        if not res_start:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
        else:
            res_restart = None

        if res_start:
            print("-> 检测到初始【选择密函】界面，开始流程...")
            click(*COORDS["start_btn"], connector, dev)
            combat_prep(connector, dev)
        elif res_restart:
            print("-> 检测到【再次挑战】界面，直接跳转...")
            click(*COORDS["restart_btn"], connector, dev)
            time.sleep(1)
            combat_prep(connector, dev)
        else:
            print("未检测到开始或再次挑战按钮，默认认为在战斗中，进入监控...")

        # 2. 主逻辑循环
        while True:
            # --- 等待战斗结束（结算界面） ---
            # 设置超时 600秒
            print(f"\n[第 {run_count + 1} 轮] 战斗进行中，等待结算 (超时: 6分钟)...")

            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=360, raise_err=True)

            run_count += 1
            print(f"===== 第 {run_count} 次运行完成 ===== || {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

            # 点击结算确认
            click(*COORDS["confirm_btn"], connector, dev)
            print("等待结算动画...")
            time.sleep(3)

            # --- 等待再次挑战 ---
            print("正在等待【再次挑战】按钮 (超时: 30秒)...")
            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=30, raise_err=True)

            # 点击重开
            click(*COORDS["restart_btn"], connector, dev)
            print("-> 重开战斗")

            time.sleep(1)
            combat_prep(connector, dev)

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