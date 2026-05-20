import time
import random
import subprocess
import os
import json
from datetime import datetime
import math
import socket
import re
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from PIL import Image

# ============================================
# 全局运行控制与异常
# ============================================
_IS_RUNNING = True  # 全局运行标志


class StopScriptException(Exception):
    """自定义异常，用于在停止时跳出深层循环"""
    pass


class TimeoutException(Exception):
    """自定义超时异常"""
    pass


def set_running_state(state: bool):
    global _IS_RUNNING
    _IS_RUNNING = state


def check_running():
    if not _IS_RUNNING:
        raise StopScriptException("用户请求停止脚本")


def smart_sleep(seconds: float):
    """智能休眠：替代 time.sleep，支持被全局停止信号随时中断"""
    end_time = time.time() + seconds
    while time.time() < end_time:
        check_running()
        time.sleep(min(0.1, end_time - time.time()))


# ============================================
# 配置管理
# ============================================
class ConfigManager:
    """独立的配置文件统一管理类"""

    DEFAULT_CONFIG = {
        "commission_multiplier": "不使用",
        "last_ip": "",
        "email_enabled": False,
        "email_smtp": "smtp.qq.com",
        "email_port": "465",
        "email_sender": "",
        "email_pwd": "",
        "email_receiver": ""
    }

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.data = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.data.update(json.load(f))
            except Exception as e:
                print(f"读取配置失败: {e}")

    def save(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def get(self, key: str, default=None):
        # 重新从磁盘加载，保证实时同步
        self.load()
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        # 兼容旧逻辑中的特殊映射
        if key == "multiplier":
            key = "commission_multiplier"
        self.data[key] = value
        self.save()

# 获取当前文件所在目录的父目录（即项目根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# 全局配置实例
config_mgr = ConfigManager(CONFIG_PATH)

# ============================================
# 动态分辨率配置与转换(不需要改动)
# ============================================
RESOLUTION_CONFIG = {
    "base_width": 2800,
    "base_height": 1840,
    "curr_width": None,
    "curr_height": None
}


def init_resolution(connector, device_id: Optional[str] = None):
    """
    初始化设备真实分辨率，建议在脚本启动连接ADB后调用一次
    """
    try:
        size = connector.get_screen_size(device_id)
        if size:
            w, h = size
            # 自动防呆：保证基础横竖屏逻辑一致
            if RESOLUTION_CONFIG["base_width"] > RESOLUTION_CONFIG["base_height"]:
                RESOLUTION_CONFIG["curr_width"] = max(w, h)
                RESOLUTION_CONFIG["curr_height"] = min(w, h)
            else:
                RESOLUTION_CONFIG["curr_width"] = min(w, h)
                RESOLUTION_CONFIG["curr_height"] = max(w, h)

            print("✅ 动态分辨率初始化 → 成功")
            return True
        else:
            print("❌ 获取分辨率失败: 未能从设备读取到有效的分辨率信息")
    except Exception as e:
        print(f"❌ 获取分辨率失败，详细异常信息: {e}")
    return False


def adapt_coord(x: int, y: int):
    """坐标转换计算"""
    if not RESOLUTION_CONFIG["curr_width"] or not RESOLUTION_CONFIG["curr_height"]:
        return x, y  # 未初始化时，按原绝对坐标返回

    scale_x = RESOLUTION_CONFIG["curr_width"] / RESOLUTION_CONFIG["base_width"]
    scale_y = RESOLUTION_CONFIG["curr_height"] / RESOLUTION_CONFIG["base_height"]
    return int(x * scale_x), int(y * scale_y)


# ============================================
# 核心工具：ADB 连接与设备控制
# ============================================
class ADBConnector:
    """管理与Android设备的ADB连接及基础操作"""

    def __init__(self, adb_path: str = None):
        self.adb_path = self._resolve_adb_path(adb_path)

    def _resolve_adb_path(self, adb_path: str) -> str:
        if adb_path:
            return os.path.normpath(adb_path)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths_to_check = [
            os.path.join(base_dir, "adb", "adb.exe"),
            os.path.join(os.path.dirname(base_dir), "adb", "adb.exe")
        ]
        for path in paths_to_check:
            if os.path.exists(path):
                return os.path.normpath(path)
        return "adb"  # Fallback to system PATH

    def _run_cmd(self, cmd: List[str], timeout: int = 30) -> Optional[subprocess.CompletedProcess]:
        """内部统一命令执行器，处理异常和超时"""
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"命令执行超时: {' '.join(cmd)}")
            return None
        except FileNotFoundError:
            print(f"找不到命令: {cmd[0]}")
            return None
        except Exception as e:
            print(f"执行命令发生异常: {e}")
            return None

    def execute_adb(self, command: List[str], device_id: Optional[str] = None, timeout: int = 30) -> Optional[str]:
        """执行 ADB 专用命令"""
        full_cmd = [self.adb_path]
        if device_id:
            full_cmd.extend(["-s", device_id])
        full_cmd.extend(command)

        result = self._run_cmd(full_cmd, timeout)
        if result and result.returncode == 0:
            return result.stdout
        elif result:
            print(f"ADB命令执行失败: {result.stderr}")
        return None

    def get_screen_size(self, device_id: Optional[str] = None):
        """获取设备当前的屏幕分辨率"""
        try:
            result = self.execute_adb(["shell", "wm", "size"], device_id)
            if result:
                # 解析输出，例如 "Physical size: 1080x2340"
                # 优先匹配 Override size (如果有修改过分辨率)
                match = re.search(r'Override size:\s*(\d+)x(\d+)', result)
                if not match:
                    match = re.search(r'Physical size:\s*(\d+)x(\d+)', result)

                if match:
                    return int(match.group(1)), int(match.group(2))
            return None
        except Exception as e:
            print(f"获取分辨率失败: {e}")
            return None

    # --- 设备状态与连接 ---

    def check_adb_installed(self) -> bool:
        return self._run_cmd([self.adb_path, "version"], timeout=10) is not None

    def start_adb_server(self) -> bool:
        res = self._run_cmd([self.adb_path, "start-server"])
        return res is not None and res.returncode == 0

    def list_devices(self) -> List[str]:
        res = self._run_cmd([self.adb_path, "devices"], timeout=10)
        if not res or res.returncode != 0:
            return []

        devices = []
        for line in res.stdout.strip().split('\n')[1:]:
            parts = line.split('\t')
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices

    def connect_device(self, device_ip: str, port: int = 5555) -> bool:
        target = f"{device_ip}:{port}"
        self._run_cmd([self.adb_path, "connect", target], timeout=10)
        time.sleep(0.5)

        if target not in self.list_devices():
            return False

        # 握手验证
        res = self._run_cmd([self.adb_path, "-s", target, "shell", "echo", "ready"], timeout=5)
        return res and res.stdout.strip() == "ready"

    def enable_tcpip(self, device_id: str, port: int = 5555) -> bool:
        """
        通过 USB 将设备切换到 TCP/IP 模式 (adb tcpip 5555)
        """
        try:
            # 执行 adb -s [device_id] tcpip 5555
            cmd = ["-s", device_id, "tcpip", str(port)]
            result = self.execute_adb(cmd)
            return result is not None
        except Exception as e:
            print(f"激活无线模式失败: {e}")
            return False

    # --- 屏幕与交互操作 ---

    def get_screen_raw(self, device_id: Optional[str] = None) -> Optional[bytes]:
        """获取屏幕原始字节数据"""
        cmd = [self.adb_path] + (["-s", device_id] if device_id else []) + ["exec-out", "screencap", "-p"]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=30)
            return res.stdout if res.returncode == 0 else None
        except Exception as e:
            print(f"获取屏幕原始数据失败: {e}")
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

            result = self.execute_adb(screencap_command, device_id)
            if result is None:
                print("截取屏幕失败")
                return False

            # 将截图从设备拉取到本地
            print(output_path)
            pull_command = ["pull", temp_device_path, output_path]
            result_pull = self.execute_adb(pull_command, device_id)
            if result_pull is None:
                print("拉取截图失败")
                return False

            # 清理设备上的临时文件
            rm_command = ["shell", "rm", temp_device_path]
            self.execute_adb(rm_command, device_id)

            print(f"屏幕截图已保存到: {output_path}")
            return True
        except Exception as e:
            print(f"截图过程中发生错误: {e}")
            return False

    def click_screen(self, x: int, y: int, device_id: Optional[str] = None, show_log: bool = True) -> bool:
        """带动态分辨率转换的屏幕点击"""
        real_x, real_y = adapt_coord(x, y)
        res = self.execute_adb(["shell", "input", "tap", str(real_x), str(real_y)], device_id)
        if res is not None and show_log:
            print(f"已点击屏幕坐标: ({real_x}, {real_y})")
        return res is not None

    def swipe_screen(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300,
                     device_id: Optional[str] = None) -> bool:
        """带动态分辨率转换的滑动"""
        rx1, ry1 = adapt_coord(x1, y1)
        rx2, ry2 = adapt_coord(x2, y2)
        res = self.execute_adb(["shell", "input", "swipe", str(rx1), str(ry1), str(rx2), str(ry2), str(duration)],
                               device_id)
        return res is not None

    def scan_wifi_devices(self) -> List[str]:
        """扫描局域网内开启了 5555 端口的设备"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip_prefix = '.'.join(s.getsockname()[0].split('.')[:-1]) + '.'
        except Exception:
            return []

        def check_ip(ip: str):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.3)
                return ip if sock.connect_ex((ip, 5555)) == 0 else None

        target_ips = [f"{ip_prefix}{i}" for i in range(1, 255)]
        with ThreadPoolExecutor(max_workers=100) as executor:
            return [ip for ip in executor.map(check_ip, target_ips) if ip]


# ============================================
# 图像处理与识别
# ============================================
class ImageMatcher:
    @staticmethod
    def compare_template(screen_data: bytes, template_path: str, threshold: float = 0.7) -> Dict:
        """全屏自适应匹配模板，返回坐标信息"""
        template_bgr = cv2.imread(template_path)
        if template_bgr is None:
            raise ValueError(f"无法读取模板图片: {template_path}")

        screen_bgr = cv2.imdecode(np.frombuffer(screen_data, np.uint8), cv2.IMREAD_COLOR)
        if screen_bgr is None:
            raise ValueError("无法解码屏幕数据")

        template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
        screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)

        s_h, s_w = screen_gray.shape[:2]
        t_h, t_w = template_gray.shape[:2]

        best_max_corr, best_loc, best_scale = -1.0, (0, 0), 1.0

        # 多尺度匹配
        for scale in np.linspace(0.4, 1.2, 9):
            nw, nh = int(t_w * scale), int(t_h * scale)
            if nw > s_w or nh > s_h or nw < 10 or nh < 10: continue

            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            resized_temp = cv2.resize(template_gray, (nw, nh), interpolation=interpolation)
            res = cv2.matchTemplate(screen_gray, resized_temp, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_max_corr:
                best_max_corr, best_loc, best_scale = max_val, max_loc, scale
            if max_val >= 0.95: break

        x1, y1 = best_loc
        x2, y2 = x1 + int(t_w * best_scale), y1 + int(t_h * best_scale)
        is_match = best_max_corr >= threshold

        return {
            "is_match": is_match,
            "max_corr": float(best_max_corr),
            "target_range": (x1, y1, x2, y2) if is_match else None,
            "center_point": (int((x1 + x2) / 2), int((y1 + y2) / 2)) if is_match else None
        }


# ============================================
# 交互控制器
# ============================================
class JoystickController:
    """
    【最终版 - 秒级单位 + 走跑切换】带随机扰动的拟人化摇杆控制器
    - 输入时间单位为“秒” (float)
    - 支持 mode='walk' (限制半径) 和 mode='run' (越界瞬间起跑)
    - 移除了角度抖动 (保证走路不画蛇形)
    - 保留了触点漂移 (起点不固定)
    """

    def __init__(self, connector, center_x: int, center_y: int, radius: int, run_threshold: int = 150, device_id=None):
        self.connector = connector
        self.cx = center_x
        self.cy = center_y
        self.radius = radius
        self.run_threshold = run_threshold  # 走路/跑步的分界线
        self.device_id = device_id

        # 跑步速度 (像素/秒)：决定了起跑的瞬间爆发力
        self.run_speed_px = 3000

    def _get_random_start_point(self, range_limit=15):
        """获取圆心附近的随机起始点 (高斯分布模拟人手误差)"""
        offset_x = int(random.gauss(0, range_limit))
        offset_y = int(random.gauss(0, range_limit))
        # 限制最大偏移量，防止偏离太远
        offset_x = max(min(offset_x, range_limit * 2), -range_limit * 2)
        offset_y = max(min(offset_y, range_limit * 2), -range_limit * 2)
        return self.cx + offset_x, self.cy + offset_y

    def move(self, direction: str, duration: float = 1.0, mode: str = 'run', debug=False):
        """
        params:
            direction: 'w', 'a', 's', 'd' 及其组合
            duration: 持续时间 (单位：秒)，例如 0.5 或 2.5
            mode: 'walk' (走路) 或 'run' (跑步)
        """
        direction = direction.lower()
        if not direction: return

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

        # B. 力度/半径计算 (根据 Walk/Run 模式分支)
        if mode == 'walk':
            # 走路模式：限制在阈值内的 40%~90%，确保不会意外触发跑步
            min_walk = self.run_threshold * 0.4
            max_walk = self.run_threshold * 0.9
            current_radius = random.uniform(min_walk, max_walk)
        else:
            # 跑步模式：使用 Over-drag (越界拖拽) 技巧
            # 距离 = 速度(px/s) * 时间(s)
            virtual_dist = self.run_speed_px * duration
            # 确保至少拉出一定距离，并在远端加一点随机波动
            current_radius = max(self.radius * 1.2, virtual_dist)
            current_radius += random.uniform(-200, 200)
            current_radius = min(current_radius, 5000)  # 防止坐标溢出报错

        # --- 3. 计算终点 ---
        # 基于【随机后的起点】计算终点，保证滑动轨迹是【完全平行的直线】
        target_x = start_x + current_radius * math.cos(move_angle)
        target_y = start_y + current_radius * math.sin(move_angle)

        # C. 时间转换与浮动 (秒 -> 毫秒)
        # 将秒转换为毫秒，并添加 +/- 30ms 的随机波动
        base_ms = int(duration * 1000)
        actual_duration_ms = base_ms + random.randint(-30, 30)

        # 确保时间不为负数，且至少有 50ms
        actual_duration_ms = max(50, actual_duration_ms)

        if debug:
            print(f"移动: {direction} | 模式: {mode} | 设定: {duration}s | 实际指令: {actual_duration_ms}ms")

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



# ============================================
# 便捷高层 API
# ============================================
def get_adb_connector(adb_path: str = None) -> ADBConnector:
    """获取ADB连接器实例"""
    return ADBConnector(adb_path)


def ensure_adb_connection() -> ADBConnector:
    """确保ADB连接正常，如果未安装或连接失败则抛出异常"""
    connector = ADBConnector()
    if not connector.check_adb_installed():
        raise RuntimeError("错误: ADB未安装或未在PATH中找到")
    if not connector.start_adb_server():
        raise RuntimeError("错误: 无法启动ADB服务器")
    return connector

def list_devices(connector: ADBConnector) -> List[str]:
    """列出已连接的设备并在控制台打印"""
    print("ADB连接正常，正在列出已连接的设备...")
    devices = connector.list_devices()
    if devices:
        print(f"找到 {len(devices)} 个设备:")
        for device in devices:
            print(f"  - {device}")
    else:
        print("未找到已连接的设备")
    return devices

def click(x: int, y: int, connector: ADBConnector = None, device_id: str = None, show_log: bool = False):
    """
    高层点击函数
    """
    if connector is None:
        connector = ADBConnector()
    connector.click_screen(x, y, device_id, show_log)
    time.sleep(0.5)


def random_click(x1: int, y1: int, x2: int, y2: int, connector: ADBConnector = None, device_id: str = None):
    """
    区域随机点击函数
    """
    if connector is None:
        connector = ADBConnector()

    rx1, ry1 = adapt_coord(x1, y1)
    rx2, ry2 = adapt_coord(x2, y2)

    left = min(rx1, rx2)
    top = min(ry1, ry2)
    right = max(rx1, rx2)
    bottom = max(ry1, ry2)

    random_x = random.randint(left, right)
    random_y = random.randint(top, bottom)

    time.sleep(random.uniform(0.05, 0.2))

    # 因为已经是实际坐标了，所以这里直接调原生的tap命令，或者再次调用click_screen时注意别二次转换
    # 最稳妥的方式是直接走底层指令
    res = connector.execute_adb(["shell", "input", "tap", str(random_x), str(random_y)], device_id)
    if res is not None:
        time.sleep(0.05)
    else:
        print(f"点击坐标 ({random_x}, {random_y}) 失败")


def long_press(x: int, y: int, duration: float, connector: ADBConnector = None, device_id: str = None,
               show_log: bool = True):
    """
    按住屏幕指定位置，单位为秒
    :param x: 基础分辨率 X (2800)
    :param y: 基础分辨率 Y (1840)
    :param duration: 按住持续时间（秒），支持小数，如 0.5
    """
    if connector is None:
        connector = ADBConnector()

    # 转换为实际分辨率坐标
    real_x, real_y = adapt_coord(x, y)

    # 将秒转换为 ADB 所需的毫秒
    duration_ms = int(duration * 1000)

    # ADB 长按原理：起始点和终点相同，并指定持续时间
    cmd = [
        "shell", "input", "swipe",
        str(real_x), str(real_y),
        str(real_x), str(real_y),
        str(duration_ms)
    ]

    res = connector.execute_adb(cmd, device_id)
    if res is not None and show_log:
        print(f"-> 已长按坐标: ({real_x}, {real_y}) 持续 {duration}s")
    return res is not None

def random_sleep(min_time: float, max_time: float = None, variation: float = 0.1):
    """支持 GUI 中断的随机睡眠 """
    check_running()
    if max_time is not None:
        sleep_time = random.uniform(min_time, max_time)
    else:
        base_variation = min_time * variation
        sleep_time = max(0.3, min_time + random.uniform(-base_variation, base_variation * 2))

    status_notifier.log(f"等待 {sleep_time:.2f} 秒...")
    smart_sleep(sleep_time)


def random_sleep_extended(min_time: float, max_time: float = None, variation: float = 0.1):
    """支持 GUI 中断的长时间随机睡眠 """
    random_sleep(min_time, max_time, variation)


def execute_screenshot_and_match(device_id: str, connector: ADBConnector, template_path: str, region=None,
                                 debug: bool = False) -> Dict:
    raw_data = connector.get_screen_raw(device_id)
    if not raw_data:
        return {"is_match": False}
    res = ImageMatcher.compare_template(raw_data, template_path)
    if debug:
        status_notifier.log(f"截图匹配结果: {res}")
    return res


def wait_until_match(device_id: str, connector: ADBConnector, template_path: str, timeout: int = 60,
                     raise_err: bool = True, debug: bool = False) -> Optional[Dict]:
    """阻塞式等待图片出现"""
    print(f"正在等待: {template_path} (超时: {timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        check_running()
        res = execute_screenshot_and_match(device_id, connector, template_path)
        if res.get('is_match'):
            return res
        elif debug:
            print(f"  未匹配: {res}")
        time.sleep(1.5)

    if raise_err:
        raise TimeoutException(f"等待超时：{timeout}秒内未找到目标 {template_path}")
    return None


# ============================================
# 统一状态与日志分发器（用于主页表格与侧边栏日志分流）
# ============================================
class ScriptStatusSignaler:
    def __init__(self):
        self.callback = None
        self.log_callback = None

    def update(self, current_round: int, step_desc: str, total_round: int = None):
        """同步更新主界面单行看板表格的状态"""
        if self.callback:
            self.callback(current_round, step_desc, total_round)
        # 步骤也会自动在侧边栏详细日志中同步写一份
        self.log(f"[步骤] {step_desc}")

    def log(self, text: str):
        """同步将详细调试信息追加到侧边栏日志面板"""
        if self.log_callback:
            self.log_callback(text)
        else:
            print(text)

# 全局单例，供所有自动化业务脚本和GUI导入共享
status_notifier = ScriptStatusSignaler()
