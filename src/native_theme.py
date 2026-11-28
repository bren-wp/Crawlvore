"""Shared native design tokens, no web renderer."""
import tkinter as tk
import math
import sys
from pathlib import Path
from tkinter import ttk, font as tkfont
from native_render import rounded_surface, stroke_icon, surface_color, gradient_bands, header_surface, card_corner, gradient_surface, dithered_gradient_surface, mix_rgb, dithered_card_corner

BG="#08131e";SIDE="#0b1724";PANEL="#101f2d";PANEL2="#182b3b";LINE="#2a4355"
TEXT="#edf4fa";MUTED="#a8bacb";ACCENT="#36ebba";INK="#05291f";ACTIVE="#103f39"

def nav_icon(root,key,color):
    segments=[]
    def line(x1,y1,x2,y2):
        segments.append((x1+.5,y1+.5,x2+.5,y2+.5))
    def rect(x,y,w,h):
        line(x,y,x+w,y);line(x+w,y,x+w,y+h);line(x+w,y+h,x,y+h);line(x,y+h,x,y)
    if key=="overview":
        for x in (2,11):
            for y in (2,11):rect(x,y,5,5)
    elif key=="directory":
        rect(3,3,7,14);rect(10,8,6,9)
        for y in (6,10,14):line(5,y,7,y)
        line(1,17,18,17)
    elif key=="jobs":
        rect(2,5,15,12);line(2,9,17,9);line(6,2,6,6);line(13,2,13,6)
    elif key=="data":
        line(2,6,17,6);line(13,2,17,6);line(13,10,17,6)
        line(17,14,2,14);line(6,10,2,14);line(6,18,2,14)
    elif key=="analytics":
        rect(2,12,3,6);rect(8,7,3,11);rect(14,2,3,16)
    elif key=="registry":
        line(2,7,9,2);line(9,2,17,7);line(2,7,17,7);line(2,17,17,17)
        for x in (4,9,14):line(x,8,x,15)
    else:
        points=((8,2),(11,2),(12,5),(15,5),(18,8),(15,11),(15,14),(12,15),(11,18),(8,18),(7,15),(4,15),(2,12),(4,9),(4,6),(7,5),(8,2))
        for start,end in zip(points,points[1:]):line(*start,*end)
        rect(7,7,5,5)
    return tk.PhotoImage(master=root,data=stroke_icon(tuple(segments),color))

def brand_surface(root):
    return tk.PhotoImage(master=root,data=rounded_surface(ACCENT,ACCENT,11,38))


