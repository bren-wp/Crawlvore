"""Crawlvora native desktop migration: Tcl/Tk widgets, no browser renderer."""
import argparse
from contextlib import nullcontext
import os
import queue
import sys
import tempfile
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import ttk, messagebox
from native_client import WorkerProcess

BG, PANEL, TEXT, MUTED, ACCENT = "#111923", "#1a2735", "#e7edf5", "#a9b9cb", "#43d2af"
CONTACTS = {"Sve adrese": "", "Ima e-poštu": "email", "Ima telefon": "phone", "Ima web": "web"}
GROUPS = {
    "Identifikacija": (("oib","OIB"),("mbs","MBS"),("industry","Djelatnost"),("year","Godina osnivanja")),
    "Kontakt i sjedište": (("email","E-pošta"),("phone","Telefon"),("website","Web"),("address","Adresa"),("postal","Poštanski broj"),("city","Grad")),
    "Poslovni podaci": (("employees","Zaposlenici"),("description","Opis"),("products","Proizvodi i usluge"))
}

def workspace_path():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Crawlvora"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home()/".local/share"))) / "Crawlvora"

class Desktop:
    def __init__(self, root, workspace, smoke=False):
        self.root, self.smoke = root, smoke
        self.cancel_start=threading.Event()
        self.worker = None
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
        root.title("Crawlvora")
        root.geometry("1120x730")
        root.minsize(820, 540)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL, font=("Segoe UI", 10))
        style.configure("TButton", background=PANEL, padding=(12,8), borderwidth=0)
        style.map("TButton", background=[("active","#30475a"),("pressed","#30475a")])
        style.configure("Accent.TButton", background=ACCENT, foreground=BG)
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=32)
        style.configure("Treeview.Heading", background=BG, foreground=MUTED, relief="flat")
        style.map("Treeview", background=[("selected","#245668")])
        style.configure("TCombobox", fieldbackground=PANEL, foreground=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly",PANEL)], foreground=[("readonly",TEXT)])
        style.configure("Title.TLabel", font=("Segoe UI",20,"bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        self.status = tk.StringVar(value="Priprema radnog prostora…")
        self.header = ttk.Frame(root,padding=18)
        self.header.pack(fill="x")
        ttk.Label(self.header,text="Crawlvora",style="Title.TLabel").pack(side="left")
        self.stats = tk.StringVar(value="")
        ttk.Label(self.header,textvariable=self.stats,style="Muted.TLabel").pack(side="right")
        self.body = ttk.Frame(root,padding=(18,0,18,14))
        self.body.pack(fill="both",expand=True)
        ttk.Label(root,textvariable=self.status,style="Muted.TLabel",padding=(18,8)).pack(fill="x")
        navigation=ttk.Frame(self.body)
        navigation.pack(fill="x",pady=(0,12))
        ttk.Button(navigation,text="Sinkronizacija",command=self.sync_dialog).pack(side="left")
        ttk.Button(navigation,text="Izrada kopije",command=self.backup_dialog).pack(side="left",padx=8)
        self.build_directory()
        self.root.after(40,self.drain)
        self.submit(lambda:WorkerProcess(workspace,smoke=smoke,cancel=self.cancel_start),self.started)

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
        self.refresh()
        self.poll_sync()

    def facets(self, result):
        cities,industries = result
        self.citybox.configure(values=["Svi gradovi"]+[x if isinstance(x,str) else x.get("city","") for x in cities])
        self.industrybox.configure(values=["Sve djelatnosti"]+industries)

    def build_directory(self):
        ttk.Label(self.body,text="Poslovni imenik",style="Title.TLabel").pack(anchor="w",pady=(0,12))
        filters=ttk.Frame(self.body)
        filters.pack(fill="x",pady=(0,10))
        self.query=tk.StringVar()
        self.city=tk.StringVar(value="Svi gradovi")
        self.industry=tk.StringVar(value="Sve djelatnosti")
        self.contact=tk.StringVar(value="Sve adrese")
        ttk.Label(filters,text="Naziv, OIB ili MBS").grid(row=0,column=0,sticky="w")
        entry=ttk.Entry(filters,textvariable=self.query)
        entry.grid(row=1,column=0,sticky="ew",padx=(0,8))
        for index,label,var,values in ((1,"Grad",self.city,["Svi gradovi"]),(2,"Djelatnost (NKD)",self.industry,["Sve djelatnosti"]),(3,"Kontakt",self.contact,list(CONTACTS))):
            ttk.Label(filters,text=label).grid(row=0,column=index,sticky="w")
            box=ttk.Combobox(filters,textvariable=var,values=values,state="readonly",width=18)
            box.grid(row=1,column=index,sticky="ew",padx=(0,8))
            box.bind("<<ComboboxSelected>>",lambda _e:self.schedule_search())
            if index==1:self.citybox=box
            if index==2:self.industrybox=box
        filters.columnconfigure(0,weight=3)
        filters.columnconfigure(2,weight=2)
        ttk.Button(filters,text="Pretraži",style="Accent.TButton",command=self.schedule_search).grid(row=1,column=4)
        self.query.trace_add("write",lambda *_:self.schedule_search())
        table=ttk.Frame(self.body)
        table.pack(fill="both",expand=True)
        self.tree=ttk.Treeview(table,columns=("name","oib","city","industry","email"),show="headings",selectmode="browse")
        for key,label,width in (("name","Tvrtka",270),("oib","OIB",100),("city","Grad",110),("industry","Djelatnost",230),("email","E-pošta",180)):
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
        params={"q":self.query.get(),"city":"" if self.city.get()=="Svi gradovi" else self.city.get(),
                "industry":"" if self.industry.get()=="Sve djelatnosti" else self.industry.get(),
                "contact":CONTACTS.get(self.contact.get(),""),"page":self.page,"limit":25}
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
        for group,fields in GROUPS.items():
            frame=ttk.Frame(notebook,padding=12)
            notebook.add(frame,text=group)
            for key,label in fields:
                ttk.Label(frame,text=label,style="Muted.TLabel").pack(anchor="w")
                value=tk.Text(frame,height=2,wrap="word",background=PANEL,foreground=TEXT,relief="flat",font=("Segoe UI",10))
                value.insert("1.0",str(company.get(key) or "—"))
                value.configure(state="disabled")
                value.pack(fill="x",pady=(0,5))
        ttk.Button(dialog,text="Zatvori",command=dialog.destroy).pack(anchor="e",padx=18,pady=10)
        if self.smoke:
            self.result=0 if company.get("title")=="Sintetička tvrtka" else 1
            dialog.destroy()
            self.close()

    def sync_dialog(self):
        if not self.client:return
        dialog=tk.Toplevel(self.root)
        dialog.title("Crawlvora – sinkronizacija")
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
            if not messagebox.askyesno("Crawlvora","Potvrđujete ovlašteni pristup podacima?",parent=dialog):return
            data={"client_id":user.get(),"client_secret":secret.get(),"persist":persist.get(),"permission":True}
            secret.set("")
            self.submit(lambda:self.client.request("/api/registry/credentials",data=data),update_access)
        ttk.Button(frame,text="Spremi pristup",command=save).pack(anchor="w")
        def start():
            if not messagebox.askyesno("Crawlvora","Pokrenuti osvježavanje poslovnih podataka?",parent=dialog):return
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
                    self.refresh()
                    self.submit(lambda:(self.client.request("/api/cities"),self.client.request("/api/industries")),self.facets)
                else:self.status.set("Sinkronizacija nije završena.")
        if not self.sync_polling:
            self.sync_polling=True
            def failed(_exc):self.sync_polling=False
            self.submit(lambda:self.client.request("/api/status"),done,failed)
        self.root.after(3500,self.poll_sync)

    def backup_dialog(self):
        if not self.client:return
        dialog=tk.Toplevel(self.root)
        dialog.title("Crawlvora – sigurnosne kopije")
        dialog.geometry("530x280")
        dialog.configure(bg=BG)
        frame=ttk.Frame(dialog,padding=18)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Sigurnosna kopija",style="Title.TLabel").pack(anchor="w")
        status=tk.StringVar(value="Izradite novu provjerenu kopiju postojećeg radnog prostora.")
        ttk.Label(frame,textvariable=status,wraplength=470).pack(anchor="w",pady=16)
        def create():
            if not messagebox.askyesno("Crawlvora","Izraditi novu sigurnosnu kopiju?",parent=dialog):return
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
        if self.closed:
            return
        if self.worker is None and not self.smoke:
            if not messagebox.askyesno("Crawlvora","Prekinuti pripremu radnog prostora?"):
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
    parser=argparse.ArgumentParser(description="Crawlvora nativno sučelje")
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
