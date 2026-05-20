import sys
import time
import importlib.util
import os
import subprocess
import json
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QApplication,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtGui import QFont, QIcon
from qfluentwidgets import (
    FluentWindow, SubtitleLabel, BodyLabel, ComboBox, PrimaryPushButton,
    PushButton, TextEdit, CardWidget, FluentIcon as FIF, InfoBar,
    InfoBarPosition, ProgressBar, NavigationItemPosition, ScrollArea,
    TableWidget, LineEdit, SwitchButton, PasswordLineEdit, MessageBox, SettingCard,
)


# ============================================
# 1. scripts 目录路径自动定位
# ============================================
def find_project_root():
    current_path = os.path.dirname(os.path.abspath(__file__))
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

try:
    import utils.tools
    from utils.tools import ADBConnector, set_running_state, StopScriptException

    APP_CONFIG = utils.tools.config_mgr
except ImportError as e:
    print(f"导入错误: {e}")
    ADBConnector = None


# ============================================
# 重定向 sys.stdout 的日志流分配器
# ============================================
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)

    def write(self, text):
        # 过滤掉空行，防止 TextEdit 出现过多无意义折行
        if text.strip():
            self.textWritten.emit(str(text))

    def flush(self):
        pass


# ============================================
# 2. 辅助类：工作线程与设备信息线程
# ============================================
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
        print(f"=== 正在启动脚本: {file_name} ===")

        try:
            connector = ADBConnector()
            utils.tools.init_resolution(connector, self.device_id)
        except Exception as e:
            print(f"⚠️ 动态分辨率初始化异常: {e}")

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
            print(f"❌ 运行出错: {e}\n{traceback.format_exc()}")
            self.error_signal.emit(str(e))
        finally:
            time.sleep = original_sleep
            self.finished_signal.emit()

    def stop(self):
        set_running_state(False)


class DeviceInfoWorker(QThread):
    info_signal = pyqtSignal(list)

    def run(self):
        data = []
        try:
            connector = ADBConnector()
            devices = connector.list_devices()
            if not devices:
                data.append(("状态", "未检测到设备"))
                self.info_signal.emit(data);
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
                            if "level" in line: output = line.split(':')[-1].strip() + "%"; break
                    data.append((label, output))
                except Exception:
                    data.append((label, "获取失败"))
            self.info_signal.emit(data)
        except Exception as e:
            data.append(("错误", str(e)))
            self.info_signal.emit(data)


class ScanWifiWorker(QThread):
    scan_finished = pyqtSignal(list)

    def run(self):
        connector = ADBConnector()
        ips = connector.scan_wifi_devices()
        self.scan_finished.emit(ips)


# ============================================
# 3. 侧边栏独立的日志面板 (LogInterface)
# ============================================
class LogInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('logInterface')
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        self.titleLabel = SubtitleLabel('详细运行日志', self.scrollWidget)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.titleLabel)

        self.logCard = CardWidget(self.scrollWidget)
        self.cardLayout = QVBoxLayout(self.logCard)
        self.cardLayout.setContentsMargins(15, 15, 15, 15)

        self.logText = TextEdit(self.logCard)
        self.logText.setReadOnly(True)
        self.logText.setFixedHeight(450)
        self.cardLayout.addWidget(self.logText)

        self.btnLayout = QHBoxLayout()
        self.clearBtn = PushButton("清空日志台", self.logCard)
        self.clearBtn.setIcon(FIF.DELETE)
        self.clearBtn.clicked.connect(self.logText.clear)
        self.btnLayout.addStretch(1)
        self.btnLayout.addWidget(self.clearBtn)
        self.cardLayout.addLayout(self.btnLayout)

        self.vBoxLayout.addWidget(self.logCard)
        self.vBoxLayout.addStretch(1)

    @pyqtSlot(str)
    def append_log(self, text):
        """接收日志并自动渲染 HTML 染色效果"""
        current_time = time.strftime("%H:%M:%S", time.localtime())
        cleaned_text = text.strip()

        if "✅" in cleaned_text or "成功" in cleaned_text:
            html = f'<font color="#0F7B42">[{current_time}] {cleaned_text}</font>'
        elif "❌" in cleaned_text or "错误" in cleaned_text or "异常" in cleaned_text:
            html = f'<font color="#851614"><b>[{current_time}] {cleaned_text}</b></font>'
        elif "[步骤]" in cleaned_text:
            html = f'<font color="#0066CC"><b>[{current_time}] {cleaned_text}</b></font>'
        else:
            html = f'<font color="#777777">[{current_time}]</font> <font color="#333333">{cleaned_text}</font>'
        self.logText.append(html)


