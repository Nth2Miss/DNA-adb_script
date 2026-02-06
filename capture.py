import cv2
from utils.tools import ADBConnector, ensure_adb_connection, list_devices, execute_screenshot_and_match, random_click
import sys


def main():
    try:
        # 确保ADB连接
        connector = ensure_adb_connection()

        # 列出设备
        devices = list_devices(connector)

        # 如果有设备，执行截图和模板匹配
        if devices:
            first_device = devices[0]
            connector.capture_screen("screenshot.png",first_device)




    except RuntimeError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
