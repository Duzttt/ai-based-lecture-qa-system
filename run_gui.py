"""PyQt6 GUI launcher for RAG backend and frontend with LLM provider switcher."""

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPalette, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
ENV_FILE = BASE_DIR / ".env"
SETTINGS_FILE = BASE_DIR / "data" / "settings.json"
RAG_CONFIG_FILE = BASE_DIR / "data" / "rag_config.json"
BACKEND_CMD = [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"]
FRONTEND_CMD = ["npm", "run", "dev"]

VALID_PROVIDERS = {"gemini", "openrouter", "local_llm"}

PROVIDER_META = {
    "gemini": {
        "label": "Gemini",
        "icon": "\u2728",
        "default_model": "gemini-2.5-flash",
        "requires_key": True,
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
    },
    "openrouter": {
        "label": "OpenRouter",
        "icon": "\U0001f517",
        "default_model": "nvidia/nemotron-3-super-120b-a12b:free",
        "requires_key": True,
        "models": [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ],
    },
    "local_llm": {
        "label": "Local (Ollama)",
        "icon": "\U0001f3e0",
        "default_model": "qwen2.5:3b",
        "requires_key": False,
        "models": [
            "gemma4:latest",
            "gemma4:e4b",
            "qwen3.5:4b",
            "qwen2.5:3b",
        ],
    },
}


def _fetch_ollama_models() -> list[str]:
    """Fetch installed local models from Ollama; fall back silently on error."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        payload = response.json()
        models: list[str] = []
        for item in payload.get("models", []):
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if name and name not in models:
                    models.append(name)
        return models
    except (requests.RequestException, ValueError, TypeError):
        return []


# ── Catppuccin Mocha palette ───────────────────────────────────────────
C_BASE = "#1e1e2e"
C_MANTLE = "#181825"
C_CRUST = "#11111b"
C_SURFACE0 = "#313244"
C_SURFACE1 = "#45475a"
C_SURFACE2 = "#585b70"
C_TEXT = "#cdd6f4"
C_SUBTEXT = "#a6adc8"
C_BLUE = "#89b4fa"
C_GREEN = "#a6e3a1"
C_RED = "#f38ba8"
C_YELLOW = "#f9e2af"
C_MAUVE = "#cba6f7"
C_LAVENDER = "#b4befe"
C_TEAL = "#94e2d5"


GLOBAL_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C_BASE};
    color: {C_TEXT};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {C_SURFACE1};
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
    font-size: 13px;
    color: {C_LAVENDER};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    left: 12px;
}}
QPushButton {{
    background-color: {C_SURFACE0};
    color: {C_TEXT};
    border: 1px solid {C_SURFACE1};
    border-radius: 8px;
    padding: 7px 18px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {C_SURFACE1};
    border-color: {C_SURFACE2};
}}
QPushButton:pressed {{
    background-color: {C_SURFACE2};
}}
QPushButton:disabled {{
    background-color: {C_CRUST};
    color: {C_SURFACE2};
    border-color: {C_SURFACE0};
}}
QPushButton[accent="true"] {{
    background-color: {C_BLUE};
    color: {C_CRUST};
    border-color: {C_BLUE};
}}
QPushButton[accent="true"]:hover {{
    background-color: {C_LAVENDER};
}}
QPushButton[danger="true"] {{
    background-color: {C_RED};
    color: {C_CRUST};
    border-color: {C_RED};
}}
QPushButton[danger="true"]:hover {{
    background-color: #eba0b3;
}}
QComboBox {{
    background-color: {C_SURFACE0};
    color: {C_TEXT};
    border: 1px solid {C_SURFACE1};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    min-width: 120px;
}}
QComboBox:hover {{
    border-color: {C_BLUE};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {C_SUBTEXT};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {C_MANTLE};
    color: {C_TEXT};
    border: 1px solid {C_SURFACE1};
    border-radius: 6px;
    selection-background-color: {C_SURFACE1};
    selection-color: {C_BLUE};
    padding: 4px;
}}
QLineEdit {{
    background-color: {C_SURFACE0};
    color: {C_TEXT};
    border: 1px solid {C_SURFACE1};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    selection-background-color: {C_BLUE};
    selection-color: {C_CRUST};
}}
QLineEdit:focus {{
    border-color: {C_BLUE};
}}
QLineEdit:disabled {{
    background-color: {C_CRUST};
    color: {C_SURFACE2};
}}
QTextEdit {{
    background-color: {C_MANTLE};
    color: {C_TEXT};
    border: 1px solid {C_SURFACE0};
    border-radius: 8px;
    padding: 8px;
    font-family: 'Cascadia Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 11px;
    selection-background-color: {C_SURFACE1};
}}
QLabel {{
    color: {C_TEXT};
}}
QSplitter::handle {{
    background-color: {C_SURFACE0};
    height: 2px;
}}
QFrame[frameShape="4"] {{
    color: {C_SURFACE1};
    max-height: 1px;
}}
"""


# ── Helpers ────────────────────────────────────────────────────────────

def _read_env_var(key: str, default: str = "") -> str:
    if not ENV_FILE.exists():
        return default
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            return stripped.split("=", 1)[1].strip().strip("\"'")
    return default


def _set_env_var(key: str, value: str) -> None:
    env_text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = env_text.splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _sync_rag_model(model: str) -> None:
    """Keep rag_config llm_model aligned with runtime LLM settings."""
    model_name = model.strip()
    if not model_name:
        return

    config: dict = {}
    if RAG_CONFIG_FILE.exists():
        try:
            with RAG_CONFIG_FILE.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                config = loaded
        except (OSError, json.JSONDecodeError):
            config = {}

    config["llm_model"] = model_name
    RAG_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RAG_CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ── Background process reader ─────────────────────────────────────────

class ProcessReader(QThread):
    """Read stdout from a subprocess line-by-line and emit signals."""

    line_ready = pyqtSignal(str, str, str)  # tag, text, color
    finished_signal = pyqtSignal(str)  # tag

    def __init__(self, proc: subprocess.Popen, tag: str, color: str) -> None:
        super().__init__()
        self._proc = proc
        self._tag = tag
        self._color = color

    def run(self) -> None:
        assert self._proc.stdout is not None
        try:
            for line in iter(self._proc.stdout.readline, ""):
                if not line:
                    break
                self.line_ready.emit(self._tag, line.rstrip("\n\r"), self._color)
            self._proc.stdout.close()
        except Exception:
            pass
        self.finished_signal.emit(self._tag)


# ── Status dot widget ─────────────────────────────────────────────────

class StatusDot(QLabel):
    def __init__(self, initial_color: str = C_RED, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._set_color(initial_color)

    def _set_color(self, color: str) -> None:
        self.setStyleSheet(
            f"background-color: {color}; border-radius: 5px; border: none;"
        )

    def set_running(self) -> None:
        self._set_color(C_GREEN)

    def set_stopped(self) -> None:
        self._set_color(C_RED)

    def set_warning(self) -> None:
        self._set_color(C_YELLOW)


# ── Main Window ───────────────────────────────────────────────────────

class ServerGUI(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RAG Server Launcher")
        self.setMinimumSize(900, 640)
        self.resize(960, 700)

        self.backend_proc: Optional[subprocess.Popen] = None
        self.frontend_proc: Optional[subprocess.Popen] = None
        self._readers: list[ProcessReader] = []
        self._suppress_llm_autosave = False

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(10)

        self._build_header(root_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        self._build_server_controls(top_layout)
        self._build_llm_panel(top_layout)

        splitter.addWidget(top_widget)
        self._build_log_area(splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter)

        self._load_llm_state()

    # ── Header ─────────────────────────────────────────────────────

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QHBoxLayout()
        title = QLabel("RAG Server Launcher")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {C_BLUE}; padding: 4px 0;"
        )
        header.addWidget(title)
        header.addStretch()

        btn_browser = QPushButton("Open Browser")
        btn_browser.setProperty("accent", True)
        btn_browser.clicked.connect(self._open_browser)
        header.addWidget(btn_browser)

        btn_logs = QPushButton("LLM Logs")
        btn_logs.clicked.connect(self._open_llm_logs)
        header.addWidget(btn_logs)

        btn_ollama = QPushButton("Ollama Serve")
        btn_ollama.clicked.connect(self._start_ollama_serve)
        header.addWidget(btn_ollama)

        parent_layout.addLayout(header)

    # ── Server controls ────────────────────────────────────────────

    def _build_server_controls(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Services")
        grid = QVBoxLayout(group)
        grid.setSpacing(8)

        # Backend row
        row_be = QHBoxLayout()
        self.dot_backend = StatusDot()
        row_be.addWidget(self.dot_backend)
        lbl = QLabel("Django Backend  :8000")
        lbl.setMinimumWidth(200)
        row_be.addWidget(lbl)

        self.btn_be_start = QPushButton("Start")
        self.btn_be_start.clicked.connect(self._start_backend)
        row_be.addWidget(self.btn_be_start)
        self.btn_be_stop = QPushButton("Stop")
        self.btn_be_stop.clicked.connect(self._stop_backend)
        row_be.addWidget(self.btn_be_stop)

        self.lbl_be_status = QLabel("Stopped")
        self.lbl_be_status.setStyleSheet(f"color: {C_RED}; font-weight: 600;")
        self.lbl_be_status.setMinimumWidth(70)
        row_be.addWidget(self.lbl_be_status)
        row_be.addStretch()
        grid.addLayout(row_be)

        # Frontend row
        row_fe = QHBoxLayout()
        self.dot_frontend = StatusDot()
        row_fe.addWidget(self.dot_frontend)
        lbl2 = QLabel("Vue Frontend     :5173")
        lbl2.setMinimumWidth(200)
        row_fe.addWidget(lbl2)

        self.btn_fe_start = QPushButton("Start")
        self.btn_fe_start.clicked.connect(self._start_frontend)
        row_fe.addWidget(self.btn_fe_start)
        self.btn_fe_stop = QPushButton("Stop")
        self.btn_fe_stop.clicked.connect(self._stop_frontend)
        row_fe.addWidget(self.btn_fe_stop)

        self.lbl_fe_status = QLabel("Stopped")
        self.lbl_fe_status.setStyleSheet(f"color: {C_RED}; font-weight: 600;")
        self.lbl_fe_status.setMinimumWidth(70)
        row_fe.addWidget(self.lbl_fe_status)
        row_fe.addStretch()
        grid.addLayout(row_fe)

        # PDF parser row
        row_pdf = QHBoxLayout()
        row_pdf.addSpacing(14)
        lbl3 = QLabel("PDF Parser")
        lbl3.setMinimumWidth(200)
        row_pdf.addWidget(lbl3)

        self.combo_parser = QComboBox()
        self.combo_parser.addItems(["pypdf", "opendataloader"])
        current_parser = _read_env_var("PDF_PARSER", "pypdf")
        idx = self.combo_parser.findText(current_parser)
        if idx >= 0:
            self.combo_parser.setCurrentIndex(idx)
        self.combo_parser.currentTextChanged.connect(self._on_parser_changed)
        row_pdf.addWidget(self.combo_parser)

        self.lbl_parser_hint = QLabel("restart backend to apply")
        self.lbl_parser_hint.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 11px; font-style: italic;"
        )
        self.lbl_parser_hint.hide()
        row_pdf.addWidget(self.lbl_parser_hint)
        row_pdf.addStretch()

        # Bulk buttons
        row_bulk = QHBoxLayout()
        btn_all_start = QPushButton("Start All")
        btn_all_start.setProperty("accent", True)
        btn_all_start.clicked.connect(self._start_all)
        row_bulk.addWidget(btn_all_start)

        btn_all_stop = QPushButton("Stop All")
        btn_all_stop.setProperty("danger", True)
        btn_all_stop.clicked.connect(self._stop_all)
        row_bulk.addWidget(btn_all_stop)
        row_bulk.addStretch()

        grid.addLayout(row_pdf)
        grid.addLayout(row_bulk)
        parent_layout.addWidget(group)

    # ── LLM Provider Panel ─────────────────────────────────────────

    def _build_llm_panel(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("LLM Provider")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # Provider selector row
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Provider"))
        self.combo_provider = QComboBox()
        for pid, meta in PROVIDER_META.items():
            self.combo_provider.addItem(f"{meta['icon']}  {meta['label']}", pid)
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        self.combo_provider.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        row1.addWidget(self.combo_provider)

        self.lbl_provider_status = QLabel()
        self.lbl_provider_status.setFixedWidth(80)
        self.lbl_provider_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row1.addWidget(self.lbl_provider_status)
        layout.addLayout(row1)

        # Model selector row
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Model"))
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.currentTextChanged.connect(self._on_model_changed)
        self.combo_model.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        row2.addWidget(self.combo_model)
        layout.addLayout(row2)

        # API key row
        row3 = QHBoxLayout()
        self.lbl_api_key = QLabel("API Key")
        row3.addWidget(self.lbl_api_key)
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_api_key.setPlaceholderText("Enter API key…")
        self.input_api_key.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        row3.addWidget(self.input_api_key)

        self.btn_toggle_key = QPushButton("Show")
        self.btn_toggle_key.setFixedWidth(52)
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        row3.addWidget(self.btn_toggle_key)
        layout.addLayout(row3)

        # Action row
        row4 = QHBoxLayout()
        row4.addStretch()

        self.btn_save_llm = QPushButton("  Apply Settings  ")
        self.btn_save_llm.setProperty("accent", True)
        self.btn_save_llm.clicked.connect(self._save_llm_settings)
        row4.addWidget(self.btn_save_llm)

        self.btn_reset_llm = QPushButton("Reset to .env defaults")
        self.btn_reset_llm.clicked.connect(self._reset_llm_settings)
        row4.addWidget(self.btn_reset_llm)
        layout.addLayout(row4)

        # Current config display
        self.lbl_active_config = QLabel()
        self.lbl_active_config.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 11px; padding: 4px 0 0 0;"
        )
        self.lbl_active_config.setWordWrap(True)
        layout.addWidget(self.lbl_active_config)

        parent_layout.addWidget(group)

    # ── Log Area ───────────────────────────────────────────────────

    def _build_log_area(self, splitter: QSplitter) -> None:
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 6, 0, 0)

        lbl = QLabel("Logs")
        lbl.setStyleSheet(
            f"color: {C_BLUE}; font-weight: 700; font-size: 12px; "
            "font-family: 'Cascadia Mono', monospace; padding: 2px 4px;"
        )
        log_layout.addWidget(lbl)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)

        splitter.addWidget(log_widget)

    # ── Logging ────────────────────────────────────────────────────

    def _log(self, tag: str, text: str, color: str = C_TEXT) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontFamily("Cascadia Mono, Fira Code, Consolas, monospace")
        cursor = self.log_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(f"[{tag}] {text}\n", fmt)
        self.log_area.setTextCursor(cursor)
        self.log_area.ensureCursorVisible()

    # ── Process helpers ────────────────────────────────────────────

    def _attach_reader(
        self, proc: subprocess.Popen, tag: str, color: str
    ) -> ProcessReader:
        reader = ProcessReader(proc, tag, color)
        reader.line_ready.connect(self._log)
        self._readers.append(reader)
        reader.start()
        return reader

    # ── Backend ────────────────────────────────────────────────────

    def _start_backend(self) -> None:
        if self.backend_proc and self.backend_proc.poll() is None:
            self._log("BACKEND", "Already running.", C_YELLOW)
            return
        self._log("BACKEND", "Starting Django backend\u2026", C_BLUE)
        kwargs: dict = dict(
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        self.backend_proc = subprocess.Popen(BACKEND_CMD, **kwargs)
        self._attach_reader(self.backend_proc, "BACKEND", C_BLUE)
        self.dot_backend.set_running()
        self.lbl_be_status.setText("Running")
        self.lbl_be_status.setStyleSheet(f"color: {C_GREEN}; font-weight: 600;")

    def _stop_backend(self) -> None:
        if self.backend_proc and self.backend_proc.poll() is None:
            self.backend_proc.terminate()
            try:
                self.backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_proc.kill()
            self._log("BACKEND", "Stopped.", C_RED)
        self.backend_proc = None
        self.dot_backend.set_stopped()
        self.lbl_be_status.setText("Stopped")
        self.lbl_be_status.setStyleSheet(f"color: {C_RED}; font-weight: 600;")

    # ── Frontend ───────────────────────────────────────────────────

    def _start_frontend(self) -> None:
        if self.frontend_proc and self.frontend_proc.poll() is None:
            self._log("FRONTEND", "Already running.", C_YELLOW)
            return
        self._log("FRONTEND", "Starting Vue frontend\u2026", C_GREEN)
        kwargs: dict = dict(
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=True,
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        self.frontend_proc = subprocess.Popen(FRONTEND_CMD, **kwargs)
        self._attach_reader(self.frontend_proc, "FRONTEND", C_GREEN)
        self.dot_frontend.set_running()
        self.lbl_fe_status.setText("Running")
        self.lbl_fe_status.setStyleSheet(f"color: {C_GREEN}; font-weight: 600;")

    def _stop_frontend(self) -> None:
        if self.frontend_proc and self.frontend_proc.poll() is None:
            self.frontend_proc.terminate()
            try:
                self.frontend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.frontend_proc.kill()
            self._log("FRONTEND", "Stopped.", C_RED)
        self.frontend_proc = None
        self.dot_frontend.set_stopped()
        self.lbl_fe_status.setText("Stopped")
        self.lbl_fe_status.setStyleSheet(f"color: {C_RED}; font-weight: 600;")

    # ── Bulk ───────────────────────────────────────────────────────

    def _start_all(self) -> None:
        self._start_backend()
        self._start_frontend()

    def _stop_all(self) -> None:
        self._stop_backend()
        self._stop_frontend()

    # ── Browser ────────────────────────────────────────────────────

    def _open_browser(self) -> None:
        QDesktopServices.openUrl(QUrl("http://localhost:5173"))

    def _open_llm_logs(self) -> None:
        QDesktopServices.openUrl(QUrl("http://localhost:8000/llm-logs"))

    def _is_ollama_ready(self) -> bool:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _start_ollama_serve(self) -> None:
        if self._is_ollama_ready():
            self._log("OLLAMA", "Already running on http://localhost:11434", C_YELLOW)
            return

        self._log("OLLAMA", "Starting ollama serve...", C_TEAL)
        kwargs: dict = dict(
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(["ollama", "serve"], **kwargs)
        self._attach_reader(proc, "OLLAMA", C_TEAL)

        def _probe() -> None:
            for _ in range(6):
                if self._is_ollama_ready():
                    self._log("OLLAMA", "Service is ready.", C_GREEN)
                    return
                threading.Event().wait(1.0)
            self._log("OLLAMA", "Service may still be starting...", C_YELLOW)

        threading.Thread(target=_probe, daemon=True).start()

    # ── PDF parser ─────────────────────────────────────────────────

    def _on_parser_changed(self, value: str) -> None:
        _set_env_var("PDF_PARSER", value)
        self.lbl_parser_hint.show()
        self._log("PARSER", f"Switched to {value} (restart backend to apply)", C_YELLOW)

    # ── LLM Provider Logic ─────────────────────────────────────────

    def _load_llm_state(self) -> None:
        """Populate controls from persisted settings.json + .env fallback."""
        self._suppress_llm_autosave = True
        data = _load_settings()
        provider = data.get("provider", _read_env_var("LLM_PROVIDER", "gemini"))
        if provider not in VALID_PROVIDERS:
            provider = "gemini"

        idx = self.combo_provider.findData(provider)
        if idx >= 0:
            self.combo_provider.setCurrentIndex(idx)
        self._populate_models(provider)

        model = data.get("model", "")
        if model:
            midx = self.combo_model.findText(model)
            if midx >= 0:
                self.combo_model.setCurrentIndex(midx)
            else:
                self.combo_model.setEditText(model)

        api_key = data.get("api_key") or ""
        if not api_key:
            if provider == "gemini":
                api_key = _read_env_var("GEMINI_API_KEY", "")
            elif provider == "openrouter":
                api_key = _read_env_var("OPENROUTER_API_KEY", "")
        self.input_api_key.setText(api_key)

        self._update_provider_status(provider, api_key)
        self._update_active_label()
        self._suppress_llm_autosave = False

    def _populate_models(self, provider: str) -> None:
        """Fill the model combo for the chosen provider."""
        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        meta = PROVIDER_META.get(provider, {})
        models = list(meta.get("models", []))
        if provider == "local_llm":
            dynamic_models = _fetch_ollama_models()
            if dynamic_models:
                models = dynamic_models
        for m in models:
            self.combo_model.addItem(m)
        self.combo_model.blockSignals(False)

    def _on_provider_changed(self, _index: int) -> None:
        if self._suppress_llm_autosave:
            return
        provider = self.combo_provider.currentData()
        if not provider:
            return
        meta = PROVIDER_META.get(provider, {})
        self._populate_models(provider)

        needs_key = meta.get("requires_key", True)
        self.input_api_key.setEnabled(needs_key)
        self.lbl_api_key.setEnabled(needs_key)
        self.btn_toggle_key.setEnabled(needs_key)
        if not needs_key:
            self.input_api_key.clear()
            self.input_api_key.setPlaceholderText("Not required for local LLM")
        else:
            self.input_api_key.setPlaceholderText("Enter API key\u2026")
            if provider == "gemini":
                self.input_api_key.setText(_read_env_var("GEMINI_API_KEY", ""))
            elif provider == "openrouter":
                self.input_api_key.setText(_read_env_var("OPENROUTER_API_KEY", ""))

        self._update_provider_status(provider, self.input_api_key.text())
        self._save_llm_settings(require_api_key=False, auto=True)

    def _on_model_changed(self, _value: str) -> None:
        if self._suppress_llm_autosave:
            return
        self._save_llm_settings(require_api_key=False, auto=True)

    def _update_provider_status(self, provider: str, api_key: str) -> None:
        meta = PROVIDER_META.get(provider, {})
        needs_key = meta.get("requires_key", True)
        if not needs_key:
            self.lbl_provider_status.setText("Local")
            self.lbl_provider_status.setStyleSheet(
                f"color: {C_TEAL}; font-size: 11px; font-weight: 600; "
                f"background: rgba(148,226,213,0.12); border-radius: 10px; padding: 2px 8px;"
            )
        elif api_key:
            self.lbl_provider_status.setText("Ready")
            self.lbl_provider_status.setStyleSheet(
                f"color: {C_GREEN}; font-size: 11px; font-weight: 600; "
                f"background: rgba(166,227,161,0.12); border-radius: 10px; padding: 2px 8px;"
            )
        else:
            self.lbl_provider_status.setText("No API Key")
            self.lbl_provider_status.setStyleSheet(
                f"color: {C_RED}; font-size: 11px; font-weight: 600; "
                f"background: rgba(243,139,168,0.12); border-radius: 10px; padding: 2px 8px;"
            )

    def _toggle_key_visibility(self) -> None:
        if self.input_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key.setText("Hide")
        else:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key.setText("Show")

    def _save_llm_settings(
        self, require_api_key: bool = True, auto: bool = False
    ) -> None:
        provider = self.combo_provider.currentData()
        model = self.combo_model.currentText().strip()
        api_key = self.input_api_key.text().strip()

        if not provider:
            return

        meta = PROVIDER_META.get(provider, {})
        if require_api_key and meta.get("requires_key") and not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                f"The {meta['label']} provider requires an API key.\n\n"
                "Please enter your key or switch to Local (Ollama).",
            )
            return

        data: dict = {
            "provider": provider,
            "model": model or meta.get("default_model", ""),
        }
        if api_key:
            data["api_key"] = api_key
        else:
            data["api_key"] = None

        _save_settings(data)
        _sync_rag_model(str(data["model"]))

        self._update_provider_status(provider, api_key)
        self._update_active_label()
        if auto:
            self._log(
                "LLM",
                f"Auto-synced backend provider={provider}  model={data['model']}",
                C_MAUVE,
            )
        else:
            self._log(
                "LLM",
                f"Saved: provider={provider}  model={data['model']}",
                C_MAUVE,
            )

    def _reset_llm_settings(self) -> None:
        provider = _read_env_var("LLM_PROVIDER", "gemini")
        if provider not in VALID_PROVIDERS:
            provider = "gemini"

        meta = PROVIDER_META.get(provider, {})
        data = {
            "provider": provider,
            "model": meta.get("default_model", ""),
            "api_key": None,
        }
        _save_settings(data)
        self._load_llm_state()
        self._log("LLM", "Reset to .env defaults", C_YELLOW)

    def _update_active_label(self) -> None:
        data = _load_settings()
        provider = data.get("provider", "?")
        model = data.get("model", "?")
        has_key = bool(data.get("api_key"))
        meta = PROVIDER_META.get(provider, {})
        icon = meta.get("icon", "")
        label = meta.get("label", provider)
        key_status = "key set" if has_key else ("local" if not meta.get("requires_key") else "no key")
        self.lbl_active_config.setText(
            f"Active: {icon} {label}  \u2022  {model}  \u2022  {key_status}"
        )

    # ── Cleanup ────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._stop_all()
        for reader in self._readers:
            reader.quit()
            reader.wait(2000)
        event.accept()


# ── Entry point ────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(C_BASE))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(C_MANTLE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(C_SURFACE0))
    palette.setColor(QPalette.ColorRole.Text, QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(C_SURFACE0))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(C_BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(C_CRUST))
    app.setPalette(palette)

    app.setStyleSheet(GLOBAL_STYLESHEET)

    window = ServerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
