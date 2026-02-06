import cv2
from utils.tools import ADBConnector, ensure_adb_connection, list_devices
import sys

def send_key_q():
    try:
        # 确保ADB连接
        connector = ensure_adb_connection()

        # 列出设备
        devices = list_devices(connector)

        # 如果有设备，发送按键Q
        if devices:
            first_device = devices[0]
            print(f"向设备 {first_device} 发送按键 Q")

            # 使用ADBConnector的execute_adb_command方法发送按键命令
            result = connector.execute_adb_command(["shell", "input", "keyevent", "45"], first_device)

            if result is not None:
                print("成功发送按键 Q")
                return True
            else:
                print("发送按键失败")
                return False
        else:
            print("未找到连接的设备")
            return False

    except Exception as e:
        print(f"发送按键Q时发生错误: {e}")
        return False

if __name__ == "__main__":
    send_key_q()
    cv2.waitKey()
    cv2.destroyAllWindows()