def install(root):
    style=ttk.Style(root)
    style.theme_use("clam")
    available={name.casefold():name for name in tkfont.families(root)}
    family=next((available[name] for name in ("inter","segoe ui","noto sans","dejavu sans")
                 if name in available),tkfont.nametofont("TkDefaultFont",root=root).actual("family"))
    style.configure(".",background=BG,foreground=TEXT,fieldbackground=BG,font=(family,-13),bordercolor=LINE,lightcolor=LINE,darkcolor=LINE)
    for name,fill,fg in (("TButton",PANEL2,TEXT),("Accent.TButton",ACCENT,INK),
                         ("Nav.TButton",SIDE,TEXT),("Active.Nav.TButton",ACTIVE,ACCENT)):
        style.configure(name,background=fill,foreground=fg,padding=(11,9),
                        anchor="w" if "Nav" in name else "center",font=(family,-13 if "Nav" in name else -12,"bold"),borderwidth=1)
        style.map(name,foreground=[("disabled",MUTED),("active",fg)],background=[("active",fill)])
    style.configure("Upload.TFrame",background=BG,borderwidth=1,relief="solid")
    style.configure("Upload.TLabel",background=BG,foreground=TEXT)
    style.configure("UploadIcon.TLabel",background=BG,foreground=ACCENT,font=(family,-28,"bold"))
    style.configure("Header.TFrame",background=SIDE)
    style.configure("Header.TLabel",background=SIDE,foreground=MUTED)
    style.configure("HeaderTitle.TLabel",background=SIDE,foreground=TEXT,font=(family,-13,"bold"))
    style.configure("Small.TButton",padding=(10,6),font=(family,-12,"bold"))
    style.configure("Hint.TLabel",background=PANEL2,foreground=MUTED,padding=8,font=(family,-12))
    style.configure("Recent.Treeview",rowheight=36)
    style.configure("Card.TFrame",background=BG,borderwidth=0,relief="flat")
    style.configure("Panel.TFrame",background=PANEL,borderwidth=0,relief="flat")
    style.configure("PanelInner.TFrame",background=PANEL)
    style.configure("Panel.TCheckbutton",background=PANEL,foreground=TEXT,indicatorbackground=BG,indicatorforeground=ACCENT,indicatorcolor=BG,indicatordiameter=12)
    style.map("Panel.TCheckbutton",indicatorcolor=[("selected",ACCENT)],background=[("active",PANEL)])
    style.configure("Vertical.TScrollbar",background=PANEL2,troughcolor=BG,arrowcolor=MUTED,bordercolor=BG,lightcolor=PANEL2,darkcolor=PANEL2)
    style.configure("TScrollbar",background=PANEL2,troughcolor=BG,arrowcolor=MUTED,bordercolor=BG,lightcolor=PANEL2,darkcolor=PANEL2)
    style.configure("TSeparator",background=LINE)
    style.configure("Nav.TButton",borderwidth=0)
    style.configure("Treeview",font=(family,-12))
    style.configure("Panel.TLabel",background=PANEL)
    style.configure("Metric.TLabel",background=PANEL,font=(family,-30,"bold"))
    style.configure("Title.TLabel",font=(family,-30,"bold"))
    style.configure("Kicker.TLabel",foreground=ACCENT,font=(family,-10,"bold"))
    style.configure("Muted.TLabel",foreground=MUTED,font=(family,-12))
    style.configure("PanelTitle.TLabel",background=PANEL,font=(family,-16,"bold"),padding=0)
    style.configure("PanelMuted.TLabel",background=PANEL,foreground=MUTED,font=(family,-12))
    style.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=39,borderwidth=0)
    style.configure("Treeview.Heading",background=PANEL2,foreground=MUTED,relief="flat",font=(family,-10,"bold"),padding=(8,8))
    style.map("Treeview",background=[("selected",ACTIVE)],foreground=[("selected",TEXT)])
    style.configure("TEntry",fieldbackground=BG,padding=(8,8),bordercolor=LINE)
    style.configure("TCombobox",fieldbackground=BG,foreground=TEXT,background=PANEL2,padding=(8,7),arrowsize=14)
    style.map("TCombobox",fieldbackground=[("readonly",BG)],foreground=[("readonly",TEXT)])
    style.configure("TSpinbox",fieldbackground=BG,padding=(8,7))
    style.configure("TLabelframe",background=PANEL,bordercolor=LINE,relief="solid")
    style.configure("TLabelframe.Label",background=PANEL,foreground=TEXT,font=(family,-16,"bold"))
    style.configure("TNotebook",background=BG,borderwidth=0)
    style.configure("TNotebook.Tab",background=PANEL2,foreground=TEXT,padding=(12,8))
    style.map("TNotebook.Tab",background=[("selected",ACTIVE)],foreground=[("selected",ACCENT)])
    style.configure("Horizontal.TProgressbar",background=ACCENT,troughcolor=PANEL2,bordercolor=PANEL2,lightcolor=ACCENT,darkcolor=ACCENT,thickness=8)

    install_control_states(root,style,family)
    return family

