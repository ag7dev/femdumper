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
import subprocess
from functools import partial
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTextEdit, QLineEdit, QFileDialog, QMessageBox,
    QRadioButton, QButtonGroup, QStatusBar, QScrollArea, QFrame, QProgressBar,
    QGroupBox, QSplitter, QSizePolicy, QComboBox, QSpinBox, QListWidget,
    QListWidgetItem, QInputDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor, QIcon, QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize

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
SETTINGS_FILE = os.path.join(FEMDUMPER_FOLDER, "settings.json")
TRIGGER_PATH = "None"

# Create output folder
if not os.path.exists(FEMDUMPER_FOLDER):
    os.makedirs(FEMDUMPER_FOLDER)

def get_resource_name(file_path, base_path=None):
    """Return the resource folder for a given file.

    This walks up the directory tree starting from the file location and
    returns the first directory that contains either a ``fxmanifest.lua`` or
    ``__resource.lua``.  If none are found, the direct parent folder name of
    the file is returned. ``base_path`` is optional and only used to limit the
    search when provided.
    """

    current = os.path.dirname(file_path)
    while True:
        if os.path.exists(os.path.join(current, "fxmanifest.lua")) or \
           os.path.exists(os.path.join(current, "__resource.lua")):
            return os.path.basename(current)

        if base_path and os.path.abspath(current) == os.path.abspath(base_path):
            break

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    return os.path.basename(os.path.dirname(file_path))

