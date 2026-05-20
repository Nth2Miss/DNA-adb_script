import cv2
import sys
import time
import re
from datetime import datetime
import numpy as np
import easyocr
from utils.tools import (
    ADBConnector, JoystickController, click, wait_until_match, adapt_coord,
    StopScriptException, TimeoutException, status_notifier
)
import utils.notification as notification

# 初始化 OCR 模型
print("正在加载 OCR 模型...")
reader = easyocr.Reader(['ch_sim', 'en'])

# --- 配置区：集中管理坐标和路径 ---
TEMPLATES = {
    "start": "templates/xzmh.png",
    "confirm": "templates/confirm.png",
    "restart": "templates/restart.png"
}

COORDS = {
    "start_btn": (2400, 1740),
    "secret_1": (1425, 885),
    "confirm_sel": (2010, 1210),
    "confirm_btn": (1330, 1650),
    "restart_btn": (1882, 1735),
    "ult_pos": (2050, 1650),
    "card_1": (1015, 1235),
    "card_2": (1400, 1235),
    "card_3": (1785, 1230),
}

CROP_REGIONS = [
    (920, 1140, 1150, 1192),
    (1295, 1140, 1500, 1192),
    (1680, 1140, 1900, 1192)
]


def combat_prep(connector, device, joystick, run_count, total_round):
    """封装：选密函 -> 进场 -> 移动 -> 开大"""
    status_notifier.update(run_count, "正在自动选择底层首选项...", total_round)
    click(*COORDS["secret_1"], connector, device, show_log=False)
    time.sleep(0.5)
    click(*COORDS["confirm_sel"], connector, device, show_log=False)

    status_notifier.update(run_count, "正在等待加载中 (15s)...", total_round)
    time.sleep(15)

    status_notifier.update(run_count, "执行大段冲刺跑位...", total_round)
    joystick.move('w', 18)
    click(*COORDS["ult_pos"], connector, device, show_log=False)


def select_min_owned_reward(connector, dev, run_count, total_round):
    """截屏并使用 OCR 识别持有数最少的密函，然后点击"""
    status_notifier.update(run_count, "🔍 正在进行高级 OCR 密函持有数比对...", total_round)

    try:
        raw_data = connector.get_screen_raw(dev)
        if not raw_data: raise RuntimeError("获取截图数据为空")
        screen = cv2.imdecode(np.frombuffer(raw_data, np.uint8), cv2.IMREAD_COLOR)
        if screen is None: raise RuntimeError("截图数据解码失败")
    except Exception as e:
        raise RuntimeError(f"截屏环节发生严重错误: {e}")

    screen_h, screen_w = screen.shape[:2]
    min_val = float('inf')
    min_idx = 0
    cards_coords = [COORDS["card_1"], COORDS["card_2"], COORDS["card_3"]]

    for i, (base_x1, base_y1, base_x2, base_y2) in enumerate(CROP_REGIONS):
        try:
            real_x1, real_y1 = adapt_coord(base_x1, base_y1)
            real_x2, real_y2 = adapt_coord(base_x2, base_y2)

            start_y, end_y = max(0, min(real_y1, real_y2)), max(0, min(real_max := max(real_y1, real_y2), screen_h))
            start_x, end_x = max(0, min(real_x1, real_x2)), max(0, min(real_max2 := max(real_x1, real_x2), screen_w))

            crop_img = screen[start_y:end_y, start_x:end_x]
            if crop_img.size == 0: continue

            result = reader.readtext(crop_img, detail=0)
            text = "".join(result)
            nums = re.findall(r'\d+', text)
            if nums:
                val = int(nums[-1])
                print(f"      - 卡片 {i + 1} 识别数量: {val}")
                if val < min_val:
                    min_val = val
                    min_idx = i
        except Exception as e:
            print(f"      - 卡片 {i + 1} 识别出错: {e}")

    print(f"    -> 智能判定选择卡片 {min_idx + 1}")
    click(*cards_coords[min_idx], connector, dev, show_log=False)
    time.sleep(0.5)


def run(device_id=None):
    run_count = 1
    total_round = "∞"

    try:
        connector = ADBConnector()
        if device_id:
            dev = device_id
        else:
            devices = connector.list_devices()
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
            click(*COORDS["start_btn"], connector, dev, show_log=False)
            combat_prep(connector, dev, joystick, run_count, total_round)
        elif res_restart:
            click(*COORDS["restart_btn"], connector, dev, show_log=False)
            time.sleep(1)
            combat_prep(connector, dev, joystick, run_count, total_round)
        else:
            status_notifier.update(run_count, "监控中：直接进入战斗...", total_round)

        # 2. 主逻辑循环
        while True:
            status_notifier.update(run_count, "⚔️ 战斗进行中，等待结算...", total_round)
            wait_until_match(dev, connector, TEMPLATES["confirm"], timeout=300, raise_err=True)

            # 动态识别并点击
            select_min_owned_reward(connector, dev, run_count, total_round)

            status_notifier.update(run_count, "✅ 识别完成，执行结算确认", total_round)
            click(*COORDS["confirm_btn"], connector, dev, show_log=False)
            time.sleep(3)

            status_notifier.update(run_count, "正在等待再次挑战按钮...", total_round)
            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=30, raise_err=True)

            print(f"=== 第 {run_count} 轮 结束 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

            run_count += 1
            status_notifier.update(run_count, "点击重开，准备下一轮...", total_round)
            click(*COORDS["restart_btn"], connector, dev, show_log=False)
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