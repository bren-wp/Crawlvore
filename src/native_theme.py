"""Shared native design tokens, no web renderer."""
import tkinter as tk
from tkinter import ttk

BG="#08131e";SIDE="#0b1724";PANEL="#101f2d";PANEL2="#182b3b";LINE="#2a4355"
TEXT="#edf4fa";MUTED="#a8bacb";ACCENT="#36ebba";INK="#05291f";ACTIVE="#103f39"

def nav_icon(root,key,color):
    image=tk.PhotoImage(master=root,width=20,height=20)
    def line(x1,y1,x2,y2):
        steps=max(abs(x2-x1),abs(y2-y1),1)
        for i in range(steps+1):
            x=round(x1+(x2-x1)*i/steps);y=round(y1+(y2-y1)*i/steps)
            image.put(color,(x,y,min(20,x+2),min(20,y+2)))
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
    return image

def install(root):
    style=ttk.Style(root)
    style.theme_use("clam")
    style.configure(".",background=BG,foreground=TEXT,fieldbackground=BG,font=("Segoe UI",10),bordercolor=LINE,lightcolor=LINE,darkcolor=LINE)
    for name,fill,fg in (("TButton",PANEL2,TEXT),("Accent.TButton",ACCENT,INK),
                         ("Nav.TButton",SIDE,TEXT),("Active.Nav.TButton",ACTIVE,ACCENT)):
        style.configure(name,background=fill,foreground=fg,padding=(11,9),
                        anchor="w" if "Nav" in name else "center",font=("Segoe UI",10,"bold"),borderwidth=1)
        style.map(name,foreground=[("disabled",MUTED),("active",fg)],background=[("active",fill)])
    style.configure("Panel.TFrame",background=PANEL,borderwidth=1,relief="solid")
    style.configure("PanelInner.TFrame",background=PANEL)
    style.configure("Panel.TCheckbutton",background=PANEL,foreground=TEXT,indicatorcolor=BG)
    style.map("Panel.TCheckbutton",indicatorcolor=[("selected",ACCENT)],background=[("active",PANEL)])
    style.configure("TScrollbar",background=PANEL2,troughcolor=BG,arrowcolor=MUTED,bordercolor=BG,lightcolor=PANEL2,darkcolor=PANEL2)
    style.configure("TSeparator",background=LINE)
    style.configure("Nav.TButton",borderwidth=0)
    style.configure("Treeview",font=("Segoe UI",10))
    style.configure("Panel.TLabel",background=PANEL)
    style.configure("Metric.TLabel",background=PANEL,font=("Segoe UI",23,"bold"))
    style.configure("Title.TLabel",font=("Segoe UI",23,"bold"))
    style.configure("Kicker.TLabel",foreground=ACCENT,font=("Segoe UI",9,"bold"))
    style.configure("Muted.TLabel",foreground=MUTED)
    style.configure("PanelTitle.TLabel",background=PANEL,font=("Segoe UI",13,"bold"))
    style.configure("PanelMuted.TLabel",background=PANEL,foreground=MUTED)
    style.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=43,borderwidth=0)
    style.configure("Treeview.Heading",background=PANEL2,foreground=MUTED,relief="flat",font=("Segoe UI",9,"bold"),padding=(8,8))
    style.map("Treeview",background=[("selected",ACTIVE)],foreground=[("selected",TEXT)])
    style.configure("TEntry",fieldbackground=BG,padding=(8,8),bordercolor=LINE)
    style.configure("TCombobox",fieldbackground=BG,foreground=TEXT,background=PANEL2,padding=(8,7),arrowsize=14)
    style.map("TCombobox",fieldbackground=[("readonly",BG)],foreground=[("readonly",TEXT)])
    style.configure("TSpinbox",fieldbackground=BG,padding=(8,7))
    style.configure("TLabelframe",background=PANEL,bordercolor=LINE,relief="solid")
    style.configure("TLabelframe.Label",background=PANEL,foreground=TEXT,font=("Segoe UI",12,"bold"))
    style.configure("TNotebook",background=BG,borderwidth=0)
    style.configure("TNotebook.Tab",background=PANEL2,foreground=TEXT,padding=(12,8))
    style.map("TNotebook.Tab",background=[("selected",ACTIVE)],foreground=[("selected",ACCENT)])
    style.configure("Horizontal.TProgressbar",background=ACCENT,troughcolor=PANEL2,bordercolor=PANEL2,lightcolor=ACCENT,darkcolor=ACCENT)

def panel(parent,title=None,padding=15):
    box=ttk.Frame(parent,style="Panel.TFrame",padding=padding)
    if title:ttk.Label(box,text=title,style="PanelTitle.TLabel").pack(anchor="w",pady=(0,12))
    return box
