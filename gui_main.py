import sys
import time
import importlib.util
import os
import subprocess
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QApplication,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtGui import QFont, QIcon
# 引入 Fluent Widgets 组件
from qfluentwidgets import (
    FluentWindow,
    SubtitleLabel,
    BodyLabel,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    TextEdit,
    CardWidget,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    ProgressBar,
    NavigationItemPosition,
    ScrollArea,
    TableWidget,
    LineEdit,
)


# ============================================
# 1. scripts 目录路径自动定位
# ============================================
def find_project_root():
    """自动向上递归寻找包含 scripts 的目录"""
    current_path = os.path.dirname(os.path.abspath(__file__))
    print(f"[Debug] 启动位置: {current_path}")

    for i in range(4):
        if os.path.exists(os.path.join(current_path, "scripts")):
            return current_path
        parent = os.path.dirname(current_path)
        if parent == current_path: break
        current_path = parent
    return os.path.dirname(os.path.abspath(__file__))


PROJECT_ROOT = find_project_root()
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 导入工具
try:
    import utils.tools
    from utils.tools import ADBConnector, set_running_state, StopScriptException
except ImportError as e:
    print(f"导入错误: {e}")
    ADBConnector = None


# ============================================
# 2. 辅助类：日志流 & 工作线程
# ============================================
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

    def flush(self):
        pass