def install_control_states(root,style,family):
    """Keep live clam controls and use the product palette in every state."""
    style.configure(".",focuscolor=ACCENT,focusthickness=2,focussolid=True)
    for name,fill,fg,hover,pressed in (
        ("TButton",PANEL2,TEXT,"#21394b",ACTIVE),
        ("Small.TButton",PANEL2,TEXT,"#21394b",ACTIVE),
        ("Accent.TButton",ACCENT,INK,"#51efc5","#26cda3"),
        ("Nav.TButton",SIDE,TEXT,PANEL2,ACTIVE),
        ("Active.Nav.TButton",ACTIVE,ACCENT,ACTIVE,ACTIVE),
    ):
        edge=ACCENT if name=="Accent.TButton" else LINE
        borders=[("disabled",LINE),("focus",ACCENT),("active",ACCENT if name=="Accent.TButton" else LINE)]
        style.configure(name,background=fill,foreground=fg,bordercolor=edge,
                        lightcolor=fill,darkcolor=fill,focuscolor=ACCENT if fg!=INK else INK)
        colors=[("disabled",PANEL),("pressed",pressed),("active",hover)]
        style.map(name,background=colors,lightcolor=colors,darkcolor=colors,
                  foreground=[("disabled",MUTED)],bordercolor=borders)
    for name in ("TEntry","TCombobox","TSpinbox"):
        style.configure(name,fieldbackground=BG,foreground=TEXT,insertcolor=ACCENT,
                        selectbackground=ACTIVE,selectforeground=TEXT,arrowcolor=MUTED,
                        bordercolor=LINE,lightcolor=LINE)
        style.map(name,fieldbackground=[("disabled",PANEL),("readonly",BG)],
                  foreground=[("disabled",MUTED),("readonly",TEXT)],
                  bordercolor=[("disabled",LINE),("focus",ACCENT)],
                  lightcolor=[("disabled",LINE),("focus",ACCENT)],
                  background=[("disabled",PANEL),("pressed",ACTIVE),("active",PANEL2),("readonly",PANEL2)],
                  arrowcolor=[("disabled",MUTED),("active",ACCENT)])
    for name in ("TCheckbutton","Panel.TCheckbutton","TRadiobutton"):
        fill=PANEL if name.startswith("Panel.") else BG
        style.configure(name,background=fill,foreground=TEXT,indicatorbackground=BG,
                        indicatorforeground=ACCENT,upperbordercolor=LINE,lowerbordercolor=LINE)
        style.map(name,background=[("active",fill)],foreground=[("disabled",MUTED)],
                  indicatorbackground=[("disabled",PANEL),("pressed",ACTIVE),("selected",ACTIVE)],
                  indicatorforeground=[("disabled",MUTED),("selected",ACCENT)],
                  upperbordercolor=[("focus",ACCENT)],lowerbordercolor=[("focus",ACCENT)])
    style.map("Treeview",background=[("disabled",PANEL),("selected",ACTIVE)],
              foreground=[("disabled",MUTED),("selected",TEXT)],
              bordercolor=[("focus",ACCENT)],lightcolor=[("focus",ACCENT)])
    style.map("Treeview.Heading",background=[("pressed",ACTIVE),("active",PANEL2)],
              foreground=[("active",TEXT)],lightcolor=[("active",PANEL2)],darkcolor=[("active",PANEL2)])
    style.map("TNotebook.Tab",background=[("disabled",PANEL),("selected",ACTIVE),("active",PANEL2)],
              foreground=[("disabled",MUTED),("selected",ACCENT)],
              lightcolor=[("selected",ACTIVE),("!selected",PANEL2)],
              darkcolor=[("selected",ACTIVE),("!selected",PANEL2)])
    # Tk creates the dropdown as a separate listbox, outside ttk styling.
    for option,value in (("background",BG),("foreground",TEXT),("selectBackground",ACTIVE),
                         ("selectForeground",TEXT),("highlightColor",ACCENT),("font",(family,-13))):
        root.option_add("*TCombobox*Listbox."+option,value)


def panel(parent,title=None,padding=15):
    box=ttk.Frame(parent,style="Panel.TFrame",padding=padding)
    if title:ttk.Label(box,text=title,style="PanelTitle.TLabel").pack(anchor="w",pady=(0,12))
    return box

