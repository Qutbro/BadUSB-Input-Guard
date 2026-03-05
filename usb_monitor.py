import time
import re
import win32com.client
import pythoncom


def extract_vid_pid(device_id):
    match = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", device_id)
    if match:
        return match.group(1), match.group(2)
    return None


def monitor_usb(whitelist, usb_state, timing_state, on_device_removed, log):

    pythoncom.CoInitialize()
    wmi = win32com.client.GetObject(r"winmgmts:\\.\root\cimv2")

    known = set()
    log("[INFO] USB monitor started")


    while True:
        current = set()

        for dev in wmi.InstancesOf("Win32_PnPEntity"):
            if not dev.DeviceID.startswith("USB"):
                continue

            vp = extract_vid_pid(dev.DeviceID)
            if not vp:
                continue

            current.add(vp)

            if vp not in known:
                log(f"[USB CONNECTED] VID={vp[0]} PID={vp[1]} | {dev.Name}")

                if vp not in whitelist:
                    log("[INFO] Device NOT in whitelist → monitoring input")
                    usb_state["current_device"] = vp
                    usb_state["suspicious"] = False
                else:
                    print("[INFO] Device is trusted")

        removed = known - current
        if removed:
            for vp in removed:
                if usb_state["current_device"] == vp:
                    on_device_removed()
                    usb_state["current_device"] = None
                    timing_state["detected"] = False
                    timing_state["min_delta"] = None

        known = current
        time.sleep(1)
