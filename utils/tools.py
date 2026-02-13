import time
import random
import subprocess
import os
from typing import List, Optional
import cv2
import numpy as np
from PIL import Image
import io
import math
import socket
import re
from datetime import datetime

# ============================================
# 全局运行控制
# ============================================
_IS_RUNNING = True  # 全局运行标志

class StopScriptException(Exception):
    """自定义异常，用于在停止时跳出深层循环"""
    pass

def set_running_state(state: bool):
    """GUI 调用此函数来控制启停"""
    global _IS_RUNNING
    _IS_RUNNING = state

def check_running():
    """检查是否应该停止，如果是则抛出异常"""
    if not _IS_RUNNING:
        raise StopScriptException("用户请求停止脚本")

def smart_sleep(seconds):
    """
    【新增】智能休眠函数
    替代 time.sleep，每 0.1 秒检查一次停止信号
    """
    end_time = time.time() + seconds
    while time.time() < end_time:
        check_running()  # <--- 关键：时刻检查停止
        # 计算剩余时间，最多睡 0.1 秒
        remaining = end_time - time.time()
        time.sleep(min(0.1, max(0, remaining)))

class ADBConnector:
    """
    ADB连接器类，用于管理与Android设备的连接
    """

    def __init__(self, adb_path: str = None):
        # 检查项目目录下的 adb 文件夹中是否有 adb.exe
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_adb_path = os.path.join(current_dir, "adb", "adb.exe")

        if adb_path is None:
            if os.path.exists(local_adb_path):
                self.adb_path = local_adb_path
            else:
                # 尝试另一种路径计算方式（如果main.py不在项目根目录）
                local_adb_path_alt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "adb",
                                                  "adb.exe")

                if os.path.exists(local_adb_path_alt):
                    self.adb_path = local_adb_path_alt
                else:
                    self.adb_path = "adb"  # 使用系统 PATH 中的 adb
        else:
            self.adb_path = adb_path

        # 确保路径使用正确格式
        self.adb_path = os.path.normpath(self.adb_path)

    def check_adb_installed(self) -> bool:
        """
        检查系统是否已安装ADB
        """
        try:
            result = subprocess.run([self.adb_path, "version"],
                                    capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except FileNotFoundError:
            return False
        except subprocess.TimeoutExpired:
            return False

    def start_adb_server(self) -> bool:
        """
        启动ADB服务器
        """
        try:
            result = subprocess.run([self.adb_path, "start-server"],
                                    capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def stop_adb_server(self) -> bool:
        """
        停止ADB服务器
        """
        try:
            result = subprocess.run([self.adb_path, "kill-server"],
                                    capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def enable_tcpip(self, device_id: str, port: int = 5555) -> bool:
        """
        通过 USB 将设备切换到 TCP/IP 模式 (adb tcpip 5555)
        """
        try:
            # 执行 adb -s [device_id] tcpip 5555
            cmd = ["-s", device_id, "tcpip", str(port)]
            result = self.execute_adb_command(cmd)
            return result is not None
        except Exception as e:
            print(f"激活无线模式失败: {e}")
            return False

    def list_devices(self) -> List[str]:
        """
        列出所有已连接的设备
        返回设备序列号列表
        """
        try:
            result = subprocess.run([self.adb_path, "devices"],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return []

            lines = result.stdout.strip().split('\n')[1:]  # 跳过第一行标题
            devices = []
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        device_id = parts[0]
                        status = parts[1]
                        if status == "device":
                            devices.append(device_id)
            return devices
        except subprocess.TimeoutExpired:
            return []

    def connect_device(self, device_ip: str, port: int = 5555) -> bool:
        """
        通过IP地址连接设备
        """
        try:
            result = subprocess.run([self.adb_path, "connect", f"{device_ip}:{port}"],
                                    capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def disconnect_device(self, device_ip: str, port: int = 5555) -> bool:
        """
        断开设备连接
        """
        try:
            result = subprocess.run([self.adb_path, "disconnect", f"{device_ip}:{port}"],
                                    capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def is_device_connected(self, device_id: Optional[str] = None) -> bool:
        """
        检查是否有设备连接
        如果指定了device_id，则检查该特定设备是否连接
        """
        devices = self.list_devices()
        if device_id:
            return device_id in devices
        else:
            return len(devices) > 0

    def execute_adb_command(self, command: List[str], device_id: Optional[str] = None) -> Optional[str]:
        """
        执行ADB命令
        """
        try:
            full_command = [self.adb_path]
            if device_id:
                full_command.extend(["-s", device_id])
            full_command.extend(command)

            result = subprocess.run(full_command,
                                    capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"ADB命令执行失败: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            print("ADB命令执行超时")
            return None

    def capture_screen(self, output_path: str = "screenshot.png", device_id: Optional[str] = None) -> bool:
        """
        截取设备屏幕并保存到本地

        Args:
            output_path: 本地保存路径
            device_id: 设备ID，如果为None则使用默认设备

        Returns:
            bool: 截图是否成功
        """
        try:
            # 使用screencap命令截取屏幕并保存到设备临时位置
            temp_device_path = "/sdcard/screenshot_temp.png"
            screencap_command = ["shell", "screencap", "-p", temp_device_path]

            result = self.execute_adb_command(screencap_command, device_id)
            if result is None:
                print("截取屏幕失败")
                return False

            # 将截图从设备拉取到本地
            print(output_path)
            pull_command = ["pull", temp_device_path, output_path]
            result_pull = self.execute_adb_command(pull_command, device_id)
            if result_pull is None:
                print("拉取截图失败")
                return False

            # 清理设备上的临时文件
            rm_command = ["shell", "rm", temp_device_path]
            self.execute_adb_command(rm_command, device_id)

            print(f"屏幕截图已保存到: {output_path}")
            return True
        except Exception as e:
            print(f"截图过程中发生错误: {e}")
            return False

    def get_screen_raw(self, device_id: Optional[str] = None) -> Optional[bytes]:
        """
        直接获取设备屏幕截图的原始数据

        Args:
            device_id: 设备ID，如果为None则使用默认设备

        Returns:
            bytes: 截图的原始数据，失败时返回None
        """
        try:
            # 使用screencap命令截取屏幕并直接输出到stdout
            full_command = [self.adb_path]
            if device_id:
                full_command.extend(["-s", device_id])
            full_command.extend(["exec-out", "screencap", "-p"])

            result = subprocess.run(full_command, capture_output=True)

            if result.returncode == 0:
                return result.stdout
            else:
                print(f"获取屏幕截图失败: {result.stderr.decode()}")
                return None
        except Exception as e:
            print(f"获取屏幕原始数据时发生错误: {e}")
            return None

    def get_screen_region(self, x1: int, y1: int, x2: int, y2: int, device_id: Optional[str] = None) -> Optional[bytes]:
        """
        获取设备屏幕指定区域的截图

        Args:
            x1, y1: 区域左上角坐标
            x2, y2: 区域右下角坐标
            device_id: 设备ID，如果为None则使用默认设备

        Returns:
            bytes: 截图的原始数据，失败时返回None
        """
        try:
            # 获取完整屏幕截图
            full_screenshot_data = self.get_screen_raw(device_id)
            if not full_screenshot_data:
                return None

            # 将字节数据转换为图像对象
            try:
                image = Image.open(io.BytesIO(full_screenshot_data))
            except UnicodeDecodeError as e:
                print(f"解码屏幕截图数据时发生编码错误: {e}")
                return None
            except Exception as e:
                print(f"解码屏幕截图数据时发生错误: {e}")
                return None

            # 裁剪指定区域 (左, 上, 右, 下)
            cropped_image = image.crop((x1, y1, x2, y2))

            # 将裁剪后的图像转换为字节数据
            output_buffer = io.BytesIO()
            # 保存为PNG格式，移除可能引起警告的色彩配置文件
            # 避免保存色彩度量信息以防止cHRM警告
            cropped_image.save(output_buffer, format='PNG',
                               compress_level=6,
                               optimize=True,
                               icc_profile=None,
                               exif=None)
            cropped_image_data = output_buffer.getvalue()

            return cropped_image_data
        except ImportError:
            print("错误: 需要安装Pillow库来处理图像裁剪: pip install Pillow")
            return None
        except Exception as e:
            print(f"截取屏幕区域时发生错误: {e}")
            return None

    def click_screen(self, x: int, y: int, device_id: Optional[str] = None) -> bool:
        """
        点击设备屏幕指定位置

        Args:
            x: 点击位置的x坐标
            y: 点击位置的y坐标
            device_id: 设备ID，如果为None则使用默认设备

        Returns:
            bool: 点击是否成功
        """
        try:
            # 使用adb shell input tap命令点击指定坐标
            tap_command = ["shell", "input", "tap", str(x), str(y)]
            result = self.execute_adb_command(tap_command, device_id)

            if result is not None:
                print(f"已点击屏幕坐标: ({x}, {y})")
                return True
            else:
                print(f"点击屏幕坐标 ({x}, {y}) 失败")
                return False
        except Exception as e:
            print(f"点击屏幕时发生错误: {e}")
            return False

    def swipe_screen(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300,
                     device_id: Optional[str] = None, debug: bool = False) -> bool:
        """
        在屏幕上执行滑动操作 (模拟摇杆拖拽)

        Args:
            x1, y1: 起始坐标 (通常是摇杆中心)
            x2, y2: 终点坐标 (通常是摇杆边缘)
            duration: 滑动持续时间(ms)，即按住摇杆的时间
            device_id: 设备ID
        """
        try:
            # adb shell input swipe <x1> <y1> <x2> <y2> <duration>
            cmd = ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)]
            result = self.execute_adb_command(cmd, device_id)

            if result is not None:
                if debug:
                    print(f"滑动操作: ({x1},{y1}) -> ({x2},{y2}) 耗时 {duration}ms")
                return True
            return False
        except Exception as e:
            print(f"滑动操作失败: {e}")
            return False

    def compare_region_with_template(self, screen_data, template_path, threshold=0.8, debug=False):
        """
        全屏自适应匹配，并返回目标在大图上的坐标范围
        """
        # 1. 加载并预处理图片
        template_bgr = cv2.imread(template_path)
        if template_bgr is None:
            raise ValueError(f"无法读取模板图片: {template_path}")
        template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)

        if isinstance(screen_data, np.ndarray):
            screen_gray = cv2.cvtColor(screen_data, cv2.COLOR_BGR2GRAY) if len(screen_data.shape) == 3 else screen_data
        else:
            screen_bgr = cv2.imdecode(np.frombuffer(screen_data, np.uint8), cv2.IMREAD_COLOR)
            if screen_bgr is None:
                raise ValueError("无法解码屏幕数据")
            screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)

        s_h, s_w = screen_gray.shape[:2]
        t_h, t_w = template_gray.shape[:2]

        best_max_corr = -1.0
        best_loc = (0, 0)
        best_scale = 1.0

        # 2. 多尺度匹配
        scales = np.linspace(0.4, 1.2, 9)
        for scale in scales:
            nw, nh = int(t_w * scale), int(t_h * scale)
            if nw > s_w or nh > s_h or nw < 10 or nh < 10:
                continue

            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            resized_temp = cv2.resize(template_gray, (nw, nh), interpolation=interpolation)

            res = cv2.matchTemplate(screen_gray, resized_temp, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_max_corr:
                best_max_corr = max_val
                best_loc = max_loc
                best_scale = scale

            if max_val >= 0.95:  # 极高匹配度直接跳出
                break

        # 3. 计算坐标范围
        # best_loc 是左上角 (x, y)
        x1, y1 = best_loc
        # 根据匹配时的缩放比例计算右下角
        x2 = x1 + int(t_w * best_scale)
        y2 = y1 + int(t_h * best_scale)

        is_match = best_max_corr >= threshold

        result = {
            "is_match": is_match,
            "max_corr": float(best_max_corr),
            "target_range": (x1, y1, x2, y2),  # 返回坐标范围
            "center_point": (int((x1 + x2) / 2), int((y1 + y2) / 2))  # 顺便返回中心点以便点击
        }

        if debug:
            print(f"匹配度: {best_max_corr:.4f}, 范围: ({x1}, {y1}) -> ({x2}, {y2})")

        return result

    def scan_wifi_devices(self) -> List[str]:
        """
        扫描局域网内开启了 5555 端口的设备
        """
        found_ips = []
        # 获取本机局域网 IP 段 (例如 192.168.1)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()

            ip_prefix = '.'.join(local_ip.split('.')[:-1]) + '.'
        except:
            return []

        # 扫描常用段 (1-254)，使用多线程或短超时
        print(f"正在扫描网段: {ip_prefix}x")
        for i in range(1, 255):
            ip = ip_prefix + str(i)
            # 简单端口检查
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.01)  # 极短超时以提高扫描速度
            result = sock.connect_ex((ip, 5555))
            if result == 0:
                found_ips.append(ip)
            sock.close()

        return found_ips

#摇杆移动
class JoystickController:
    """
    【修正版 - 秒级单位】带随机扰动的拟人化摇杆控制器
    - 输入时间单位改为“秒” (float)
    - 移除了角度抖动 (保证走路不画蛇形)
    - 保留了触点漂移 (起点不固定)
    - 保留了力度浮动 (拖动距离微调)
    """

    def __init__(self, connector, center_x: int, center_y: int, radius: int, device_id=None):
        self.connector = connector
        self.cx = center_x
        self.cy = center_y
        self.radius = radius
        self.device_id = device_id

    def _get_random_start_point(self, range_limit=15):
        """获取圆心附近的随机起始点 (高斯分布模拟人手误差)"""
        offset_x = int(random.gauss(0, range_limit))
        offset_y = int(random.gauss(0, range_limit))
        # 限制最大偏移量，防止偏离太远
        offset_x = max(min(offset_x, range_limit * 2), -range_limit * 2)
        offset_y = max(min(offset_y, range_limit * 2), -range_limit * 2)
        return self.cx + offset_x, self.cy + offset_y

    def move(self, direction: str, duration: float = 1.0, debug=False):
        """
        params:
            direction: 'w', 'a', 's', 'd' 及其组合
            duration: 持续时间 (单位：秒)，例如 0.5 或 2.5
        """
        direction = direction.lower()
        if not direction: return
        print(f"移动: {direction} | 持续时间: {duration}s")

        # --- 1. 基础方向向量 ---
        dx, dy = 0, 0
        if 'w' in direction: dy -= 1  # 上
        if 's' in direction: dy += 1  # 下
        if 'a' in direction: dx -= 1  # 左
        if 'd' in direction: dx += 1  # 右

        if dx == 0 and dy == 0: return

        # 计算标准移动角度
        move_angle = math.atan2(dy, dx)

        # --- 2. 随机化处理 ---

        # A. 触点漂移
        # 获取一个随机的起始点，而不是永远从圆心开始
        start_x, start_y = self._get_random_start_point(range_limit=10)

        # B. 力度/半径浮动
        # 半径在 95% ~ 105% 之间浮动，模拟手指拉动距离的微小变化
        radius_multiplier = random.uniform(0.95, 1.05)
        current_radius = self.radius * radius_multiplier

        # --- 3. 计算终点 ---
        # 基于【随机后的起点】计算终点，而不是基于【圆心】
        # 这样生成的滑动轨迹是【完全平行的直线】，不会导致方向偏转
        target_x = start_x + current_radius * math.cos(move_angle)
        target_y = start_y + current_radius * math.sin(move_angle)

        # C. 时间转换与浮动 (秒 -> 毫秒)
        # 将秒转换为毫秒，并添加 +/- 30ms 的随机波动
        base_ms = int(duration * 1000)
        actual_duration_ms = base_ms + random.randint(-30, 30)

        # 确保时间不为负数，且至少有 50ms
        actual_duration_ms = max(50, actual_duration_ms)

        if debug:
            print(f"移动: {direction} | 设定: {duration}s | 实际指令: {actual_duration_ms}ms")

        # --- 4. 执行滑动 ---
        # 转换为整数坐标
        sx, sy = int(start_x), int(start_y)
        ex, ey = int(target_x), int(target_y)

        self.connector.swipe_screen(
            sx, sy,
            ex, ey,
            actual_duration_ms,
            self.device_id
        )



def get_adb_connector(adb_path: str = None) -> ADBConnector:
    """
    获取ADB连接器实例
    """
    return ADBConnector(adb_path)


def ensure_adb_connection() -> ADBConnector:
    """
    确保ADB连接正常，如果未安装或连接失败则抛出异常
    """
    connector = ADBConnector()

    if not connector.check_adb_installed():
        raise RuntimeError("错误: ADB未安装或未在PATH中找到")

    if not connector.start_adb_server():
        raise RuntimeError("错误: 无法启动ADB服务器")

    return connector


def list_devices(connector):
    """
    列出已连接的设备
    """
    print("ADB连接正常，正在列出已连接的设备...")
    devices = connector.list_devices()
    if devices:
        print(f"找到 {len(devices)} 个设备:")
        for device in devices:
            print(f"  - {device}")
    else:
        print("未找到已连接的设备")
    return devices


def execute_screenshot_and_match(device_id, connector, template_path, debug=False):
    """
    执行全屏匹配并返回坐标范围
    """
    raw_data = connector.get_screen_raw(device_id)
    if not raw_data:
        return None

    result = connector.compare_region_with_template(raw_data, template_path, debug=debug)

    if result["is_match"]:
        # 如果匹配成功，直接返回坐标范围字典
        return {
            "is_match": result["is_match"],
            "max_corr": result["max_corr"],
            "range": result["target_range"],
            "center": result["center_point"]
        }
    return {
        "is_match": result["is_match"]
    }


def click(x, y, connector=None, device_id=None):
    """
    在指定坐标处点击
    :param x: 点击x坐标
    :param y: 点击y坐标
    :param connector: ADB连接器实例，如果为None则使用新实例
    :param device_id: 设备ID，如果为None则使用默认设备
    """
    if connector is None:
        connector = ADBConnector()
    connector.click_screen(x, y, device_id)
    time.sleep(0.5)


def random_click(x1, y1, x2, y2, connector=None, device_id=None):
    """
    在指定的矩形区域内随机点击
    :param x1: 按钮左上角x坐标
    :param y1: 按钮左上角y坐标
    :param x2: 按钮右下角x坐标
    :param y2: 按钮右下角y坐标
    :param connector: ADB连接器实例，如果为None则使用新实例
    :param device_id: 设备ID，如果为None则使用默认设备
    """
    # 确保坐标顺序正确
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)

    # 在矩形区域内随机选择一个点
    random_x = random.randint(left, right)
    random_y = random.randint(top, bottom)

    # 如果没有提供连接器，则创建一个新的连接器
    if connector is None:
        connector = ADBConnector()

    # 添加随机延迟
    time.sleep(random.uniform(0.05, 0.2))

    # 使用ADB点击
    result = connector.click_screen(random_x, random_y, device_id)
    if result:
        # print(f"在坐标 ({random_x}, {random_y}) 处点击")
        time.sleep(0.05)
    else:
        print(f"点击坐标 ({random_x}, {random_y}) 失败")


def random_sleep(t, variation=0.1):
    """
    修改版：支持 GUI 中断
    """
    check_running()  # 先检查一次

    # 原有逻辑计算时间
    if t < 1:
        sleep_time = random.uniform(t * 0.8, t * 1.5)
    else:
        base_variation = t * variation
        sleep_time = t + random.uniform(-base_variation, base_variation * 2)
        sleep_time = max(sleep_time, 0.3)

    print(f"等待 {sleep_time:.2f} 秒")
    smart_sleep(sleep_time)


def random_sleep_extended(min_time, max_time):
    """
    修改版：支持 GUI 中断
    """
    check_running()  # 先检查一次

    sleep_time = random.uniform(min_time, max_time)
    print(f"等待 {sleep_time:.2f} 秒")
    smart_sleep(sleep_time)


class TimeoutException(Exception):
    """自定义超时异常"""
    pass


def wait_until_match(device_id, connector, template_path, timeout=60, raise_err=True):
    """
    阻塞式等待图片出现
    :param timeout: 最大等待时间（秒）
    :param raise_err: 超时是否抛出异常（True=抛出异常停止脚本，False=返回None继续运行）
    :return: 匹配结果 result 字典，如果超时且 raise_err=False 则返回 None
    """
    print(f"正在等待: {template_path} (超时: {timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        # 1. 检查是否用户点了停止
        check_running()

        # 2. 尝试匹配
        res = execute_screenshot_and_match(device_id, connector, template_path, debug=False)

        if res['is_match']:
            # 匹配成功，直接返回结果
            return res

        time.sleep(1.5)

    # 4. 时间到了还没找到
    if raise_err:
        raise TimeoutException(f"等待超时：{timeout}秒内未找到目标 {template_path}")

    return None