def clip_band(points,projection,bound,keep_above):
    if not points:return []
    result=[]
    prev=points[-1]
    d0=projection(prev)-bound
    for point in points:
        d1=projection(point)-bound
        inside=(d1>=0 if keep_above else d1<=0)
        was=(d0>=0 if keep_above else d0<=0)
        if inside!=was:
            t=d0/(d0-d1)
            result.append((prev[0]+t*(point[0]-prev[0]),prev[1]+t*(point[1]-prev[1])))
        if inside:result.append(point)
        prev,d0=point,d1
    return result

def rounded_points(width,height,radius):
    r=min(radius,width/2,height/2)
    result=[]
    for cx,cy,start in ((width-r,r,-90),(width-r,height-r,0),(r,height-r,90),(r,r,180)):
        for angle in range(start,start+91,15):
            a=math.radians(angle)
            result.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return result

def clear_chart(canvas):
    """Clear chart data without removing the composited background."""
    background=getattr(canvas,"_chart_background_item",None)
    for item in canvas.find_all():
        if item!=background:canvas.delete(item)


def gradient_origin(canvas):
    root=canvas.winfo_toplevel()
    return ((canvas.winfo_rootx()-root.winfo_rootx())%8,
            (canvas.winfo_rooty()-root.winfo_rooty())%8)


def composite_gradient(canvas,start,end,border,width,height,region=None):
    """Apply ordered quantization to the product's low-contrast CSS gradients."""
    if (start,end)==(PANEL,"#0c1a26"):
        endpoint=mix_rgb(PANEL,BG,.45)
    elif (start,end)==(SIDE,BG):
        endpoint=BG
    else:
        return gradient_surface(start,end,border,width,height,region)
    return dithered_gradient_surface(start,endpoint,border,width,height,region,gradient_origin(canvas))


def shade_children(parent,canvas,start,end,width,height):
    """Compose chart surfaces exactly and shade opaque native widget backgrounds."""
    style=ttk.Style(parent)
    px,py=canvas.winfo_rootx(),canvas.winfo_rooty()
    def visit(widget):
        for child in widget.winfo_children():
            if child is canvas or not child.winfo_ismapped():continue
            if isinstance(child,Card):continue
            x,y=child.winfo_rootx()-px,child.winfo_rooty()-py
            w,h=child.winfo_width(),child.winfo_height()
            color=surface_color(start,end,width,height,x+w/2,y+h/2)
            if isinstance(child,ttk.Widget):
                current=child.cget("style")
                base=getattr(child,"_surface_base",current)
                if base in ("Panel.TLabel","PanelMuted.TLabel","PanelTitle.TLabel","Metric.TLabel","PanelInner.TFrame","Panel.TCheckbutton"):
                    name="Shade"+color[1:]+"."+base
                    if current!=name:
                        child._surface_base=base
                        style.configure(name,background=color)
                        if base=="Panel.TCheckbutton":
                            style.map(name,background=[("active",color)])
                        child.configure(style=name)
                elif isinstance(child,ttk.Treeview) and base in ("","Treeview","Recent.Treeview"):
                    base=base or "Treeview"
                    name="Shade"+color[1:]+"."+base
                    if current!=name:
                        child._surface_base=base
                        style.configure(name,background=color,fieldbackground=color)
                        child.configure(style=name)
            elif isinstance(child,tk.Canvas) and not getattr(child,"_surface_decoration",False):
                if not hasattr(child,"_surface_original_bg"):
                    child._surface_original_bg=child.cget("background")
                if child._surface_original_bg==PANEL:
                    refresh=getattr(canvas,"_schedule_shade",None)
                    if refresh is not None and not getattr(child,"_chart_shade_bound",False):
                        child.bind("<Configure>",refresh,add="+")
                        child.bind("<Map>",refresh,add="+")
                        child._chart_shade_bound=True
                    if child.cget("background")!=color:child.configure(background=color)
                    valid=(min(x,y)>=0 and min(w,h)>0 and x+w<=width and y+h<=height
                           and min(width,height)>=3 and max(width,height)<=4096 and width*height<=2_000_000)
                    key=(start,end,width,height,x,y,w,h,gradient_origin(canvas)) if valid else None
                    if key!=getattr(child,"_chart_background_key",None):
                        child.delete("chart-background")
                        child._chart_background_item=None
                        child._chart_background_image=None
                        if key is not None:
                            child._chart_background_image=tk.PhotoImage(master=child,data=composite_gradient(canvas,start,end,None,width,height,(x,y,w,h)))
                            child._chart_background_item=child.create_image(0,0,image=child._chart_background_image,anchor="nw",tags="chart-background")
                            child.tag_lower(child._chart_background_item)
                        child._chart_background_key=key
            visit(child)
    visit(parent)

