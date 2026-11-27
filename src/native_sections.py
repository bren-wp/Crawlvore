"""Native secondary pages using the same authenticated business API."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from native_transfer import upload,download

FORMATS={"CSV":"csv","JSON":"json","Excel":"xlsx"}
FIELDS={"title":"Naziv tvrtke","email":"E-pošta","phone":"Telefon","oib":"OIB","mbs":"MBS","website":"Web","city":"Grad","address":"Adresa","postal":"Poštanski broj","country":"Država","industry":"Djelatnost"}
STATES={"queued":"Na čekanju","retry_wait":"Čeka ponavljanje","running":"Aktivno","completed":"Završeno","failed":"Pogreška","cancelled":"Otkazano","interrupted":"Prekinuto"}

class SecondaryPages:
    def section_header(self,view,kicker,title,description):
        ttk.Label(view,text=kicker,foreground="#52d6b0").pack(anchor="w")
        ttk.Label(view,text=title,style="Title.TLabel").pack(anchor="w",pady=(4,4))
        ttk.Label(view,text=description,style="Muted.TLabel").pack(anchor="w",pady=(0,16))
    def two_columns(self,view):
        grid=ttk.Frame(view);grid.pack(fill="both",expand=True)
        for index in (0,1):grid.columnconfigure(index,weight=1,uniform="column")
        return grid
    def panel(self,grid,title,column,row=0):
        panel=ttk.LabelFrame(grid,text=title,padding=14)
        panel.grid(row=row,column=column,sticky="nsew",padx=(0,12 if column==0 else 0),pady=(0,12))
        return panel
    def build_jobs(self):
        view=self.views["jobs"]
        self.section_header(view,"AUTOMATIZACIJA","Zadaci i raspored","Planirajte osvježavanje i pratite izvršavanje zadataka.")
        grid=ttk.Frame(view);grid.pack(fill="x")
        grid.columnconfigure(0,weight=5);grid.columnconfigure(1,weight=4)
        left=self.panel(grid,"Dnevna sinkronizacija",0)
        right=self.panel(grid,"Radni red",1)
        self.schedule_enabled=tk.BooleanVar()
        self.schedule_permission=tk.BooleanVar()
        self.schedule_hour=tk.StringVar(value="3")
        ttk.Checkbutton(left,text="Automatsko osvježavanje",variable=self.schedule_enabled).pack(anchor="w",pady=6)
        ttk.Label(left,text="Sat pokretanja (lokalno vrijeme)").pack(anchor="w")
        ttk.Spinbox(left,from_=0,to=23,textvariable=self.schedule_hour,width=12).pack(anchor="w",pady=6)
        ttk.Checkbutton(left,text="Imam ovlaštenje za automatsko osvježavanje",variable=self.schedule_permission).pack(anchor="w")
        buttons=ttk.Frame(left);buttons.pack(fill="x",pady=12)
        ttk.Button(buttons,text="Spremi raspored",style="Accent.TButton",command=self.save_schedule).pack(side="left")
        ttk.Button(buttons,text="+ Sinkronizacija",command=self.enqueue_sync).pack(side="left",padx=8)
        self.job_metrics=tk.StringVar(value="—")
        ttk.Label(right,textvariable=self.job_metrics,justify="left").pack(anchor="w",pady=8)
        ttk.Label(right,text="Serijsko izvršavanje bez paralelnih zahtjeva.",wraplength=320,style="Muted.TLabel").pack(anchor="w")
        history=ttk.LabelFrame(view,text="Povijest zadataka",padding=14);history.pack(fill="both",expand=True,pady=(8,0))
        self.job_table=ttk.Treeview(history,columns=("id","state","created","finished","attempts"),show="headings",height=6)
        for key,label,width in (("id","Br.",48),("state","Status",130),("created","Dodano (UTC)",150),("finished","Završeno (UTC)",150),("attempts","Pokušaji",65)):
            self.job_table.heading(key,text=label);self.job_table.column(key,width=width)
        self.job_table.pack(fill="both",expand=True)
        buttons=ttk.Frame(history);buttons.pack(fill="x",pady=6)
        ttk.Button(buttons,text="Osvježi",command=self.refresh_jobs).pack(side="right")
        ttk.Button(buttons,text="Otkaži odabrani zadatak",command=self.cancel_job).pack(side="right",padx=6)
    def refresh_jobs(self):
        if not self.client:return
        def done(data):
            self.schedule_enabled.set(bool(data["schedule"]["enabled"]))
            self.schedule_hour.set(str(data["schedule"]["hour"]))
            self.job_table.delete(*self.job_table.get_children())
            counts={key:0 for key in ("queued","retry_wait","running","completed","failed")}
            for row in data["jobs"]:
                state=row["state"]
                if state in counts:counts[state]+=1
                self.job_table.insert("","end",iid=str(row["id"]),values=(row["id"],STATES.get(state,state),row["created"],row["finished"] or "—",row["attempts"]))
            self.job_metrics.set("\n".join(f"{STATES[key]}: {count}" for key,count in counts.items()))
        self.submit(lambda:self.client.request("/api/jobs"),done)
    def save_schedule(self):
        if not self.client:return
        try:
            hour=int(self.schedule_hour.get())
            if not 0<=hour<=23:raise ValueError
        except ValueError:
            self.status.set("Unesite sat od 0 do 23.");return
        data={"enabled":self.schedule_enabled.get(),"hour":hour,"permission":self.schedule_permission.get()}
        self.submit(lambda:self.client.request("/api/jobs/schedule",data=data),lambda _:(self.refresh_jobs(),self.status.set("Raspored je spremljen.")))
    def enqueue_sync(self):
        if not self.client or not messagebox.askyesno("Tvrtke","Potvrđujete ovlašteno osvježavanje podataka?"):return
        self.submit(lambda:self.client.request("/api/jobs/add",data={"kind":"registry","config":{"permission":True,"limit":1000}}),lambda _:self.refresh_jobs())
    def cancel_job(self):
        if not self.client or not self.job_table.selection():return
        identifier=int(self.job_table.selection()[0])
        self.submit(lambda:self.client.request("/api/jobs/cancel",data={"id":identifier}),lambda _:self.refresh_jobs())
    def build_data(self):
        view=self.views["data"]
        self.section_header(view,"UPRAVLJANJE BAZOM","Uvoz i izvoz","Kontrolirajte svoje podatke bez slanja na vanjske servise.")
        grid=self.two_columns(view)
        left=self.panel(grid,"Uvoz podataka",0)
        right=self.panel(grid,"Izvoz podataka",1)
        self.import_path=None
        self.import_label=tk.StringVar(value="Nije odabrana datoteka.")
        ttk.Label(left,text="CSV ili JSON datoteka, najviše 2 GiB.",wraplength=360).pack(anchor="w",pady=8)
        ttk.Button(left,text="Odaberi datoteku",command=self.choose_import).pack(fill="x",pady=6)
        ttk.Label(left,textvariable=self.import_label,wraplength=360).pack(anchor="w",pady=8)
        self.import_button=ttk.Button(left,text="Uvezi zapise",style="Accent.TButton",state="disabled",command=self.run_import)
        self.import_button.pack(anchor="w")
        buttons=ttk.Frame(right);buttons.pack(fill="x",pady=(0,12))
        for label,route in (("CSV","/api/export"),("JSON","/api/export-json"),("Excel","/api/export-xlsx")):
            ttk.Button(buttons,text=label,command=lambda label=label,route=route:self.export_file(route,FORMATS[label],{})).pack(side="left",padx=(0,6))
        fields=ttk.LabelFrame(right,text="Izvoz odabranih polja",padding=8);fields.pack(fill="x")
        self.export_fields={}
        for i,(key,label) in enumerate(FIELDS.items()):
            var=tk.BooleanVar(value=True);self.export_fields[key]=var
            ttk.Checkbutton(fields,text=label,variable=var).grid(row=i//2,column=i%2,sticky="w")
        buttons=ttk.Frame(right);buttons.pack(fill="x",pady=6)
        ttk.Button(buttons,text="Odaberi sve",command=lambda:[v.set(True) for v in self.export_fields.values()]).pack(side="left")
        ttk.Button(buttons,text="Poništi odabir",command=lambda:[v.set(False) for v in self.export_fields.values()]).pack(side="left",padx=6)
        self.export_format=tk.StringVar(value="CSV")
        ttk.Combobox(right,textvariable=self.export_format,values=list(FORMATS),state="readonly").pack(fill="x",pady=8)
        self.export_distinct=tk.BooleanVar(value=True);self.export_filtered=tk.BooleanVar()
        ttk.Checkbutton(right,text="Ukloni duplikate",variable=self.export_distinct).pack(anchor="w")
        ttk.Checkbutton(right,text="Primijeni filtre imenika",variable=self.export_filtered).pack(anchor="w")
        ttk.Button(right,text="Izvezi odabrana polja",style="Accent.TButton",command=self.export_selected).pack(anchor="w",pady=8)
    def choose_import(self):
        name=filedialog.askopenfilename(filetypes=[("Poslovni podaci","*.csv *.json"),("CSV","*.csv"),("JSON","*.json")])
        if name:
            self.import_path=Path(name);self.import_label.set(self.import_path.name)
            self.import_button.configure(state="normal")
    def run_import(self):
        if not self.client or not self.import_path:return
        path=self.import_path
        if not messagebox.askyesno("Tvrtke","Uvesti odabranu datoteku?"):return
        self.import_button.configure(state="disabled")
        self.status.set("Uvoz podataka…")
        def done(data):
            self.import_button.configure(state="normal")
            self.status.set(f"Učitano: {data['read']}, dodano: {data['added']}.")
            self.submit(lambda:(self.client.request("/api/cities"),self.client.request("/api/industries")),self.facets)
        def failed(_exc):
            self.import_button.configure(state="normal");self.status.set("Uvoz nije uspio.")
        route="/api/import-json" if path.suffix.lower()==".json" else "/api/import"
        self.submit(lambda:upload(self.client,route,path),done,failed)
    def export_file(self,route,kind,params):
        if not self.client:return
        path=filedialog.asksaveasfilename(defaultextension="."+kind,initialfile="tvrtke."+kind)
        if not path:return
        self.status.set("Izvoz podataka…")
        self.submit(lambda:download(self.client,route,params,path),lambda _:self.status.set("Izvoz je dovršen."))
    def export_selected(self):
        fields=[key for key,v in self.export_fields.items() if v.get()]
        if not fields:self.status.set("Odaberite najmanje jedno polje.");return
        kind=FORMATS[self.export_format.get()]
        params={"fields":",".join(fields),"format":kind,"omit_empty":"1","distinct":"1" if self.export_distinct.get() else "0"}
        if self.export_filtered.get():params.update(self.directory_filters())
        self.export_file("/api/export-fields",kind,params)
    def build_analytics(self):
        view=self.views["analytics"]
        self.section_header(view,"POSLOVNA ANALITIKA","Analitika i izvještaji","Pokrivenost i evidentirane promjene poslovnih podataka.")
        top=ttk.Frame(view);top.pack(fill="x",pady=(0,12))
        self.analytics_values={}
        for col,(key,label) in enumerate((("total","Tvrtke u bazi"),("cities","Gradovi"),("phones","S telefonom"),("websites","S web stranicom"))):
            top.columnconfigure(col,weight=1,uniform="metric")
            panel=ttk.LabelFrame(top,text=label,padding=12);panel.grid(row=0,column=col,sticky="nsew",padx=(0,6))
            var=tk.StringVar(value="—");self.analytics_values[key]=var
            ttk.Label(panel,textvariable=var,font=("Segoe UI",22,"bold")).pack(anchor="w")
        grid=self.two_columns(view)
        left=self.panel(grid,"Najzastupljeniji gradovi",0)
        right=self.panel(grid,"Dostupnost podataka",1)
        self.analytics_cities=tk.StringVar(value="—");self.analytics_coverage=tk.StringVar(value="—")
        ttk.Label(left,textvariable=self.analytics_cities,justify="left").pack(anchor="w")
        ttk.Label(right,textvariable=self.analytics_coverage,justify="left").pack(anchor="w")
        history=self.panel(grid,"Povijest promjena",0,1)
        self.analytics_history=tk.StringVar(value="—")
        ttk.Label(history,textvariable=self.analytics_history,justify="left").pack(anchor="w")
        exports=self.panel(grid,"Izvoz podataka",1,1)
        for label,route in (("CSV","/api/export"),("JSON","/api/export-json"),("Excel","/api/export-xlsx")):
            ttk.Button(exports,text="Izvoz "+label,command=lambda label=label,route=route:self.export_file(route,FORMATS[label],{})).pack(anchor="w",pady=4)
    def refresh_analytics(self):
        if not self.client:return
        def done(result):
            stats,history=result
            for key,var in self.analytics_values.items():var.set(f"{stats[key]:,}".replace(",","."))
            self.analytics_cities.set("\n".join(f"{r['city']}: {r['n']:,}".replace(",",".") for r in stats["top_cities"]) or "Nema podataka.")
            self.analytics_coverage.set("\n".join(f"{label}: {stats[key]:,} ({100*stats[key]/max(1,stats['total']):.1f}%)" for key,label in (("phones","Telefon"),("websites","Web stranica"))))
            self.analytics_history.set("\n".join(f"{r['day']}: {r['n']}" for r in history["days"][-10:]) or "Nema evidentiranih promjena.")
        self.submit(lambda:(self.client.request("/api/stats"),self.client.request("/api/analytics")),done)

    def build_registry(self):
        view=self.views["registry"]
        self.section_header(view,"TVRTKE","Tvrtke","Osvježavanje i pregled dostupnih skupina poslovnih podataka.")
        metrics=ttk.Frame(view);metrics.pack(fill="x",pady=(0,12))
        self.registry_values={}
        for col,(key,label) in enumerate((("runs","Snimke"),("complete","Dovršene snimke"),("categories","Kategorije"),("rows","Izvorni redci"))):
            metrics.columnconfigure(col,weight=1,uniform="metric")
            panel=ttk.LabelFrame(metrics,text=label,padding=12);panel.grid(row=0,column=col,sticky="nsew",padx=(0,6))
            var=tk.StringVar(value="—");self.registry_values[key]=var
            ttk.Label(panel,textvariable=var,font=("Segoe UI",22,"bold")).pack(anchor="w")
        grid=ttk.Frame(view);grid.pack(fill="x")
        grid.columnconfigure(0,weight=1);grid.columnconfigure(1,weight=1)
        actions=self.panel(grid,"Osvježavanje poslovnih podataka",0)
        operation=self.panel(grid,"Trenutačna operacija",1)
        ttk.Label(actions,text="Veličina stranice").pack(anchor="w")
        self.registry_limit=tk.StringVar(value="1000")
        ttk.Spinbox(actions,from_=1,to=1000,textvariable=self.registry_limit,width=12).pack(anchor="w",pady=4)
        self.registry_permission=tk.BooleanVar()
        ttk.Checkbutton(actions,text="Imam ovlaštenje za osvježavanje",variable=self.registry_permission).pack(anchor="w")
        buttons=ttk.Frame(actions);buttons.pack(fill="x",pady=8)
        self.registry_start=ttk.Button(buttons,text="Nastavi sinkronizaciju",style="Accent.TButton",command=lambda:self.registry_operation("start"))
        self.registry_start.pack(side="left")
        self.registry_stop=ttk.Button(buttons,text="Zaustavi",command=lambda:self.registry_operation("stop"))
        self.registry_stop.pack(side="left",padx=6)
        self.registry_check=ttk.Button(actions,text="Provjeri vezu",command=lambda:self.registry_operation("check"))
        self.registry_check.pack(anchor="w")
        self.registry_progress=tk.StringVar(value="Nema aktivne sinkronizacije")
        ttk.Label(operation,textvariable=self.registry_progress,wraplength=300).pack(anchor="w",pady=8)
        self.registry_bar=ttk.Progressbar(operation,maximum=100);self.registry_bar.pack(fill="x",pady=8)
        category_panel=ttk.LabelFrame(view,text="Preuzete kategorije",padding=12);category_panel.pack(fill="both",expand=True)
        self.registry_table=ttk.Treeview(category_panel,columns=("snapshot","category","rows","status"),show="headings",height=6)
        for key,label,width in (("snapshot","Snimka",90),("category","Kategorija",250),("rows","Redaka",130),("status","Status",100)):
            self.registry_table.heading(key,text=label);self.registry_table.column(key,width=width)
        self.registry_table.pack(fill="both",expand=True)
        buttons=ttk.Frame(category_panel);buttons.pack(fill="x",pady=6)
        ttk.Button(buttons,text="Osvježi",command=self.refresh_registry).pack(side="right")
        ttk.Button(buttons,text="Otvori kategoriju",command=self.open_category).pack(side="right",padx=6)
        self.registry_table.bind("<Double-1>",lambda _e:self.open_category())
        self.registry_items={}

    def refresh_registry(self):
        if not self.client:return
        def done(result):
            data,status=result
            runs=data["runs"];categories=data["categories"]
            for key,value in (("runs",len(runs)),("complete",sum(bool(r["complete"]) for r in runs)),("categories",sum(bool(r["done"]) for r in categories)),("rows",sum(r["rows"] for r in categories))):
                self.registry_values[key].set(f"{value:,}".replace(",","."))
            self.registry_table.delete(*self.registry_table.get_children());self.registry_items.clear()
            for index,row in enumerate(categories):
                self.registry_items[str(index)]=row
                self.registry_table.insert("","end",iid=str(index),values=(row["snapshot"],row["category"],f"{row['rows']} / {row['total'] if row['total'] is not None else '—'}","Preuzeto" if row["done"] else "U tijeku"))
            active=status.get("status") in ("running","stopping")
            self.registry_start.configure(state="normal" if data.get("configured") and not active else "disabled")
            self.registry_check.configure(state="normal" if data.get("configured") and not active else "disabled")
            self.registry_stop.configure(state="normal" if active else "disabled")
            self.registry_progress.set("Sinkronizacija je u tijeku…" if active else "Nema aktivne sinkronizacije")
            self.registry_bar["value"]=100*status.get("projected",0)/max(1,status.get("projection_total",1)) if status.get("phase")=="projection" else 0
        self.submit(lambda:(self.client.request("/api/registry"),self.client.request("/api/status")),done)

    def registry_operation(self,action):
        if not self.client:return
        try:
            limit=int(self.registry_limit.get())
            if not 1<=limit<=1000:raise ValueError
        except ValueError:
            self.status.set("Veličina stranice mora biti od 1 do 1000.");return
        route="/api/stop" if action=="stop" else "/api/registry/"+action
        data={} if action=="stop" else {"permission":self.registry_permission.get(),"limit":limit}
        self.submit(lambda:self.client.request(route,data=data),lambda _:self.refresh_registry())

    def open_category(self):
        if not self.registry_table.selection():return
        row=self.registry_items[self.registry_table.selection()[0]]
        dialog=tk.Toplevel(self.root);dialog.title(row["category"].replace("_"," ").capitalize());dialog.geometry("900x600")
        search=tk.StringVar();page=1
        toolbar=ttk.Frame(dialog,padding=8);toolbar.pack(fill="x")
        ttk.Entry(toolbar,textvariable=search).pack(side="left",fill="x",expand=True)
        body=tk.Text(dialog,wrap="word",background="#111b2a",foreground="#edf2f9",relief="flat");body.pack(fill="both",expand=True,padx=8)
        def load():
            params={"snapshot":row["snapshot"],"category":row["category"],"page":page,"q":search.get()}
            def done(data):
                if not dialog.winfo_exists():return
                body.configure(state="normal");body.delete("1.0","end")
                import json
                for item in data["rows"]:body.insert("end",json.dumps(item,ensure_ascii=False,indent=2)+"\n\n")
                body.configure(state="disabled")
            self.submit(lambda:self.client.request("/api/registry/rows",params),done)
        def move(delta):
            nonlocal page
            page=max(1,page+delta);load()
        def find():
            nonlocal page
            page=1;load()
        ttk.Button(toolbar,text="Pretraži",command=find).pack(side="left",padx=6)
        ttk.Button(toolbar,text="Prethodna",command=lambda:move(-1)).pack(side="left")
        ttk.Button(toolbar,text="Sljedeća",command=lambda:move(1)).pack(side="left",padx=6)
        load()
