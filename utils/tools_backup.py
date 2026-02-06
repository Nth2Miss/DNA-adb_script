import time
import random
import subprocess
import os
from typing import List, Optional
import cv2
import numpy as np
from PIL import Image
import io




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

    def compare_region_with_template(self, region_data, template_path, threshold=0.8, debug=False):
        """
        比较区域数据与模板图片的相似度

        Args:
            region_data: 区域图片数据，可以是numpy数组或字节数据
            template_path: 模板图片路径
            threshold: 匹配相似度阈值，默认0.8
            debug: 是否启用调试模式，显示详细信息

        Returns:
            dict: 包含匹配结果和匹配相似度的字典

        Raises:
            ValueError: 当无法读取模板图片或解码区域数据失败时
        """

        # 读取模板图片
        template = cv2.imread(template_path)
        if template is None:
            raise ValueError(f"无法读取模板图片: {template_path}")

        # 如果region_data是numpy数组（图片），直接使用；如果是字节数据，则解码
        if isinstance(region_data, np.ndarray):
            region = region_data
        else:
            region = cv2.imdecode(np.frombuffer(region_data, np.uint8), cv2.IMREAD_COLOR)  # 确保以彩色模式解码

        if region is None:
            raise ValueError("无法解码区域数据为图片")


        # 检查图像是否正确加载，如果图像通道数不是3（BGR），则可能加载有问题
        if len(region.shape) != 3 or region.shape[2] != 3:
            print(f"警告: 区域图片可能不是彩色图片，形状: {region.shape}")
        if len(template.shape) != 3 or template.shape[2] != 3:
            print(f"警告: 模板图片可能不是彩色图片，形状: {template.shape}")

        # 将 BGR 转换为 RGB
        region = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
        template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)

        # 确保待匹配区域图像尺寸不大于模板图像尺寸
        # 根据项目规范，必须在匹配前主动进行尺寸校验与缩放处理
        region_h, region_w = region.shape[:2]
        template_h, template_w = template.shape[:2]
        
        # 保存原始区域图片用于调试
        original_region = region.copy()
        
        if region_w > template_w or region_h > template_h:
            # 计算缩放比例，保持宽高比
            scale_w = template_w / region_w
            scale_h = template_h / region_h
            scale = min(scale_w, scale_h)  # 选择较小的缩放比例以确保完全适应
            
            # 计算新的尺寸
            new_w = int(region_w * scale)
            new_h = int(region_h * scale)
            
            # 缩放区域图片
            region = cv2.resize(region, (new_w, new_h))
            
            if debug:
                print(f"区域图片尺寸过大，已缩放至: {region.shape} (原尺寸: {original_region.shape})")

        if debug:
            print(f"原始模板图片尺寸: {template.shape}")
            print(f"原始区域图片尺寸: {original_region.shape}")
            print(f"缩放后区域图片尺寸: {region.shape}")

            # 显示调试图像，添加窗口控制避免循环中未响应
            cv2.imshow("original_region", original_region)
            cv2.imshow("region", region)
            cv2.imshow("template", template)
            cv2.waitKey(1)  # 非阻塞等待，允许GUI更新

        # 使用模板匹配方法
        # 注意：OpenCV matchTemplate要求图像尺寸不大于模板尺寸
        result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
        max_corr = result.max()
        
        # 检查模板和区域是否为纯色（避免纯色区域匹配误判）
        # 计算模板和区域的方差，如果方差很小，说明可能是纯色
        template_variance = np.var(template)
        region_variance = np.var(region)
        
        # 如果模板或区域的方差很小（接近纯色），则降低匹配度
        if template_variance < 10 or region_variance < 10:
            # 检查是否真的匹配，而不是纯色误匹配
            if template_variance < 10 and region_variance < 10:
                # 都是纯色，但颜色不同时应返回低匹配度
                template_mean_color = np.mean(template)
                region_mean_color = np.mean(region)
                if abs(template_mean_color - region_mean_color) > 50:  # 颜色差异较大
                    max_corr = 0.0
                else:
                    # 如果都是纯黑色，但实际可能不是匹配的，降低置信度
                    print("检测到纯色区域，可能为误匹配，降低置信度")
                    max_corr = max_corr * 0.1  # 降低置信度
            else:
                # 只有一个是纯色，可能是误匹配
                print("检测到纯色区域，可能为误匹配")
                max_corr = 0.0

        if debug:
            print(f"模板方差: {template_variance}, 区域方差: {region_variance}")
            print(f"匹配相似度: {max_corr}")
            print(f"阈值: {threshold}")

        # 判断是否匹配
        is_match = max_corr >= threshold
        if debug:
            print(f"匹配结果: {is_match}")
        return {"is_match": is_match, "max_corr": max_corr}


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


def execute_screenshot_and_match(device_id, connector, template_path, region_xy=None, debug=False):
    """
    执行截图和模板匹配的完整流程
    """
    if debug:
        print(f"\n正在对设备 {device_id} 进行截图...")

    # 获取屏幕截图的原始数据
    raw_data = connector.get_screen_raw(device_id)
    if not raw_data:
        print("获取屏幕截图原始数据失败！")
        return

    if debug:
        print(f"获取到屏幕截图原始数据，大小: {len(raw_data)} 字节")

    # 截取指定区域
    x1, y1, x2, y2 = region_xy
    region_data = connector.get_screen_region(x1, y1, x2, y2, device_id)
    if not region_data:
        print("截取指定区域失败！")
        return

    if debug:
        print(f"获取到指定区域截图，大小: {len(region_data)} 字节")

    # 模板匹配
    result = connector.compare_region_with_template(region_data, template_path, debug=debug)
    if debug:
        print(f"匹配结果: {result['is_match']}, 匹配相似度: {result['max_corr']}")
    if result["is_match"]:
        return result["is_match"]
    return False


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
    随机暂停一段时间，模拟真实用户操作
    :param t: 基础等待时间（秒）
    :param variation: 变化系数，默认为0.1，表示在基础时间上增加随机变化
    """
    # 对于游戏脚本，我们使用更自然的等待模式
    if t < 1:  # 如果基础时间小于1秒，使用较小的变化范围
        sleep_time = random.uniform(t * 0.8, t * 1.5)
    else:  # 对于较长的等待时间，使用更大幅度的变化
        # 基础时间加上一个基于variation参数的随机值
        base_variation = t * variation
        sleep_time = t + random.uniform(-base_variation, base_variation * 2)

        # 确保等待时间不会太短
        sleep_time = max(sleep_time, 0.3)

    time.sleep(sleep_time)
    print(f"等待 {sleep_time:.2f} 秒")


def random_sleep_extended(min_time, max_time):
    """
    在指定范围内随机暂停，适用于等待游戏加载或完成
    :param min_time: 最短等待时间
    :param max_time: 最长等待时间
    """
    sleep_time = random.uniform(min_time, max_time)
    time.sleep(sleep_time)
    print(f"等待 {sleep_time:.2f} 秒")