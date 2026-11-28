"""Configure a disposable Windows CI desktop for fully visible RGB capture."""
import ctypes
import sys
from ctypes import wintypes


class DisplayMode(ctypes.Structure):
    _fields_=[
        ("device",wintypes.WCHAR*32),("spec",wintypes.WORD),
        ("driver",wintypes.WORD),("size",wintypes.WORD),("extra",wintypes.WORD),
        ("fields",wintypes.DWORD),("position_x",wintypes.LONG),
        ("position_y",wintypes.LONG),("orientation",wintypes.DWORD),
        ("fixed_output",wintypes.DWORD),("color",wintypes.SHORT),
        ("duplex",wintypes.SHORT),("y_resolution",wintypes.SHORT),
        ("tt_option",wintypes.SHORT),("collate",wintypes.SHORT),
        ("form_name",wintypes.WCHAR*32),("log_pixels",wintypes.WORD),
        ("bits_per_pixel",wintypes.DWORD),("width",wintypes.DWORD),
        ("height",wintypes.DWORD),("display_flags",wintypes.DWORD),
        ("frequency",wintypes.DWORD),("icm_method",wintypes.DWORD),
        ("icm_intent",wintypes.DWORD),("media_type",wintypes.DWORD),
        ("dither_type",wintypes.DWORD),("reserved1",wintypes.DWORD),
        ("reserved2",wintypes.DWORD),("panning_width",wintypes.DWORD),
        ("panning_height",wintypes.DWORD),
    ]


def main():
    if sys.platform!="win32":
        raise RuntimeError("Windows display setup requires Windows")
    import os
    if os.environ.get("GITHUB_ACTIONS")!="true":
        raise RuntimeError("Display changes are restricted to disposable CI runners")
    user=ctypes.WinDLL("user32",use_last_error=True)
    user.SetProcessDPIAware()
    user.EnumDisplaySettingsW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,ctypes.POINTER(DisplayMode)]
    user.ChangeDisplaySettingsW.argtypes=[ctypes.POINTER(DisplayMode),wintypes.DWORD]
    user.ChangeDisplaySettingsW.restype=wintypes.LONG
    current=DisplayMode()
    current.size=ctypes.sizeof(current)
    if not user.EnumDisplaySettingsW(None,0xffffffff,ctypes.byref(current)):
        raise RuntimeError("Cannot read Windows display mode")
    print(f"Current display: {current.width}x{current.height}",flush=True)
    if current.width>=1360 and current.height>=800:
        return
    candidates=[]
    for index in range(1024):
        mode=DisplayMode()
        mode.size=ctypes.sizeof(mode)
        if not user.EnumDisplaySettingsW(None,index,ctypes.byref(mode)):
            break
        if mode.width>=1360 and mode.height>=800 and mode.bits_per_pixel>=24:
            candidates.append(mode)
    for mode in sorted(candidates,key=lambda m:(m.width*m.height,-m.bits_per_pixel,-m.frequency)):
        # Test first; apply to this session only, never update the registry.
        if user.ChangeDisplaySettingsW(ctypes.byref(mode),2)!=0:
            continue
        if user.ChangeDisplaySettingsW(ctypes.byref(mode),0)==0:
            print(f"Selected display: {mode.width}x{mode.height}",flush=True)
            return
    raise RuntimeError("No supported Windows display mode can fit the reference viewport")


if __name__=="__main__":
    main()
