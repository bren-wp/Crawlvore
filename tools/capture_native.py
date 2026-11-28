"""Capture actual native widgets from a disposable fixture, not the user's database."""
import argparse
import ctypes
import os
import sys
import tempfile
import time
from pathlib import Path
import tkinter as tk
from PIL import ImageGrab, ImageStat

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from native_desktop import Desktop
from core import Store

def wait(root,predicate,timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        root.update()
        if predicate():return
        time.sleep(.025)
    raise RuntimeError("Native view did not become ready")

def capture(root,path):
    root.update()
    if sys.platform=="win32":
        hwnd=ctypes.windll.user32.GetAncestor(root.winfo_id(),2)
        if not hwnd:raise RuntimeError("Window handle not available")
        im=ImageGrab.grab(window=hwnd).convert("RGB")
        # Keep real client pixels, excluding only the OS title bar and border.
        from ctypes import wintypes
        rect=wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd,ctypes.byref(rect)):raise RuntimeError("Window bounds unavailable")
        if im.size==(rect.right-rect.left,rect.bottom-rect.top):
            x,y=root.winfo_rootx()-rect.left,root.winfo_rooty()-rect.top
            w,h=root.winfo_width(),root.winfo_height()
            if x>=0 and y>=0 and x+w<=im.width and y+h<=im.height:im=im.crop((x,y,x+w,y+h))
    elif sys.platform.startswith("linux"):
        if not root.winfo_viewable() or not os.environ.get("DISPLAY"):
            raise RuntimeError("Mapped X11 window required for native capture")
        x,y=root.winfo_rootx(),root.winfo_rooty()
        w,h=root.winfo_width(),root.winfo_height()
        im=ImageGrab.grab(bbox=(x,y,x+w,y+h),xdisplay=os.environ["DISPLAY"]).convert("RGB")
    else:
        raise RuntimeError("Unsupported native screenshot platform")
    if min(im.size)<200 or max(ImageStat.Stat(im).stddev)<5:raise RuntimeError("Empty window capture")
    im.save(path)
    return im

def run(output,width=1280,height=700):
    if sys.platform!="win32" and not sys.platform.startswith("linux"):raise RuntimeError("Windows or X11 required.")
    output.mkdir(parents=True,exist_ok=True)
    for name in list(os.environ):
        if name.startswith(("SUDREG_","CRAWLVORA_")):os.environ.pop(name,None)
    with tempfile.TemporaryDirectory(prefix="tvrtke-native-capture-") as tmp:
        store=Store(Path(tmp)/"companies.sqlite3")
        with store.db() as conn:
            for index,name in enumerate(("Atlas Demo","Birch Demo","Cedar Demo","Delta Demo","Elm Demo","Fjord Demo")):
                store.upsert(conn,{"title":name,"city":("Zagreb","Rijeka","Split")[index%3],
                                    "website":"https://example.invalid","entity_kind":"company","email":"kontakt@example.invalid" if index==0 else ""})
            conn.execute("INSERT INTO meta(key,value) VALUES ('seeded','1')")
        root=tk.Tk();app=Desktop(root,Path(tmp))
        try:
            w,h=width,height
            if w>root.winfo_screenwidth()-80 or h>root.winfo_screenheight()-100:raise ValueError("Requested viewport exceeds available screen.")
            root.geometry(f"{w}x{h}+30+30")
            wait(root,lambda:app.metric_values["total"].get()=="6")
            steps=[("overview",lambda:app.metric_values["total"].get()=="6"),("directory",lambda:app.total==6),
                   ("jobs",lambda:app.job_metrics.get()!="—"),("data",lambda:app.import_button.winfo_ismapped()),
                   ("analytics",lambda:app.analytics_values["total"].get()=="6"),("registry",lambda:app.registry_values["runs"].get()=="0"),
                   ("settings",lambda:app.access_status.get() in ("Pristup omogućen","Pristup nije omogućen"))]
            import json
            report=[]
            for key,ready in steps:
                app.show_view(key)
                wait(root,ready)
                until=time.monotonic()+.2
                while time.monotonic()<until:root.update();time.sleep(.02)
                im=capture(root,output/(key+".png"))
                if im.size!=(width,height):
                    raise RuntimeError(f"Native viewport mismatch: {key}: {im.size} != {(width,height)}")
                report.append({"view":key,"capture":list(im.size)})
            for w,h in ((960,600),(800,540),(640,420)):
                if w>root.winfo_screenwidth()-50 or h>root.winfo_screenheight()-80:continue
                root.geometry(f"{w}x{h}+30+30")
                for key,_ in steps:
                    app.show_view(key)
                    until=time.monotonic()+.15
                    while time.monotonic()<until:root.update();time.sleep(.02)
                    def reachable():
                        box=app.viewport.bbox(app.content_window)
                        return (not root.attributes("-fullscreen") and box and box[2]>=app.content.winfo_reqwidth()
                                and box[3]>=app.content.winfo_reqheight()
                                and all(b.winfo_ismapped() and b.winfo_height()>15 and b.winfo_y()+b.winfo_height()<=app.sidebar.winfo_height() for b in app.nav.values()))
                    try:wait(root,reachable,timeout=3)
                    except RuntimeError as error:raise RuntimeError(f"Unreachable content: {key} {w}x{h}") from error
                print(f"All seven views accessible via viewport at {w}x{h}",flush=True)
            (output/"capture.json").write_text(json.dumps({"captures":report,"platform":sys.platform,"font_family":app.font_family,"tk_scaling":float(root.tk.call("tk","scaling"))},indent=2),encoding="utf-8")
            print(json.dumps(report,indent=2),flush=True)
        finally:
            app.smoke=True  # Disposable fixture: never block CI on a close-confirmation dialog.
            app.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("output",type=Path)
    p.add_argument("--width",type=int,default=1280);p.add_argument("--height",type=int,default=700)
    args=p.parse_args();run(args.output,args.width,args.height)
