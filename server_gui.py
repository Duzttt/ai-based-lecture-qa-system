"""
Server Control GUI for RAG Lecture Q&A System.

Dark-themed tkinter interface for managing the Django backend and
Vue frontend servers.  Features include tabbed real-time log streaming,
animated status indicators, port health checks, uptime display, and
per-server restart controls.
"""

import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
import platform

PROJECT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

# ── Platform-aware fonts ────────────────────────────────────────
_SYS = platform.system()
FONT_UI = {"Windows": "Segoe UI", "Darwin": "Helvetica Neue"}.get(_SYS, "DejaVu Sans")
FONT_MONO = {"Windows": "Consolas", "Darwin": "Menlo"}.get(_SYS, "DejaVu Sans Mono")


# ── Colour palette ──────────────────────────────────────────────
class C:
    BG           = "#0b0f1a"
    BG_SURFACE   = "#111827"
    BG_CARD      = "#1a2340"
    BG_LOG       = "#070b14"

    ACCENT       = "#6366f1"
    ACCENT_DIM   = "#4f46e5"
    ACCENT_DEEP  = "#1e1b4b"

    GREEN        = "#22c55e"
    GREEN_DIM    = "#16a34a"
    RED          = "#ef4444"
    RED_DIM      = "#dc2626"
    YELLOW       = "#eab308"

    TEXT         = "#e2e8f0"
    TEXT_DIM     = "#94a3b8"
    TEXT_MUTED   = "#475569"

    BORDER       = "#1e293b"
    BORDER_LIGHT = "#334155"


