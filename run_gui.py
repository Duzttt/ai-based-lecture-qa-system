"""GUI launcher for RAG backend and frontend."""

import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import scrolledtext
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

BACKEND_CMD = [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"]
FRONTEND_CMD = ["npm", "run", "dev"]


class ServerGUI:
    """A minimal Tkinter GUI to start/stop Django backend and Vue frontend."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("RAG Server Launcher")
        self.root.geometry("800x560")
        self.root.configure(bg="#1e1e2e")
        self.root.resizable(True, True)

        self.backend_proc: subprocess.Popen | None = None
        self.frontend_proc: subprocess.Popen | None = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        bg = "#1e1e2e"
        fg = "#cdd6f4"
        btn_bg = "#313244"
        accent = "#89b4fa"
        red = "#f38ba8"
        surface = "#181825"

        style_btn = {
            "font": ("Segoe UI", 11, "bold"),
            "fg": fg,
            "bg": btn_bg,
            "activeforeground": fg,
            "activebackground": "#45475a",
            "bd": 0,
            "padx": 16,
            "pady": 6,
            "cursor": "hand2",
        }

        # ── Header ──
        header = tk.Frame(root, bg=bg, pady=10)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="RAG Server Launcher",
            font=("Segoe UI", 16, "bold"),
            fg=accent,
            bg=bg,
        ).pack()

        # ── Backend row ──
        backend_row = tk.Frame(root, bg=bg, padx=20, pady=4)
        backend_row.pack(fill=tk.X)

        tk.Label(
            backend_row,
            text="Django Backend  :8000",
            font=("Segoe UI", 11),
            fg=fg,
            bg=bg,
            width=28,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.btn_backend_start = tk.Button(
            backend_row, text="Start", command=self.start_backend, **style_btn
        )
        self.btn_backend_start.pack(side=tk.LEFT, padx=4)

        self.btn_backend_stop = tk.Button(
            backend_row, text="Stop", command=self.stop_backend, **style_btn
        )
        self.btn_backend_stop.pack(side=tk.LEFT, padx=4)

        self.backend_status = tk.Label(
            backend_row,
            text="● Stopped",
            font=("Segoe UI", 11),
            fg=red,
            bg=bg,
        )
        self.backend_status.pack(side=tk.LEFT, padx=12)

        # ── Frontend row ──
        frontend_row = tk.Frame(root, bg=bg, padx=20, pady=4)
        frontend_row.pack(fill=tk.X)

        tk.Label(
            frontend_row,
            text="Vue Frontend    :5173",
            font=("Segoe UI", 11),
            fg=fg,
            bg=bg,
            width=28,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.btn_frontend_start = tk.Button(
            frontend_row, text="Start", command=self.start_frontend, **style_btn
        )
        self.btn_frontend_start.pack(side=tk.LEFT, padx=4)

        self.btn_frontend_stop = tk.Button(
            frontend_row, text="Stop", command=self.stop_frontend, **style_btn
        )
        self.btn_frontend_stop.pack(side=tk.LEFT, padx=4)

        self.frontend_status = tk.Label(
            frontend_row,
            text="● Stopped",
            font=("Segoe UI", 11),
            fg=red,
            bg=bg,
        )
        self.frontend_status.pack(side=tk.LEFT, padx=12)

        # ── Bulk actions ──
        bulk_row = tk.Frame(root, bg=bg, padx=20, pady=8)
        bulk_row.pack(fill=tk.X)

        tk.Button(bulk_row, text="Start All", command=self.start_all, **style_btn).pack(
            side=tk.LEFT, padx=4
        )

        tk.Button(bulk_row, text="Stop All", command=self.stop_all, **style_btn).pack(
            side=tk.LEFT, padx=4
        )

        tk.Button(
            bulk_row,
            text="Open Browser",
            command=self.open_browser,
            **style_btn,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            bulk_row,
            text="LLM Logs",
            command=self.open_llm_logs,
            **style_btn,
        ).pack(side=tk.RIGHT, padx=4)

        # ── Log area ──
        log_frame = tk.Frame(root, bg=bg, padx=20, pady=8)
        log_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            log_frame,
            text="Logs",
            font=("Cascadia Mono", 10, "bold"),
            fg=accent,
            bg=bg,
            anchor="w",
        ).pack(fill=tk.X)

        self.log_area = scrolledtext.ScrolledText(
            log_frame,
            font=("Cascadia Mono", 9),
            fg=fg,
            bg=surface,
            insertbackground=fg,
            bd=0,
            padx=8,
            pady=8,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)

    # ── Logging helper ──────────────────────────────────────────────

    def _log(self, tag: str, text: str, color: str = "#cdd6f4") -> None:
        def _insert() -> None:
            self.log_area.configure(state=tk.NORMAL)
            self.log_area.insert(tk.END, f"[{tag}] {text}\n", tag)
            self.log_area.tag_config(tag, foreground=color)
            self.log_area.see(tk.END)
            self.log_area.configure(state=tk.DISABLED)

        self.root.after(0, _insert)

    # ── Stream reader ───────────────────────────────────────────────

    def _read_stream(self, proc: subprocess.Popen, tag: str, color: str) -> None:
        """Read stdout lines from *proc* and push to the log widget."""
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            self._log(tag, line.rstrip(), color)
        proc.stdout.close()

    # ── Backend ─────────────────────────────────────────────────────

    def start_backend(self) -> None:
        if self.backend_proc and self.backend_proc.poll() is None:
            self._log("BACKEND", "Already running.", "#f9e2af")
            return
        self._log("BACKEND", "Starting Django backend …", "#89b4fa")
        self.backend_proc = subprocess.Popen(
            BACKEND_CMD,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        t = threading.Thread(
            target=self._read_stream,
            args=(self.backend_proc, "BACKEND", "#89b4fa"),
            daemon=True,
        )
        t.start()
        self.backend_status.config(text="● Running", fg="#a6e3a1")

    def stop_backend(self) -> None:
        if self.backend_proc and self.backend_proc.poll() is None:
            self.backend_proc.terminate()
            self.backend_proc.wait(timeout=5)
            self._log("BACKEND", "Stopped.", "#f38ba8")
        self.backend_proc = None
        self.backend_status.config(text="● Stopped", fg="#f38ba8")

    # ── Frontend ────────────────────────────────────────────────────

    def start_frontend(self) -> None:
        if self.frontend_proc and self.frontend_proc.poll() is None:
            self._log("FRONTEND", "Already running.", "#f9e2af")
            return
        self._log("FRONTEND", "Starting Vue frontend …", "#a6e3a1")
        self.frontend_proc = subprocess.Popen(
            FRONTEND_CMD,
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        t = threading.Thread(
            target=self._read_stream,
            args=(self.frontend_proc, "FRONTEND", "#a6e3a1"),
            daemon=True,
        )
        t.start()
        self.frontend_status.config(text="● Running", fg="#a6e3a1")

    def stop_frontend(self) -> None:
        if self.frontend_proc and self.frontend_proc.poll() is None:
            self.frontend_proc.terminate()
            self.frontend_proc.wait(timeout=5)
            self._log("FRONTEND", "Stopped.", "#f38ba8")
        self.frontend_proc = None
        self.frontend_status.config(text="● Stopped", fg="#f38ba8")

    # ── Bulk ────────────────────────────────────────────────────────

    def start_all(self) -> None:
        self.start_backend()
        self.start_frontend()

    def stop_all(self) -> None:
        self.stop_backend()
        self.stop_frontend()

    # ── Browser ─────────────────────────────────────────────────────

    def open_browser(self) -> None:
        webbrowser.open("http://localhost:5173")

    def open_llm_logs(self) -> None:
        webbrowser.open("http://localhost:8000/llm-logs")

    # ── Cleanup ─────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self.stop_all()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ServerGUI(root)
    root.mainloop()
