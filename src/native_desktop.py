"""Crawlvora native desktop migration: Tcl/Tk widgets, no browser renderer."""
import argparse
import json
from contextlib import nullcontext
import os
import queue
import sys
import tempfile
import threading
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import ttk, messagebox
from native_client import WorkerProcess
from native_sections import SecondaryPages
from native_theme import BG, SIDE, PANEL, PANEL2, LINE, TEXT, MUTED, ACCENT, INK, install, nav_icon

CONTACTS = {"Svi zapisi": "", "Ima telefon": "phone", "Ima web": "web", "Ima e-poštu": "email", "Bez telefona i weba": "missing"}
KINDS = {"Sve vrste":"","Trgovačka društva":"company","Poduzetnici i obrti":"entrepreneur","Institucije":"institution","Neprofitne organizacije":"nonprofit","Neklasificirani subjekti":"unknown"}
SORTS = {"Naziv A–Ž":"title","Naziv Ž–A":"title_desc","Grad":"city","Zadnje dodani":"new"}
GROUPS = {
    "Identifikacija": (("oib","OIB"),("mbs","MBS"),("industry","Djelatnost"),("year","Godina osnivanja")),
    "Kontakt i sjedište": (("email","E-pošta"),("phone","Telefon"),("website","Web"),("address","Adresa"),("postal","Poštanski broj"),("city","Grad")),
    "Poslovni podaci": (("employees","Zaposlenici"),("description","Opis"),("products","Proizvodi i usluge"))
}

def workspace_path():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Crawlvora"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home()/".local/share"))) / "Crawlvora"