# ============================================
# 4. 主页 (HomeInterface)
# ============================================
class HomeInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.config_file = os.path.join(PROJECT_ROOT, "config.json")
        self.setObjectName('homeInterface')
        self.worker = None
        self.script_map = {}

        self.init_ui()

        # 绑定表格数据槽
        from utils.tools import status_notifier
        status_notifier.callback = self.on_status_updated

        self.refresh_devices()
        self.scan_scripts()

    def init_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        # 各卡片和组件之间的垂直间距设为 20 像素
        self.vBoxLayout.setSpacing(20)

        # --- 标题 ---
        self.titleLabel = SubtitleLabel('二重螺旋 自动化控制台', self)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.titleLabel)

        # --- 设备卡片 ---
        self.deviceCard = CardWidget(self)
        layout_d = QVBoxLayout(self.deviceCard)
        layout_d.setSpacing(8)  # 设备卡片内部两行保持 8 像素的舒适行距
        layout_d.setContentsMargins(16, 12, 16, 12)

        row1 = QHBoxLayout()
        self.deviceCombo = ComboBox(self)
        self.btn_refresh = PushButton("刷新设备", self)
        self.btn_refresh.setIcon(FIF.SYNC)
        self.btn_refresh.clicked.connect(self.refresh_devices)
        row1.addWidget(BodyLabel("当前设备", self))
        row1.addWidget(self.deviceCombo, 1)
        row1.addWidget(self.btn_refresh)

        row2 = QHBoxLayout()
        self.ipInput = LineEdit(self)
        self.ipInput.setPlaceholderText("设备 IP")
        self.ipInput.setClearButtonEnabled(True)
        if APP_CONFIG: self.ipInput.setText(APP_CONFIG.get("last_ip", ""))
        self.btn_scan_wifi = PushButton("自动扫描", self)
        self.btn_scan_wifi.setIcon(FIF.SEARCH)
        self.btn_scan_wifi.clicked.connect(self.auto_scan_wifi)
        self.btn_wifi_connect = PushButton("无线连接", self)
        self.btn_wifi_connect.setIcon(FIF.WIFI)
        self.btn_wifi_connect.clicked.connect(self.connect_wifi_device)
        row2.addWidget(BodyLabel("远程连接", self))
        row2.addWidget(self.ipInput, 1)
        row2.addWidget(self.btn_scan_wifi)
        row2.addWidget(self.btn_wifi_connect)
        layout_d.addLayout(row1)
        layout_d.addLayout(row2)
        self.vBoxLayout.addWidget(self.deviceCard)

        # --- 脚本卡片 ---
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

        # --- 底部控制按钮组 ---
        self.btnLayout = QHBoxLayout()
        self.startBtn = PrimaryPushButton("开始运行", self)
        self.startBtn.setIcon(FIF.PLAY)
        self.startBtn.clicked.connect(self.start_script)
        self.stopBtn = PushButton("停止运行", self)
        self.stopBtn.setIcon(FIF.PAUSE)
        self.stopBtn.setEnabled(False)
        self.stopBtn.clicked.connect(self.stop_script)
        self.clearBtn = PushButton("清空看板", self)
        self.clearBtn.setIcon(FIF.DELETE)
        self.btnLayout.addWidget(self.startBtn)
        self.btnLayout.addWidget(self.stopBtn)
        self.btnLayout.addWidget(self.clearBtn)
        self.vBoxLayout.addLayout(self.btnLayout)
        self.vBoxLayout.addSpacing(15)

        # --- 进度条 ---
        self.progressBar = ProgressBar(self)
        self.progressBar.hide()
        self.vBoxLayout.addWidget(self.progressBar)

        self.vBoxLayout.addSpacing(15)

        self.tableTitleLabel = BodyLabel('📊 实时运行状态看板', self)
        self.tableTitleLabel.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.tableTitleLabel)

        # --- 左侧表头、右侧数据的监控属性看板 ---
        self.statusTable = TableWidget(self)
        self.statusTable.setBorderVisible(True)
        self.statusTable.setBorderRadius(8)

        # 设置 4 行、1 列（隐藏上方表头，开启左侧垂直表头）
        self.statusTable.setColumnCount(1)
        self.statusTable.setRowCount(4)

        # 隐藏传统的顶部水平表头
        self.statusTable.horizontalHeader().hide()

        # 启用并设置左侧垂直表头
        self.statusTable.setVerticalHeaderLabels(['当前脚本', '目标轮次', '当前进度', '当前操作步骤'])
        self.statusTable.verticalHeader().show()
        # 让左侧表头文字自适应列宽
        self.statusTable.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # 让右侧数据列自动拉伸填满剩余宽度
        self.statusTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # 4行数据，每行给 26 像素宽容高度，表头总高设置在 130 左右非常饱满舒适
        self.statusTable.setFixedHeight(160)

        self.clear_table_data()
        self.vBoxLayout.addWidget(self.statusTable)

        self.vBoxLayout.addStretch(1)

        self.clearBtn.clicked.connect(self.clear_table_data)

    def clear_table_data(self):
        # 只有1列，所以列索引全是 0，行索引为 0~3
        self.statusTable.setItem(0, 0, QTableWidgetItem("-"))
        self.statusTable.setItem(1, 0, QTableWidgetItem("-"))
        self.statusTable.setItem(2, 0, QTableWidgetItem("-"))
        self.statusTable.setItem(3, 0, QTableWidgetItem("就绪 / 未启动"))

    def on_status_updated(self, current_round, step_desc):
        # 更新第 2 行（当前进度）与第 3 行（操作步骤）
        self.statusTable.setItem(2, 0, QTableWidgetItem(f"第 {current_round} 轮"))

        step_item = QTableWidgetItem(step_desc)
        if "✅" in step_desc or "成功" in step_desc:
            step_item.setForeground(Qt.GlobalColor.darkGreen)
        elif "❌" in step_desc or "错误" in step_desc:
            step_item.setForeground(Qt.GlobalColor.red)
        self.statusTable.setItem(3, 0, step_item)

    def start_script(self):
        device = self.deviceCombo.text()
        if device in ["未找到设备", "ADB 异常", "错误: utils 导入失败", ""]:
            self.show_info("错误", "请先连接设备", True);
            return
        name = self.scriptCombo.currentText()
        script_path = self.script_map.get(name)
        if not script_path: self.show_info("错误", "请选择有效的脚本", True); return

        self.toggle_ui(True)
        main_win = self.window()
        if hasattr(main_win, 'logInterface'): main_win.logInterface.logText.clear()

        # 开始运行时填充第 0 行和第 1 行
        self.statusTable.setItem(0, 0, QTableWidgetItem(name))
        self.statusTable.setItem(1, 0, QTableWidgetItem("999 次"))
        self.statusTable.setItem(2, 0, QTableWidgetItem("准备中..."))

        self.worker = Worker(script_path, device)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(lambda e: self.show_info("出错", "请查看侧边栏日志", True))
        self.worker.start()

    def stop_script(self):
        if self.worker:
            self.stopBtn.setText("停止中...")
            self.stopBtn.setEnabled(False)
            self.worker.stop()

    def on_finished(self):
        self.toggle_ui(False)
        self.stopBtn.setText("停止运行")
        self.clear_table_data()
        self.show_info("结束", "任务已停止")

    def toggle_ui(self, running):
        self.startBtn.setEnabled(not running)
        self.stopBtn.setEnabled(running)
        self.deviceCombo.setEnabled(not running)
        self.btn_refresh.setEnabled(not running)
        self.ipInput.setEnabled(not running)
        self.btn_wifi_connect.setEnabled(not running)
        self.scriptCombo.setEnabled(not running)
        self.btn_scan_scripts.setEnabled(not running)
        if running:
            self.progressBar.show(); self.progressBar.setRange(0, 0)
        else:
            self.progressBar.hide()

    def refresh_devices(self):
        self.deviceCombo.clear()
        if not ADBConnector: return
        try:
            connector = ADBConnector()
            devs = connector.list_devices()
            if devs:
                self.deviceCombo.addItems(devs); self.deviceCombo.setCurrentIndex(0)
            else:
                self.deviceCombo.addItem("未找到设备")
        except:
            self.deviceCombo.addItem("ADB 异常")

    def scan_scripts(self):
        self.scriptCombo.clear();
        self.script_map = {};
        count = 0;
        target_dir = None
        for name in ["scripts", "scrips"]:
            d = os.path.join(PROJECT_ROOT, name)
            if os.path.exists(d): target_dir = d; break
        if target_dir:
            for f in os.listdir(target_dir):
                full_path = os.path.join(target_dir, f)
                if f.endswith(".py") and os.path.isfile(full_path):
                    self.scriptCombo.addItem(f);
                    self.script_map[f] = full_path;
                    count += 1
        if count > 0:
            self.scriptCombo.setCurrentIndex(0); self.show_info("加载成功", f"已加载 {count} 个脚本")
        else:
            self.scriptCombo.addItem("未找到脚本")

    def auto_scan_wifi(self):
        self.btn_scan_wifi.setEnabled(False);
        self.btn_scan_wifi.setText("扫描中...")
        self.show_info("扫描", "正在搜索局域网内的安卓设备...")
        self.scan_worker = ScanWifiWorker()
        self.scan_worker.scan_finished.connect(self.on_wifi_scan_finished)
        self.scan_worker.start()

    def on_wifi_scan_finished(self, ips):
        self.btn_scan_wifi.setEnabled(True);
        self.btn_scan_wifi.setText("自动扫描")
        if not ips:
            self.show_info("扫描完成", "未发现开启 5555 端口的设备", True)
        else:
            self.ipInput.setText(ips[0])
            if APP_CONFIG: APP_CONFIG.set("last_ip", ips[0])
            self.show_info("扫描成功", f"找到 {len(ips)} 个设备，已填入: {ips[0]}")

    def connect_wifi_device(self):
        ip = self.ipInput.text().strip()
        if not ip: self.show_info("错误", "请输入有效的 IP 地址", True); return
        if not ADBConnector: return
        connector = ADBConnector()
        target = ip if ":" in ip else f"{ip}:5555"
        self.show_info("正在连接", f"尝试连接至 {target}...")
        if connector.connect_device(ip):
            time.sleep(0.5);
            online_devices = connector.list_devices()
            if any(target in dev for dev in online_devices):
                self.show_info("成功", f"已连接至 {target}")
                if APP_CONFIG: APP_CONFIG.set("last_ip", ip)
                self.refresh_devices()
            else:
                self.show_info("失败", "连接已建立但设备处于离线或未授权状态", True)
        else:
            self.show_info("失败", "请确保手机已开启无线调试且在同一局域网", True)

    def show_info(self, title, content, is_error=False):
        func = InfoBar.error if is_error else InfoBar.success
        func(title=title, content=content, position=InfoBarPosition.TOP_RIGHT, parent=self, duration=2000)

    def closeEvent(self, event):
        if APP_CONFIG: APP_CONFIG.set("last_ip", self.ipInput.text().strip())
        if self.worker: self.worker.stop()
        super().closeEvent(event)


