import sys
import os
import re
import shutil
import time
import threading
import concurrent.futures
import requests
import json
import random
import string
import psutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTextEdit, QLineEdit, QFileDialog, QMessageBox,
    QRadioButton, QButtonGroup, QStatusBar, QScrollArea, QFrame, QProgressBar,
    QGroupBox, QSplitter, QSizePolicy, QComboBox, QSpinBox, QColorDialog, QSlider,
    QTabBar
)
from PyQt6.QtGui import (
    QFont, QPalette, QColor, QTextCursor, QIcon, QPixmap, 
    QLinearGradient, QPainter, QBrush, QPen, QPainterPath, QMovie
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve, 
    QParallelAnimationGroup, QSequentialAnimationGroup, QPoint, QRect, QRectF, pyqtProperty
)

################## Global Constants #######################
ANTICHEAT_KEYWORDS = [
    "Anticheat", "Godmode", "Noclip", "Eulen", "Detection", "Shield", 
    "Fiveguard", "deltax", "waveshield", "spaceshield", "mixas", 
    "protected", "cheater", "cheat", "banNoclip", "Detects", 
    "blacklisted", "CHEATER BANNED:", "core_shield", "freecam"
]
FOLDERS_TO_IGNORE = ["monitor", "easyadmin"]
EXTENSIONS_TO_SEARCH = [".lua", ".html", ".js", ".json"]
DESKTOP_PATH = os.path.expanduser("~/Desktop")
FEMDUMPER_FOLDER = os.path.join(DESKTOP_PATH, "FemDumper")
TRIGGER_PATH = "None"

# Create output folder
if not os.path.exists(FEMDUMPER_FOLDER):
    os.makedirs(FEMDUMPER_FOLDER)

# Define color themes
THEMES = {
    "Midnight Purple": {
        "base": "#1e0a2a",
        "highlight": "#9b59b6",
        "accent": "#8e44ad",
        "text": "#ecf0f1",
        "button": "#8e44ad",
        "button_hover": "#9b59b6"
    },
    "Cyber Neon": {
        "base": "#0a0a1a",
        "highlight": "#00ffea",
        "accent": "#0078d7",
        "text": "#ffffff",
        "button": "#0078d7",
        "button_hover": "#00aaff"
    },
    "Lava Red": {
        "base": "#1a0a0a",
        "highlight": "#ff3300",
        "accent": "#e62e2e",
        "text": "#f5f5f5",
        "button": "#e62e2e",
        "button_hover": "#ff3300"
    },
    "Emerald Green": {
        "base": "#0a1a0a",
        "highlight": "#2ecc71",
        "accent": "#27ae60",
        "text": "#ecf0f1",
        "button": "#27ae60",
        "button_hover": "#2ecc71"
    },
    "Ocean Blue": {
        "base": "#0a0f1a",
        "highlight": "#3498db",
        "accent": "#2980b9",
        "text": "#ecf0f1",
        "button": "#2980b9",
        "button_hover": "#3498db"
    }
}

################## Worker Threads #########################
class TriggerScanner(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, path, keyword=""):
        super().__init__()
        self.path = path
        self.keyword = keyword.lower()

    def run(self):
        try:
            trigger_events = []
            total_files = sum([len(files) for _, _, files in os.walk(self.path)])
            processed_files = 0
            
            for root, dirs, files in os.walk(self.path):
                for filename in files:
                    if filename.endswith(".lua"):
                        file_path = os.path.join(root, filename)
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    if re.search(r"\b(TriggerServerEvent|TriggerEvent)\b", line):
                                        if not self.keyword or self.keyword in line.lower():
                                            trigger_events.append((folder_name, line_number, line.strip()))
                        except Exception as e:
                            continue
                    
                    processed_files += 1
                    self.progress.emit(processed_files, total_files)
            
            self.finished.emit(trigger_events)
        except Exception as e:
            self.error.emit(str(e))

