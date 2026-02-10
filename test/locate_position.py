# -*- coding: utf-8 -*-
import cv2
import numpy as np
from utils.tools import ensure_adb_connection

# ==========================================
# 配置区域
# ==========================================
# 缩放比例：0.5 表示显示 50% 大小
# 如果屏幕还是太大，可以改成 0.4 或 0.3
SCALE = 0.4


# ==========================================

def main():
    print("正在初始化 ADB 连接...")
    try:
        connector = ensure_adb_connection()
        devices = connector.list_devices()
        if not devices:
            print("❌ 未发现设备")
            return

        device_id = devices[0]
        print(f"✅ 已连接设备: {device_id}")
        print(f"ℹ️ 当前显示缩放比例: {SCALE * 100}%")

        run_gui(connector, device_id)

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        input("按回车键退出...")


def run_gui(connector, device_id):
    window_name = "Coordinates Tool"
    cv2.namedWindow(window_name)

    # 存储原始图片（全分辨率）和显示图片（缩放后）
    raw_image = None
    display_image = None

    def refresh_screen():
        nonlocal raw_image, display_image
        print("\n正在刷新屏幕...")
        raw_data = connector.get_screen_raw(device_id)

        if raw_data:
            # 1. 解码为原始全分辨率图片
            image_np = np.frombuffer(raw_data, np.uint8)
            raw_image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

            # 2. 生成缩放后的图片用于显示
            # fx, fy 是宽高的缩放因子
            display_image = cv2.resize(raw_image, None, fx=SCALE, fy=SCALE)

            cv2.imshow(window_name, display_image)
            print("✅ 画面已更新")
        else:
            print("❌ 获取截图失败")

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if raw_image is None: return

            # === 核心逻辑：坐标还原 ===
            # 鼠标点击的是缩放后的坐标 (x, y)
            # 我们需要除以缩放比例，还原回真实坐标
            real_x = int(x / SCALE)
            real_y = int(y / SCALE)

            # 确保坐标不超出真实图片范围
            h, w = raw_image.shape[:2]
            real_x = min(max(0, real_x), w - 1)
            real_y = min(max(0, real_y), h - 1)

            print(f"\n>>> 📍 真实坐标: ({real_x}, {real_y})")
            print(f"    📋 代码: click({real_x}, {real_y})")

            # === 视觉反馈 ===
            # 在显示的图片（小图）上画圈，方便你看
            # 这里直接在 display_image 上画，不需要还原坐标
            img_show = display_image.copy()
            cv2.circle(img_show, (x, y), 5, (0, 0, 255), -1)
            cv2.putText(img_show, f"({real_x},{real_y})", (x + 10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow(window_name, img_show)

    cv2.setMouseCallback(window_name, on_mouse)
    refresh_screen()

    print("\n操作说明:")
    print(" [鼠标左键] 点击获取真实坐标")
    print(" [R 键]     刷新屏幕")
    print(" [Q 键]     退出")

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key == ord('r') or key == ord('R'):
            refresh_screen()
        elif key == ord('q') or key == ord('Q') or key == 27:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()