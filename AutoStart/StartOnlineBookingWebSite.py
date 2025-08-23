# C:\wanderers_web\AutoStart\StartOnlineBookingWebSite.py
# Tray launcher for Wanderers Web (runs Waitress under logged-in user)
# Requires: pystray, Pillow

import os, sys, time, threading, subprocess, webbrowser, shutil
from datetime import datetime
import pystray
from PIL import Image, ImageDraw

BASE_DIR      = r"C:\wanderers_web"                      # your app root; must contain run.py (exporting app)
AUTOSTART_DIR = os.path.join(BASE_DIR, "AutoStart")
LOG_DIR       = os.path.join(AUTOSTART_DIR, "logs")
URL           = "http://localhost:8181"

# Logging limits
MAX_TRAY_LOG_SIZE      = 1 * 1024 * 1024   # 1 MB for tray_launcher.log
MAX_WAITRESS_LOG_SIZE  = 10 * 1024 * 1024  # 10 MB for waitress.*.log

# persistent flag file for logging
LOG_FLAG_FILE = os.path.join(AUTOSTART_DIR, "logging_enabled.flag")

WAITRESS_ARGS = [
    "--host=0.0.0.0",
    "--port=8181",
    "--threads=12",
    "--backlog=2048",
    "--recv-bytes=16384",
    "--send-bytes=32768",
    "run:app",
]

_proc = None
_icon = None
_status = "stopped"   # starting|running|stop_pending|stopped|error|restarting
_status_lock = threading.Lock()
_stop_event = threading.Event()
LOGGING_ENABLED = False  # DEFAULT: logging disabled

# Keep references to log file handles so we can close them before deleting
_log_out_handle = None
_log_err_handle = None

def ensure_dirs():
    os.makedirs(LOG_DIR, exist_ok=True)

def _truncate_if_too_large(path: str, limit_bytes: int):
    """If file exceeds limit_bytes, clear it."""
    try:
        if os.path.exists(path) and os.path.getsize(path) > limit_bytes:
            open(path, "w").close()
    except Exception:
        pass

def _read_logging_flag():
    """Load persisted logging state; default OFF if flag absent/bad."""
    global LOGGING_ENABLED
    try:
        if os.path.exists(LOG_FLAG_FILE):
            val = open(LOG_FLAG_FILE, "r", encoding="utf-8", errors="ignore").read().strip()
            LOGGING_ENABLED = (val == "1")
        else:
            LOGGING_ENABLED = False
    except Exception:
        LOGGING_ENABLED = False

def _write_logging_flag():
    try:
        with open(LOG_FLAG_FILE, "w", encoding="utf-8", errors="ignore") as f:
            f.write("1" if LOGGING_ENABLED else "0")
    except Exception:
        pass

def log_line(msg):
    """Append one line to tray_launcher.log, with 1MB cap."""
    ensure_dirs()
    tray_log = os.path.join(LOG_DIR, "tray_launcher.log")
    _truncate_if_too_large(tray_log, MAX_TRAY_LOG_SIZE)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(tray_log, "a", encoding="utf-8", errors="ignore") as f:
            f.write(f"[{stamp}] {msg}\n")
    except Exception:
        pass

def set_status(s):
    global _status
    with _status_lock:
        _status = s
    try:
        if _icon:
            _icon.title = f"Wanderers Web — {s}"
            _icon.update_menu()
    except Exception:
        pass

def is_running():
    with _status_lock:
        return _status == "running"

def is_stopped_like():
    with _status_lock:
        return _status in ("stopped", "error")

def colour_for_status():
    with _status_lock:
        s = _status
    if s == "running": return (0,180,0,255)
    if s in ("starting","stop_pending","restarting"): return (220,140,0,255)
    if s in ("stopped","error"): return (200,0,0,255)
    return (120,120,120,255)

def make_icon(colour):
    img = Image.new("RGBA",(16,16),(0,0,0,0))
    d = ImageDraw.Draw(img)
    d.ellipse((1,1,15,15), fill=colour)
    return img

def refresh_icon():
    if _icon:
        _icon.icon = make_icon(colour_for_status())

def waitress_cmd():
    if shutil.which("waitress-serve"):
        return ["waitress-serve"] + WAITRESS_ARGS
    py = sys.executable or "python"
    return [py, "-m", "waitress"] + WAITRESS_ARGS

def _safe_delete(path, attempts=6, delay=0.15):
    for _ in range(attempts):
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception:
            time.sleep(delay)
    return False

def _delete_waitress_logs():
    """Delete existing waitress logs (with small retry to handle AV/locks)."""
    for fn in ("waitress.out.log", "waitress.err.log"):
        _safe_delete(os.path.join(LOG_DIR, fn))

