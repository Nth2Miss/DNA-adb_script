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

def spiral(connector, device_id, num):
    print("-> 执行螺旋操作...")
    for i in range(num):
        print(f"   螺旋第 {i + 1} 次")
        click(2330, 1020, connector, device_id)
        time.sleep(0.5)


def timeout(connector, device_id):
    print("-> 执行超时重试...")
    # esc
    click(100, 80, connector, device_id)