################## Settings Management ####################
def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def load_settings():
    default_settings = {
        "trigger_path": "None",
        "ac_keywords": ANTICHEAT_KEYWORDS,
        "ignore_folders": FOLDERS_TO_IGNORE,
        "risky_triggers": []
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                loaded = json.load(f)
                
                # Update with loaded settings, keeping defaults for missing keys
                for key in default_settings:
                    if key in loaded:
                        default_settings[key] = loaded[key]
                return default_settings
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    return default_settings

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
                        resource = get_resource_name(file_path, self.path)
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    if re.search(r"\b(TriggerServerEvent|TriggerEvent)\b", line):
                                        if not self.keyword or self.keyword in line.lower():
                                            trigger_events.append((resource, file_path, line_number, line.strip()))
                        except Exception:
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

    def __init__(self, path, ac_keywords, ignore_folders):
        super().__init__()
        self.path = path
        self.ac_keywords = ac_keywords
        self.ignore_folders = ignore_folders

    def run(self):
        try:
            found_entries = []
            total_files = sum([len(files) for _, _, files in os.walk(self.path)])
            processed_files = 0
            
            for root, dirs, files in os.walk(self.path):
                # Ignore specified folders
                for folder in self.ignore_folders:
                    if folder in dirs:
                        dirs.remove(folder)
                
                for filename in files:
                    if any(filename.endswith(ext) for ext in EXTENSIONS_TO_SEARCH):
                        file_path = os.path.join(root, filename)
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    for keyword in self.ac_keywords:
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
                            ac_detections.append((folder_name, detection_name))
            
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

################## Main Application #######################
class FemDumperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FemDumper - Made by FemScripts.de")
        self.setGeometry(100, 100, 1200, 800)
        
        # Load settings
        self.settings = load_settings()
        TRIGGER_PATH = self.settings["trigger_path"]
        
        # Set app icon
        self.setWindowIcon(self.create_icon())
        
        # Set fixed dark theme
        self.setStyleSheet(self.get_style_sheet())
        
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

    def get_style_sheet(self):
        return """
            QMainWindow {
                background-color: #121212;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background: #1e1e1e;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #2a2a2a;
                color: #ddd;
                padding: 8px 15px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #444;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #3a3a3a;
                border-bottom: 2px solid #4a9;
            }
            QPushButton {
                background-color: #333;
                color: #eee;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QTextEdit, QLineEdit {
                background-color: #252525;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
                selection-background-color: #4a9;
            }
            QLabel {
                color: #ddd;
            }
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                background: #252525;
            }
            QProgressBar::chunk {
                background-color: #4a9;
                width: 10px;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #ddd;
                background: #1e1e1e;
            }
            QScrollArea {
                background: #1e1e1e;
                border: none;
            }
            QListWidget {
                background-color: #252525;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QSpinBox {
                background-color: #252525;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
        """

    def create_icon(self):
        # Create a simple programmatic icon
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        return QIcon(pixmap)

    def init_ui(self):
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header with logo and title
        header_layout = QHBoxLayout()
        
        # Title
        title = QLabel("FemDumper")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9;")
        header_layout.addWidget(title)
        
        # Spacer
        header_layout.addStretch()
        
        # Path display
        self.path_label = QLabel()
        self.path_label.setFont(QFont("Arial", 10))
        self.path_label.setStyleSheet("color: #aaa;")
        header_layout.addWidget(self.path_label)
        
        main_layout.addLayout(header_layout)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
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
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(100)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()
        
        self.setCentralWidget(main_widget)

    def create_home_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Welcome message
        welcome = QLabel("Complete FiveM Server Dump Analysis Tool")
        welcome.setFont(QFont("Arial", 16))
        welcome.setStyleSheet("color: #4a9;")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome)
        
        # Description
        desc = QLabel(
            "FemDumper helps you analyze FiveM server dumps by scanning for triggers, "
            "webhooks, anti-cheat systems, and variables. All results are saved to your desktop."
        )
        desc.setFont(QFont("Arial", 10))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        # Quick actions
        group = QGroupBox("Quick Actions")
        group_layout = QVBoxLayout(group)
        
        btn_layout = QHBoxLayout()
        
        path_btn = QPushButton("Set Path")
        path_btn.setFixedHeight(40)
        path_btn.clicked.connect(self.browse_directory)
        
        scan_btn = QPushButton("Run All Scans")
        scan_btn.setFixedHeight(40)
        scan_btn.clicked.connect(self.run_all_scans)
        
        btn_layout.addWidget(path_btn)
        btn_layout.addWidget(scan_btn)
        
        group_layout.addLayout(btn_layout)
        layout.addWidget(group)
        
        # Stats
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        stats = [
            "• Trigger Scanner: Finds TriggerServerEvent and TriggerEvent calls",
            "• Webhook Scanner: Locates valid Discord webhooks",
            "• Anti-Cheat Detection: Scans for known AC systems and keywords",
            "• Variable Scanner: Identifies special variables",
            "• Trigger Builder: Creates FiveM trigger code"
        ]
        
        for stat in stats:
            label = QLabel(stat)
            label.setFont(QFont("Arial", 9))
            stats_layout.addWidget(label)
        
        layout.addWidget(stats_group)
        
        # Footer
        footer = QLabel("© 2023 FemScripts.de")
        footer.setFont(QFont("Arial", 8))
        footer.setStyleSheet("color: #666;")
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
        title.setStyleSheet("color: #4a9;")
        layout.addWidget(title)
        
        # Search controls
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for keywords in triggers...")
        
        search_btn = QPushButton("Search")
        search_btn.setFixedHeight(35)
        search_btn.clicked.connect(self.search_triggers)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_triggers_btn = QPushButton("Scan Triggers")
        self.scan_triggers_btn.setFixedHeight(35)
        self.scan_triggers_btn.clicked.connect(self.find_triggers)
        
        self.export_triggers_btn = QPushButton("Export Results")
        self.export_triggers_btn.setFixedHeight(35)
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

        self.trigger_table = QTableWidget()
        self.trigger_table.setColumnCount(5)
        self.trigger_table.setHorizontalHeaderLabels([
            "Resource",
            "Trigger",
            "Status",
            "Risk Level",
            "Actions",
        ])
        header = self.trigger_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.trigger_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        results_layout.addWidget(self.trigger_table)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Triggers")

    def create_webhooks_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Webhook Scanner")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9;")
        layout.addWidget(title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_webhooks_btn = QPushButton("Scan Webhooks")
        self.scan_webhooks_btn.setFixedHeight(35)
        self.scan_webhooks_btn.clicked.connect(self.find_webhooks)
        
        self.delete_webhooks_btn = QPushButton("Delete Webhooks")
        self.delete_webhooks_btn.setFixedHeight(35)
        self.delete_webhooks_btn.clicked.connect(self.delete_webhooks)
        
        self.webhook_info_btn = QPushButton("Get Webhook Info")
        self.webhook_info_btn.setFixedHeight(35)
        self.webhook_info_btn.clicked.connect(self.show_webhook_info)
        
        self.export_webhooks_btn = QPushButton("Export Results")
        self.export_webhooks_btn.setFixedHeight(35)
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
        
        self.webhook_table = QTableWidget()
        self.webhook_table.setColumnCount(3)
        self.webhook_table.setHorizontalHeaderLabels([
            "File",
            "Webhook",
            "Actions",
        ])
        header = self.webhook_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.webhook_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        results_layout.addWidget(self.webhook_table)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Webhooks")

    def create_anticheat_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Anti-Cheat Detection")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9;")
        layout.addWidget(title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_keywords_btn = QPushButton("Scan Keywords")
        self.scan_keywords_btn.setFixedHeight(35)
        self.scan_keywords_btn.clicked.connect(self.find_anticheat_keywords)
        
        self.scan_known_ac_btn = QPushButton("Scan Known ACs")
        self.scan_known_ac_btn.setFixedHeight(35)
        self.scan_known_ac_btn.clicked.connect(self.find_known_anticheats)
        
        self.export_ac_btn = QPushButton("Export Results")
        self.export_ac_btn.setFixedHeight(35)
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
        
        keywords_text = QLabel(", ".join(self.settings["ac_keywords"]))
        keywords_text.setFont(QFont("Arial", 9))
        keywords_text.setWordWrap(True)
        keywords_layout.addWidget(keywords_text)
        
        layout.addWidget(keywords_frame)
        
        # Results area
        results_frame = QFrame()
        results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        
        self.anticheat_table = QTableWidget()
        self.anticheat_table.setColumnCount(3)
        self.anticheat_table.setHorizontalHeaderLabels([
            "Resource",
            "Line",
            "Content",
        ])
        header_ac = self.anticheat_table.horizontalHeader()
        header_ac.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_ac.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_ac.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.anticheat_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Known AC table
        self.known_ac_table = QTableWidget()
        self.known_ac_table.setColumnCount(2)
        self.known_ac_table.setHorizontalHeaderLabels([
            "Resource",
            "AC Name",
        ])
        header_known = self.known_ac_table.horizontalHeader()
        header_known.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_known.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.known_ac_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        results_layout.addWidget(self.anticheat_table)
        results_layout.addWidget(self.known_ac_table)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Anti-Cheat")

    def create_variables_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Variable Scanner")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9;")
        layout.addWidget(title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.scan_vars_btn = QPushButton("Scan Variables")
        self.scan_vars_btn.setFixedHeight(35)
        self.scan_vars_btn.clicked.connect(self.find_variables)
        
        self.export_vars_btn = QPushButton("Export Results")
        self.export_vars_btn.setFixedHeight(35)
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
        
        self.variable_table = QTableWidget()
        self.variable_table.setColumnCount(3)
        self.variable_table.setHorizontalHeaderLabels([
            "Resource",
            "Line",
            "Variable",
        ])
        header_var = self.variable_table.horizontalHeader()
        header_var.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_var.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_var.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.variable_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        results_layout.addWidget(self.variable_table)
        layout.addWidget(results_frame, 1)
        
        self.tab_widget.addTab(tab, "Variables")

    def create_builder_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title = QLabel("Trigger Event Builder")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9;")
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
        
        self.generate_btn = QPushButton("Generate Code")
        self.generate_btn.clicked.connect(self.generate_trigger_code)
        
        self.save_btn = QPushButton("Save Code")
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
        title.setStyleSheet("color: #4a9;")
        layout.addWidget(title)
        
        # Path settings
        path_group = QGroupBox("Server Dump Path")
        path_layout = QVBoxLayout(path_group)
        
        path_control_layout = QHBoxLayout()
        
        self.path_input = QLineEdit()
        self.path_input.setText(self.settings["trigger_path"])
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_directory)
        
        save_btn = QPushButton("Save Path")
        save_btn.clicked.connect(self.save_path)
        
        path_control_layout.addWidget(self.path_input)
        path_control_layout.addWidget(browse_btn)
        path_control_layout.addWidget(save_btn)
        
        path_layout.addLayout(path_control_layout)
        layout.addWidget(path_group)
        
        # AC Keywords settings
        ac_group = QGroupBox("Anti-Cheat Keywords")
        ac_layout = QVBoxLayout(ac_group)
        
        # Keywords list
        self.ac_list = QListWidget()
        self.ac_list.addItems(self.settings["ac_keywords"])
        ac_layout.addWidget(self.ac_list)
        
        # Keyword buttons
        ac_btn_layout = QHBoxLayout()
        
        self.add_keyword_btn = QPushButton("Add Keyword")
        self.add_keyword_btn.clicked.connect(self.add_keyword)
        
        self.edit_keyword_btn = QPushButton("Edit Keyword")
        self.edit_keyword_btn.clicked.connect(self.edit_keyword)
        
        self.remove_keyword_btn = QPushButton("Remove Keyword")
        self.remove_keyword_btn.clicked.connect(self.remove_keyword)
        
        ac_btn_layout.addWidget(self.add_keyword_btn)
        ac_btn_layout.addWidget(self.edit_keyword_btn)
        ac_btn_layout.addWidget(self.remove_keyword_btn)
        
        ac_layout.addLayout(ac_btn_layout)
        layout.addWidget(ac_group)
        
        # Ignore Folders settings
        folder_group = QGroupBox("Folders to Ignore")
        folder_layout = QVBoxLayout(folder_group)
        
        # Folders list
        self.folder_list = QListWidget()
        self.folder_list.addItems(self.settings["ignore_folders"])
        folder_layout.addWidget(self.folder_list)
        
        # Folder buttons
        folder_btn_layout = QHBoxLayout()
        
        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.clicked.connect(self.add_folder)
        
        self.edit_folder_btn = QPushButton("Edit Folder")
        self.edit_folder_btn.clicked.connect(self.edit_folder)
        
        self.remove_folder_btn = QPushButton("Remove Folder")
        self.remove_folder_btn.clicked.connect(self.remove_folder)
        
        folder_btn_layout.addWidget(self.add_folder_btn)
        folder_btn_layout.addWidget(self.edit_folder_btn)
        folder_btn_layout.addWidget(self.remove_folder_btn)
        
        folder_layout.addLayout(folder_btn_layout)
        layout.addWidget(folder_group)

        # Risky Triggers settings
        risky_group = QGroupBox("Risky Triggers")
        risky_layout = QVBoxLayout(risky_group)

        self.risky_list = QListWidget()
        self.risky_list.addItems(self.settings.get("risky_triggers", []))
        risky_layout.addWidget(self.risky_list)

        risky_btn_layout = QHBoxLayout()
        self.add_risky_btn = QPushButton("Add Trigger")
        self.add_risky_btn.clicked.connect(self.add_risky_trigger)
        self.remove_risky_btn = QPushButton("Remove Trigger")
        self.remove_risky_btn.clicked.connect(self.remove_risky_trigger)
        risky_btn_layout.addWidget(self.add_risky_btn)
        risky_btn_layout.addWidget(self.remove_risky_btn)
        risky_layout.addLayout(risky_btn_layout)

        layout.addWidget(risky_group)
        
        # Save settings button
        self.save_settings_btn = QPushButton("Save All Settings")
        self.save_settings_btn.clicked.connect(self.save_all_settings)
        layout.addWidget(self.save_settings_btn)
        
        # Info
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout(info_group)
        
        info_label = QLabel(
            "FemDumper v2.0\n"
            "Created by FemScripts.de\n\n"
            "Features:\n"
            "- Trigger event scanning\n- Webhook detection & deletion\n"
            "- Anti-cheat system detection\n- Variable scanning\n"
            "- Trigger code builder"
        )
        info_label.setWordWrap(True)
        
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Settings")
    
    def add_keyword(self):
        keyword, ok = QInputDialog.getText(
            self, "Add Keyword", "Enter anti-cheat keyword:"
        )
        if ok and keyword:
            self.settings["ac_keywords"].append(keyword)
            self.ac_list.addItem(keyword)
            self.status_bar.showMessage(f"Keyword '{keyword}' added")
    
    def edit_keyword(self):
        selected = self.ac_list.currentItem()
        if not selected:
            return
            
        old_keyword = selected.text()
        new_keyword, ok = QInputDialog.getText(
            self, "Edit Keyword", "Edit keyword:", text=old_keyword
        )
        if ok and new_keyword:
            idx = self.settings["ac_keywords"].index(old_keyword)
            self.settings["ac_keywords"][idx] = new_keyword
            selected.setText(new_keyword)
            self.status_bar.showMessage(f"Keyword updated to '{new_keyword}'")
    
    def remove_keyword(self):
        selected = self.ac_list.currentItem()
        if not selected:
            return
            
        keyword = selected.text()
        self.settings["ac_keywords"].remove(keyword)
        self.ac_list.takeItem(self.ac_list.row(selected))
        self.status_bar.showMessage(f"Keyword '{keyword}' removed")
    
    def add_folder(self):
        folder, ok = QInputDialog.getText(
            self, "Add Folder", "Enter folder name to ignore:"
        )
        if ok and folder:
            self.settings["ignore_folders"].append(folder)
            self.folder_list.addItem(folder)
            self.status_bar.showMessage(f"Folder '{folder}' added to ignore list")
    
    def edit_folder(self):
        selected = self.folder_list.currentItem()
        if not selected:
            return
            
        old_folder = selected.text()
        new_folder, ok = QInputDialog.getText(
            self, "Edit Folder", "Edit folder name:", text=old_folder
        )
        if ok and new_folder:
            idx = self.settings["ignore_folders"].index(old_folder)
            self.settings["ignore_folders"][idx] = new_folder
            selected.setText(new_folder)
            self.status_bar.showMessage(f"Folder updated to '{new_folder}'")
    
    def remove_folder(self):
        selected = self.folder_list.currentItem()
        if not selected:
            return

        folder = selected.text()
        self.settings["ignore_folders"].remove(folder)
        self.folder_list.takeItem(self.folder_list.row(selected))
        self.status_bar.showMessage(f"Folder '{folder}' removed from ignore list")

    def add_risky_trigger(self):
        trigger, ok = QInputDialog.getText(
            self, "Add Risky Trigger", "Enter trigger name:"
        )
        if ok and trigger:
            self.settings.setdefault("risky_triggers", []).append(trigger)
            self.risky_list.addItem(trigger)
            self.status_bar.showMessage(f"Risky trigger '{trigger}' added")

    def remove_risky_trigger(self):
        selected = self.risky_list.currentItem()
        if not selected:
            return

        trigger = selected.text()
        self.settings.setdefault("risky_triggers", []).remove(trigger)
        self.risky_list.takeItem(self.risky_list.row(selected))
        self.status_bar.showMessage(f"Risky trigger '{trigger}' removed")
    
    def save_all_settings(self):
        # Update settings from UI
        self.settings["trigger_path"] = self.path_input.text()
        self.settings["ac_keywords"] = [self.ac_list.item(i).text() for i in range(self.ac_list.count())]
        self.settings["ignore_folders"] = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        self.settings["risky_triggers"] = [self.risky_list.item(i).text() for i in range(self.risky_list.count())]
        
        # Save to file
        if save_settings(self.settings):
            global TRIGGER_PATH
            TRIGGER_PATH = self.settings["trigger_path"]
            self.path_label.setText(f"<b>Current Path:</b> {TRIGGER_PATH}")
            self.status_bar.showMessage("Settings saved successfully!")
        else:
            self.status_bar.showMessage("Error saving settings!")

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

    def save_path(self):
        global TRIGGER_PATH
        TRIGGER_PATH = self.path_input.text()
        self.path_label.setText(f"<b>Current Path:</b> {TRIGGER_PATH}")
        self.status_bar.showMessage("Path saved successfully")

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
        self.trigger_table.setRowCount(0)
        
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
            self.populate_trigger_table(self.trigger_results)
            return
            
        # Filter results by keyword
        filtered = [res for res in self.trigger_results if keyword in res[3].lower()]
        
        if not filtered:
            self.trigger_table.setRowCount(0)
            return
        self.populate_trigger_table(filtered)
        self.status_bar.showMessage(f"Found {len(filtered)} triggers containing '{keyword}'")

    def on_triggers_found(self, results):
        self.progress_bar.hide()
        self.trigger_results = results

        if not results:
            self.trigger_table.setRowCount(0)
            self.status_bar.showMessage("Trigger scan completed: 0 events found")
            return

        self.status_bar.showMessage(
            f"Trigger scan completed: {len(results)} events found"
        )

        self.populate_trigger_table(results)

        # Save to file
        output_file = os.path.join(FEMDUMPER_FOLDER, "trigger_events.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            for resource, file_path, line, content in results:
                f.write(f"\n{'='*25} [{resource} - Line {line}] {'='*25}\n")
                f.write(f"{content}\n")

    def populate_trigger_table(self, results):
        self.trigger_table.setRowCount(0)
        risky = [r.lower() for r in self.settings.get("risky_triggers", [])]
        for resource, file_path, line, content in results:
            risk_level = "Risky" if any(x in content.lower() for x in risky) else "N/A"
            row = self.trigger_table.rowCount()
            self.trigger_table.insertRow(row)
            self.trigger_table.setItem(row, 0, QTableWidgetItem(resource))
            self.trigger_table.setItem(row, 1, QTableWidgetItem(content))
            status_item = QTableWidgetItem("New")
            status_item.setBackground(QColor("green"))
            self.trigger_table.setItem(row, 2, status_item)
            self.trigger_table.setItem(row, 3, QTableWidgetItem(risk_level))
            btn = QPushButton("VSCode")
            btn.clicked.connect(partial(self.open_in_vscode, file_path, line))
            self.trigger_table.setCellWidget(row, 4, btn)

    def populate_webhook_table(self, results):
        self.webhook_table.setRowCount(0)
        for path, url in results:
            row = self.webhook_table.rowCount()
            self.webhook_table.insertRow(row)
            self.webhook_table.setItem(row, 0, QTableWidgetItem(os.path.basename(path)))
            self.webhook_table.setItem(row, 1, QTableWidgetItem(url))
            btn = QPushButton("VSCode")
            btn.clicked.connect(partial(self.open_in_vscode, path, 1))
            self.webhook_table.setCellWidget(row, 2, btn)

    def populate_anticheat_table(self, results):
        self.anticheat_table.setRowCount(0)
        for folder, line, content in results:
            row = self.anticheat_table.rowCount()
            self.anticheat_table.insertRow(row)
            self.anticheat_table.setItem(row, 0, QTableWidgetItem(folder))
            self.anticheat_table.setItem(row, 1, QTableWidgetItem(str(line)))
            self.anticheat_table.setItem(row, 2, QTableWidgetItem(content))

    def populate_known_ac_table(self, results):
        self.known_ac_table.setRowCount(0)
        for folder, ac_name in results:
            row = self.known_ac_table.rowCount()
            self.known_ac_table.insertRow(row)
            self.known_ac_table.setItem(row, 0, QTableWidgetItem(folder))
            self.known_ac_table.setItem(row, 1, QTableWidgetItem(ac_name))

    def populate_variable_table(self, results):
        self.variable_table.setRowCount(0)
        for folder, line, content in results:
            row = self.variable_table.rowCount()
            self.variable_table.insertRow(row)
            self.variable_table.setItem(row, 0, QTableWidgetItem(folder))
            self.variable_table.setItem(row, 1, QTableWidgetItem(str(line)))
            self.variable_table.setItem(row, 2, QTableWidgetItem(content))

    def find_webhooks(self):
        if not self.validate_path():
            return
            
        # Disable button during scan
        self.scan_webhooks_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning for Discord webhooks...")
        self.progress_bar.show()
        
        # Clear previous results
        self.webhook_table.setRowCount(0)
        
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
            self.webhook_table.setRowCount(0)
            self.status_bar.showMessage("Webhook scan completed: 0 webhooks found")
            return

        self.status_bar.showMessage(
            f"Webhook scan completed: {len(results)} webhooks found"
        )

        self.populate_webhook_table(results)
        
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
        self.anticheat_table.setRowCount(0)
        self.known_ac_table.setRowCount(0)
        
        # Create and start scanner thread
        self.anticheat_scanner = AnticheatScanner(
            TRIGGER_PATH, 
            self.settings["ac_keywords"],
            self.settings["ignore_folders"]
        )
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
            self.anticheat_table.setRowCount(0)
            self.status_bar.showMessage("Anti-cheat scan completed: 0 keywords found")
            return
            
        self.status_bar.showMessage(
            f"Anti-cheat scan completed: {len(results)} keywords found"
        )
        
        self.populate_anticheat_table(results)
        
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
            self.status_bar.showMessage("Known AC scan completed: 0 detections")
            return

        self.populate_known_ac_table(results)
        self.status_bar.showMessage(
            f"Known AC scan completed: {len(results)} detections"
        )
        
        # Save to file
        output_file = os.path.join(FEMDUMPER_FOLDER, "known_anticheats.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            for folder, ac_name in results:
                f.write(f"{ac_name} detected in {folder}\n")

    def find_variables(self):
        if not self.validate_path():
            return
            
        # Disable button during scan
        self.scan_vars_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning for variables...")
        self.progress_bar.show()
        
        # Clear previous results
        self.variable_table.setRowCount(0)
        
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
            self.variable_table.setRowCount(0)
            self.status_bar.showMessage("Variable scan completed: 0 variables found")
            return
            
        self.status_bar.showMessage(
            f"Variable scan completed: {len(results)} variables found"
        )
        
        self.populate_variable_table(results)
        
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

    def open_in_vscode(self, path, line):
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", "The requested file does not exist!")
            return

        try:
            subprocess.Popen(["code", "-g", f"{path}:{line}"])
        except Exception as e:
            QMessageBox.critical(
                self,
                "Open Error",
                "Failed to open in VSCode. Ensure the 'code' command is installed and in your PATH."
            )

    def update_progress(self, current, total):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)

    def on_scan_error(self, error):
        self.progress_bar.hide()
        QMessageBox.critical(self, "Scan Error", f"An error occurred: {error}")

    def closeEvent(self, event):
        # Save settings on close
        self.save_all_settings()
        
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