# 脚本执行线程
class Worker(QThread):
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, script_path, device_id):
        super().__init__()
        self.script_path = script_path
        self.device_id = device_id

    def run(self):
        if not self.script_path or not os.path.exists(self.script_path):
            self.error_signal.emit(f"错误: 找不到文件 {self.script_path}")
            self.finished_signal.emit()
            return

        set_running_state(True)
        file_name = os.path.basename(self.script_path)
        print(f"--- 正在启动: {file_name} ---")

        # 劫持 sleep
        original_sleep = time.sleep

        def interruptible_sleep(seconds):
            end_time = time.time() + seconds
            while time.time() < end_time:
                if hasattr(utils.tools, 'check_running'):
                    utils.tools.check_running()
                left = end_time - time.time()
                original_sleep(min(0.1, max(0, left)))

        time.sleep = interruptible_sleep

        try:
            mod_name = f"script_{int(time.time())}"
            spec = importlib.util.spec_from_file_location(mod_name, self.script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module

            os.chdir(PROJECT_ROOT)
            spec.loader.exec_module(module)

            if hasattr(module, 'run'):
                module.run(self.device_id)
            elif hasattr(module, 'main'):
                module.main()
            else:
                print(f"错误: {file_name} 中未找到 run(device_id) 或 main() 函数")

        except StopScriptException:
            print(">>> 🛑 脚本已成功停止")
        except Exception as e:
            import traceback
            if "StopScriptException" not in str(type(e)):
                print(f"❌ 运行出错: {e}\n{traceback.format_exc()}")
                self.error_signal.emit(str(e))
        finally:
            time.sleep = original_sleep
            self.finished_signal.emit()

    def stop(self):
        set_running_state(False)


# ============================================
# 3. 设备信息获取线程
# ============================================
class DeviceInfoWorker(QThread):
    # 发送 List[Tuple[str, str]]，方便表格显示
    info_signal = pyqtSignal(list)

    def run(self):
        data = []
        try:
            connector = ADBConnector()
            devices = connector.list_devices()
            if not devices:
                data.append(("状态", "未检测到设备"))
                self.info_signal.emit(data)
                return

            dev = devices[0]
            adb = connector.adb_path

            data.append(("设备 ID", dev))

            cmds = [
                ("设备型号", ["shell", "getprop", "ro.product.model"]),
                ("品牌厂商", ["shell", "getprop", "ro.product.brand"]),
                ("安卓版本", ["shell", "getprop", "ro.build.version.release"]),
                ("屏幕分辨率", ["shell", "wm", "size"]),
                ("电池电量", ["shell", "dumpsys", "battery"])
            ]

            for label, cmd_args in cmds:
                try:
                    full_cmd = [adb, "-s", dev] + cmd_args
                    startupinfo = None
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                    res = subprocess.run(full_cmd, capture_output=True, text=True, startupinfo=startupinfo, timeout=5)
                    output = res.stdout.strip()

                    if "battery" in cmd_args:
                        for line in output.split('\n'):
                            if "level" in line:
                                output = line.split(':')[-1].strip() + "%"
                                break

                    data.append((label, output))
                except Exception:
                    data.append((label, "获取失败"))

            self.info_signal.emit(data)

        except Exception as e:
            data.append(("错误", str(e)))
            self.info_signal.emit(data)


# ============================================
# 4. 设置页面
# ============================================
class SettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('settingInterface')
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        # 1. 标题
        self.titleLabel = SubtitleLabel('设置', self.scrollWidget)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.titleLabel)

        # 2. 设备信息卡片
        self.deviceInfoCard = CardWidget(self.scrollWidget)
        self.infoLayout = QVBoxLayout(self.deviceInfoCard)
        self.infoLayout.setContentsMargins(20, 20, 20, 20)

        # 3. 无线模式激活卡片
        self.wifiCard = CardWidget(self.scrollWidget)
        self.wifiLayout = QVBoxLayout(self.wifiCard)
        self.wifiLayout.setContentsMargins(20, 20, 20, 20)

        self.wifiTitle = BodyLabel("无线模式助手", self.wifiCard)
        self.wifiTitle.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))

        self.wifiTip = BodyLabel(
            "说明：请先通过 USB 连接手机，点击下方按钮开启 5555 端口。激活后即可拔掉数据线进行无线连接。", self.wifiCard)
        self.wifiTip.setWordWrap(True)
        self.wifiTip.setTextColor("#666666", "#999999")

        self.activeWifiBtn = PrimaryPushButton("激活当前 USB 设备的无线模式", self.wifiCard)
        self.activeWifiBtn.setIcon(FIF.WIFI)
        self.activeWifiBtn.clicked.connect(self.activate_tcpip)

        self.wifiLayout.addWidget(self.wifiTitle)
        self.wifiLayout.addWidget(self.wifiTip)
        self.wifiLayout.addSpacing(10)
        self.wifiLayout.addWidget(self.activeWifiBtn)

        self.vBoxLayout.addWidget(self.wifiCard)  # 添加到主垂直布局

        # 卡片标题栏
        title_h_layout = QHBoxLayout()
        self.infoTitle = BodyLabel("当前设备信息", self.deviceInfoCard)
        self.infoTitle.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))

        self.refreshInfoBtn = PushButton("刷新", self.deviceInfoCard)
        self.refreshInfoBtn.setIcon(FIF.SYNC)
        self.refreshInfoBtn.setFixedWidth(80)
        self.refreshInfoBtn.clicked.connect(self.load_device_info)

        title_h_layout.addWidget(self.infoTitle)
        title_h_layout.addStretch(1)
        title_h_layout.addWidget(self.refreshInfoBtn)

        # 表格显示区
        self.infoTable = TableWidget(self.deviceInfoCard)
        self.infoTable.setBorderVisible(True)
        self.infoTable.setBorderRadius(8)
        self.infoTable.setWordWrap(False)
        self.infoTable.setColumnCount(2)
        self.infoTable.setHorizontalHeaderLabels(['属性', '详细信息'])
        # 隐藏垂直表头（行号）
        self.infoTable.verticalHeader().hide()
        # 让表格列宽自动铺满
        self.infoTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # 设置初始高度
        self.infoTable.setFixedHeight(270)

        self.infoLayout.addLayout(title_h_layout)
        self.infoLayout.addSpacing(15)
        self.infoLayout.addWidget(self.infoTable)

        self.vBoxLayout.addWidget(self.deviceInfoCard)
        self.vBoxLayout.addStretch(1)

        self.load_device_info()

    def load_device_info(self):
        # 清空并显示加载状态
        self.infoTable.setRowCount(1)
        self.infoTable.setItem(0, 0, QTableWidgetItem("状态"))
        self.infoTable.setItem(0, 1, QTableWidgetItem("正在读取..."))
        self.refreshInfoBtn.setEnabled(False)

        self.worker = DeviceInfoWorker()
        self.worker.info_signal.connect(self.on_info_loaded)
        self.worker.start()

    def on_info_loaded(self, data):
        self.refreshInfoBtn.setEnabled(True)
        # 填充表格
        self.infoTable.setRowCount(len(data))
        for i, (key, val) in enumerate(data):
            # 第一列：属性名
            item_key = QTableWidgetItem(key)
            item_key.setFlags(Qt.ItemFlag.ItemIsEnabled)  # 只读
            self.infoTable.setItem(i, 0, item_key)

            # 第二列：值
            item_val = QTableWidgetItem(str(val))
            item_val.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)  # 可选中复制
            self.infoTable.setItem(i, 1, item_val)

    def activate_tcpip(self):
        """激活选中设备的 TCP 模式"""
        connector = ADBConnector()
        devices = connector.list_devices()  # 获取当前连接列表

        if not devices:
            InfoBar.warning(title="未发现设备", content="请先通过 USB 连接手机", position=InfoBarPosition.TOP_RIGHT,
                            parent=self)
            return

        # 默认尝试激活列表中的第一个设备（通常是 USB 连接的那个）
        target_dev = devices[0]

        import re
        if re.match(r"^\d+\.\d+\.\d+\.\d+", target_dev):
            InfoBar.info(title="提示", content="该设备已经是无线模式", position=InfoBarPosition.TOP_RIGHT, parent=self)
            return

        success = connector.enable_tcpip(target_dev)

        if success:
            InfoBar.success(
                title="激活成功",
                content=f"设备 {target_dev} 已开启无线等待。现在可以拔掉数据线并在主页输入 IP 连接了。",
                position=InfoBarPosition.TOP_RIGHT,
                parent=self,
                duration=5000
            )
        else:
            InfoBar.error(title="激活失败", content="请检查开发者选项中是否允许 USB 调试",
                          position=InfoBarPosition.TOP_RIGHT, parent=self)


