import cv2
from utils.tools import ADBConnector, ensure_adb_connection, list_devices, execute_screenshot_and_match, random_click, \
    random_sleep, random_sleep_extended
import sys
import time

#轮数
Round = 999

# 图像识别参数
check_interval = 2  # 检测间隔（秒）

start_time = time.time()

def main():
    try:
        # 确保ADB连接
        connector = ensure_adb_connection()

        # 列出设备
        devices = list_devices(connector)

        # 如果有设备，执行截图和模板匹配
        if devices:
            first_device = devices[0]
            print(f"连接到设备: {first_device}")

            # 开始挑战
            # res = execute_screenshot_and_match(first_device, connector, "../templates/start.png",
            #                                    (2315, 1705, 2700, 1775), debug=False)
            # if res:
            #     random_click(2315, 1705, 2770, 1775, connector, first_device)
            #     random_sleep(3)
            #
            #     random_click(1440, 1190, 1980, 1250, connector, first_device)
            #
            #     random_sleep_extended(80, 90)
            # else:
            #     print("未找到开始按钮")
            #     sys.exit(1)

            # 主循环
            for i in range(Round):
                print(f"\n--- 第 {i + 1} 轮开始 ---")

                # 检测再次进行按钮
                attempt_count = 0
                while True:
                    res = execute_screenshot_and_match(first_device, connector, "../templates/restart.png",
                                                       (1682, 1700, 2147, 1778), debug=False)
                    if res:
                        print("✓ 检测到再次进行按钮，点击继续...")
                        random_click(1682, 1700, 2147, 1778, connector, first_device)
                        random_sleep(3)
                        random_click(1440, 1190, 1980, 1250, connector, first_device)
                        break
                    else:
                        attempt_count += 1
                        # 每隔一定次数打印一次等待信息，避免输出过多
                        if attempt_count % 5 == 0:
                            print(f"⏳ 等待再次进行按钮出现... (已等待 {attempt_count * check_interval} 秒)")
                        time.sleep(check_interval)

                print(f"--- 第 {i + 1} 轮完成 ---")

    except RuntimeError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
    cv2.waitKey()
    cv2.destroyAllWindows()