def shade_sidebar(parent,canvas,start,end,width,height):
    """Match classic sidebar labels to the underlying procedural surface."""
    style=ttk.Style(parent)
    px,py=canvas.winfo_rootx(),canvas.winfo_rooty()
    def visit(widget):
        for child in widget.winfo_children():
            if child is canvas or not child.winfo_ismapped():continue
            if isinstance(child,(tk.Frame,tk.Label,tk.Canvas)):
                original=getattr(child,"_sidebar_original_bg",None)
                if original is None:
                    original=child.cget("background")
                    child._sidebar_original_bg=original
                if original==SIDE:
                    x=child.winfo_rootx()-px+child.winfo_width()/2
                    y=child.winfo_rooty()-py+child.winfo_height()/2
                    color=surface_color(start,end,width,height,x,y)
                    if child.cget("background")!=color:
                        child.configure(background=color)
            elif isinstance(child,ttk.Button):
                current=child.cget("style")
                if current=="Active.Nav.TButton" or current=="Nav.TButton" or current.endswith(".Nav.TButton"):
                    x=child.winfo_rootx()-px+child.winfo_width()/2
                    y=child.winfo_rooty()-py+child.winfo_height()/2
                    color=surface_color(start,end,width,height,x,y)
                    name="Shade"+color[1:]+".Nav.TButton"
                    if getattr(child,"_nav_idle_style",None)!=name:
                        style.configure(name,background=color,lightcolor=color,darkcolor=color)
                        child._nav_idle_style=name
                    if current!="Active.Nav.TButton" and current!=name:
                        child.configure(style=name)
            visit(child)
    visit(parent)