# ============================================
# 5. 主页 (HomeInterface)
# ============================================
class HomeInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('homeInterface')
        self.worker = None
        self.original_stdout = sys.stdout
        self.script_map = {}

        self.init_ui()

        self.emitting_stream = EmittingStream()
        self.emitting_stream.textWritten.connect(self.on_log_received)
        sys.stdout = self.emitting_stream

        self.refresh_devices()
        self.scan_scripts()

    def init_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        self.titleLabel = SubtitleLabel('二重螺旋 自动化控制台', self)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.titleLabel)

        self.deviceCard = CardWidget(self)
        layout_d = QVBoxLayout(self.deviceCard)  # 改为垂直布局以容纳两行

        # 第一行：现有刷新和选择
        row1 = QHBoxLayout()
        self.deviceCombo = ComboBox(self)
        self.btn_refresh = PushButton("刷新设备", self)
        self.btn_refresh.setIcon(FIF.SYNC)
        self.btn_refresh.clicked.connect(self.refresh_devices)
        row1.addWidget(BodyLabel("当前设备", self))
        row1.addWidget(self.deviceCombo, 1)
        row1.addWidget(self.btn_refresh)

        # 第二行：WiFi 连接

        row2 = QHBoxLayout()
        self.ipInput = LineEdit(self)
        self.ipInput.setPlaceholderText("设备 IP")
        self.ipInput.setClearButtonEnabled(True)

        self.btn_wifi_connect = PushButton("无线连接", self)
        self.btn_wifi_connect.setIcon(FIF.WIFI)
        self.btn_wifi_connect.clicked.connect(self.connect_wifi_device)

        row2.addWidget(BodyLabel("远程连接", self))
        row2.addWidget(self.ipInput, 1)
        row2.addWidget(self.btn_wifi_connect)

        layout_d.addLayout(row1)
        layout_d.addLayout(row2)
        self.vBoxLayout.addWidget(self.deviceCard)

        # 脚本
        self.scriptCard = CardWidget(self)
        layout_s = QHBoxLayout(self.scriptCard)
        layout_s.setContentsMargins(16, 12, 16, 12)
        layout_s.setSpacing(10)
        self.scriptCombo = ComboBox(self)
        self.btn_scan_scripts = PushButton("刷新列表", self)
        self.btn_scan_scripts.setIcon(FIF.FOLDER)
        self.btn_scan_scripts.clicked.connect(self.scan_scripts)
        layout_s.addWidget(BodyLabel("脚本", self))
        layout_s.addWidget(self.scriptCombo, 1)
        layout_s.addWidget(self.btn_scan_scripts)
        self.vBoxLayout.addWidget(self.scriptCard)

        # 按钮
        self.btnLayout = QHBoxLayout()
        self.startBtn = PrimaryPushButton("开始运行", self)
        self.startBtn.setIcon(FIF.PLAY)
        self.startBtn.clicked.connect(self.start_script)
        self.stopBtn = PushButton("停止运行", self)
        self.stopBtn.setIcon(FIF.PAUSE)
        self.stopBtn.setEnabled(False)
        self.stopBtn.clicked.connect(self.stop_script)
        self.clearBtn = PushButton("清空日志", self)
        self.clearBtn.setIcon(FIF.DELETE)

        self.btnLayout.addWidget(self.startBtn)
        self.btnLayout.addWidget(self.stopBtn)
        self.btnLayout.addWidget(self.clearBtn)
        self.vBoxLayout.addLayout(self.btnLayout)

        # 日志
        self.progressBar = ProgressBar(self)
        self.progressBar.hide()
        self.vBoxLayout.addWidget(self.progressBar)
        self.logText = TextEdit(self)
        self.logText.setReadOnly(True)
        self.logText.setFixedHeight(300)
        self.vBoxLayout.addWidget(self.logText)

        self.clearBtn.clicked.connect(self.logText.clear)

    def refresh_devices(self):
        self.deviceCombo.clear()
        if not ADBConnector:
            self.deviceCombo.addItem("错误: utils 导入失败")
            return
        try:
            connector = ADBConnector()
            devs = connector.list_devices()
            if devs:
                self.deviceCombo.addItems(devs)
                self.deviceCombo.setCurrentIndex(0)
            else:
                self.deviceCombo.addItem("未找到设备")
        except:
            self.deviceCombo.addItem("ADB 异常")

    def connect_wifi_device(self):
        ip = self.ipInput.text().strip()
        if not ip:
            self.show_info("错误", "请输入有效的 IP 地址", True)
            return

        if not ADBConnector:
            return

        connector = ADBConnector()
        # 如果 IP 没带端口，自动补齐 5555
        target = ip if ":" in ip else f"{ip}:5555"

        self.show_info("正在连接", f"尝试连接至 {target}...")

        # 执行连接
        success = connector.connect_device(ip)  # tools.py 已有此方法

        if success:
            self.show_info("成功", f"已连接至 {target}")
            self.refresh_devices()
        else:
            self.show_info("失败", "请确保手机已开启无线调试且在同一局域网", True)


    def scan_scripts(self):
        self.scriptCombo.clear()
        self.script_map = {}
        count = 0

        # main_p = os.path.join(PROJECT_ROOT, "main.py")
        # if os.path.exists(main_p):
        #     self.scriptCombo.addItem("main.py")
        #     self.script_map["main.py"] = main_p
        #     count += 1

        target_dir = None
        for name in ["scripts", "scrips"]:
            d = os.path.join(PROJECT_ROOT, name)
            if os.path.exists(d):
                target_dir = d
                break

        if target_dir:
            for f in os.listdir(target_dir):
                full_path = os.path.join(target_dir, f)
                if f.endswith(".py") and os.path.isfile(full_path):
                    self.scriptCombo.addItem(f)
                    self.script_map[f] = full_path
                    count += 1

        if count > 0:
            self.scriptCombo.setCurrentIndex(0)
            self.show_info("加载成功", f"已加载 {count} 个脚本")
        else:
            self.scriptCombo.addItem("未找到脚本")

    def start_script(self):
        device = self.deviceCombo.text()
        if device in ["未找到设备", "ADB 异常", "错误: utils 导入失败", ""]:
            self.show_info("错误", "请先连接设备", True)
            return

        name = self.scriptCombo.currentText()
        script_path = self.script_map.get(name)
        if not script_path:
            self.show_info("错误", "请选择有效的脚本", True)
            return

        self.toggle_ui(True)
        self.logText.clear()
        self.worker = Worker(script_path, device)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(lambda e: self.show_info("出错", "查看日志", True))
        self.worker.start()

    def stop_script(self):
        if self.worker:
            self.stopBtn.setText("停止中...")
            self.stopBtn.setEnabled(False)
            self.worker.stop()

    def on_finished(self):
        self.toggle_ui(False)
        self.stopBtn.setText("停止运行")
        self.show_info("结束", "任务已停止")

    def toggle_ui(self, running):
        """控制 UI 控件的启用/禁用状态"""
        # 按钮状态切换
        self.startBtn.setEnabled(not running)
        self.stopBtn.setEnabled(running)

        # 1. 禁用/启用上方设备选择区域
        self.deviceCombo.setEnabled(not running)
        self.btn_refresh.setEnabled(not running)  # 刷新设备按钮

        # 2. 禁用/启用无线连接区域 (新添加的控件)
        self.ipInput.setEnabled(not running)
        self.btn_wifi_connect.setEnabled(not running)

        # 3. 禁用/启用脚本选择区域
        self.scriptCombo.setEnabled(not running)
        self.btn_scan_scripts.setEnabled(not running)  # 刷新列表按钮

        # 4. 进度条显示控制
        if running:
            self.progressBar.show()
            self.progressBar.setRange(0, 0)
        else:
            self.progressBar.hide()

    def on_log_received(self, text):
        cursor = self.logText.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.logText.setTextCursor(cursor)

    def show_info(self, title, content, is_error=False):
        func = InfoBar.error if is_error else InfoBar.success
        func(title=title, content=content, position=InfoBarPosition.TOP_RIGHT, parent=self, duration=2000)

    def closeEvent(self, event):
        sys.stdout = self.original_stdout
        if self.worker: self.worker.stop()
        super().closeEvent(event)


# ============================================
# 6. 主窗口
# ============================================
class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('二重螺旋 自动化')
        self.setWindowIcon(QIcon('assets/logo.png'))
        self.resize(900, 700)

        self.homeInterface = HomeInterface(self)
        self.homeInterface.setObjectName('homeInterface')
        self.addSubInterface(self.homeInterface, FIF.HOME, '控制台')

        self.settingInterface = SettingInterface(self)
        self.addSubInterface(self.settingInterface, FIF.SETTING, '设置', NavigationItemPosition.BOTTOM)


if __name__ == '__main__':
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())