# -*- coding: utf-8 -*-
from plyer import notification

# 定义通用标题前缀
APP_NAME = "二重螺旋 自动化脚本"


def _send_core(title, message):
    """
    基础通知发送逻辑（内部调用）
    """
    try:
        notification.notify(
            title=title,
            message=message,
            app_icon=None,  # 如果有 .ico 图标文件，可以在此处填写路径，例如 'icon.ico'
            timeout=5,  # 通知显示持续时间（秒）
        )
    except Exception as e:
        print(f"系统通知发送失败: {e}")


def send_success(count):
    """
    发送运行成功通知
    :param count: 运行的次数
    """
    title = f"{APP_NAME} - 运行完成"
    message = f"脚本执行成功！\n当前累计运行次数：{count} 次"
    _send_core(title, message)


def send_failure(error_msg="未知错误"):
    """
    发送运行失败/报错通知
    :param error_msg: 具体的错误信息
    """
    title = f"{APP_NAME} - 运行出错"
    message = f"脚本异常终止。\n原因：{error_msg}"
    _send_core(title, message)


# --- 测试代码 (实际调用时可删除) ---
if __name__ == "__main__":
    # 测试成功场景
    # send_success(10)

    # 测试失败场景
    send_failure("无法找到目标窗口句柄")