def decorate(parent,start=PANEL,end="#0c1a26",radius=12,outer=BG,border=LINE):
    """Draw only procedural surface geometry behind live native controls."""
    canvas=tk.Canvas(parent,bg=outer,highlightthickness=0,borderwidth=0,takefocus=0)
    canvas._surface_decoration=True
    canvas.place(x=0,y=0,relwidth=1,relheight=1,bordermode="outside")
    canvas.tk.call("lower",canvas._w)
    last=None
    pending=None
    shade_pending=None
    def shade():
        nonlocal shade_pending
        shade_pending=None
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if isinstance(parent,Card):
            shade_children(parent,canvas,start,end,w,h)
        elif isinstance(parent,tk.Frame) and start==SIDE and end==BG:
            shade_sidebar(parent,canvas,start,end,w,h)
    def schedule_shade(_event=None):
        nonlocal shade_pending
        if shade_pending is None:
            shade_pending=canvas.after(60,shade)
    canvas._schedule_shade=schedule_shade

    def draw():
        nonlocal last,pending,shade_pending
        pending=None
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if min(w,h)<3:return
        schedule_shade()
        geometry=(w,h,gradient_origin(canvas))
        if geometry==last:return
        last=geometry
        canvas.delete("surface")
        canvas.gradient_image=None
        if (type(radius) is int and 0<=radius<=32 and min(w,h)>=2*radius
                and max(w,h)<=4096 and w*h<=2_000_000):
            canvas.gradient_image=tk.PhotoImage(master=canvas,data=composite_gradient(canvas,start,end,border,w,h))
            canvas.create_image(0,0,image=canvas.gradient_image,anchor="nw",tags="surface")
        else:
            points=rounded_points(w-1,h-1,radius)
            angle=math.radians(145)
            dx,dy=math.sin(angle),-math.cos(angle)
            span=max(1,dx*(w-1)+dy*(h-1))
            def projection(point):return (dx*point[0]+dy*point[1])/span
            for left,right,color in gradient_bands(start,end):
                polygon=clip_band(points,projection,left,True)
                polygon=clip_band(polygon,projection,min(1,right+.001),False)
                if len(polygon)>=3:
                    canvas.create_polygon(*[v for point in polygon for v in point],fill=color,outline="",tags="surface")
            if border:
                canvas.create_line(*[v for point in points+[points[0]] for v in point],fill=border,width=1,tags="surface")
        canvas.corner_images=[]
        if type(radius) is int and 1<=radius<=32 and min(w,h)>=2*radius:
            for corner,(x,y) in enumerate(((0,0),(w-radius,0),(w-radius,h-radius),(0,h-radius))):
                if (start,end)==(PANEL,"#0c1a26"):
                    data=dithered_card_corner(start,mix_rgb(PANEL,BG,.45),outer,border,w,h,radius,corner,gradient_origin(canvas))
                else:
                    data=card_corner(start,end,outer,border,w,h,radius,corner)
                image=tk.PhotoImage(master=canvas,data=data)
                canvas.corner_images.append(image)
                canvas.create_image(x,y,image=image,anchor="nw",tags="surface")
    def resized(_event):
        nonlocal pending
        if pending is not None:canvas.after_cancel(pending)
        pending=canvas.after(45,draw)
    def destroyed(_event):
        nonlocal pending,shade_pending
        if pending is not None:
            canvas.after_cancel(pending)
            pending=None
        if shade_pending is not None:
            canvas.after_cancel(shade_pending)
            shade_pending=None
    canvas.bind("<Configure>",resized)
    canvas.bind("<Map>",resized,add="+")
    canvas.bind("<Destroy>",destroyed)
    return canvas

class Card(ttk.Frame):
    def __init__(self,parent,title=None,padding=15,outer=BG,**kwargs):
        super().__init__(parent,style="Card.TFrame",padding=padding,**kwargs)
        decorate(self,outer=outer)
        if title:ttk.Label(self,text=title,style="PanelTitle.TLabel").pack(anchor="w",pady=(0,12))

def header_glow(parent):
    """Composite one procedural header across otherwise opaque native frames."""
    canvas=tk.Canvas(parent,height=119,bg=BG,highlightthickness=0,borderwidth=0,takefocus=0)
    canvas._surface_decoration=True
    canvas.place(x=0,y=0,relwidth=1,bordermode="outside")
    canvas.tk.call("lower",canvas._w)
    pending=None
    last=0

    def compose(widget,width):
        for child in widget.winfo_children():
            if child is canvas or not child.winfo_ismapped():continue
            if not isinstance(child,ttk.Frame) or isinstance(child,Card) or child.cget("style"):
                continue
            if not getattr(child,"_header_glow_bound",False):
                child.bind("<Configure>",resized,add="+")
                child.bind("<Map>",resized,add="+")
                child._header_glow_bound=True
            x,y=child.winfo_rootx()-canvas.winfo_rootx(),child.winfo_rooty()-canvas.winfo_rooty()
            x0,y0=max(0,x),max(0,y)
            x1,y1=min(width,x+child.winfo_width()),min(119,y+child.winfo_height())
            patch=getattr(child,"_header_glow_patch",None)
            if x1<=x0 or y1<=y0:
                if patch is not None:patch.place_forget()
                continue
            key=(last,x0,y0,x1,y1,x,y)
            if patch is None:
                patch=tk.Canvas(child,bg=BG,borderwidth=0,highlightthickness=0,takefocus=0)
                patch._surface_decoration=True
                child._header_glow_patch=patch
            if getattr(patch,"_header_key",None)!=key:
                image=tk.PhotoImage(master=patch,width=x1-x0,height=y1-y0)
                image.tk.call(str(image),"copy",str(canvas.surface),"-from",x0,y0,x1,y1)
                patch.delete("glow")
                patch.create_image(0,0,image=image,anchor="nw",tags="glow")
                patch.surface=image
                patch._header_key=key
            patch.place(x=x0-x,y=y0-y,width=x1-x0,height=y1-y0,bordermode="outside")
            patch.tk.call("lower",patch._w)
            compose(child,width)

    def draw():
        nonlocal pending,last
        pending=None
        w=canvas.winfo_width()
        if not 20<=w<=4096:return
        key=(w,gradient_origin(canvas))
        if key!=last:
            canvas.surface=tk.PhotoImage(master=canvas,data=header_surface(BG,ACCENT,w,origin=key[1]))
            canvas.delete("glow")
            canvas.create_image(0,0,image=canvas.surface,anchor="nw",tags="glow")
            last=key
        compose(parent,w)

    def resized(_event=None):
        nonlocal pending
        if pending is None and canvas.winfo_exists():
            pending=canvas.after(60,draw)

    def destroyed(_event):
        nonlocal pending
        if pending is not None:canvas.after_cancel(pending)
        pending=None
    canvas.bind("<Configure>",resized)
    canvas.bind("<Map>",resized,add="+")
    canvas.bind("<Destroy>",destroyed)
    canvas.schedule_composite=resized
    return canvas