def _open_logs_handles():
    """Create stdout/stderr handles per LOGGING_ENABLED, with 10MB caps on waitress logs."""
    try:
        if LOGGING_ENABLED:
            ensure_dirs()
            out_path = os.path.join(LOG_DIR, "waitress.out.log")
            err_path = os.path.join(LOG_DIR, "waitress.err.log")
            _truncate_if_too_large(out_path, MAX_WAITRESS_LOG_SIZE)
            _truncate_if_too_large(err_path, MAX_WAITRESS_LOG_SIZE)
            out = open(out_path, "a", encoding="utf-8", errors="ignore")
            err = open(err_path, "a", encoding="utf-8", errors="ignore")
        else:
            out = open(os.devnull, "a")
            err = open(os.devnull, "a")
        return out, err
    except Exception:
        return open(os.devnull, "a"), open(os.devnull, "a")

def start_server():
    """Start waitress if not already running."""
    global _proc, _log_out_handle, _log_err_handle
    if _proc and _proc.poll() is None:
        set_status("running"); return
    set_status("starting"); refresh_icon()
    cmd = waitress_cmd()
    _log_out_handle, _log_err_handle = _open_logs_handles()
    log_line(f"Starting: {' '.join(cmd)} (cwd={BASE_DIR}, logging={'ON' if LOGGING_ENABLED else 'OFF'})")
    try:
        _proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=_log_out_handle,
            stderr=_log_err_handle,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        set_status("running"); refresh_icon()
    except Exception as e:
        log_line(f"ERROR starting waitress: {e!r}")
        set_status("error"); refresh_icon()

def _close_log_handles():
    global _log_out_handle, _log_err_handle
    for h in (_log_out_handle, _log_err_handle):
        try:
            if h and not h.closed:
                h.close()
        except Exception:
            pass
    _log_out_handle = None
    _log_err_handle = None

def stop_server():
    """Stop waitress and close log handles so files can be deleted."""
    global _proc
    if _proc and _proc.poll() is None:
        set_status("stop_pending"); refresh_icon()
        try:
            _proc.terminate()
            for _ in range(50):
                if _proc.poll() is not None: break
                time.sleep(0.1)
            if _proc.poll() is None:
                _proc.kill()
        except Exception as e:
            log_line(f"ERROR stopping waitress: {e!r}")
    _proc = None
    _close_log_handles()
    set_status("stopped"); refresh_icon()

def restart_server(icon=None, item=None):
    set_status("restarting"); refresh_icon()
    stop_server()
    time.sleep(0.4)
    start_server()

def toggle_logging(icon=None, item=None):
    """Toggle logging. Always stop -> delete logs -> start. Also persists flag."""
    global LOGGING_ENABLED
    LOGGING_ENABLED = not LOGGING_ENABLED
    _write_logging_flag()
    stop_server()
    _delete_waitress_logs()
    log_line(f"Logging toggled {'ON' if LOGGING_ENABLED else 'OFF'}; logs cleared; restarting.")
    start_server()

def start_menu_action(icon=None, item=None):
    """Manual start from tray."""
    if is_stopped_like():
        start_server()

def stop_menu_action(icon=None, item=None):
    """Manual stop from tray."""
    if is_running():
        stop_server()

def open_site(icon=None, item=None):
    try:
        webbrowser.open(URL)
    except Exception:
        pass

def open_logs(icon=None, item=None):
    ensure_dirs()
    try:
        os.startfile(LOG_DIR)
    except Exception:
        pass

def exit_app(icon=None, item=None):
    _stop_event.set()
    stop_server()
    try:
        icon.stop()
    except Exception:
        pass

def watchdog():
    while not _stop_event.is_set():
        p = _proc
        if p and p.poll() is not None:
            log_line("Waitress exited. Auto-restarting in 2s.")
            set_status("restarting"); refresh_icon()
            time.sleep(2)
            start_server()
        time.sleep(1.0)

def icon_menu():
    from pystray import Menu, MenuItem
    return Menu(
        MenuItem("Open site", open_site, default=True),
        MenuItem("Start server", start_menu_action,
                 enabled=lambda item: is_stopped_like()),
        MenuItem("Restart server", restart_server),
        MenuItem("Stop server", stop_menu_action,
                 enabled=lambda item: is_running()),
        MenuItem("Open logs folder", open_logs),
        MenuItem(
            "Enable logging",
            toggle_logging,
            checked=lambda item: LOGGING_ENABLED
        ),
        MenuItem("Exit", exit_app),
    )

def main():
    global _icon
    ensure_dirs()
    _read_logging_flag()
    # Clean up stale waitress logs regardless of initial state
    _delete_waitress_logs()
    # Start server automatically on tray start
    start_server()
    threading.Thread(target=watchdog, daemon=True).start()
    _icon = pystray.Icon(name="Wanderers Web", title=f"Wanderers Web — {_status}",
                         icon=make_icon(colour_for_status()), menu=icon_menu())
    _icon.run()

if __name__ == "__main__":
    # prevent duplicate instances
    lock_path = os.path.join(AUTOSTART_DIR, "StartOnlineBookingWebSite.lock")
    try:
        if os.path.exists(lock_path) and (time.time() - os.path.getmtime(lock_path) < 86400):
            sys.exit(0)
        with open(lock_path, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    try:
        main()
    finally:
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass
