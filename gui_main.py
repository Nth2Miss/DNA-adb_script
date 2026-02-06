import sys
import time
import importlib.util
import os
import types  # 用于模块操作
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QApplication
from PyQt6.QtGui import QFont

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
    ProgressBar
)


# ============================================
# 1. 核心：路径自动定位
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

# 导入工具 (确保 utils/tools.py 已包含 set_running_state/check_running)
try:
    import utils.tools  # 获取模块对象以便动态检查
    from utils.tools import ADBConnector, list_devices, set_running_state, StopScriptException
except ImportError as e:
    print(f"导入错误: {e}")
    ADBConnector = None


# ============================================
# 2. 日志流
# ============================================
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

    def flush(self):
        pass


# ============================================
# 3. 工作线程 (包含“魔法”中断补丁)
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

        # 1. 开启全局运行状态
        set_running_state(True)
        file_name = os.path.basename(self.script_path)
        print(f"--- 正在启动: {file_name} ---")

        # ===================================================
        # 【核心黑科技】劫持 time.sleep 实现立即停止
        # ===================================================
        original_sleep = time.sleep  # 保存原始 sleep

        def interruptible_sleep(seconds):
            """替代原版 sleep，支持中途打断"""
            end_time = time.time() + seconds
            while time.time() < end_time:
                # 检查 utils.tools 里的状态
                if hasattr(utils.tools, 'check_running'):
                    utils.tools.check_running()  # 如果停止则抛出异常

                # 每次只睡 0.1 秒，保证响应迅速
                left = end_time - time.time()
                original_sleep(min(0.1, max(0, left)))

        # 覆盖 time.sleep
        time.sleep = interruptible_sleep
        # ===================================================

        try:
            # 2. 动态加载脚本
            mod_name = f"script_{int(time.time())}"
            spec = importlib.util.spec_from_file_location(mod_name, self.script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module

            # 切换工作目录到项目根目录 (解决 templates 路径问题)
            os.chdir(PROJECT_ROOT)

            # 执行脚本代码
            spec.loader.exec_module(module)

            # 3. 运行入口函数
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
            # 过滤掉我们自己抛出的 StopScriptException
            if "StopScriptException" not in str(type(e)):
                print(f"❌ 运行出错: {e}\n{traceback.format_exc()}")
                self.error_signal.emit(str(e))
        finally:
            # ===============================================
            # 【恢复现场】还原 time.sleep
            # ===============================================
            time.sleep = original_sleep
            self.finished_signal.emit()

    def stop(self):
        # 关闭全局开关 -> interruptible_sleep 会捕获到并抛出异常
        set_running_state(False)


# ============================================
# 4. 主界面 (UI 优化版 + 修复顺序错误)
# ============================================
class HomeInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('homeInterface')
        self.worker = None
        self.original_stdout = sys.stdout

        # 使用字典存储路径
        self.script_map = {}

        self.init_ui()

        self.emitting_stream = EmittingStream()
        self.emitting_stream.textWritten.connect(self.on_log_received)
        sys.stdout = self.emitting_stream

        # 启动扫描
        self.refresh_devices()
        self.scan_scripts()

    def init_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        self.titleLabel = SubtitleLabel('二重螺旋 自动化控制台', self)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.vBoxLayout.addWidget(self.titleLabel)

        # --- 设备卡片 (优化间距) ---
        self.deviceCard = CardWidget(self)
        layout_d = QHBoxLayout(self.deviceCard)
        layout_d.setContentsMargins(16, 12, 16, 12)
        layout_d.setSpacing(10)

        self.deviceCombo = ComboBox(self)
        btn_d = PushButton("刷新设备", self)
        btn_d.setIcon(FIF.SYNC)
        btn_d.clicked.connect(self.refresh_devices)

        layout_d.addWidget(BodyLabel("设备", self))
        layout_d.addWidget(self.deviceCombo, 1)
        layout_d.addWidget(btn_d)

        self.vBoxLayout.addWidget(self.deviceCard)

        # --- 脚本卡片 (优化间距) ---
        self.scriptCard = CardWidget(self)
        layout_s = QHBoxLayout(self.scriptCard)
        layout_s.setContentsMargins(16, 12, 16, 12)
        layout_s.setSpacing(10)

        self.scriptCombo = ComboBox(self)
        btn_s = PushButton("刷新列表", self)
        btn_s.setIcon(FIF.FOLDER)
        btn_s.clicked.connect(self.scan_scripts)

        layout_s.addWidget(BodyLabel("脚本", self))
        layout_s.addWidget(self.scriptCombo, 1)
        layout_s.addWidget(btn_s)

        self.vBoxLayout.addWidget(self.scriptCard)

        # --- 按钮区域 ---
        self.btnLayout = QHBoxLayout()
        self.startBtn = PrimaryPushButton("开始运行", self)
        self.startBtn.setIcon(FIF.PLAY)
        self.startBtn.clicked.connect(self.start_script)

        self.stopBtn = PushButton("停止运行", self)
        self.stopBtn.setIcon(FIF.PAUSE)
        self.stopBtn.setEnabled(False)
        self.stopBtn.clicked.connect(self.stop_script)

        # 清空日志按钮
        self.clearBtn = PushButton("清空日志", self)
        self.clearBtn.setIcon(FIF.DELETE)

        self.btnLayout.addWidget(self.startBtn)
        self.btnLayout.addWidget(self.stopBtn)
        self.btnLayout.addWidget(self.clearBtn)
        self.vBoxLayout.addLayout(self.btnLayout)

        # --- 日志区域 ---
        self.progressBar = ProgressBar(self)
        self.progressBar.hide()
        self.vBoxLayout.addWidget(self.progressBar)

        self.logText = TextEdit(self)
        self.logText.setReadOnly(True)
        self.logText.setFixedHeight(300)
        self.vBoxLayout.addWidget(self.logText)

        # 必须等到 self.logText 创建后，再绑定信号
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

    def scan_scripts(self):
        """扫描 scripts 文件夹"""
        self.scriptCombo.clear()
        self.script_map = {}
        count = 0

        # 1. Main.py
        # main_p = os.path.join(PROJECT_ROOT, "main.py")
        # if os.path.exists(main_p):
        #     self.scriptCombo.addItem("main.py")
        #     self.script_map["main.py"] = main_p
        #     count += 1

        # 2. Scripts
        target_dir = None
        for name in ["scripts", "scrips"]:
            d = os.path.join(PROJECT_ROOT, name)
            if os.path.exists(d):
                target_dir = d
                break

        if target_dir:
            print(f"扫描脚本目录: {target_dir}")
            for f in os.listdir(target_dir):
                full_path = os.path.join(target_dir, f)
                if f.endswith(".py") and os.path.isfile(full_path):
                    self.scriptCombo.addItem(f)
                    self.script_map[f] = full_path
                    count += 1
                    print(f"  + 加载: {f}")
        else:
            print("警告: 未找到 scripts 文件夹")

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

        # 使用字典查路径，确保稳定
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
        self.startBtn.setEnabled(not running)
        self.stopBtn.setEnabled(running)
        self.deviceCombo.setEnabled(not running)
        self.scriptCombo.setEnabled(not running)
        self.clearBtn.setEnabled(True)
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


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('二重螺旋 自动化')
        self.resize(900, 700)
        self.homeInterface = HomeInterface(self)
        self.homeInterface.setObjectName('homeInterface')
        self.addSubInterface(self.homeInterface, FIF.HOME, '控制台')


if __name__ == '__main__':
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())