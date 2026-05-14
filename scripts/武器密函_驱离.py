import cv2
import sys
import time
from datetime import datetime
import easyocr
from utils.tools import *
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

# 格式: (x1, y1)
COORDS = {
    "start_btn": (2400, 1740),
    "secret_1": (1425, 885),
    "confirm_sel": (2010, 1210),
    "confirm_btn": (1330, 1650),
    "restart_btn": (1882, 1735),
    "ult_pos": (2050, 1650),
    # === 三张卡片的中心点击坐标 ===
    "card_1": (1015, 1235),
    "card_2": (1400, 1235),
    "card_3": (1785, 1230),
}

# === 持有数数字裁剪区域 (左上x1, 左上y1, 右下x2, 右下y2) ===
CROP_REGIONS = [
    (920, 1140, 1150, 1192),   # 卡片1数字区域  [x1:y1, x2:y2]
    (1295, 1140, 1500, 1192),  # 卡片2数字区域
    (1680, 1140, 1900, 1192)   # 卡片3数字区域
]


def combat_prep(connector, device, joystick):
    """封装：选密函 -> 进场 -> 移动 -> 开大"""
    print("    -> 正在选择密函...")
    click(*COORDS["secret_1"], connector, device, show_log=False)
    time.sleep(0.5)
    click(*COORDS["confirm_sel"], connector, device, show_log=False)

    print("    -> 等待加载中(15s)...")
    time.sleep(15)

    print("    -> 执行入场移动与技能...")
    joystick.move('w', 18)
    click(*COORDS["ult_pos"], connector, device, show_log=False)


def select_min_owned_reward(connector, dev):
    """截屏并使用 OCR 识别持有数最少的密函，然后点击（支持动态分辨率与安全边界）"""
    print("    -> 正在进行 OCR 识别密函持有数...")

    # 1. 获取当前屏幕截图
    try:
        raw_data = connector.get_screen_raw(dev)
        if not raw_data:
            raise RuntimeError("获取截图数据为空，设备可能已断开或响应超时")

        screen = cv2.imdecode(np.frombuffer(raw_data, np.uint8), cv2.IMREAD_COLOR)
        if screen is None:
            raise RuntimeError("截图数据解码失败")

    except Exception as e:
        raise RuntimeError(f"截屏环节发生严重错误: {e}")

    # 获取当前真实截图的宽高
    screen_h, screen_w = screen.shape[:2]

    min_val = float('inf')
    min_idx = 0
    cards_coords = [COORDS["card_1"], COORDS["card_2"], COORDS["card_3"]]

    for i, (base_x1, base_y1, base_x2, base_y2) in enumerate(CROP_REGIONS):
        try:
            real_x1, real_y1 = adapt_coord(base_x1, base_y1)
            real_x2, real_y2 = adapt_coord(base_x2, base_y2)

            # === 终极防空图与防越界保护 ===
            # 1. 确保起点小于终点
            start_y = min(real_y1, real_y2)
            end_y = max(real_y1, real_y2)
            start_x = min(real_x1, real_x2)
            end_x = max(real_x1, real_x2)

            # 2. 确保坐标不超出屏幕真实边界
            start_y = max(0, min(start_y, screen_h))
            end_y = max(0, min(end_y, screen_h))
            start_x = max(0, min(start_x, screen_w))
            end_x = max(0, min(end_x, screen_w))

            # 3. 裁切图片 (NumPy 内部必须是 y 在前，x 在后)
            crop_img = screen[start_y:end_y, start_x:end_x]

            # 4. 再次确认切出来的图片不是空的
            if crop_img.size == 0 or crop_img.shape[0] == 0 or crop_img.shape[1] == 0:
                print(f"      - 卡片 {i + 1} 裁剪区域为空，跳过该卡片。")
                continue

            # 保存调试图片
            cv2.imwrite(f"debug_crop_card_{i + 1}.jpg", crop_img)

            # OCR 读取文字
            result = reader.readtext(crop_img, detail=0)
            text = "".join(result)

            # 使用正则提取文本中的数字
            nums = re.findall(r'\d+', text)
            if nums:
                val = int(nums[-1])
                print(f"      - 卡片 {i + 1} 识别数量: {val}")
                if val < min_val:
                    min_val = val
                    min_idx = i
            else:
                print(f"      - 卡片 {i + 1} 未识别到数字，跳过 (OCR识别结果为: '{text}')")
        except Exception as e:
            print(f"      - 卡片 {i + 1} 识别出错: {e}")

    print(f"    -> 识别完成，选择卡片 {min_idx + 1} (持有数: {min_val if min_val != float('inf') else '未知'})")
    click(*cards_coords[min_idx], connector, dev, show_log=False)
    time.sleep(0.5)



def main():
    connector = ADBConnector()
    devices = connector.list_devices()
    if not devices:
        print("未找到设备")
        return

    dev = devices[0]
    joystick = JoystickController(connector, 450, 1440, 150, dev)
    run_count = 1

    print("=== √ 脚本启动 ===")
    print("\n=== 提示：默认选择持有数最少 ===")

    try:
        # 1. 初始检测进入
        print("正在检查初始状态...")
        res_start = wait_until_match(dev, connector, TEMPLATES["start"], timeout=5, raise_err=False)

        if not res_start:
            res_restart = wait_until_match(dev, connector, TEMPLATES["restart"], timeout=5, raise_err=False)
        else:
            res_restart = None

        print(f"\n=== 第 {run_count} 轮 开始 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

        if res_start:
            click(*COORDS["start_btn"], connector, dev, show_log=False)
            combat_prep(connector, dev, joystick)
        elif res_restart:
            click(*COORDS["restart_btn"], connector, dev, show_log=False)
            time.sleep(1)
            combat_prep(connector, dev, joystick)
        else:
            print("    -> 未检测到开始或再次挑战按钮，默认认为在战斗中，进入监控...")
        # 2. 主逻辑循环
        while True:
            # --- 等待战斗结束（结算界面） ---
            print("    -> 战斗进行中，等待结算...")
            wait_until_match(dev, connector, TEMPLATES["confirm"], timeout=300, raise_err=True)

            # === 识别最少密函，再点击确认 ===
            select_min_owned_reward(connector, dev)

            # 点击结算确认
            click(*COORDS["confirm_btn"], connector, dev, show_log=False)
            print("    -> 等待结算动画...")
            time.sleep(3)

            # --- 等待再次挑战 ---
            print("    -> 等待【再次挑战】按钮...")
            wait_until_match(dev, connector, TEMPLATES["restart"], timeout=30, raise_err=True)

            # 点击重开
            click(*COORDS["restart_btn"], connector, dev, show_log=False)
            print("    -> 重开战斗")

            # 【在重开战斗后，结算并打印这一轮的结束】
            print(f"=== 第 {run_count} 轮 结束 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

            run_count += 1

            print(f"=== 第 {run_count} 轮 开始 || {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

            time.sleep(1)
            combat_prep(connector, dev, joystick)

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


if __name__ == "__main__":
    main()