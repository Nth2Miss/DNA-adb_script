from utils.tools import *
from utils.scripts import *


# 1. 连接设备
connector = ensure_adb_connection()
devices = list_devices(connector)

if devices:
    device_id = devices[0]

    # 2. 初始化摇杆
    joystick = JoystickController(
        connector=connector,
        center_x=450,
        center_y=1440,
        radius=150,
        device_id=device_id
    )

    print("开始移动测试...")

    # 向前走 2.5 秒
    joystick.move('w', 10)
    joystick.move('a', 10)
    joystick.move('w', 3)
    joystick.move('a', 25)

    fuwei(connector, device_id)



    print(">>> 任务完成")