from utils.tools import *

def fuwei(connector, device_id):
    print("-> 执行角色复位...")
    # esc
    click(100, 80, connector, device_id)
    # 设置
    click(2000, 1700, connector, device_id)
    # 复位角色
    click(110, 870, connector, device_id)
    click(2300, 520, connector, device_id)
    click(1470, 1030, connector, device_id)

def ult(connector, device_id):
    print("-> 执行大招...")
    click(2050, 1650, connector, device_id)