class WebhookScanner(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.webhook_pattern = re.compile(r"https://discord\.com/api/webhooks/\w+/\w+")

    def is_webhook_valid(self, url):
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def run(self):
        try:
            webhook_urls = []
            total_files = sum([len(files) for _, _, files in os.walk(self.path)])
            processed_files = 0
            
            for root, dirs, files in os.walk(self.path):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    if os.path.isfile(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8", errors="ignore") as file:
                                content = file.read()
                                matches = self.webhook_pattern.findall(content)
                                for match in matches:
                                    if self.is_webhook_valid(match):
                                        webhook_urls.append((full_path, match))
                        except Exception:
                            continue
                    
                    processed_files += 1
                    self.progress.emit(processed_files, total_files)
            
            self.finished.emit(webhook_urls)
        except Exception as e:
            self.error.emit(str(e))

class AnticheatScanner(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            found_entries = []
            total_files = sum([len(files) for _, _, files in os.walk(self.path)])
            processed_files = 0
            
            for root, dirs, files in os.walk(self.path):
                for folder in FOLDERS_TO_IGNORE:
                    if folder in dirs:
                        dirs.remove(folder)
                
                for filename in files:
                    if any(filename.endswith(ext) for ext in EXTENSIONS_TO_SEARCH):
                        file_path = os.path.join(root, filename)
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    for keyword in ANTICHEAT_KEYWORDS:
                                        if keyword in line:
                                            found_entries.append((folder_name, line_number, line.strip()))
                        except Exception:
                            continue
                    
                    processed_files += 1
                    self.progress.emit(processed_files, total_files)
            
            self.finished.emit(found_entries)
        except Exception as e:
            self.error.emit(str(e))

class KnownAnticheatScanner(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            ac_detections = []
            ac_files = {
                "shared_fg-obfuscated.lua": "FiveGuard",
                "fini_events.lua": "FiniAC",
                "c-bypass.lua": "Reaper-AC",
                "waveshield.lua": "WaveShield"
            }
            
            for file_to_check, detection_name in ac_files.items():
                for root, dirs, files in os.walk(self.path):
                    for filename in files:
                        if filename == file_to_check:
                            folder_name = os.path.basename(root)
                            ac_detections.append(f"{detection_name} detected in {folder_name}")
            
            self.finished.emit(ac_detections)
        except Exception as e:
            self.error.emit(str(e))

class VariableScanner(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            variables_list = []
            total_files = sum([len(files) for _, _, files in os.walk(self.path)])
            processed_files = 0
            
            for root, dirs, files in os.walk(self.path):
                for filename in files:
                    if filename.endswith(".lua"):
                        file_path = os.path.join(root, filename)
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    if re.search(r'\bvar_\w+\b', line):
                                        variables_list.append((folder_name, line_number, line.strip()))
                        except Exception:
                            continue
                    
                    processed_files += 1
                    self.progress.emit(processed_files, total_files)
            
            self.finished.emit(variables_list)
        except Exception as e:
            self.error.emit(str(e))

################## Gradient Button ########################
class ShinyButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._animation = QPropertyAnimation(self, b"color_offset")
        self._animation.setDuration(1500)
        self._animation.setLoopCount(-1)
        self._animation.setStartValue(0)
        self._animation.setEndValue(100)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._color_offset = 0
        self.hover_animation = QPropertyAnimation(self, b"size")
        self.hover_animation.setDuration(200)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
    def get_color_offset(self):
        if not hasattr(self, '_color_offset'):
            self._color_offset = 0
        return self._color_offset

        
    def set_color_offset(self, value):
        self._color_offset = value
        self.update()
        
    color_offset = pyqtProperty(int, get_color_offset, set_color_offset)
    
    def enterEvent(self, event):
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.size())
        self.hover_animation.setEndValue(QSize(self.width() + 10, self.height()))
        self.hover_animation.start()
        if not self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.size())
        self.hover_animation.setEndValue(QSize(self.width() - 10, self.height()))
        self.hover_animation.start()
        super().leaveEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw button background with gradient
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        theme = self.parent().theme if hasattr(self.parent(), 'theme') else THEMES["Midnight Purple"]
        
        offset = self._color_offset / 100.0
        gradient.setColorAt(max(0, offset - 0.3), QColor(theme["button"]))
        gradient.setColorAt(offset, QColor(theme["highlight"]).lighter(150))
        gradient.setColorAt(min(1, offset + 0.3), QColor(theme["button"]))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Rounded rectangle
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        painter.drawPath(path)
        
        # Draw text
        painter.setPen(QColor(theme["text"]))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

################## Animated Tab Bar #######################
class AnimatedTabBar(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setMovable(True)
        self.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)
        
    def tabInserted(self, index):
        super().tabInserted(index)
        self.animate_tab(index)
        
    def animate_tab(self, index):
        tab = self.tabBar().tabButton(index, QTabBar.ButtonPosition.LeftSide)
        if not tab:
            tab = self.tabBar().tabButton(index, QTabBar.ButtonPosition.RightSide)
        if tab:
            animation = QPropertyAnimation(tab, b"geometry")
            animation.setDuration(300)
            animation.setEasingCurve(QEasingCurve.Type.OutBack)
            original_geometry = tab.geometry()
            animation.setStartValue(QRect(original_geometry.x(), original_geometry.y() + 20, 
                                          original_geometry.width(), original_geometry.height()))
            animation.setEndValue(original_geometry)
            animation.start()

################## Main Application #######################
class FemDumperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FemDumper - Made by FemScripts.de")
        self.setGeometry(100, 100, 1200, 800)
        self.current_theme = "Midnight Purple"
        
        # Set initial theme
        self.apply_theme(self.current_theme)
        
        # Set app icon
        self.setWindowIcon(self.create_icon())
        
        # Initialize UI
        self.init_ui()
        
        # Set initial path
        self.path_label.setText(f"<b>Current Path:</b> {TRIGGER_PATH}")
        
        # Connect global signals
        self.trigger_scanner = None
        self.webhook_scanner = None
        self.anticheat_scanner = None
        self.variable_scanner = None
        self.known_anticheat_scanner = None

    def create_icon(self):
        # Create a simple programmatic icon
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        return QIcon(pixmap)
    
    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        theme = THEMES[theme_name]
        
        # Set application style
        style = f"""
            QMainWindow {{
                background-color: {theme["base"]};
                color: {theme["text"]};
            }}
            QTabWidget::pane {{
                border: 1px solid {theme["accent"]};
                background: {theme["base"]};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {theme["base"]};
                color: {theme["text"]};
                padding: 12px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border: 1px solid {theme["accent"]};
                margin-right: 2px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {theme["accent"]};
                color: {theme["text"]};
                border-bottom: 3px solid {theme["highlight"]};
            }}
            QTextEdit, QLineEdit, QComboBox, QSpinBox {{
                background-color: {theme["base"]};
                color: {theme["text"]};
                border: 1px solid {theme["accent"]};
                border-radius: 6px;
                padding: 8px;
                selection-background-color: {theme["highlight"]};
                font-size: 12px;
            }}
            QLabel {{
                color: {theme["text"]};
            }}
            QProgressBar {{
                border: 1px solid {theme["accent"]};
                border-radius: 6px;
                text-align: center;
                background: {theme["base"]};
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {theme["highlight"]};
                border-radius: 5px;
            }}
            QGroupBox {{
                border: 1px solid {theme["accent"]};
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 20px;
                font-weight: bold;
                color: {theme["text"]};
                background: {theme["base"]};
                font-size: 14px;
            }}
            QScrollArea {{
                background: {theme["base"]};
                border: none;
            }}
            QRadioButton {{
                color: {theme["text"]};
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid {theme["accent"]};
            }}
            QRadioButton::indicator:checked {{
                background-color: {theme["highlight"]};
                border: 2px solid {theme["highlight"]};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                border: 1px solid {theme["accent"]};
                background: {theme["base"]};
            }}
        """
        self.setStyleSheet(style)

    def init_ui(self):
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Header with logo and title
        header_layout = QHBoxLayout()
        
        # Animated title
        title = QLabel("FemDumper")
        title.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        title.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 #ff007f, stop:0.5 #ff00ff, stop:1 #007fff);
        """)
        
        # Animation for title
        title_animation = QPropertyAnimation(title, b"pos")
        title_animation.setDuration(3000)
        title_animation.setLoopCount(-1)
        title_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        title_animation.setStartValue(QPoint(0, 0))
        title_animation.setKeyValueAt(0.5, QPoint(20, 0))
        title_animation.setEndValue(QPoint(0, 0))
        title_animation.start()
        
        header_layout.addWidget(title)
        
        # Spacer
        header_layout.addStretch()
        
        # Path display
        self.path_label = QLabel()
        self.path_label.setFont(QFont("Arial", 10))
        header_layout.addWidget(self.path_label)
        
        main_layout.addLayout(header_layout)
        
        # Create animated tab widget
        self.tab_widget = AnimatedTabBar()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_home_tab()
        self.create_triggers_tab()
        self.create_webhooks_tab()
        self.create_anticheat_tab()
        self.create_variables_tab()
        self.create_builder_tab()
        self.create_settings_tab()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(100)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()
        
        # Add glowing effect animation
        self.glow_animation = QPropertyAnimation(self, b"windowOpacity")
        self.glow_animation.setDuration(2000)
        self.glow_animation.setLoopCount(-1)
        self.glow_animation.setStartValue(1.0)
        self.glow_animation.setKeyValueAt(0.5, 0.95)
        self.glow_animation.setEndValue(1.0)
        self.glow_animation.start()
        
        self.setCentralWidget(main_widget)

    def create_home_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Animated welcome message
        welcome = QLabel("Complete FiveM Server Dump Analysis Tool")
        welcome.setFont(QFont("Arial", 16))
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Animation for welcome message
        welcome_animation = QPropertyAnimation(welcome, b"geometry")
        welcome_animation.setDuration(2000)
        welcome_animation.setLoopCount(-1)
        welcome_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        orig_geo = welcome.geometry()
        welcome_animation.setStartValue(QRect(orig_geo.x(), orig_geo.y(), orig_geo.width(), orig_geo.height()))
        welcome_animation.setKeyValueAt(0.5, QRect(orig_geo.x(), orig_geo.y() + 10, orig_geo.width(), orig_geo.height()))
        welcome_animation.setEndValue(QRect(orig_geo.x(), orig_geo.y(), orig_geo.width(), orig_geo.height()))
        welcome_animation.start()
        
        layout.addWidget(welcome)
        
        # Description
        desc = QLabel(
            "FemDumper helps you analyze FiveM server dumps by scanning for:\n"
            "- Trigger events\n- Discord webhooks\n- Anti-cheat systems\n- Special variables\n\n"
            "All results are saved to your desktop in the FemDumper folder."
        )
        desc.setFont(QFont("Arial", 10))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        # Quick actions
        group = QGroupBox("Quick Actions")
        group_layout = QVBoxLayout(group)
        
        btn_layout = QHBoxLayout()
        
        path_btn = ShinyButton("Set Path")
        path_btn.clicked.connect(self.browse_directory)
        
        scan_btn = ShinyButton("Run All Scans")
        scan_btn.clicked.connect(self.run_all_scans)
        
        btn_layout.addWidget(path_btn)
        btn_layout.addWidget(scan_btn)
        
        group_layout.addLayout(btn_layout)
        layout.addWidget(group)
        
        # Animated GIF
        gif_label = QLabel()
        movie = QMovie(":dna.gif")  # Placeholder for actual animation
        gif_label.setMovie(movie)
        movie.start()
        gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(gif_label)
        
        # Footer
        footer = QLabel("© 2023 FemScripts.de")
        footer.setFont(QFont("Arial", 8))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Home")

    def create_triggers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Trigger Event Scanner")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Search controls
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for keywords in triggers...")
        
        search_btn = ShinyButton("Search")
        search_btn.clicked.connect(self.search_triggers)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_triggers_btn = ShinyButton("Scan Triggers")
        self.scan_triggers_btn.clicked.connect(self.find_triggers)
        
        self.export_triggers_btn = ShinyButton("Export Results")
        self.export_triggers_btn.clicked.connect(
            lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "trigger_events.txt"))
        )
        
        controls_layout.addWidget(self.scan_triggers_btn)
        controls_layout.addWidget(self.export_triggers_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Results area
        results_frame = QFrame()
        results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        
        self.trigger_text = QTextEdit()
        self.trigger_text.setReadOnly(True)
        self.trigger_text.setFont(QFont("Consolas", 10))
        self.trigger_text.setPlaceholderText("Trigger results will appear here...")
        
        results_layout.addWidget(self.trigger_text)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Triggers")

    def create_webhooks_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Webhook Scanner")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_webhooks_btn = ShinyButton("Scan Webhooks")
        self.scan_webhooks_btn.clicked.connect(self.find_webhooks)
        
        self.delete_webhooks_btn = ShinyButton("Delete Webhooks")
        self.delete_webhooks_btn.clicked.connect(self.delete_webhooks)
        
        self.webhook_info_btn = ShinyButton("Get Webhook Info")
        self.webhook_info_btn.clicked.connect(self.show_webhook_info)
        
        self.export_webhooks_btn = ShinyButton("Export Results")
        self.export_webhooks_btn.clicked.connect(
            lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt"))
        )
        
        controls_layout.addWidget(self.scan_webhooks_btn)
        controls_layout.addWidget(self.delete_webhooks_btn)
        controls_layout.addWidget(self.webhook_info_btn)
        controls_layout.addWidget(self.export_webhooks_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Results area
        results_frame = QFrame()
        results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        
        self.webhook_text = QTextEdit()
        self.webhook_text.setReadOnly(True)
        self.webhook_text.setFont(QFont("Consolas", 10))
        self.webhook_text.setPlaceholderText("Webhook results will appear here...")
        
        results_layout.addWidget(self.webhook_text)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Webhooks")

    def create_anticheat_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Anti-Cheat Detection")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_keywords_btn = ShinyButton("Scan Keywords")
        self.scan_keywords_btn.clicked.connect(self.find_anticheat_keywords)
        
        self.scan_known_ac_btn = ShinyButton("Scan Known ACs")
        self.scan_known_ac_btn.clicked.connect(self.find_known_anticheats)
        
        self.export_ac_btn = ShinyButton("Export Results")
        self.export_ac_btn.clicked.connect(
            lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "anticheat_results.txt"))
        )
        
        controls_layout.addWidget(self.scan_keywords_btn)
        controls_layout.addWidget(self.scan_known_ac_btn)
        controls_layout.addWidget(self.export_ac_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Keywords info
        keywords_frame = QFrame()
        keywords_frame.setFrameShape(QFrame.Shape.StyledPanel)
        keywords_layout = QVBoxLayout(keywords_frame)
        
        keywords_label = QLabel("Active Anti-Cheat Keywords:")
        keywords_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        keywords_layout.addWidget(keywords_label)
        
        keywords_text = QLabel(", ".join(ANTICHEAT_KEYWORDS))
        keywords_text.setFont(QFont("Arial", 9))
        keywords_text.setWordWrap(True)
        keywords_layout.addWidget(keywords_text)
        
        layout.addWidget(keywords_frame)
        
        # Results area
        results_frame = QFrame()
        results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        
        self.anticheat_text = QTextEdit()
        self.anticheat_text.setReadOnly(True)
        self.anticheat_text.setFont(QFont("Consolas", 10))
        self.anticheat_text.setPlaceholderText("Anti-cheat results will appear here...")
        
        results_layout.addWidget(self.anticheat_text)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Anti-Cheat")

    def create_variables_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Variable Scanner")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_vars_btn = ShinyButton("Scan Variables")
        self.scan_vars_btn.clicked.connect(self.find_variables)
        
        self.export_vars_btn = ShinyButton("Export Results")
        self.export_vars_btn.clicked.connect(
            lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "variables.txt"))
        )
        
        controls_layout.addWidget(self.scan_vars_btn)
        controls_layout.addWidget(self.export_vars_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Results area
        results_frame = QFrame()
        results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        
        self.variable_text = QTextEdit()
        self.variable_text.setReadOnly(True)
        self.variable_text.setFont(QFont("Consolas", 10))
        self.variable_text.setPlaceholderText("Variable results will appear here...")
        
        results_layout.addWidget(self.variable_text)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Variables")

    def create_builder_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Trigger Event Builder")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Form
        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        
        # Event Type
        type_layout = QHBoxLayout()
        type_label = QLabel("Event Type:")
        type_label.setFixedWidth(100)
        
        self.type_group = QButtonGroup()
        self.server_radio = QRadioButton("Server Event")
        self.server_radio.setChecked(True)
        self.client_radio = QRadioButton("Client Event")
        
        self.type_group.addButton(self.server_radio)
        self.type_group.addButton(self.client_radio)
        
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.server_radio)
        type_layout.addWidget(self.client_radio)
        type_layout.addStretch()
        
        form_layout.addLayout(type_layout)
        
        # Event Name
        name_layout = QHBoxLayout()
        name_label = QLabel("Event Name:")
        name_label.setFixedWidth(100)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter event name...")
        
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input, 1)
        
        form_layout.addLayout(name_layout)
        
        # Parameters
        param_layout = QHBoxLayout()
        param_label = QLabel("Parameters:")
        param_label.setFixedWidth(100)
        
        self.param_input = QLineEdit()
        self.param_input.setPlaceholderText("param1, param2, param3...")
        
        param_layout.addWidget(param_label)
        param_layout.addWidget(self.param_input, 1)
        
        form_layout.addLayout(param_layout)
        
        # Loop Settings
        loop_layout = QHBoxLayout()
        loop_label = QLabel("Loop Type:")
        loop_label.setFixedWidth(100)
        
        self.loop_combo = QComboBox()
        self.loop_combo.addItems(["No Loop", "Infinite Loop", "Fixed Times"])
        
        self.loop_count = QSpinBox()
        self.loop_count.setRange(1, 1000)
        self.loop_count.setValue(5)
        self.loop_count.setEnabled(False)
        
        self.loop_combo.currentIndexChanged.connect(
            lambda: self.loop_count.setEnabled(self.loop_combo.currentText() == "Fixed Times")
        )
        
        loop_layout.addWidget(loop_label)
        loop_layout.addWidget(self.loop_combo)
        loop_layout.addWidget(QLabel("Count:"))
        loop_layout.addWidget(self.loop_count)
        loop_layout.addStretch()
        
        form_layout.addLayout(loop_layout)
        
        layout.addWidget(form_frame)
        
        # Code preview
        preview_label = QLabel("Generated Trigger Code:")
        layout.addWidget(preview_label)
        
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Consolas", 10))
        self.code_preview.setPlaceholderText("Generated code will appear here...")
        layout.addWidget(self.code_preview, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.generate_btn = ShinyButton("Generate Code")
        self.generate_btn.clicked.connect(self.generate_trigger_code)
        
        self.save_btn = ShinyButton("Save Code")
        self.save_btn.clicked.connect(self.save_trigger_code)
        
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        self.tab_widget.addTab(tab, "Builder")

    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Theme settings
        theme_group = QGroupBox("Color Theme")
        theme_layout = QVBoxLayout(theme_group)
        
        theme_control_layout = QHBoxLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.current_theme)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        
        theme_control_layout.addWidget(QLabel("Select Theme:"))
        theme_control_layout.addWidget(self.theme_combo)
        theme_control_layout.addStretch()
        
        theme_layout.addLayout(theme_control_layout)
        
        # Custom color button
        self.custom_color_btn = ShinyButton("Custom Colors")
        self.custom_color_btn.clicked.connect(self.custom_colors)
        theme_layout.addWidget(self.custom_color_btn)
        
        layout.addWidget(theme_group)
        
        # Path settings
        path_group = QGroupBox("Server Dump Path")
        path_layout = QVBoxLayout(path_group)
        
        path_control_layout = QHBoxLayout()
        
        self.path_input = QLineEdit()
        self.path_input.setText(TRIGGER_PATH)
        
        browse_btn = ShinyButton("Browse")
        browse_btn.clicked.connect(self.browse_directory)
        
        save_btn = ShinyButton("Save Path")
        save_btn.clicked.connect(self.save_path)
        
        path_control_layout.addWidget(self.path_input)
        path_control_layout.addWidget(browse_btn)
        path_control_layout.addWidget(save_btn)
        
        path_layout.addLayout(path_control_layout)
        layout.addWidget(path_group)
        
        # Animation settings
        anim_group = QGroupBox("Animation Effects")
        anim_layout = QVBoxLayout(anim_group)
        
        anim_control_layout = QHBoxLayout()
        anim_control_layout.addWidget(QLabel("Animation Intensity:"))
        
        self.anim_slider = QSlider(Qt.Orientation.Horizontal)
        self.anim_slider.setRange(0, 100)
        self.anim_slider.setValue(50)
        anim_control_layout.addWidget(self.anim_slider)
        
        anim_layout.addLayout(anim_control_layout)
        
        # Glow effect toggle
        self.glow_toggle = QRadioButton("Enable Glow Effects")
        self.glow_toggle.setChecked(True)
        anim_layout.addWidget(self.glow_toggle)
        
        layout.addWidget(anim_group)
        
        # Info
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)
        
        info_label = QLabel(
            "FemDumper v2.0\n"
            "Created by FemScripts.de\n\n"
            "Features:\n"
            "- Trigger event scanning\n- Webhook detection & deletion\n"
            "- Anti-cheat system detection\n- Variable scanning\n"
            "- Trigger code builder\n- Custom themes & animations"
        )
        info_label.setWordWrap(True)
        
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Settings")

    def browse_directory(self):
        global TRIGGER_PATH
        path = QFileDialog.getExistingDirectory(
            self, 
            "Select Server Dump Folder", 
            DESKTOP_PATH
        )
        
        if path:
            TRIGGER_PATH = path
            self.path_label.setText(f"<b>Current Path:</b> {TRIGGER_PATH}")
            self.path_input.setText(TRIGGER_PATH)
            self.status_bar.showMessage("Path set successfully")
            
            # Animate path label
            path_animation = QPropertyAnimation(self.path_label, b"geometry")
            path_animation.setDuration(500)
            path_animation.setEasingCurve(QEasingCurve.Type.OutBack)
            orig_geo = self.path_label.geometry()
            path_animation.setStartValue(QRect(orig_geo.x(), orig_geo.y() + 20, orig_geo.width(), orig_geo.height()))
            path_animation.setEndValue(orig_geo)
            path_animation.start()

    def save_path(self):
        global TRIGGER_PATH
        TRIGGER_PATH = self.path_input.text()
        self.path_label.setText(f"<b>Current Path:</b> {TRIGGER_PATH}")
        self.status_bar.showMessage("Path saved successfully")

    def change_theme(self, theme_name):
        self.apply_theme(theme_name)
        self.status_bar.showMessage(f"Theme changed to {theme_name}")

    def custom_colors(self):
        color = QColorDialog.getColor()
        if color.isValid():
            # Create a new theme based on the selected color
            base_color = color.darker(150)
            highlight_color = color.lighter(130)
            accent_color = color
            
            theme_name = f"Custom: {color.name()}"
            THEMES[theme_name] = {
                "base": base_color.name(),
                "highlight": highlight_color.name(),
                "accent": accent_color.name(),
                "text": "#ffffff",
                "button": accent_color.name(),
                "button_hover": highlight_color.name()
            }
            
            self.theme_combo.addItem(theme_name)
            self.theme_combo.setCurrentText(theme_name)
            self.apply_theme(theme_name)

    def validate_path(self):
        if TRIGGER_PATH == "None" or not os.path.exists(TRIGGER_PATH):
            QMessageBox.critical(
                self, 
                "Invalid Path", 
                "Please set a valid path first!"
            )
            return False
        return True

    def run_all_scans(self):
        if not self.validate_path():
            return
            
        self.find_triggers()
        self.find_webhooks()
        self.find_anticheat_keywords()
        self.find_known_anticheats()
        self.find_variables()
        
        self.status_bar.showMessage("All scans started...")

    def find_triggers(self):
        if not self.validate_path():
            return
            
        # Disable button during scan
        self.scan_triggers_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning for trigger events...")
        self.progress_bar.show()
        
        # Clear previous results
        self.trigger_text.clear()
        
        # Get search keyword
        keyword = self.search_input.text().strip()
        
        # Create and start scanner thread
        self.trigger_scanner = TriggerScanner(TRIGGER_PATH, keyword)
        self.trigger_scanner.progress.connect(self.update_progress)
        self.trigger_scanner.finished.connect(self.on_triggers_found)
        self.trigger_scanner.error.connect(self.on_scan_error)
        self.trigger_scanner.finished.connect(
            lambda: self.scan_triggers_btn.setEnabled(True)
        )
        self.trigger_scanner.start()

    def search_triggers(self):
        if not hasattr(self, 'trigger_results') or not self.trigger_results:
            QMessageBox.warning(self, "No Data", "Please scan for triggers first!")
            return
            
        keyword = self.search_input.text().strip().lower()
        if not keyword:
            # Show all results if no keyword
            self.trigger_text.setPlainText("\n".join(
                f"[{folder}] Line {line}: {content}"
                for folder, line, content in self.trigger_results
            ))
            return
            
        # Filter results by keyword
        filtered = [
            (folder, line, content)
            for folder, line, content in self.trigger_results
            if keyword in content.lower()
        ]
        
        if not filtered:
            self.trigger_text.setPlainText(f"No trigger events found containing '{keyword}'")
            return
            
        self.trigger_text.setPlainText("\n".join(
            f"[{folder}] Line {line}: {content}"
            for folder, line, content in filtered
        ))
        self.status_bar.showMessage(f"Found {len(filtered)} triggers containing '{keyword}'")

    def on_triggers_found(self, results):
        self.progress_bar.hide()
        self.trigger_results = results
        
        if not results:
            self.trigger_text.setPlainText("No trigger events found.")
            self.status_bar.showMessage("Trigger scan completed: 0 events found")
            return
            
        self.status_bar.showMessage(
            f"Trigger scan completed: {len(results)} events found"
        )
        
        # Display first 100 results
        self.trigger_text.setPlainText("\n".join(
            f"[{folder}] Line {line}: {content}"
            for folder, line, content in results[:100]
        ))
        
        # Save to file
        output_file = os.path.join(FEMDUMPER_FOLDER, "trigger_events.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            for folder, line, content in results:
                f.write(f"\n{'='*25} [{folder} - Line {line}] {'='*25}\n")
                f.write(f"{content}\n")

    def find_webhooks(self):
        if not self.validate_path():
            return
            
        # Disable button during scan
        self.scan_webhooks_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning for Discord webhooks...")
        self.progress_bar.show()
        
        # Clear previous results
        self.webhook_text.clear()
        
        # Create and start scanner thread
        self.webhook_scanner = WebhookScanner(TRIGGER_PATH)
        self.webhook_scanner.progress.connect(self.update_progress)
        self.webhook_scanner.finished.connect(self.on_webhooks_found)
        self.webhook_scanner.error.connect(self.on_scan_error)
        self.webhook_scanner.finished.connect(
            lambda: self.scan_webhooks_btn.setEnabled(True)
        )
        self.webhook_scanner.start()

    def on_webhooks_found(self, results):
        self.progress_bar.hide()
        
        if not results:
            self.webhook_text.setPlainText("No valid Discord webhooks found.")
            self.status_bar.showMessage("Webhook scan completed: 0 webhooks found")
            return
            
        self.status_bar.showMessage(
            f"Webhook scan completed: {len(results)} webhooks found"
        )
        
        # Display first 50 results
        self.webhook_text.setPlainText("\n\n".join(
            f"File: {path}\nWebhook: {url}"
            for path, url in results[:50]
        ))
        
        # Save to file
        output_file = os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"File Path{' ' * 55}| Webhook URL\n")
            f.write(f"{'-'*80}\n")
            for path, url in results:
                f.write(f"{path:<60} | {url}\n")

    def delete_webhooks(self):
        if not QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete all found webhooks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            return
            
        self.status_bar.showMessage("Deleting webhooks...")
        
        webhook_file = os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt")
        if not os.path.exists(webhook_file):
            QMessageBox.warning(self, "File Not Found", "Webhook file does not exist!")
            return
            
        try:
            with open(webhook_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                webhooks = []
                for line in lines[2:]:  # Skip header
                    if "|" in line:
                        webhooks.append(line.split("|")[1].strip())
            
            for url in webhooks:
                try:
                    response = requests.delete(url, timeout=5)
                    if response.status_code == 204:
                        self.status_bar.showMessage(f"Deleted: {url}")
                except requests.RequestException as e:
                    self.status_bar.showMessage(f"Error deleting: {str(e)}")
            
            self.status_bar.showMessage("Webhook deletion completed!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete webhooks: {str(e)}")

    def show_webhook_info(self):
        webhook_file = os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt")
        if not os.path.exists(webhook_file):
            QMessageBox.warning(self, "File Not Found", "Webhook file does not exist!")
            return
            
        try:
            with open(webhook_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                webhooks = []
                for line in lines[2:]:
                    if "|" in line:
                        webhooks.append(line.split("|")[1].strip())
            
            # Create info window
            info_window = QTextEdit()
            info_window.setWindowTitle("Webhook Information")
            info_window.setGeometry(100, 100, 600, 400)
            info_window.setReadOnly(True)
            info_window.setFont(QFont("Consolas", 10))
            
            for url in webhooks:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        info_window.append(f"URL: {url}\n")
                        info_window.append(json.dumps(data, indent=4))
                        info_window.append("\n" + "-"*80 + "\n")
                except requests.RequestException as e:
                    info_window.append(f"Error for {url}: {str(e)}\n\n")
            
            info_window.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to get webhook info: {str(e)}")

    def find_anticheat_keywords(self):
        if not self.validate_path():
            return
            
        # Disable button during scan
        self.scan_keywords_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning for anti-cheat keywords...")
        self.progress_bar.show()
        
        # Clear previous results
        self.anticheat_text.clear()
        
        # Create and start scanner thread
        self.anticheat_scanner = AnticheatScanner(TRIGGER_PATH)
        self.anticheat_scanner.progress.connect(self.update_progress)
        self.anticheat_scanner.finished.connect(self.on_anticheat_found)
        self.anticheat_scanner.error.connect(self.on_scan_error)
        self.anticheat_scanner.finished.connect(
            lambda: self.scan_keywords_btn.setEnabled(True)
        )
        self.anticheat_scanner.start()

    def on_anticheat_found(self, results):
        self.progress_bar.hide()
        
        if not results:
            self.anticheat_text.setPlainText("No anti-cheat keywords found.")
            self.status_bar.showMessage("Anti-cheat scan completed: 0 keywords found")
            return
            
        self.status_bar.showMessage(
            f"Anti-cheat scan completed: {len(results)} keywords found"
        )
        
        # Display first 100 results
        self.anticheat_text.setPlainText("\n".join(
            f"[{folder}] Line {line}: {content}"
            for folder, line, content in results[:100]
        ))
        
        # Save to file
        output_file = os.path.join(FEMDUMPER_FOLDER, "anticheat_keywords.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            for folder, line, content in results:
                f.write(f"[{folder}] - [Line {line}] {content}\n")

    def find_known_anticheats(self):
        if not self.validate_path():
            return
            
        # Disable button during scan
        self.scan_known_ac_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning for known anti-cheats...")
        
        # Create and start scanner thread
        self.known_anticheat_scanner = KnownAnticheatScanner(TRIGGER_PATH)
        self.known_anticheat_scanner.finished.connect(self.on_known_anticheats_found)
        self.known_anticheat_scanner.error.connect(self.on_scan_error)
        self.known_anticheat_scanner.finished.connect(
            lambda: self.scan_known_ac_btn.setEnabled(True)
        )
        self.known_anticheat_scanner.start()

    def on_known_anticheats_found(self, results):
        if not results:
            # Append to existing results
            self.anticheat_text.append("\nNo known anti-cheats detected.")
            self.status_bar.showMessage("Known AC scan completed: 0 detections")
            return
            
        # Append to existing results
        self.anticheat_text.append("\n" + "\n".join(results))
        self.status_bar.showMessage(
            f"Known AC scan completed: {len(results)} detections"
        )
        
        # Save to file
        output_file = os.path.join(FEMDUMPER_FOLDER, "known_anticheats.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            for detection in results:
                f.write(f"{detection}\n")

    def find_variables(self):
        if not self.validate_path():
            return
            
        # Disable button during scan
        self.scan_vars_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning for variables...")
        self.progress_bar.show()
        
        # Clear previous results
        self.variable_text.clear()
        
        # Create and start scanner thread
        self.variable_scanner = VariableScanner(TRIGGER_PATH)
        self.variable_scanner.progress.connect(self.update_progress)
        self.variable_scanner.finished.connect(self.on_variables_found)
        self.variable_scanner.error.connect(self.on_scan_error)
        self.variable_scanner.finished.connect(
            lambda: self.scan_vars_btn.setEnabled(True)
        )
        self.variable_scanner.start()

    def on_variables_found(self, results):
        self.progress_bar.hide()
        
        if not results:
            self.variable_text.setPlainText("No special variables found.")
            self.status_bar.showMessage("Variable scan completed: 0 variables found")
            return
            
        self.status_bar.showMessage(
            f"Variable scan completed: {len(results)} variables found"
        )
        
        # Display first 100 results
        self.variable_text.setPlainText("\n".join(
            f"[{folder}] Line {line}: {content}"
            for folder, line, content in results[:100]
        ))
        
        # Save to file
        output_file = os.path.join(FEMDUMPER_FOLDER, "variables.txt")
        with open(output_file, "a", encoding="utf-8") as f:
            f.write("\nVariables:\n")
            for folder, line, content in results:
                f.write(f"[{folder}] - [Line {line}] {content}\n")

    def generate_trigger_code(self):
        event_type = "server" if self.server_radio.isChecked() else "client"
        event_name = self.name_input.text().strip()
        params = [p.strip() for p in self.param_input.text().split(",") if p.strip()]
        loop_type = self.loop_combo.currentText()
        loop_count = self.loop_count.value()
        
        if not event_name:
            QMessageBox.warning(self, "Missing Information", "Please enter an event name!")
            return
            
        # Generate code
        param_string = ", ".join([f'"{p}"' for p in params])
        
        if event_type == "server":
            code = f"TriggerServerEvent('{event_name}'"
        else:
            code = f"TriggerEvent('{event_name}'"
        
        if param_string:
            code += f", {param_string}"
        
        code += ")"
        
        # Add loop if needed
        if loop_type == "Infinite Loop":
            code = f"""while true do
    {code}
    Citizen.Wait(0)
end"""
        elif loop_type == "Fixed Times":
            code = f"""for i = 1, {loop_count} do
    {code}
    Citizen.Wait(0)
end"""
        
        # Display code
        self.code_preview.setPlainText(code)

    def save_trigger_code(self):
        code = self.code_preview.toPlainText()
        if not code or "Generated code" in code:
            QMessageBox.warning(self, "No Code", "No code to save!")
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Trigger Code",
            DESKTOP_PATH,
            "Lua Files (*.lua);;All Files (*)"
        )
        
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"-- Generated by FemDumper\n{code}")
                self.status_bar.showMessage("Trigger code saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save file: {str(e)}")

    def open_file(self, path):
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", "The requested file does not exist!")
            return
            
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                os.system(f"{opener} {path}")
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open file: {str(e)}")

    def update_progress(self, current, total):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)

    def on_scan_error(self, error):
        self.progress_bar.hide()
        QMessageBox.critical(self, "Scan Error", f"An error occurred: {error}")

    def closeEvent(self, event):
        if QMessageBox.question(
            self,
            "Exit FemDumper",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = FemDumperApp()
    window.show()
    
    sys.exit(app.exec())