def product_icon(root):
    """Reuse the original launch asset in source and packaged native builds."""
    bundle=getattr(sys,"_MEIPASS",None)
    path=Path(bundle)/"assets"/"icon.png" if bundle else Path(__file__).resolve().parents[1]/"desktop"/"src-tauri"/"icons"/"icon.png"
    icon=tk.PhotoImage(master=root,file=str(path))
    root.iconphoto(True,icon)
    return icon

class NativeTable(ttk.Treeview):
    """Native table with bounded row-hover rendering; retain real selection."""
    _hover_tag="tvrtke_pointer_row"

    def __init__(self,parent,**kwargs):
        super().__init__(parent,**kwargs)
        self._hover_row=""
        self.tag_configure(self._hover_tag,background=PANEL2)
        self.bind("<Motion>",self._pointer,add="+")
        self.bind("<Leave>",self._clear_pointer,add="+")

    def _pointer(self,event):
        row=self.identify_row(event.y) if self.identify_region(event.x,event.y) in ("tree","cell") else ""
        if row==self._hover_row:return
        self._clear_pointer()
        if row and self.exists(row):
            tags=tuple(self.item(row,"tags"))
            if self._hover_tag not in tags:
                self.item(row,tags=(*tags,self._hover_tag))
            self._hover_row=row

    def _clear_pointer(self,_event=None):
        row,self._hover_row=self._hover_row,""
        if row and self.exists(row):
            self.item(row,tags=tuple(tag for tag in self.item(row,"tags") if tag!=self._hover_tag))

    def delete(self,*items):
        self._clear_pointer()
        return super().delete(*items)


class NativeDialog(tk.Toplevel):
    """Shared branded window surface; existing commands and modality stay intact."""
    def __init__(self,parent,**kwargs):
        super().__init__(parent,**kwargs)
        self.configure(background=BG)
        self._dialog_parent=parent

    def geometry(self,newGeometry=None):
        if newGeometry and "+" not in newGeometry and "-" not in newGeometry:
            try:
                width,height=map(int,newGeometry.split("x"))
            except ValueError:
                return super().geometry(newGeometry)
            parent=self._dialog_parent
            x=max(0,min(parent.winfo_rootx()+(parent.winfo_width()-width)//2,
                        self.winfo_screenwidth()-width))
            y=max(0,min(parent.winfo_rooty()+(parent.winfo_height()-height)//2,
                        self.winfo_screenheight()-height-40))
            newGeometry=f"{width}x{height}+{x}+{y}"
        return super().geometry(newGeometry)