# ============================================
# 5. 设置页面与其它设置页面基本类
# ============================================
class SettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('settingInterface')
        self.scrollWidget = QWidget();
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.setWidget(self.scrollWidget);
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30);
        self.vBoxLayout.setSpacing(20)
        self.titleLabel = SubtitleLabel('设置', self.scrollWidget)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.titleLabel)

        self.wifiCard = CardWidget(self.scrollWidget);
        self.wifiLayout = QVBoxLayout(self.wifiCard)
        self.wifiLayout.setContentsMargins(20, 20, 20, 20)
        self.wifiTitle = BodyLabel("无线模式助手", self.wifiCard);
        self.wifiTitle.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.wifiTip = BodyLabel(
            "说明：请先通过 USB 连接手机，点击下方按钮开启 5555 端口。激活后即可拔掉数据线进行无线连接。", self.wifiCard)
        self.wifiTip.setWordWrap(True);
        self.wifiTip.setTextColor("#666666", "#999999")
        self.activeWifiBtn = PrimaryPushButton("激活当前 USB 设备的无线模式", self.wifiCard);
        self.activeWifiBtn.setIcon(FIF.WIFI)
        self.activeWifiBtn.clicked.connect(self.activate_tcpip)
        self.scrcpyBtn = PrimaryPushButton("启动Scrcpy", self.wifiCard);
        self.scrcpyBtn.setIcon(FIF.GAME);
        self.scrcpyBtn.clicked.connect(self.start_scrcpy)
        self.wifiLayout.addWidget(self.wifiTitle);
        self.wifiLayout.addWidget(self.wifiTip);
        self.wifiLayout.addSpacing(10);
        self.wifiLayout.addWidget(self.activeWifiBtn);
        self.wifiLayout.addSpacing(10);
        self.wifiLayout.addWidget(self.scrcpyBtn)
        self.vBoxLayout.addWidget(self.wifiCard)

        self.deviceInfoCard = CardWidget(self.scrollWidget);
        self.infoLayout = QVBoxLayout(self.deviceInfoCard);
        self.infoLayout.setContentsMargins(20, 20, 20, 20)
        title_h_layout = QHBoxLayout();
        self.infoTitle = BodyLabel("当前设备信息", self.deviceInfoCard);
        self.infoTitle.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.refreshInfoBtn = PushButton("刷新", self.deviceInfoCard);
        self.refreshInfoBtn.setIcon(FIF.SYNC);
        self.refreshInfoBtn.setFixedWidth(80);
        self.refreshInfoBtn.clicked.connect(self.load_device_info)
        title_h_layout.addWidget(self.infoTitle);
        title_h_layout.addStretch(1);
        title_h_layout.addWidget(self.refreshInfoBtn)
        self.infoTable = TableWidget(self.deviceInfoCard);
        self.infoTable.setBorderVisible(True);
        self.infoTable.setBorderRadius(8);
        self.infoTable.setColumnCount(2);
        self.infoTable.setHorizontalHeaderLabels(['属性', '详细信息']);
        self.infoTable.verticalHeader().hide();
        self.infoTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);
        self.infoTable.setFixedHeight(270)
        self.infoLayout.addLayout(title_h_layout);
        self.infoLayout.addSpacing(15);
        self.infoLayout.addWidget(self.infoTable)
        device_ops_layout = QHBoxLayout();
        self.stopAppBtn = PushButton("终止设备应用", self.deviceInfoCard);
        self.stopAppBtn.setIcon(FIF.CLOSE);
        self.stopAppBtn.clicked.connect(self.stop_game_app)
        self.lockScreenBtn = PushButton("锁屏/电源键", self.deviceInfoCard);
        self.lockScreenBtn.setIcon(FIF.POWER_BUTTON);
        self.lockScreenBtn.clicked.connect(self.lock_device_screen)
        device_ops_layout.addWidget(self.stopAppBtn);
        device_ops_layout.addWidget(self.lockScreenBtn);
        device_ops_layout.addStretch(1)
        self.infoLayout.addSpacing(10);
        self.infoLayout.addLayout(device_ops_layout)
        self.vBoxLayout.addWidget(self.deviceInfoCard);
        self.vBoxLayout.addStretch(1)
        self.load_device_info()

    def load_device_info(self):
        self.infoTable.setRowCount(1);
        self.infoTable.setItem(0, 0, QTableWidgetItem("状态"));
        self.infoTable.setItem(0, 1, QTableWidgetItem("正在读取..."));
        self.refreshInfoBtn.setEnabled(False)
        self.worker = DeviceInfoWorker();
        self.worker.info_signal.connect(self.on_info_loaded);
        self.worker.start()

    def on_info_loaded(self, data):
        self.refreshInfoBtn.setEnabled(True);
        self.infoTable.setRowCount(len(data))
        for i, (key, val) in enumerate(data):
            item_key = QTableWidgetItem(key);
            item_key.setFlags(Qt.ItemFlag.ItemIsEnabled);
            self.infoTable.setItem(i, 0, item_key)
            item_val = QTableWidgetItem(str(val));
            item_val.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable);
            self.infoTable.setItem(i, 1, item_val)

    def activate_tcpip(self):
        connector = ADBConnector();
        devices = connector.list_devices()
        if not devices: InfoBar.warning(title="未发现设备", content="请先通过 USB 连接手机",
                                        position=InfoBarPosition.TOP_RIGHT, parent=self); return
        target_dev = devices[0];
        import re
        if re.match(r"^\d+\.\d+\.\d+\.\d+", target_dev): InfoBar.info(title="提示", content="该设备已经是无线模式",
                                                                      position=InfoBarPosition.TOP_RIGHT,
                                                                      parent=self); return
        if connector.enable_tcpip(target_dev):
            InfoBar.success(title="激活成功",
                            content=f"设备 {target_dev} 已开启无线等待。现在可以拔掉数据线并在主页输入 IP 连接了。",
                            position=InfoBarPosition.TOP_RIGHT, parent=self, duration=5000)
        else:
            InfoBar.error(title="激活失败", content="请检查开发者选项中是否允许 USB 调试",
                          position=InfoBarPosition.TOP_RIGHT, parent=self)

    def start_scrcpy(self):
        scrcpy_path = r"scrcpy-win64-v3.3.3\scrcpy.exe"
        if not os.path.exists(scrcpy_path): print(f"错误: 找不到文件 {scrcpy_path}"); return
        try:
            subprocess.Popen([scrcpy_path], cwd=os.path.dirname(scrcpy_path),
                             creationflags=subprocess.CREATE_NO_WINDOW); InfoBar.success(title="启动成功",
                                                                                         content="scrcpy 已启动",
                                                                                         position=InfoBarPosition.TOP_RIGHT,
                                                                                         parent=self)
        except Exception as e:
            InfoBar.error(title="启动失败", content=str(e), position=InfoBarPosition.TOP_RIGHT, parent=self)

    def stop_game_app(self):
        connector = ADBConnector();
        devices = connector.list_devices()
        if not devices: InfoBar.warning("未发现设备", "请先连接手机", position=InfoBarPosition.TOP_RIGHT,
                                        parent=self); return
        package_name = "com.hero.dna.gf";
        target_dev = devices[0]
        if connector.execute_adb(["shell", "am", "force-stop", package_name], target_dev) is not None:
            InfoBar.success("操作成功", f"已尝试终止 {package_name}", position=InfoBarPosition.TOP_RIGHT, parent=self)

    def lock_device_screen(self):
        connector = ADBConnector();
        devices = connector.list_devices()
        if not devices: InfoBar.warning("未发现设备", "请先连接手机", position=InfoBarPosition.TOP_RIGHT,
                                        parent=self); return
        if connector.execute_adb(["shell", "input", "keyevent", "26"], devices[0]) is not None:
            InfoBar.success("指令已发送", "已模拟电源键操作", position=InfoBarPosition.TOP_RIGHT, parent=self)


class OtherSettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('otherSettingInterface')
        self.scrollWidget = QWidget();
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.setWidget(self.scrollWidget);
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30);
        self.vBoxLayout.setSpacing(20)
        self.titleLabel = SubtitleLabel('其他设置', self.scrollWidget)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.titleLabel)

        self.commissionCard = SettingCard(FIF.DICTIONARY, "委托手册倍率", "设置脚本运行过程中委托手册的使用倍率",
                                          self.scrollWidget)
        self.multiplierCombo = ComboBox(self.commissionCard);
        self.multiplierCombo.addItems(["不使用", "100%", "200%", "800%", "2000%"]);
        self.multiplierCombo.setFixedWidth(120)
        if APP_CONFIG: self.multiplierCombo.setCurrentText(APP_CONFIG.get("multiplier", "不使用"))
        self.multiplierCombo.currentTextChanged.connect(
            lambda text: APP_CONFIG.set("multiplier", text) if APP_CONFIG else None)
        self.commissionCard.hBoxLayout.addStretch(1);
        self.commissionCard.hBoxLayout.addWidget(self.multiplierCombo);
        self.commissionCard.hBoxLayout.addSpacing(15)
        self.vBoxLayout.addWidget(self.commissionCard)

        from qfluentwidgets import ExpandSettingCard
        self.emailCard = ExpandSettingCard(FIF.MAIL, "邮件通知", "设置 SMTP 服务以接收自动化脚本运行结果的实时通知",
                                           self.scrollWidget)
        self.emailSwitch = SwitchButton();
        self.emailSwitch.setOnText("已开启");
        self.emailSwitch.setOffText("已关闭")
        if APP_CONFIG: self.emailSwitch.setChecked(APP_CONFIG.get("email_enabled", False))
        self.emailSwitch.checkedChanged.connect(
            lambda checked: APP_CONFIG.set("email_enabled", checked) if APP_CONFIG else None)
        self.emailCard.addWidget(self.emailSwitch)
        self.emailConfigWidget = QWidget();
        self.configLayout = QVBoxLayout(self.emailConfigWidget)
        self.configLayout.setContentsMargins(20, 10, 20, 20);
        self.configLayout.setSpacing(15)

        def add_row(label, key, widget, default=""):
            row = QHBoxLayout();
            row.addWidget(BodyLabel(label))
            val = APP_CONFIG.get(key, default) if APP_CONFIG else default
            widget.setText(val);
            widget.textChanged.connect(lambda t: APP_CONFIG.set(key, t) if APP_CONFIG else None)
            row.addWidget(widget, 1);
            self.configLayout.addLayout(row);
            return widget

        self.smtpInput = add_row("SMTP 服务器:", "email_smtp", LineEdit(), "smtp.qq.com")
        self.portInput = add_row("SMTP 端口号:", "email_port", LineEdit(), "465")
        self.senderInput = add_row("发件人邮箱:", "email_sender", LineEdit())
        self.pwdInput = PasswordLineEdit();
        self.pwdInput.setPlaceholderText("填入邮箱授权码");
        add_row("邮箱授权码:", "email_pwd", self.pwdInput)
        self.receiverInput = add_row("收件人邮箱:", "email_receiver", LineEdit())
        self.testMailBtn = PushButton("发送测试邮件");
        self.testMailBtn.setIcon(FIF.MAIL);
        self.testMailBtn.clicked.connect(self.test_send_mail)
        self.configLayout.addWidget(self.testMailBtn, 0, Qt.AlignmentFlag.AlignRight)
        self.emailCard.viewLayout.addWidget(self.emailConfigWidget);
        self.vBoxLayout.addWidget(self.emailCard)

        self.reloadUtilsCard = SettingCard(FIF.SYNC, "开发与调试",
                                           "重新加载 utils.tools 和 utils.scripts 模块，修改底层代码后无需重启即可生效",
                                           self.scrollWidget)
        self.reloadUtilsBtn = PushButton("重载 Utils", self.reloadUtilsCard);
        self.reloadUtilsBtn.setIcon(FIF.UPDATE);
        self.reloadUtilsBtn.clicked.connect(self.reload_utils)
        self.reloadUtilsCard.hBoxLayout.addStretch(1);
        self.reloadUtilsCard.hBoxLayout.addWidget(self.reloadUtilsBtn);
        self.reloadUtilsCard.hBoxLayout.addSpacing(15)
        self.vBoxLayout.addWidget(self.reloadUtilsCard);
        self.vBoxLayout.addStretch(1)

    def test_send_mail(self):
        self.testMailBtn.setEnabled(False);
        self.testMailBtn.setText("发送中...")
        import threading;
        from PyQt6.QtCore import QMetaObject, Q_ARG
        def worker():
            try:
                from utils.notification import send_notification
                result = send_notification("二重螺旋 自动化 - 测试邮件", "测试成功！")
                success, msg = result if result else (False, "无返回结果")
                QMetaObject.invokeMethod(self, "show_msg", Qt.ConnectionType.QueuedConnection,
                                         Q_ARG(str, "success" if success else "error"), Q_ARG(str, msg))
            except Exception as e:
                QMetaObject.invokeMethod(self, "show_msg", Qt.ConnectionType.QueuedConnection, Q_ARG(str, "error"),
                                         Q_ARG(str, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def reload_utils(self):
        self.reloadUtilsBtn.setEnabled(False);
        self.reloadUtilsBtn.setText("重载中...")
        try:
            import importlib;
            import utils.tools
            try:
                import utils.scripts
            except ImportError:
                pass
            importlib.reload(utils.tools)
            if 'utils.scripts' in sys.modules: importlib.reload(sys.modules['utils.scripts'])
            global ADBConnector, set_running_state, StopScriptException, APP_CONFIG
            ADBConnector = utils.tools.ADBConnector;
            set_running_state = utils.tools.set_running_state
            StopScriptException = utils.tools.StopScriptException;
            APP_CONFIG = utils.tools.config_mgr
            InfoBar.success(title="操作成功", content="Utils 下的 tools 与 scripts 模块已重新加载，可以直接运行新逻辑。",
                            position=InfoBarPosition.TOP_RIGHT, parent=self)
        except Exception as e:
            InfoBar.error(title="重载失败", content=f"错误信息: {str(e)}", position=InfoBarPosition.TOP_RIGHT,
                          parent=self)
        finally:
            self.reloadUtilsBtn.setEnabled(True); self.reloadUtilsBtn.setText("重载 Utils")

    @pyqtSlot(str, str)
    def show_msg(self, type_str, msg):
        self.testMailBtn.setEnabled(True);
        self.testMailBtn.setText("发送测试邮件")
        if type_str == "success":
            InfoBar.success("成功", msg, position=InfoBarPosition.TOP_RIGHT, parent=self)
        else:
            InfoBar.error("失败", msg, position=InfoBarPosition.TOP_RIGHT, parent=self)


# ============================================
# 6. 主窗口 (MainWindow)
# ============================================
class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('二重螺旋 自动化')
        self.setWindowIcon(QIcon('assets/logo.png'))
        self.resize(950, 720)

        self.original_stdout = sys.stdout

        # 1. 控制台主页 (靠顶部)
        self.homeInterface = HomeInterface(self)
        self.homeInterface.setObjectName('homeInterface')
        self.addSubInterface(self.homeInterface, FIF.HOME, '控制台')

        # 2. 其他设置页面 (靠顶部)
        self.otherSettingInterface = OtherSettingInterface(self)
        self.otherSettingInterface.setObjectName('otherSettingInterface')
        self.addSubInterface(self.otherSettingInterface, FIF.SETTING, '其他设置')

        # 3. 实例化详细日志面板
        self.logInterface = LogInterface(self)
        self.logInterface.setObjectName('logInterface')

        # 同时打通通知单例的 log 数据流向
        from utils.tools import status_notifier
        status_notifier.log_callback = self.logInterface.append_log

        # 对系统标准的 print 劫持，加入详细日志面板
        self.emitting_stream = EmittingStream()
        self.emitting_stream.textWritten.connect(self.logInterface.append_log)
        sys.stdout = self.emitting_stream

        # 锁定日志面板在“设置”上方 (NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.logInterface, FIF.DOCUMENT, '详细日志', NavigationItemPosition.BOTTOM)

        # 4. 基础设置页面
        self.settingInterface = SettingInterface(self)
        self.settingInterface.setObjectName('settingInterface')
        self.addSubInterface(self.settingInterface, FIF.SETTING, '设置', NavigationItemPosition.BOTTOM)

    def closeEvent(self, event):
        title = '确认退出';
        content = '确定要关闭程序吗？'
        w = MessageBox(title, content, self)
        w.yesButton.setText('确定');
        w.cancelButton.setText('取消')
        if w.exec():
            sys.stdout = self.original_stdout  # 关闭前恢复系统标准流
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())