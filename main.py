import threading
import ui

from pynput import keyboard as pynput_keyboard

from config import load_whitelist, MIN_ALLOWED_DELTA as DEFAULT_MIN_DELTA
from usb_monitor import monitor_usb
from timing_detector import update_timing_state
from input_blocker import (
    install_keyboard_blocker,
    enable_keyboard_block,
    disable_keyboard_block,
    release_all_modifiers,
)
from ui import (
    start_ui,
    log,
    set_status_active,
    set_status_alert,
    set_status_blocked,
    show_badusb_alert,
)


# ==================================================
# GLOBAL CONFIG (runtime)
# ==================================================

MIN_ALLOWED_DELTA = DEFAULT_MIN_DELTA

# ==================================================
# STATE
# ==================================================

usb_state = {
    "current_device": None,   # (VID, PID)
    "suspicious": False,
}

timing_state = {
    "last_time": None,
    "last_key": None,
    "min_delta": None,
    "detected": False,
}

# ==================================================
# LOAD CONFIG
# ==================================================

WHITELIST = load_whitelist()

# ==================================================
# UI → BACKEND CALLBACKS
# ==================================================

def handle_threshold_change(value: float):
    """
    Обновление порога минимального интервала ввода
    """
    global MIN_ALLOWED_DELTA
    MIN_ALLOWED_DELTA = value
    log(f"[CONFIG] Minimal allowed delta updated to {value:.6f} s")


# регистрируем callback в UI
ui.on_threshold_changed = handle_threshold_change

# ==================================================
# USB CALLBACKS
# ==================================================

def on_device_removed():
    """
    Вызывается при физическом отключении подозрительного USB
    """
    log("[USB REMOVED] Device disconnected")

    disable_keyboard_block()
    release_all_modifiers()

    set_status_active()

    timing_state.update(
        last_time=None,
        last_key=None,
        min_delta=None,
        detected=False,
    )

    usb_state.update(
        current_device=None,
        suspicious=False,
    )

# ==================================================
# KEYBOARD HANDLER
# ==================================================

def on_key_press(key):
    """
    Тайминг-детектор ввода
    """
    if not usb_state["current_device"]:
        return

    delta = update_timing_state(key, timing_state)
    if delta is None:
        return

    min_d = timing_state["min_delta"]
    # log(f"delta={delta:.6f} | min={min_d if min_d else 'n/a'}")

    if (
        min_d is not None
        and min_d < MIN_ALLOWED_DELTA
        and not timing_state["detected"]
    ):
        timing_state["detected"] = True
        usb_state["suspicious"] = True

        log("[ALERT] Possible BadUSB detected")
        set_status_alert()

        # 🔴 ВАЖНО: сначала отпускаем модификаторы
        release_all_modifiers()

        enable_keyboard_block()
        set_status_blocked()
        show_badusb_alert(usb_state["current_device"])
# ==================================================
# BACKEND STARTUP
# ==================================================

def start_backend():
    """
    Запуск всех фоновых компонентов
    """
    install_keyboard_blocker()

    usb_thread = threading.Thread(
        target=monitor_usb,
        args=(WHITELIST, usb_state, timing_state, on_device_removed, log),
        daemon=True,
    )
    usb_thread.start()

    keyboard_thread = threading.Thread(
        target=lambda: pynput_keyboard.Listener(
            on_press=on_key_press
        ).run(),
        daemon=True,
    )
    keyboard_thread.start()

    log("[INFO] Backend started")
    set_status_active()

# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    start_backend()
    start_ui()
