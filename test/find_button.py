import cv2
from utils.tools import ensure_adb_connection, list_devices, execute_screenshot_and_match, random_click, random_sleep, random_sleep_extended
import sys
import time

# 确保ADB连接
connector = ensure_adb_connection()

# 列出设备
devices = list_devices(connector)

# 如果有设备，执行截图和模板匹配
if devices:
    first_device = devices[0]
    res = execute_screenshot_and_match(first_device, connector, "../templates/xzmh.png", debug=False)
    print(res)
