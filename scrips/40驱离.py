from utils.tools import *
import sys
import time

Round = 9999
i = 0

def main():
    try:
        # 确保ADB连接
        connector = ensure_adb_connection()

        # 列出设备
        devices = list_devices(connector)
        
        # 如果有设备，执行截图和模板匹配
        if devices:
            first_device = devices[0]

            # 开始挑战
            res = execute_screenshot_and_match(first_device, connector, "../templates/start_1.png",debug=False)
            if res['is_match']:
                random_click(2315,1705,2770,1775, connector, first_device)
                time.sleep(0.5)
                random_click(1440, 1190, 1980, 1250, connector, first_device)

                time.sleep(15)
                connector.click_screen(2050, 1650, first_device)

            else:
                print("未找到开始按钮")
                sys.exit(1)

            # 主循环
            # for i in range(Round):
            while True:
                global i
                # 再次进行
                res = execute_screenshot_and_match(first_device, connector, "../templates/restart.png", debug=False)
                # print(f"识别{res['is_match']}")
                if res['is_match']:
                    print(f"\n第{i + 1}次运行")
                    i += 1

                    random_click(1682, 1700, 2147, 1778, connector, first_device)
                    time.sleep(0.5)

                    random_click(1440, 1190, 1980, 1250, connector, first_device)

                    time.sleep(15)

                    connector.click_screen(2050, 1650, first_device)

                    time.sleep(10)



        
    except RuntimeError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
    cv2.waitKey()
    cv2.destroyAllWindows()