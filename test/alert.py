import time
from plyer import notification
import winsound  # Windows 标准库，无需额外安装


def test_windows_notification():
    print("正在尝试发送测试通知...")


    try:
        # 2. 调用系统通知
        notification.notify(
            title="脚本测试成功！",
            message="这是来自你的自动化脚本的第 99 次运行提醒测试。",
            app_name="Python Automation",
            timeout=10  # 通知显示 10 秒
        )
        print("通知已发出，请查看屏幕右下角。")
    except Exception as e:
        print(f"发送失败，错误原因: {e}")


if __name__ == "__main__":
    test_windows_notification()