class Desktop(SecondaryPages):
    def __init__(self, root, workspace, smoke=False):
        self.root, self.smoke = root, smoke
        self.cancel_start=threading.Event()
        self.worker = None
        self.merge_active = False
        self.sync_active = False
        self.sync_polling = False
        self.client = None
        self.closed = False
        self.result = 1
        self.events = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.page, self.total, self.sequence = 1, 0, 0
        self.pending_search = False
        self.search_timer = None
        root.title("Tvrtke")
        screen_w,screen_h=root.winfo_screenwidth(),root.winfo_screenheight()
        width,height=min(1280,max(320,screen_w-100)),min(820,max(240,screen_h-120))
        root.geometry(f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//2-20)}")
        root.minsize(min(640,width),min(420,height))
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        install(root)
        self.status = tk.StringVar(value="Priprema radnog prostora…")
        shell=ttk.Frame(root)
        shell.pack(fill="both",expand=True)
        sidebar=tk.Frame(shell,bg=SIDE,width=232,highlightbackground=LINE,highlightthickness=1)
        sidebar.pack(side="left",fill="y")
        sidebar.pack_propagate(False)
        brand=tk.Frame(sidebar,bg=SIDE)
        self.brand=brand
        brand.pack(fill="x",padx=20,pady=(28,25))
        logo=tk.Canvas(brand,width=42,height=42,bg=SIDE,highlightthickness=0)
        logo.pack(side="left",padx=(0,12))
        logo.create_polygon(6,0,36,0,42,6,42,36,36,42,6,42,0,36,0,6,fill=ACCENT,outline="")
        logo.create_polygon(21,8,33,15,33,28,21,35,9,28,9,15,outline=INK,fill="",width=2)
        logo.create_line(9,15,21,22,33,15,21,8,21,22,21,35,fill=INK,width=2)
        tk.Label(brand,text="Tvrtke",bg=SIDE,fg=TEXT,font=("Segoe UI",17,"bold")).pack(anchor="w")
        tk.Label(brand,text="POSLOVNI PODACI",bg=SIDE,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w")
        self.sidebar=sidebar
        self.nav={}
        self.nav_icons={}
        self.nav_labels=[]
        def nav_label(label):
            widget=tk.Label(sidebar,text=label,bg=SIDE,fg=MUTED,font=("Segoe UI",9,"bold"))
            widget.pack(anchor="w",padx=20,pady=(14,5))
            self.nav_labels.append(widget)
        def nav(key,label,command,parent=sidebar):
            self.nav_icons[key]=(nav_icon(root,key,TEXT),nav_icon(root,key,ACCENT))
            button=ttk.Button(parent,text=label,image=self.nav_icons[key][0],compound="left",style="Nav.TButton",command=command)
            button.pack(fill="x",padx=16,pady=2)
            self.nav[key]=button
        nav_label("RADNI PROSTOR")
        nav("overview","Pregled",lambda:self.show_view("overview"))
        nav("directory","Poslovni imenik",lambda:self.show_view("directory"))
        nav_label("UPRAVLJANJE")
        nav("jobs","Zadaci i raspored",lambda:self.show_view("jobs"))
        nav("data","Uvoz i izvoz",lambda:self.show_view("data"))
        nav("analytics","Analitika i izvještaji",lambda:self.show_view("analytics"))
        nav("registry","Tvrtke – sinkronizacija",lambda:self.show_view("registry"))
        nav("settings","Postavke",lambda:self.show_view("settings"))
        main=ttk.Frame(shell)
        main.pack(side="left",fill="both",expand=True)
        self.header=ttk.Frame(main,padding=(28,10))
        self.header.pack(fill="x")
        self.crumb=tk.StringVar(value="Radni prostor / Pregled")
        ttk.Label(self.header,textvariable=self.crumb,style="Muted.TLabel").pack(side="left")
        self.stats=tk.StringVar(value="")
        ttk.Label(self.header,textvariable=self.stats,style="Muted.TLabel").pack(side="right")
        ttk.Separator(main).pack(fill="x")
        viewport=ttk.Frame(main)
        viewport.pack(fill="both",expand=True)
        self.viewport=tk.Canvas(viewport,bg=BG,highlightthickness=0)
        self.vscroll=ttk.Scrollbar(viewport,orient="vertical",command=self.viewport.yview)
        self.hscroll=ttk.Scrollbar(viewport,orient="horizontal",command=self.viewport.xview)
        self.viewport.configure(yscrollcommand=self.vscroll.set,xscrollcommand=self.hscroll.set)
        viewport.columnconfigure(0,weight=1)
        viewport.rowconfigure(0,weight=1)
        self.viewport.grid(row=0,column=0,sticky="nsew")
        self.vscroll.grid(row=0,column=1,sticky="ns")
        self.hscroll.grid(row=1,column=0,sticky="ew")
        self.vscroll.grid_remove()
        self.hscroll.grid_remove()
        self.scroll_state=(False,False)
        content=ttk.Frame(self.viewport,padding=(28,14,28,12))
        self.content=content
        self.content_window=self.viewport.create_window(0,0,anchor="nw",window=content)
        self.viewport.bind("<Configure>",self.resize_content)
        content.bind("<Configure>",self.resize_content)
        self.resize_pending=False
        self.reflow_groups=[]
        self.views={key:ttk.Frame(content) for key in ("overview","directory","settings","jobs","data","analytics","registry")}
        self.body=self.views["directory"]
        self.build_directory()
        self.build_overview()
        self.build_settings()
        self.build_jobs()
        self.build_data()
        self.build_analytics()
        self.build_registry()
        for view in self.views.values():self.polish_panel_children(view)
        self.current_view=""
        self.show_view("overview")
        ttk.Label(main,textvariable=self.status,style="Muted.TLabel",padding=(34,8)).pack(fill="x")
        self.root.after(40,self.drain)
        self.root.bind("<Configure>",self.resize_shell,add="+")
        self.root.after(100,self.reflow_layout)
        self.submit(lambda:WorkerProcess(workspace,smoke=smoke,cancel=self.cancel_start),self.started)

    def resize_shell(self,event):
        if event.widget is self.root:
            width=232 if event.width>=1100 else 205 if event.width>=780 else 174
            if int(self.sidebar.cget("width"))!=width:
                self.sidebar.configure(width=width)
                self.nav["registry"].configure(text="Tvrtke – sinkronizacija" if width>=205 else "Sinkronizacija")
            short=event.height<580
            if getattr(self,"short_navigation",None)!=short:
                self.short_navigation=short
                self.brand.pack_configure(pady=(10,8) if short else (28,25))
                for label in self.nav_labels:label.pack_configure(pady=(5,2) if short else (14,5))
                for button in self.nav.values():button.pack_configure(pady=0 if short else 2)
                style=ttk.Style(self.root)
                for name in ("Nav.TButton","Active.Nav.TButton"):style.configure(name,padding=(7,3) if short else (11,9))
            self.reflow_layout()
            self.resize_content()

    def polish_panel_children(self,widget,inside=False):
        for child in widget.winfo_children():
            panel=isinstance(child,ttk.LabelFrame) or (isinstance(child,ttk.Frame) and child.cget("style") in ("Panel.TFrame","PanelInner.TFrame"))
            if inside:
                if isinstance(child,ttk.Label) and child.cget("style") in ("","Muted.TLabel"):
                    child.configure(style="PanelMuted.TLabel" if child.cget("style")=="Muted.TLabel" else "Panel.TLabel")
                elif isinstance(child,ttk.Frame) and not panel:child.configure(style="PanelInner.TFrame")
                elif isinstance(child,ttk.Checkbutton):child.configure(style="Panel.TCheckbutton")
            self.polish_panel_children(child,inside or panel)

    def register_grid(self,grid,columns):
        self.reflow_groups.append((grid,columns,[(w,dict(w.grid_info())) for w in grid.grid_slaves()]))

    def reflow_layout(self):
        if self.closed:return
        available=self.root.winfo_width()-int(self.sidebar.cget("width"))-56
        compact=available<740
        if getattr(self,"compact_layout",None)==compact:return
        self.compact_layout=compact
        for grid,columns,items in self.reflow_groups:
            if not items:continue
            for i in range(columns):grid.columnconfigure(i,weight=0,uniform="")
            target=(2 if columns==4 else 1) if compact else columns
            for i in range(target):grid.columnconfigure(i,weight=1,uniform="responsive")
            ordered=sorted(items,key=lambda pair:(int(pair[1]["row"]),int(pair[1]["column"])))
            for i,(widget,info) in enumerate(ordered):
                if compact:widget.grid_configure(row=i//target,column=i%target,padx=(0,6 if i%target<target-1 else 0),pady=(0,8))
                else:widget.grid_configure(row=info["row"],column=info["column"],padx=info["padx"],pady=info["pady"])
        self.resize_content()

    def resize_content(self,_event=None):
        if self.resize_pending:return
        self.resize_pending=True
        self.root.after(60,self.fit_content)

    def fit_content(self):
        self.resize_pending=False
        if self.closed:return
        container=self.viewport.master
        width=container.winfo_width()
        height=container.winfo_height()
        if width<2 or height<2:return
        req_w,req_h=self.content.winfo_reqwidth(),self.content.winfo_reqheight()
        vsize=self.vscroll.winfo_reqwidth()
        hsize=self.hscroll.winfo_reqheight()
        horizontal=req_w>width
        vertical=req_h>height-(hsize if horizontal else 0)
        horizontal=req_w>width-(vsize if vertical else 0)
        vertical=req_h>height-(hsize if horizontal else 0)
        state=(horizontal,vertical)
        if state!=self.scroll_state:
            self.scroll_state=state
            for scrollbar,needed in ((self.hscroll,horizontal),(self.vscroll,vertical)):
                if needed:scrollbar.grid()
                else:scrollbar.grid_remove()
        width-=vsize if vertical else 0
        height-=hsize if horizontal else 0
        target=(max(width,req_w),max(height,req_h))
        if getattr(self,"content_size",None)!=target:
            self.content_size=target
            self.viewport.itemconfigure(self.content_window,width=target[0],height=target[1])
            self.viewport.configure(scrollregion=(0,0,*target))

    def submit(self, job, success, failure=None):
        if self.closed:
            return
        future = self.pool.submit(job)
        future.add_done_callback(lambda f:self.events.put((f,success,failure)))

    def drain(self):
        if self.closed:
            return
        try:
            while True:
                future,success,failure = self.events.get_nowait()
                try:
                    success(future.result())
                except Exception as exc:
                    if failure:
                        failure(exc)
                    else:
                        self.status.set("Operacija nije uspjela. Provjerite radni prostor.")
                        if self.smoke:
                            self.close()
        except queue.Empty:
            pass
        if not self.closed:
            self.root.after(40,self.drain)

    def started(self, worker):
        self.worker, self.client = worker, worker.client
        self.status.set("Spremno.")
        self.submit(lambda:(self.client.request("/api/cities"),self.client.request("/api/industries")),self.facets)
        if self.current_view=="overview":self.refresh_overview()
        elif self.current_view=="directory":self.refresh()
        else:self.refresh_settings()
        self.poll_sync()

    def facets(self, result):
        cities,industries = result
        self.citybox.configure(values=["Svi gradovi"]+[x if isinstance(x,str) else x.get("city","") for x in cities])
        self.industrybox.configure(values=["Sve djelatnosti"]+industries)

    def show_view(self,key):
        if self.current_view:
            self.views[self.current_view].pack_forget()
            self.nav[self.current_view].configure(style="Nav.TButton",image=self.nav_icons[self.current_view][0])
        self.current_view=key
        self.nav[key].configure(style="Active.Nav.TButton",image=self.nav_icons[key][1])
        self.views[key].pack(fill="both",expand=True)
        self.viewport.xview_moveto(0)
        self.viewport.yview_moveto(0)
        self.resize_content()
        self.crumb.set("Radni prostor / "+{"overview":"Pregled","directory":"Poslovni imenik","settings":"Postavke","jobs":"Zadaci i raspored","data":"Uvoz i izvoz","analytics":"Analitika i izvještaji","registry":"Tvrtke – sinkronizacija"}[key])
        if self.client:
            if key=="overview":self.refresh_overview()
            elif key=="directory":self.refresh()
            elif key=="settings":self.refresh_settings()
            elif key=="jobs":self.refresh_jobs()
            elif key=="analytics":self.refresh_analytics()
            elif key=="registry":self.refresh_registry()

    def build_settings(self):
        view=self.views["settings"]
        ttk.Label(view,text="UPRAVLJANJE APLIKACIJOM",foreground=ACCENT).pack(anchor="w")
        ttk.Label(view,text="Postavke",style="Title.TLabel").pack(anchor="w",pady=(4,4))
        ttk.Label(view,text="Sigurnost, pristup poslovnim podacima i informacije o aplikaciji.",style="Muted.TLabel").pack(anchor="w",pady=(0,16))
        columns=ttk.Frame(view);columns.pack(fill="both",expand=True)
        for col in (0,1):columns.columnconfigure(col,weight=1,uniform="settings")
        left=ttk.Frame(columns);left.grid(row=0,column=0,sticky="nsew",padx=(0,10))
        right=ttk.Frame(columns);right.grid(row=0,column=1,sticky="nsew")
        about=ttk.LabelFrame(left,text="O aplikaciji",padding=14);about.pack(fill="x",pady=(0,12))
        for label,value,url in (("Brend","Tvrtke",None),("Službena web stranica","tvrtke.com.hr","https://tvrtke.com.hr/"),("Izrada i razvoj","Brendigo",None),("Web stranica developera","brendigo.com","https://brendigo.com/")):
            row=ttk.Frame(about);row.pack(fill="x",pady=4)
            ttk.Label(row,text=label,style="Muted.TLabel").pack(side="left")
            if url:ttk.Button(row,text=value,command=lambda url=url:webbrowser.open_new_tab(url)).pack(side="right")
            else:ttk.Label(row,text=value).pack(side="right")
        backups=ttk.LabelFrame(left,text="Sigurnosne kopije i oporavak",padding=14);backups.pack(fill="x",pady=(0,12))
        self.backup_choice=tk.StringVar()
        self.backup_selector=ttk.Combobox(backups,textvariable=self.backup_choice,state="readonly")
        self.backup_selector.pack(fill="x",pady=6)
        self.backup_status=tk.StringVar(value="Odaberite sigurnosnu kopiju.")
        ttk.Label(backups,textvariable=self.backup_status,wraplength=380).pack(anchor="w",pady=6)
        buttons=ttk.Frame(backups);buttons.pack(fill="x")
        ttk.Button(buttons,text="Izradi kopiju",style="Accent.TButton",command=self.backup_dialog).pack(side="left")
        ttk.Button(buttons,text="Osvježi",command=self.refresh_settings).pack(side="left",padx=6)
        ttk.Button(backups,text="Vrati u novi prostor",command=self.restore_selected).pack(anchor="w",pady=6)
        self.register_grid(columns,2)
        connection=ttk.LabelFrame(right,text="Pristup poslovnim podacima",padding=14);connection.pack(fill="x",pady=(0,12))
        self.access_status=tk.StringVar(value="Provjera pristupa…")
        ttk.Label(connection,textvariable=self.access_status).pack(anchor="w",pady=4)
        ttk.Button(connection,text="Upravljaj pristupom",command=self.sync_dialog).pack(anchor="w",pady=6)
        cleanup=ttk.LabelFrame(right,text="Uređivanje baze",padding=14);cleanup.pack(fill="x")
        ttk.Label(cleanup,text="Pregledajte moguće duplikate prije spajanja.",wraplength=350).pack(anchor="w")
        ttk.Button(cleanup,text="Pregled duplikata",command=self.duplicate_dialog).pack(anchor="w",pady=6)

    def refresh_settings(self):
        if not self.client:return
        def done(data):
            recovery,access=data
            ids=[row["id"] for row in recovery["backups"]]
            self.backup_selector.configure(values=ids)
            if self.backup_choice.get() not in ids:self.backup_choice.set(ids[0] if ids else "")
            self.backup_status.set(f"Dostupne sigurnosne kopije: {len(ids)}")
            self.access_status.set("Pristup omogućen" if access["configured"] else "Pristup nije omogućen")
        self.submit(lambda:(self.client.request("/api/recovery"),self.client.request("/api/registry")),done)

    def restore_selected(self):
        if not self.client or not self.backup_choice.get():return
        if not messagebox.askyesno("Tvrtke","Vratiti odabranu kopiju u novi prostor bez zamjene postojeće baze?"):return
        data={"id":self.backup_choice.get(),"confirmed":True}
        self.submit(lambda:self.client.request("/api/recovery/restore",data=data,timeout=900),lambda _result:messagebox.showinfo("Tvrtke","Kopija je vraćena u novi prostor. Postojeća baza nije zamijenjena."))

    def build_overview(self):
        view=self.views["overview"]
        ttk.Label(view,text="POSLOVNI PODACI",foreground=ACCENT).pack(anchor="w")
        ttk.Label(view,text="Pregled imenika",style="Title.TLabel").pack(anchor="w",pady=(4,4))
        ttk.Label(view,text="Pronađite, istražite i organizirajte podatke o tvrtkama na jednom mjestu.",style="Muted.TLabel").pack(anchor="w",pady=(0,18))
        metrics=ttk.Frame(view)
        metrics.pack(fill="x",pady=(0,16))
        self.metric_values={}
        for column,(key,label) in enumerate((("total","Tvrtke u bazi"),("cities","Gradovi"),("phones","S telefonom"),("websites","S web stranicom"))):
            metrics.columnconfigure(column,weight=1,uniform="metric")
            panel=ttk.Frame(metrics,style="Panel.TFrame",padding=14)
            panel.grid(row=0,column=column,sticky="nsew",padx=(0,10 if column<3 else 0))
            ttk.Label(panel,text=label,style="Panel.TLabel").pack(anchor="w")
            value=tk.StringVar(value="—")
            ttk.Label(panel,textvariable=value,style="Metric.TLabel").pack(anchor="w",pady=(12,0))
            self.metric_values[key]=value
        self.register_grid(metrics,4)
        charts=ttk.Frame(view)
        charts.pack(fill="x",pady=(0,16))
        charts.columnconfigure(0,weight=6)
        charts.columnconfigure(1,weight=5)
        city=ttk.Frame(charts,style="Panel.TFrame",padding=14)
        city.grid(row=0,column=0,sticky="nsew",padx=(0,12))
        ttk.Label(city,text="Najzastupljeniji gradovi",style="Panel.TLabel",font=("Segoe UI",13,"bold")).pack(anchor="w")
        self.city_chart=tk.Canvas(city,width=220,height=195,bg=PANEL,highlightthickness=0)
        self.city_chart.pack(fill="x",expand=True,pady=(8,0))
        coverage=ttk.Frame(charts,style="Panel.TFrame",padding=14)
        coverage.grid(row=0,column=1,sticky="nsew")
        ttk.Label(coverage,text="Dostupnost podataka",style="Panel.TLabel",font=("Segoe UI",13,"bold")).pack(anchor="w")
        self.coverage_chart=tk.Canvas(coverage,width=200,height=195,bg=PANEL,highlightthickness=0)
        self.coverage_chart.pack(fill="x",expand=True,pady=(8,0))
        self.register_grid(charts,2)
        self.overview_data=None
        for canvas in (self.city_chart,self.coverage_chart):
            canvas.bind("<Configure>",lambda _e:self.draw_charts())
        recent=ttk.Frame(view,style="Panel.TFrame",padding=14)
        recent.pack(fill="both",expand=True)
        top=ttk.Frame(recent,style="PanelInner.TFrame")
        top.pack(fill="x")
        ttk.Label(top,text="Nedavni zapisi",style="Panel.TLabel",font=("Segoe UI",13,"bold")).pack(side="left")
        ttk.Button(top,text="Otvori imenik",command=lambda:self.show_view("directory")).pack(side="right")
        self.recent=ttk.Treeview(recent,columns=("name","city","phone","web","source","action"),show="headings",height=4)
        for key,label,width in (("name","TVRTKA",240),("city","GRAD",90),("phone","TELEFON",100),("web","WEB STRANICA",110),("source","IZVORI",100),("action","AKCIJA",65)):
            self.recent.heading(key,text=label)
            self.recent.column(key,width=width)
        self.recent.pack(fill="both",expand=True,pady=(10,0))
        def open_recent(_event):
            if self.recent.selection():
                identifier=int(self.recent.selection()[0])
                self.submit(lambda:self.client.request(f"/api/company/{identifier}"),self.profile)
        self.recent.bind("<Double-1>",open_recent)
        def click_recent(event):
            if self.recent.identify_column(event.x)=="#6" and self.recent.identify_row(event.y):
                self.recent.selection_set(self.recent.identify_row(event.y));open_recent(event)
        self.recent.bind("<ButtonRelease-1>",click_recent)
        self.recent.bind("<Return>",open_recent)

    def refresh_overview(self):
        def done(result):
            stats,companies=result
            self.overview_data=stats
            for key,value in self.metric_values.items():value.set(f"{stats[key]:,}".replace(",","."))
            self.draw_charts()
            self.recent.delete(*self.recent.get_children())
            for row in companies["rows"]:
                self.recent.insert("","end",iid=str(row["id"]),values=(row["title"],row.get("city") or "—",row.get("phone") or "—",row.get("website") or "—","Tvrtke" if "registry" in (row.get("providers") or "") else "Uvezeni podaci","Detalji →"))
            if self.smoke:
                if stats["total"]!=1 or len(self.recent.get_children())!=1 or self.metric_values["total"].get()!="1":self.close();return
                self.smoke_pages()
        self.submit(lambda:(self.client.request("/api/stats"),self.client.request("/api/companies",{"limit":5,"sort":"new"})),done)

    def smoke_pages(self):
        # Exercise all seven native page renderers using the synthetic worker.
        steps=[("registry",lambda:self.registry_values["runs"].get()=="0"),
               ("jobs",lambda:self.job_metrics.get()!="—"),
               ("data",lambda:self.import_button.winfo_ismapped() and len(self.export_fields)==11),
               ("analytics",lambda:self.analytics_values["total"].get()=="1"),
               ("settings",lambda:self.access_status.get() in ("Pristup omogućen","Pristup nije omogućen"))]
        def next_page(index):
            if self.closed:return
            if index==len(steps):
                self.show_view("directory")
                return
            key,ready=steps[index]
            self.show_view(key)
            def check(attempt=0):
                if self.closed:return
                if ready() and self.views[key].winfo_ismapped():
                    next_page(index+1)
                elif attempt>=100:self.close()
                else:self.root.after(50,lambda:check(attempt+1))
            self.root.after(50,check)
        next_page(0)

    def draw_charts(self):
        if not self.overview_data:return
        stats=self.overview_data
        for canvas in (self.city_chart,self.coverage_chart):canvas.delete("all")
        width=max(180,self.city_chart.winfo_width())
        cities=stats["top_cities"]
        largest=max(1,max((row["n"] for row in cities),default=1))
        for index,row in enumerate(cities[:6]):
            y=8+30*index
            self.city_chart.create_text(0,y,anchor="w",text=row["city"][:18],fill=TEXT)
            self.city_chart.create_rectangle(0,y+9,width,y+16,fill=PANEL2,outline="")
            self.city_chart.create_rectangle(0,y+9,width*row["n"]/largest,y+16,fill=ACCENT,outline="")
            self.city_chart.create_text(width-2,y,anchor="e",text=f"{row['n']:,}".replace(",","."),fill=MUTED)
        width=max(180,self.coverage_chart.winfo_width())
        for index,(key,label) in enumerate((("phones","Telefonski broj"),("websites","Web stranica"))):
            y=15+65*index
            pct=100*stats[key]/max(1,stats["total"])
            self.coverage_chart.create_text(0,y,anchor="w",text=label,fill=MUTED)
            self.coverage_chart.create_text(width-2,y,anchor="e",text=f"{pct:.0f}%",fill=TEXT)
            self.coverage_chart.create_rectangle(0,y+14,width,y+23,fill=PANEL2,outline="")
            self.coverage_chart.create_rectangle(0,y+14,width*pct/100,y+23,fill=ACCENT,outline="")

    def build_directory(self):
        self.section_header(self.body,"ISTRAŽIVANJE PODATAKA","Poslovni imenik","Pretražite i filtrirajte cjelokupnu bazu tvrtki.")
        filter_panel=ttk.Frame(self.body,style="Panel.TFrame",padding=15)
        filter_panel.pack(fill="x",pady=(0,12))
        ttk.Label(filter_panel,text="Napredni filtri",style="PanelTitle.TLabel").pack(anchor="w",pady=(0,12))
        filters=ttk.Frame(filter_panel)
        filters.pack(fill="x",pady=(0,10))
        self.query=tk.StringVar()
        self.city=tk.StringVar(value="Svi gradovi")
        self.industry=tk.StringVar(value="Sve djelatnosti")
        self.contact=tk.StringVar(value="Svi zapisi")
        self.kind=tk.StringVar(value="Sve vrste")
        self.sort=tk.StringVar(value="Naziv A–Ž")
        ttk.Label(filters,text="Naziv, OIB ili MBS").grid(row=0,column=0,sticky="w")
        entry=ttk.Entry(filters,textvariable=self.query)
        entry.grid(row=1,column=0,columnspan=4,sticky="ew",pady=(0,8))
        for index,label,var,values in ((1,"Grad",self.city,["Svi gradovi"]),(2,"Djelatnost (NKD)",self.industry,["Sve djelatnosti"]),(3,"Kontakt",self.contact,list(CONTACTS))):
            ttk.Label(filters,text=label).grid(row=2,column=index-1,sticky="w")
            box=ttk.Combobox(filters,textvariable=var,values=values,state="readonly",width=18)
            box.grid(row=3,column=index-1,sticky="ew",padx=(0,8))
            box.bind("<<ComboboxSelected>>",lambda _e:self.schedule_search())
            if index==1:self.citybox=box
            if index==2:self.industrybox=box
        for column in range(4):filters.columnconfigure(column,weight=1,uniform="filters")
        ttk.Button(filters,text="Pretraži",style="Accent.TButton",command=self.schedule_search).grid(row=1,column=4,padx=(8,0))
        for col,label,var,values in ((0,"Vrsta subjekta",self.kind,list(KINDS)),(1,"Sortiranje",self.sort,list(SORTS))):
            ttk.Label(filters,text=label).grid(row=4,column=col,sticky="w",pady=(8,0))
            selector=ttk.Combobox(filters,textvariable=var,values=values,state="readonly",width=18)
            selector.grid(row=5,column=col,sticky="ew",padx=(0,8))
            selector.bind("<<ComboboxSelected>>",lambda _e:self.schedule_search())
        def reset():
            for var,value in ((self.query,""),(self.city,"Svi gradovi"),(self.industry,"Sve djelatnosti"),(self.contact,"Svi zapisi"),(self.kind,"Sve vrste"),(self.sort,"Naziv A–Ž")):var.set(value)
            self.schedule_search()
        ttk.Button(filters,text="Poništi filtre",command=reset).grid(row=5,column=4)
        self.query.trace_add("write",lambda *_:self.schedule_search())
        table=ttk.Frame(self.body)
        table.pack(fill="both",expand=True)
        self.tree=ttk.Treeview(table,columns=("name","oib","city","industry","email"),show="headings",selectmode="browse")
        for key,label,width in (("name","Tvrtka",210),("oib","OIB",90),("city","Grad",90),("industry","Djelatnost",155),("email","E-pošta",140)):
            self.tree.heading(key,text=label)
            self.tree.column(key,width=width,minwidth=60,stretch=True)
        scroll=ttk.Scrollbar(table,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left",fill="both",expand=True)
        scroll.pack(side="right",fill="y")
        self.tree.bind("<Double-1>",lambda _e:self.open_selected())
        self.tree.bind("<Return>",lambda _e:self.open_selected())
        footer=ttk.Frame(self.body)
        footer.pack(fill="x",pady=(12,0))
        self.previous=ttk.Button(footer,text="Prethodna",command=lambda:self.move(-1),state="disabled")
        self.previous.pack(side="left")
        self.pagination=tk.StringVar(value="—")
        ttk.Label(footer,textvariable=self.pagination,padding=10).pack(side="left")
        self.next=ttk.Button(footer,text="Sljedeća",command=lambda:self.move(1),state="disabled")
        self.next.pack(side="left")
        ttk.Button(footer,text="Otvori profil",command=self.open_selected).pack(side="right")
        ttk.Button(footer,text="Osvježi",command=self.refresh).pack(side="right",padx=8)
        entry.focus_set()

    def schedule_search(self):
        if self.search_timer:
            self.root.after_cancel(self.search_timer)
        self.sequence+=1
        self.page=1
        self.search_timer=self.root.after(250,self.refresh)

    def move(self, delta):
        if not self.pending_search:
            self.page=max(1,self.page+delta)
            self.refresh()

    def directory_filters(self):
        return {"q":self.query.get(),"city":"" if self.city.get()=="Svi gradovi" else self.city.get(),
                "industry":"" if self.industry.get()=="Sve djelatnosti" else self.industry.get(),
                "contact":CONTACTS.get(self.contact.get(),""),"entity_kind":KINDS[self.kind.get()]}

    def refresh(self):
        self.search_timer=None
        if not self.client:
            return
        if self.pending_search:
            self.sequence+=1
            return
        self.sequence+=1
        serial=self.sequence
        self.pending_search=True
        params=dict(self.directory_filters(),sort=SORTS[self.sort.get()],page=self.page,limit=25)
        self.status.set("Učitavanje…")
        self.previous.configure(state="disabled")
        self.next.configure(state="disabled")
        def done(data):
            self.pending_search=False
            if serial!=self.sequence:
                self.refresh()
                return
            self.total=data["total"]
            pages=max(1,(self.total+24)//25)
            if self.page>pages:
                self.page=pages
                self.refresh()
                return
            self.tree.delete(*self.tree.get_children())
            for row in data["rows"]:
                self.tree.insert("","end",iid=str(row["id"]),values=tuple(row.get(k,"") or "—" for k in ("title","oib","city","industry","email")))
            self.pagination.set(f"Stranica {self.page} / {pages}")
            self.stats.set(f"{self.total:,} rezultata".replace(",","."))
            self.status.set("Nema rezultata." if not self.total else "Spremno.")
            self.previous.configure(state="normal" if self.page>1 else "disabled")
            self.next.configure(state="normal" if self.page<pages else "disabled")
            if self.smoke:
                if self.total==1 and len(self.tree.get_children())==1:
                    self.tree.selection_set(self.tree.get_children()[0])
                    self.open_selected()
                else:self.close()
        def failed(_exc):
            self.pending_search=False
            self.status.set("Pretraga nije uspjela. Pokušajte ponovno.")
            if self.smoke:self.close()
        self.submit(lambda:self.client.request("/api/companies",params),done,failed)

    def open_selected(self):
        if not self.client or not self.tree.selection():
            return
        identifier=int(self.tree.selection()[0])
        self.submit(lambda:self.client.request(f"/api/company/{identifier}"),self.profile)

    def profile(self, company):
        dialog=tk.Toplevel(self.root)
        dialog.title("Profil tvrtke")
        dialog.geometry("720x580")
        dialog.minsize(480,380)
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        ttk.Label(dialog,text=company["title"],style="Title.TLabel",wraplength=650,padding=18).pack(fill="x")
        notebook=ttk.Notebook(dialog)
        notebook.pack(fill="both",expand=True,padx=18,pady=8)
        details=ttk.Frame(notebook,padding=10)
        notebook.add(details,text="Detalji")
        for group,fields in GROUPS.items():
            section=ttk.LabelFrame(details,text=group,padding=8)
            section.pack(fill="x",pady=(0,7))
            for idx,(key,label) in enumerate(fields):
                col=idx%3;row=(idx//3)*2
                section.columnconfigure(col,weight=1,uniform="field")
                ttk.Label(section,text=label,style="Muted.TLabel").grid(row=row,column=col,sticky="w")
                value=tk.Text(section,height=1,wrap="word",background=PANEL,foreground=TEXT,relief="flat",font=("Segoe UI",10))
                value.insert("1.0",str(company.get(key) or "—"))
                value.configure(state="disabled")
                value.grid(row=row+1,column=col,sticky="ew",padx=(0,8),pady=(0,5))
        history=ttk.Frame(notebook,padding=10)
        notebook.add(history,text="Povijest promjena")
        history_text=tk.Text(history,bg=PANEL,fg=TEXT,wrap="word",relief="flat")
        history_text.pack(fill="both",expand=True)
        history_text.insert("end","Učitavanje…")
        history_text.configure(state="disabled")
        def fill_history(rows):
            if not dialog.winfo_exists():return
            history_text.configure(state="normal");history_text.delete("1.0","end")
            for row in rows:
                history_text.insert("end",str(row.get("changed_at",""))+"\n")
                for field,change in row.get("changes",{}).items():
                    history_text.insert("end",f"{field}: {change.get('before','')} → {change.get('after','')}\n")
                history_text.insert("end","\n")
            alternatives=company.get("alternate_values",[])
            if alternatives:
                history_text.insert("end","Dodatne vrijednosti\n")
                for row in alternatives:history_text.insert("end",f"{row['field']}: {row['value']}\n")
            if not rows and not alternatives:history_text.insert("end","Nema evidentiranih promjena.")
            history_text.configure(state="disabled")
        extra=ttk.Frame(notebook,padding=10)
        notebook.add(extra,text="Dodatni poslovni podaci")
        snap=tk.StringVar();snapbox=ttk.Combobox(extra,textvariable=snap,state="readonly")
        snapbox.pack(fill="x",pady=(0,8))
        extra_text=tk.Text(extra,bg=PANEL,fg=TEXT,wrap="word",relief="flat")
        extra_text.pack(fill="both",expand=True)
        extra_text.configure(state="disabled")
        offset=0
        generation=0
        nav=ttk.Frame(extra);nav.pack(fill="x",pady=8)
        prev=ttk.Button(nav,text="Prethodna",state="disabled")
        next_page=ttk.Button(nav,text="Sljedeća",state="disabled")
        prev.pack(side="left");next_page.pack(side="right")
        def load():
            nonlocal generation
            generation+=1
            seq=generation
            prev.configure(state="disabled");next_page.configure(state="disabled")
            def done(data):
                if not dialog.winfo_exists() or seq!=generation:return
                snapbox.configure(values=[item["snapshot"] for item in data["snapshots"]])
                snap.set(data["snapshot"])
                extra_text.configure(state="normal");extra_text.delete("1.0","end")
                for row in data["rows"]:
                    extra_text.insert("end",row["category"].replace("_"," ").capitalize()+"\n")
                    for field,value in row["data"].items():
                        extra_text.insert("end",field.replace("_"," ")+": "+(json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value or "—"))+"\n")
                    extra_text.insert("end","\n")
                if not data["rows"]:extra_text.insert("end","Nema dodatnih poslovnih zapisa.")
                extra_text.configure(state="disabled")
                prev.configure(state="normal" if offset else "disabled")
                next_page.configure(state="normal" if data["next"] else "disabled")
            params={"snapshot":snap.get(),"offset":offset}
            self.submit(lambda:self.client.request(f"/api/company-registry/{company['id']}",params),done)
        def move(delta):
            nonlocal offset
            offset=max(0,offset+delta)
            load()
        def changed(_event):
            nonlocal offset
            offset=0
            load()
        snapbox.bind("<<ComboboxSelected>>",changed)
        prev.configure(command=lambda:move(-25));next_page.configure(command=lambda:move(25))
        loaded=set()
        def tab_changed(_event):
            index=notebook.index(notebook.select())
            if index in loaded:return
            loaded.add(index)
            if index==1:self.submit(lambda:self.client.request(f"/api/history/{company['id']}"),fill_history)
            if index==2:load()
        notebook.bind("<<NotebookTabChanged>>",tab_changed)
        ttk.Button(dialog,text="Zatvori",command=dialog.destroy).pack(anchor="e",padx=18,pady=10)
        if self.smoke:
            self.result=0 if company.get("title")=="Sintetička tvrtka" else 1
            dialog.destroy()
            self.close()

    def duplicate_dialog(self):
        if not self.client or self.merge_active:return
        dialog=tk.Toplevel(self.root)
        dialog.title("Tvrtke – pregled duplikata")
        dialog.geometry("900x650")
        dialog.minsize(720,460)
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        frame=ttk.Frame(dialog,padding=18)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Pregled mogućih duplikata",style="Title.TLabel").pack(anchor="w")
        status=tk.StringVar(value="Provjera podataka…")
        ttk.Label(frame,textvariable=status,wraplength=800).pack(anchor="w",pady=8)
        table=ttk.Treeview(frame,columns=("name","city","address"),show="headings",selectmode="extended",height=7)
        for key,label,width in (("name","Tvrtka",330),("city","Grad",140),("address","Adresa",280)):
            table.heading(key,text=label)
            table.column(key,width=width)
        table.pack(fill="both",expand=True)
        preview=tk.Text(frame,height=9,bg=PANEL,fg=TEXT,wrap="word",relief="flat")
        preview.pack(fill="both",expand=True,pady=8)
        preview.configure(state="disabled")
        pairs={}
        busy=False
        def selected(_event=None):
            preview.configure(state="normal");preview.delete("1.0","end")
            selection=table.selection()
            if selection:
                row=pairs[selection[0]]
                for key,label in (("legacy","Raniji zapis"),("canonical","Zapis koji ostaje")):
                    item=row[key]
                    preview.insert("end",label+"\n"+"\n".join(f"{name}: {item[field] or '—'}" for field,name in (("title","Naziv"),("city","Grad"),("address","Adresa"),("oib","OIB"),("mbs","MBS"),("email","E-pošta"),("phone","Telefon")))+"\n\n")
            preview.configure(state="disabled")
            apply.configure(state="normal" if selection and not busy else "disabled")
        table.bind("<<TreeviewSelect>>",selected)
        def loaded(data):
            if not dialog.winfo_exists():return
            pairs.clear();table.delete(*table.get_children())
            for row in data["pairs"]:
                item=row["legacy"];identifier=str(item["id"]);pairs[identifier]=row
                table.insert("","end",iid=identifier,values=(item["title"],item["city"],item["address"]))
            status.set(f"Pronađeno mogućih duplikata: {data['count']}. Odaberite samo potvrđene parove. Jednaki naziv i adresa nisu dokaz jednakog identiteta.")
            selected()
        def failed(_error):
            nonlocal busy
            busy=False
            self.merge_active=False
            if dialog.winfo_exists():
                status.set("Operacija nije uspjela. Podaci nisu označeni kao spojeni.")
                selected()
        def merge_selected():
            nonlocal busy
            if busy or self.merge_active:return
            chosen=[pairs[x] for x in table.selection()]
            if not chosen or len(chosen)>100:return
            if not messagebox.askyesno("Tvrtke",f"Potvrđujete da {len(chosen)} odabranih parova predstavlja iste poslovne subjekte? Prije spajanja izradit će se provjerena sigurnosna kopija.",parent=dialog):return
            data={"confirmed":True,"pairs":[{"legacy":r["legacy"]["id"],"canonical":r["canonical"]["id"],"fingerprint":r["fingerprint"]} for r in chosen]}
            busy=True
            self.merge_active=True
            apply.configure(state="disabled")
            status.set("Izrada sigurnosne kopije i spajanje…")
            def complete(result):
                self.merge_active=False
                if dialog.winfo_exists():
                    messagebox.showinfo("Tvrtke",f"Spojeno zapisa: {result['merged']}. Sigurnosna kopija: {result['backup']}",parent=dialog)
                    dialog.destroy()
                if self.current_view=="overview":self.refresh_overview()
                else:self.refresh()
            self.submit(lambda:self.client.request("/api/duplicates/merge",data=data,timeout=900),complete,failed)
        buttons=ttk.Frame(frame);buttons.pack(fill="x")
        apply=ttk.Button(buttons,text="Spoji potvrđene parove",style="Accent.TButton",command=merge_selected,state="disabled")
        apply.pack(side="left")
        ttk.Button(buttons,text="Zatvori",command=lambda:dialog.destroy() if not busy else None).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW",lambda:dialog.destroy() if not busy else None)
        self.submit(lambda:self.client.request("/api/duplicates"),loaded,failed)

    def sync_dialog(self):
        if not self.client:return
        dialog=tk.Toplevel(self.root)
        dialog.title("Tvrtke – sinkronizacija")
        dialog.geometry("550x420")
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        frame=ttk.Frame(dialog,padding=18)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Osvježavanje podataka",style="Title.TLabel").pack(anchor="w",pady=(0,10))
        access=tk.StringVar(value="Provjera pristupa…")
        ttk.Label(frame,textvariable=access,wraplength=500).pack(anchor="w")
        def update_access(data):
            if dialog.winfo_exists():access.set("Pristup je konfiguriran." if data["configured"] else "Pristup nije konfiguriran.")
        self.submit(lambda:self.client.request("/api/registry"),update_access)
        user=tk.StringVar()
        secret=tk.StringVar()
        ttk.Label(frame,text="Identifikator pristupa").pack(anchor="w",pady=(12,0))
        ttk.Entry(frame,textvariable=user).pack(fill="x")
        ttk.Label(frame,text="Tajni ključ").pack(anchor="w",pady=(8,0))
        ttk.Entry(frame,textvariable=secret,show="•").pack(fill="x")
        persist=tk.BooleanVar(value=True)
        ttk.Checkbutton(frame,text="Spremi u sigurnu pohranu sustava",variable=persist).pack(anchor="w",pady=8)
        def save():
            if not messagebox.askyesno("Tvrtke","Potvrđujete ovlašteni pristup podacima?",parent=dialog):return
            data={"client_id":user.get(),"client_secret":secret.get(),"persist":persist.get(),"permission":True}
            secret.set("")
            self.submit(lambda:self.client.request("/api/registry/credentials",data=data),update_access)
        ttk.Button(frame,text="Spremi pristup",command=save).pack(anchor="w")
        def start():
            if not messagebox.askyesno("Tvrtke","Pokrenuti osvježavanje poslovnih podataka?",parent=dialog):return
            self.sync_active=True
            self.submit(lambda:self.client.request("/api/registry/start",data={"permission":True,"limit":500}),lambda _:dialog.destroy() if dialog.winfo_exists() else None)
        buttons=ttk.Frame(frame)
        buttons.pack(fill="x",pady=12)
        ttk.Button(buttons,text="Pokreni",style="Accent.TButton",command=start).pack(side="left")
        ttk.Button(buttons,text="Zaustavi",command=lambda:self.submit(lambda:self.client.request("/api/stop",data={}),lambda _:None)).pack(side="left",padx=8)
        ttk.Button(buttons,text="Zatvori",command=dialog.destroy).pack(side="right")

    def poll_sync(self):
        if self.closed or not self.client:return
        def done(data):
            self.sync_polling=False
            state=data.get("status")
            if data.get("kind")!="registry":return
            if state in ("running","stopping"):
                self.sync_active=True
                if data.get("phase")=="projection":
                    self.status.set(f"Obrada tvrtki: {data.get('projected',0)} / {data.get('projection_total',0)}")
                else:self.status.set("Sinkronizacija je u tijeku…")
            elif self.sync_active:
                self.sync_active=False
                if state=="completed":
                    self.page=1
                    if self.current_view=="overview":self.refresh_overview()
                    else:self.refresh()
                    self.submit(lambda:(self.client.request("/api/cities"),self.client.request("/api/industries")),self.facets)
                else:self.status.set("Sinkronizacija nije završena.")
        if not self.sync_polling:
            self.sync_polling=True
            def failed(_exc):self.sync_polling=False
            self.submit(lambda:self.client.request("/api/status"),done,failed)
        if self.current_view=="registry":self.refresh_registry()
        self.root.after(3500,self.poll_sync)

    def backup_dialog(self):
        if not self.client:return
        dialog=tk.Toplevel(self.root)
        dialog.title("Tvrtke – sigurnosne kopije")
        dialog.geometry("530x280")
        dialog.configure(bg=BG)
        frame=ttk.Frame(dialog,padding=18)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Sigurnosna kopija",style="Title.TLabel").pack(anchor="w")
        status=tk.StringVar(value="Izradite novu provjerenu kopiju postojećeg radnog prostora.")
        ttk.Label(frame,textvariable=status,wraplength=470).pack(anchor="w",pady=16)
        def create():
            if not messagebox.askyesno("Tvrtke","Izraditi novu sigurnosnu kopiju?",parent=dialog):return
            button.configure(state="disabled")
            status.set("Izrada kopije…")
            def done(_result):
                if dialog.winfo_exists():
                    status.set("Sigurnosna kopija je izrađena.")
                    button.configure(state="normal")
            def failed(_exc):
                if dialog.winfo_exists():
                    status.set("Izrada nije uspjela. Postojeći podaci su očuvani.")
                    button.configure(state="normal")
            self.submit(lambda:self.client.request("/api/recovery/create",data={}),done,failed)
        button=ttk.Button(frame,text="Izradi kopiju",style="Accent.TButton",command=create)
        button.pack(anchor="w")
        ttk.Button(frame,text="Zatvori",command=dialog.destroy).pack(anchor="e",pady=12)

    def close(self):
        if self.merge_active:
            self.status.set("Pričekajte završetak sigurne obrade duplikata.")
            return
        if self.closed:
            return
        if self.worker is None and not self.smoke:
            if not messagebox.askyesno("Tvrtke","Prekinuti pripremu radnog prostora?"):
                return
        self.closed=True
        self.cancel_start.set()
        self.root.destroy()
        # Pending startup can produce a worker after the event loop closes.
        self.pool.shutdown(wait=True,cancel_futures=True)
        if self.worker:
            self.worker.close()
        while not self.events.empty():
            future,_,_=self.events.get_nowait()
            if future.done() and not future.cancelled():
                try:
                    result=future.result()
                    if isinstance(result,WorkerProcess) and result is not self.worker:result.close()
                except Exception:
                    pass

def main():
    if "--worker" in sys.argv:
        from tvrtk_scraper import main as worker_main
        return worker_main()
    parser=argparse.ArgumentParser(description="Tvrtke – poslovni imenik")
    parser.add_argument("--data-dir",type=Path,default=workspace_path())
    parser.add_argument("--native-smoke",action="store_true")
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="crawlvora-widget-test-") if args.native_smoke else nullcontext() as tmp:
        if args.native_smoke:
            from core import Store
            args.data_dir=Path(tmp)
            store=Store(args.data_dir/"companies.sqlite3")
            with store.db() as db:store.upsert(db,{"title":"Sintetička tvrtka","mbs":"000000001"},provider="registry")
        root=tk.Tk()
        app=Desktop(root,args.data_dir,args.native_smoke)
        if args.native_smoke:root.after(90000,app.close)
        root.mainloop()
        return app.result if args.native_smoke else 0

if __name__=="__main__":
    sys.exit(main())