# ── Utilities ───────────────────────────────────────────────────
def _port_open(port, host="127.0.0.1", timeout=0.3):
    """Return True if *port* is accepting TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ── Custom widgets ──────────────────────────────────────────────
class HoverButton(tk.Canvas):
    """Canvas-drawn rounded rectangle button with hover colour swap."""

    def __init__(self, parent, text, command, color, hover=None,
                 width=90, height=30, font_size=10, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"], highlightthickness=0, **kw)
        self._cmd = command
        self._color = color
        self._hover = hover or color
        self._btn_w = width       # was self._w — collides with tkinter internals
        self._btn_h = height      # was self._h — collides with tkinter internals
        self._label = text        # was self._text — minor cleanup
        self._font = (FONT_UI, font_size, "bold")
        self._enabled = True
        self._paint(color)

        self.bind("<Enter>",    lambda _: self._paint(self._hover) if self._enabled else None)
        self.bind("<Leave>",    lambda _: self._paint(self._color))
        self.bind("<Button-1>", lambda _: self._cmd() if self._enabled else None)

    def _paint(self, fill):
        self.delete("all")
        w, h, r = self._btn_w, self._btn_h, 5
        pts = [r, 0, w - r, 0, w, r, w, h - r,
               w - r, h, r, h, 0, h - r, 0, r]
        self.create_polygon(pts, fill=fill, outline="", smooth=True)
        self.create_text(w // 2, h // 2, text=self._label,
                         fill="white", font=self._font)

    def set_enabled(self, on):
        self._enabled = on
        self._paint(self._color if on else C.BORDER)
    """Canvas-drawn rounded rectangle button with hover colour swap."""

    def __init__(self, parent, text, command, color, hover=None,
                 width=90, height=30, font_size=10, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"], highlightthickness=0, **kw)
        self._cmd = command
        self._color = color
        self._hover = hover or color
        self._w = width
        self._h = height
        self._text = text
        self._font = (FONT_UI, font_size, "bold")
        self._enabled = True
        self._paint(color)

        self.bind("<Enter>",    lambda _: self._paint(self._hover) if self._enabled else None)
        self.bind("<Leave>",    lambda _: self._paint(self._color))
        self.bind("<Button-1>", lambda _: self._cmd() if self._enabled else None)

    def _paint(self, fill):
        self.delete("all")
        w, h, r = self._w, self._h, 5
        pts = [r, 0, w - r, 0, w, r, w, h - r,
               w - r, h, r, h, 0, h - r, 0, r]
        self.create_polygon(pts, fill=fill, outline="", smooth=True)
        self.create_text(w // 2, h // 2, text=self._text,
                         fill="white", font=self._font)

    def set_enabled(self, on):
        self._enabled = on
        self._paint(self._color if on else C.BORDER)


class PulseDot(tk.Canvas):
    """Small circle with an optional pulsing outer ring."""

    def __init__(self, parent, size=10, **kw):
        super().__init__(parent, width=size + 6, height=size + 6,
                         bg=parent["bg"], highlightthickness=0, **kw)
        self._s = size
        self._color = C.RED
        self._pulsing = False
        self._phase = 0
        self._draw()

    def _draw(self):
        self.delete("all")
        s, p = self._s, 3
        if self._pulsing and self._phase % 2 == 0:
            self.create_oval(1, 1, s + p + 2, s + p + 2,
                             fill="", outline=self._color, width=1)
        self.create_oval(p, p, s + p, s + p, fill=self._color, outline="")

    def set(self, color, pulse=False):
        self._color = color
        self._pulsing = pulse
        self._draw()
        if pulse:
            self._tick()

    def _tick(self):
        if not self._pulsing:
            return
        self._phase += 1
        self._draw()
        self.after(250, self._tick)


# ── Server process manager ──────────────────────────────────────
class Server:
    """Manages a single long-running subprocess with log capture."""

    def __init__(self, name, cmd, cwd, port=None):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.port = port
        self.process = None
        self.log_queue = queue.Queue()
        self.running = False
        self._start_time = None
        self._user_stopped = False
        self._cancel_restart = False
        self._restarting = False

    def start(self):
        if self.running:
            return
        self.running = True
        self._user_stopped = False
        self._start_time = time.time()
        self.log_queue.put(f"[{self.name}] Starting\u2026\n")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.process = subprocess.Popen(
                self.cmd, cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, **kwargs,
            )
            for line in self.process.stdout:
                self.log_queue.put(line)
            rc = self.process.wait()
            if rc != 0 and not self._user_stopped:
                self.log_queue.put(f"[{self.name}] Exited with code {rc}\n")
        except FileNotFoundError:
            self.log_queue.put(f"[{self.name}] Command not found: {self.cmd[0]}\n")
        except Exception as exc:
            self.log_queue.put(f"[{self.name}] Error: {exc}\n")
        finally:
            self.running = False
            self.process = None
            self.log_queue.put(f"[{self.name}] Stopped.\n")

    def stop(self):
        self._user_stopped = True
        self._cancel_restart = True
        if self.process:
            self.running = False
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception:
                pass
            self.process = None

    @property
    def uptime(self):
        if not self.running or not self._start_time:
            return ""
        s = int(time.time() - self._start_time)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


# ── Main application ────────────────────────────────────────────
class App:
    """Builds the GUI and wires everything together."""

    MAX_LOG_LINES = 4000

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RAG Lecture Q\u2009&\u2009A \u2014 Server Control")
        self.root.geometry("960x720")
        self.root.minsize(780, 540)
        self.root.configure(bg=C.BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        self.backend = Server(
            "Backend",
            [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"],
            str(PROJECT_DIR), port=8000,
        )
        self.frontend = Server(
            "Frontend", [npm, "run", "dev"],
            str(FRONTEND_DIR), port=5173,
        )

        self._ui = {}                # server.name -> widget refs
        self._active_tab = None      # "backend" | "frontend"
        self._auto_scroll = True

        self._build()
        self._poll_logs()
        self._poll_uptime()
        self._poll_port()

    # ── Layout ──────────────────────────────────────────────────

    def _build(self):
        self._build_header()
        body = tk.Frame(self.root, bg=C.BG)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._build_cards(body)
        self._build_log_section(body)
        self._build_footer(body)

    def _build_header(self):
        bar = tk.Frame(self.root, bg=C.BG_SURFACE, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=C.ACCENT, height=3).pack(fill="x", side="top")

        inner = tk.Frame(bar, bg=C.BG_SURFACE)
        inner.pack(fill="both", expand=True, padx=20, pady=(4, 0))

        # Accent stripe
        tk.Frame(inner, bg=C.ACCENT, width=4).pack(side="left", fill="y", padx=(0, 14))

        # Title
        title_box = tk.Frame(inner, bg=C.BG_SURFACE)
        title_box.pack(side="left", fill="y")
        tk.Label(title_box, text="RAG Lecture Q&A", bg=C.BG_SURFACE, fg=C.TEXT,
                 font=(FONT_UI, 15, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Server Control Panel", bg=C.BG_SURFACE,
                 fg=C.TEXT_MUTED, font=(FONT_UI, 9)).pack(anchor="w")

        # Global buttons
        btn_box = tk.Frame(inner, bg=C.BG_SURFACE)
        btn_box.pack(side="right")
        HoverButton(btn_box, "Start All", self._start_all,
                    color=C.GREEN, hover=C.GREEN_DIM,
                    width=84, height=28, font_size=9).pack(side="right", padx=(8, 0))
        HoverButton(btn_box, "Stop All", self._stop_all,
                    color=C.RED_DIM, hover=C.RED,
                    width=84, height=28, font_size=9).pack(side="right")

    def _build_cards(self, parent):
        row = tk.Frame(parent, bg=C.BG)
        row.pack(fill="x", pady=(0, 12))
        for idx, server in enumerate((self.backend, self.frontend)):
            pad = (0, 6) if idx == 0 else (6, 0)
            self._build_card(row, server, pad)

    def _build_card(self, parent, server, padx):
        card = tk.Frame(parent, bg=C.BG_CARD,
                        highlightbackground=C.BORDER, highlightthickness=1)
        card.pack(side="left", fill="both", expand=True, padx=padx)

        # ─ top row: dot + name + status label
        top = tk.Frame(card, bg=C.BG_CARD)
        top.pack(fill="x", padx=16, pady=(14, 2))

        dot = PulseDot(top)
        dot.pack(side="left", padx=(0, 8))

        label_text = "Django" if server is self.backend else "Vite"
        tk.Label(top, text=label_text, bg=C.BG_CARD, fg=C.TEXT,
                 font=(FONT_UI, 13, "bold")).pack(side="left")

        status = tk.Label(top, text="Stopped", bg=C.BG_CARD, fg=C.RED,
                          font=(FONT_UI, 10))
        status.pack(side="right")

        # ─ subtitle row: port + health + uptime
        sub = tk.Frame(card, bg=C.BG_CARD)
        sub.pack(fill="x", padx=16, pady=(0, 2))

        tk.Label(sub, text=f":{server.port}", bg=C.BG_CARD, fg=C.TEXT_MUTED,
                 font=(FONT_MONO, 9)).pack(side="left")

        port_ind = tk.Label(sub, text="", bg=C.BG_CARD, fg=C.TEXT_MUTED,
                            font=(FONT_MONO, 9))
        port_ind.pack(side="left", padx=(10, 0))

        uptime = tk.Label(sub, text="", bg=C.BG_CARD, fg=C.TEXT_MUTED,
                          font=(FONT_MONO, 9))
        uptime.pack(side="right")

        # ─ button row
        btn_row = tk.Frame(card, bg=C.BG_CARD)
        btn_row.pack(fill="x", padx=16, pady=(8, 14))

        start_btn = HoverButton(
            btn_row, "\u25b6  Start", lambda s=server: self._start(s),
            color=C.GREEN, hover=C.GREEN_DIM, width=84, height=30)
        start_btn.pack(side="left", padx=(0, 6))

        stop_btn = HoverButton(
            btn_row, "\u25a0  Stop", lambda s=server: self._stop(s),
            color=C.RED_DIM, hover=C.RED, width=76, height=30)
        stop_btn.pack(side="left", padx=(0, 6))

        restart_btn = HoverButton(
            btn_row, "\u21bb", lambda s=server: self._restart(s),
            color=C.BORDER, hover=C.BORDER_LIGHT, width=30, height=30, font_size=12)
        restart_btn.pack(side="left")

        self._ui[server.name] = {
            "dot": dot, "status": status, "uptime": uptime,
            "port_ind": port_ind,
            "start_btn": start_btn, "stop_btn": stop_btn,
            "restart_btn": restart_btn,
        }

    def _build_log_section(self, parent):
        section = tk.Frame(parent, bg=C.BG)
        section.pack(fill="both", expand=True)

        # ─ tab bar
        tab_bar = tk.Frame(section, bg=C.BG_SURFACE)
        tab_bar.pack(fill="x")

        self._tab_backend = tk.Label(
            tab_bar, text="  Backend  ", bg=C.ACCENT, fg=C.TEXT,
            font=(FONT_UI, 10, "bold"), padx=12, pady=5, cursor="hand2")
        self._tab_backend.pack(side="left")
        self._tab_backend.bind("<Button-1>", lambda _: self._switch_tab("backend"))

        self._tab_frontend = tk.Label(
            tab_bar, text="  Frontend  ", bg=C.BG_CARD, fg=C.TEXT_DIM,
            font=(FONT_UI, 10, "bold"), padx=12, pady=5, cursor="hand2")
        self._tab_frontend.pack(side="left")
        self._tab_frontend.bind("<Button-1>", lambda _: self._switch_tab("frontend"))

        # Right-side controls
        ctrl = tk.Frame(tab_bar, bg=C.BG_SURFACE)
        ctrl.pack(side="right", padx=8)

        self._scroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            ctrl, text="Auto-scroll", variable=self._scroll_var,
            bg=C.BG_SURFACE, fg=C.TEXT_DIM, selectcolor=C.BG_CARD,
            activebackground=C.BG_SURFACE, activeforeground=C.TEXT,
            font=(FONT_UI, 9), command=self._toggle_scroll,
        ).pack(side="right")

        HoverButton(ctrl, "Clear", self._clear_logs,
                    color=C.BORDER, hover=C.BORDER_LIGHT,
                    width=50, height=22, font_size=8).pack(side="right", padx=(0, 10))

        # ─ log container
        self._log_container = tk.Frame(
            section, bg=C.BG_LOG,
            highlightbackground=C.BORDER, highlightthickness=1)
        self._log_container.pack(fill="both", expand=True, pady=(2, 0))

        self._backend_frame, self._backend_text = self._create_log(self._log_container)
        self._frontend_frame, self._frontend_text = self._create_log(self._log_container)

        self._backend_frame.pack(fill="both", expand=True)
        self._active_tab = "backend"

    def _create_log(self, parent):
        """Return (container_frame, text_widget)."""
        frame = tk.Frame(parent, bg=C.BG_LOG)
        text = tk.Text(
            frame, bg=C.BG_LOG, fg=C.TEXT_DIM, font=(FONT_MONO, 9),
            insertbackground=C.TEXT, relief="flat", wrap="word",
            state="disabled", padx=10, pady=8,
            selectbackground=C.ACCENT_DEEP, selectforeground=C.TEXT,
            borderwidth=0,
        )
        scrollbar = tk.Scrollbar(
            frame, command=text.yview, bg=C.BG,
            troughcolor=C.BG_LOG, bd=0, highlightthickness=0)
        text["yscrollcommand"] = scrollbar.set
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        return frame, text

    def _build_footer(self, parent):
        footer = tk.Frame(parent, bg=C.BG)
        footer.pack(fill="x", pady=(10, 0))
        HoverButton(footer, "Open Browser", self._open_browser,
                    color=C.ACCENT, hover=C.ACCENT_DIM,
                    width=112, height=32).pack(side="right")
        HoverButton(footer, "Open Terminal", self._open_terminal,
                    color=C.BORDER, hover=C.BORDER_LIGHT,
                    width=110, height=32).pack(side="right", padx=(0, 8))

    # ── Server actions ──────────────────────────────────────────

    def _start(self, server):
        server.start()
        w = self._ui[server.name]
        w["status"].config(text="Starting\u2026", fg=C.YELLOW)
        w["dot"].set(C.YELLOW, pulse=True)

    def _stop(self, server):
        server.stop()
        w = self._ui[server.name]
        w["status"].config(text="Stopped", fg=C.RED)
        w["dot"].set(C.RED, pulse=False)
        w["uptime"].config(text="")

    def _restart(self, server):
        if server._restarting:
            return
        server._restarting = True
        server._cancel_restart = False
        w = self._ui[server.name]
        w["status"].config(text="Restarting\u2026", fg=C.YELLOW)
        w["dot"].set(C.YELLOW, pulse=True)

        def _do():
            server.stop()
            time.sleep(0.5)
            server._restarting = False
            if not server._cancel_restart:
                server.start()

        threading.Thread(target=_do, daemon=True).start()

    def _start_all(self):
        self._start(self.backend)
        self._start(self.frontend)

    def _stop_all(self):
        self._stop(self.backend)
        self._stop(self.frontend)

    # ── Tab switching ───────────────────────────────────────────

    def _switch_tab(self, which):
        if which == self._active_tab:
            return
        # Hide current
        if self._active_tab == "backend":
            self._backend_frame.pack_forget()
        else:
            self._frontend_frame.pack_forget()

        # Show target
        if which == "backend":
            self._backend_frame.pack(fill="both", expand=True)
            self._tab_backend.config(bg=C.ACCENT, fg=C.TEXT)
            self._tab_frontend.config(bg=C.BG_CARD, fg=C.TEXT_DIM)
        else:
            self._frontend_frame.pack(fill="both", expand=True)
            self._tab_frontend.config(bg=C.ACCENT, fg=C.TEXT)
            self._tab_backend.config(bg=C.BG_CARD, fg=C.TEXT_DIM)

        self._active_tab = which

    # ── Polling loops (run on the tkinter main thread) ──────────

    def _poll_logs(self):
        pairs = [
            (self.backend, self._backend_text),
            (self.frontend, self._frontend_text),
        ]
        for server, text_widget in pairs:
            # Drain queue into a batch
            lines = []
            try:
                while True:
                    lines.append(server.log_queue.get_nowait())
            except queue.Empty:
                pass

            if lines:
                text_widget.configure(state="normal")
                for line in lines:
                    text_widget.insert("end", line)
                text_widget.configure(state="disabled")
                if self._auto_scroll:
                    text_widget.see("end")

            # Trim to prevent unbounded growth
            total = int(text_widget.index("end-1c").split(".")[0])
            if total > self.MAX_LOG_LINES:
                text_widget.configure(state="normal")
                text_widget.delete("1.0", f"{total - self.MAX_LOG_LINES}.0")
                text_widget.configure(state="disabled")

            # Sync status labels from server state
            w = self._ui.get(server.name)
            if not w:
                continue
            restarting = server._restarting
            current = w["status"].cget("text")

            if server.running and not restarting and current != "Running":
                w["status"].config(text="Running", fg=C.GREEN)
                w["dot"].set(C.GREEN, pulse=True)
            elif not server.running and not restarting and current != "Stopped":
                w["status"].config(text="Stopped", fg=C.RED)
                w["dot"].set(C.RED, pulse=False)
                w["uptime"].config(text="")

        self.root.after(100, self._poll_logs)

    def _poll_uptime(self):
        for server in (self.backend, self.frontend):
            w = self._ui.get(server.name)
            if w and server.running:
                w["uptime"].config(text=server.uptime)
        self.root.after(1000, self._poll_uptime)

    def _poll_port(self):
        for server in (self.backend, self.frontend):
            w = self._ui.get(server.name)
            if w and server.port:
                if server.running:
                    ok = _port_open(server.port)
                    w["port_ind"].config(
                        text="\u25cf listening" if ok else "\u25cb pending",
                        fg=C.GREEN if ok else C.YELLOW,
                    )
                else:
                    w["port_ind"].config(text="")
        self.root.after(2000, self._poll_port)

    # ── Misc actions ────────────────────────────────────────────

    def _toggle_scroll(self):
        self._auto_scroll = self._scroll_var.get()

    def _clear_logs(self):
        for widget in (self._backend_text, self._frontend_text):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")

    def _open_browser(self):
        import webbrowser
        webbrowser.open("http://localhost:5173")

    def _open_terminal(self):
        cwd = str(PROJECT_DIR)
        if sys.platform == "win32":
            subprocess.Popen(["cmd"], cwd=cwd)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Terminal", cwd])
        else:
            subprocess.Popen(["x-terminal-emulator"], cwd=cwd)

    def _on_close(self):
        self.backend.stop()
        self.frontend.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
