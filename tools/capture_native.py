"""Capture actual native widgets from a disposable fixture, not the user's database."""
import argparse
import ctypes
import hashlib
import platform
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

def capture_stable(root,path):
    """Require consecutive identical real RGB frames; do not mask pixels."""
    previous=None
    for attempt in range(1,9):
        until=time.monotonic()+.2
        while time.monotonic()<until:
            root.update()
            time.sleep(.025)
        im=capture(root,path)
        digest=hashlib.sha256(im.tobytes()).hexdigest()
        if digest==previous:
            return im,{"rgb_sha256":digest,"stable_frames":2,"attempts":attempt}
        previous=digest
    raise RuntimeError(f"Unstable native RGB capture: {path.name}")


def capture_dialog(root,open_dialog,path):
    before=set(root.winfo_children())
    open_dialog()
    def visible():
        return [child for child in root.winfo_children() if child not in before
                and isinstance(child,tk.Toplevel) and child.winfo_viewable()]
    wait(root,visible)
    dialog=visible()[0]
    try:
        until=time.monotonic()+.35
        while time.monotonic()<until:
            root.update()
            time.sleep(.025)
        im,evidence=capture_stable(dialog,path)
        if im.size!=(dialog.winfo_width(),dialog.winfo_height()):
            raise RuntimeError(f"Native dialog viewport mismatch: {path.name}: {im.size}")
        return {"dialog":path.stem,"capture":list(im.size),**evidence}
    finally:
        dialog.destroy()
        root.update()

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
        root=tk.Tk()
        original_scaling=float(root.tk.call("tk","scaling"))
        root.tk.call("tk","scaling",96/72)
        app=Desktop(root,Path(tmp))
        try:
            w,h=width,height
            if sys.platform=="win32":
                # ImageGrab(window=...) captures the actual window, not the
                # visible desktop. Allow the client to exceed a hosted
                # runner's display, while verifying the real client geometry.
                root.maxsize(max(w,root.winfo_screenwidth()),max(h,root.winfo_screenheight()))
            elif w>root.winfo_screenwidth()-80 or h>root.winfo_screenheight()-100:
                raise ValueError("Requested viewport exceeds available screen.")
            root.geometry(f"{w}x{h}+30+30")
            wait(root,lambda:root.winfo_width()==w and root.winfo_height()==h)
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
                im,evidence=capture_stable(root,output/(key+".png"))
                if im.size!=(width,height):
                    raise RuntimeError(f"Native viewport mismatch: {key}: {im.size} != {(width,height)}")
                report.append({"view":key,"capture":list(im.size),**evidence})
            dialogs=output/"dialogs"
            dialogs.mkdir(exist_ok=True)
            rows=app.client.request("/api/companies",{"limit":1})["rows"]
            company=app.client.request(f"/api/company/{rows[0]['id']}")
            dialog_report=[]
            for key,action in (("profile",lambda:app.profile(company)),
                               ("backup",app.backup_dialog),("sync",app.sync_dialog)):
                dialog_report.append(capture_dialog(root,action,dialogs/(key+".png")))
            for w,h in ((960,600),(800,540),(640,420)):
                if sys.platform!="win32" and (w>root.winfo_screenwidth()-50 or h>root.winfo_screenheight()-80):continue
                root.geometry(f"{w}x{h}+30+30")
                wait(root,lambda:root.winfo_width()==w and root.winfo_height()==h)
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
                    except RuntimeError as error:
                        raise RuntimeError(
                            f"Unreachable content: {key} {w}x{h}; "
                            f"bounds={app.viewport.bbox(app.content_window)}, "
                            f"requested={(app.content.winfo_reqwidth(),app.content.winfo_reqheight())}, "
                            f"sidebar={app.sidebar.winfo_height()}, "
                            f"nav={[(k,b.winfo_ismapped(),b.winfo_y(),b.winfo_height()) for k,b in app.nav.items()]}"
                        ) from error
                print(f"All seven views accessible via viewport at {w}x{h}",flush=True)
            (output/"capture.json").write_text(json.dumps({"captures":report,"dialogs":dialog_report,"platform":sys.platform,"os_version":platform.platform(),"tk_version":root.tk.call("info","patchlevel"),"original_scaling":original_scaling,"requested_dpi":96,"font_family":app.font_family,"tk_scaling":float(root.tk.call("tk","scaling"))},indent=2),encoding="utf-8")
            print(json.dumps(report,indent=2),flush=True)
        finally:
            app.smoke=True  # Disposable fixture: never block CI on a close-confirmation dialog.
            app.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("output",type=Path)
    p.add_argument("--width",type=int,default=1280);p.add_argument("--height",type=int,default=700)
    args=p.parse_args();run(args.output,args.width,args.height)
