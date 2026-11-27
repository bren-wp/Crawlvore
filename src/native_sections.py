"""Native secondary pages using the same authenticated business API."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from native_transfer import upload,download
from native_theme import Card, PANEL, TEXT, MUTED, ACCENT, PANEL2

FORMATS={"CSV":"csv","JSON":"json","Excel":"xlsx"}
FIELDS={"title":"Naziv tvrtke","email":"E-pošta","phone":"Telefon","oib":"OIB","mbs":"MBS","website":"Web","city":"Grad","address":"Adresa","postal":"Poštanski broj","country":"Država","industry":"Djelatnost"}
STATES={"queued":"Na čekanju","retry_wait":"Čeka ponavljanje","running":"Aktivno","completed":"Završeno","failed":"Pogreška","cancelled":"Otkazano","interrupted":"Prekinuto"}

class SecondaryPages:
    def section_header(self,view,kicker,title,description):
        ttk.Label(view,text=kicker,style="Kicker.TLabel").pack(anchor="w")
        ttk.Label(view,text=title,style="Title.TLabel").pack(anchor="w",pady=(2,2))
        ttk.Label(view,text=description,style="Muted.TLabel").pack(anchor="w",pady=(0,12))
    def two_columns(self,view):
        grid=ttk.Frame(view);grid.pack(fill="both",expand=True)
        for index in (0,1):grid.columnconfigure(index,weight=1,uniform="column")
        return grid
    def panel(self,grid,title,column,row=0):
        panel=Card(grid,title,padding=15)
        panel.grid(row=row,column=column,sticky="nsew",padx=(0,12 if column==0 else 0),pady=(0,12))
        return panel
    def build_jobs(self):
        view=self.views["jobs"]
        heading=ttk.Frame(view);heading.pack(fill="x")
        copy=ttk.Frame(heading);copy.pack(side="left",fill="x",expand=True)
        self.section_header(copy,"AUTOMATIZACIJA","Zadaci i raspored","Planirajte prikupljanje i pratite izvršavanje u jednom radnom prostoru.")
        ttk.Button(heading,text="Osvježi",command=self.refresh_jobs).pack(side="right",padx=(6,0))
        grid=ttk.Frame(view);grid.pack(fill="x")
        grid.columnconfigure(0,weight=5);grid.columnconfigure(1,weight=4)
        left=Card(grid,padding=15)
        left.grid(row=0,column=0,sticky="nsew",padx=(0,12),pady=(0,12))
        right=self.panel(grid,"Radni red",1)
        self.schedule_state=tk.StringVar(value="—")
        schedule_header=ttk.Frame(left,style="PanelInner.TFrame");schedule_header.pack(fill="x",pady=(0,8))
        ttk.Label(schedule_header,text="Dnevna sinkronizacija",style="PanelTitle.TLabel").pack(side="left")
        ttk.Label(schedule_header,textvariable=self.schedule_state,style="Hint.TLabel").pack(side="right")
        ttk.Label(left,text="Tvrtke · radni dani",style="PanelMuted.TLabel").pack(anchor="w",pady=(0,8))
        self.schedule_enabled=tk.BooleanVar()
        self.schedule_permission=tk.BooleanVar()
        self.schedule_hour=tk.StringVar(value="3")
        ttk.Checkbutton(left,text="Automatsko osvježavanje",variable=self.schedule_enabled).pack(anchor="w",pady=6)
        ttk.Label(left,text="Sat pokretanja (lokalno vrijeme)").pack(anchor="w")
        ttk.Spinbox(left,from_=0,to=23,textvariable=self.schedule_hour,width=12).pack(fill="x",pady=6)
        ttk.Checkbutton(left,text="Imam ovlaštenje za automatsko osvježavanje",variable=self.schedule_permission).pack(anchor="w")
        buttons=ttk.Frame(left);buttons.pack(fill="x",pady=12)
        ttk.Button(buttons,text="Spremi raspored",style="Accent.TButton",command=self.save_schedule).pack(side="left")
        ttk.Button(buttons,text="+ Sinkronizacija",command=self.enqueue_sync).pack(side="left",padx=8)
        ttk.Label(left,text="Aplikacija mora biti pokrenuta. Privremene mrežne pogreške ponavljaju se najviše dva puta.",style="PanelMuted.TLabel",wraplength=360).pack(anchor="w",pady=(4,0))
        self.job_metrics=tk.StringVar(value="—")
        ttk.Label(right,text="Serijsko izvršavanje bez paralelnih zahtjeva.",wraplength=320,style="PanelMuted.TLabel").pack(anchor="w",pady=(0,12))
        counts_grid=ttk.Frame(right,style="PanelInner.TFrame");counts_grid.pack(fill="x")
        self.job_count_values={}
        for i,key in enumerate(("queued","retry_wait","running","completed","failed")):
            col=i%4;counts_grid.columnconfigure(col,weight=1,uniform="jobs")
            card=Card(counts_grid,padding=8,outer=PANEL)
            card.grid(row=i//4,column=col,sticky="nsew",padx=(0,6),pady=(0,6))
            ttk.Label(card,text=STATES[key],style="PanelMuted.TLabel",wraplength=70).pack(anchor="w")
            value=tk.StringVar(value="—");self.job_count_values[key]=value
            ttk.Label(card,textvariable=value,style="Metric.TLabel").pack(anchor="w",pady=(4,0))
        self.register_grid(counts_grid,4)
        ttk.Label(right,text="Aktivno osvježavanje možete zaustaviti u sinkronizaciji.",style="PanelMuted.TLabel",wraplength=320).pack(anchor="w",pady=(8,0))
        self.register_grid(grid,2)
        history=Card(view,"Povijest zadataka",padding=15);history.pack(fill="both",expand=True,pady=(8,0))
        self.job_table=ttk.Treeview(history,columns=("id","source","state","created","finished","attempts"),show="headings",height=3)
        for key,label,width in (("id","BR.",40),("source","IZVOR",90),("state","STATUS",110),("created","DODANO (UTC)",140),("finished","ZAVRŠENO (UTC)",140),("attempts","POKUŠAJI",85)):
            self.job_table.heading(key,text=label,anchor="w");self.job_table.column(key,width=width)
        self.job_table.pack(fill="both",expand=True)
        buttons=ttk.Frame(history);buttons.pack(fill="x",pady=6)
        self.job_empty=tk.StringVar(value="Učitavanje zadataka…")
        ttk.Label(buttons,textvariable=self.job_empty,style="PanelMuted.TLabel").pack(side="left")
        self.job_cancel=ttk.Button(buttons,text="Otkaži odabrani zadatak",command=self.cancel_job,state="disabled")
        self.job_cancel.pack(side="right",padx=6)
        self.job_states={}
        def selected(_event):
            selection=self.job_table.selection()
            self.job_cancel.configure(state="normal" if selection and self.job_states.get(selection[0]) in ("queued","retry_wait") else "disabled")
        self.job_table.bind("<<TreeviewSelect>>",selected)
    def refresh_jobs(self):
        if not self.client:return
        def done(data):
            self.schedule_enabled.set(bool(data["schedule"]["enabled"]))
            self.schedule_hour.set(str(data["schedule"]["hour"]))
            self.schedule_state.set("Uključeno" if data["schedule"]["enabled"] else "Isključeno")
            self.job_states.clear()
            self.job_cancel.configure(state="disabled")
            self.job_table.delete(*self.job_table.get_children())
            counts={key:0 for key in ("queued","retry_wait","running","completed","failed")}
            for row in data["jobs"]:
                state=row["state"]
                if state in counts:counts[state]+=1
                self.job_states[str(row["id"])]=state
                self.job_table.insert("","end",iid=str(row["id"]),values=(row["id"],"Tvrtke" if row["kind"]=="registry" else "Ostalo",STATES.get(state,state),row["created"],row["finished"] or "—",row["attempts"]))
            for key,count in counts.items():self.job_count_values[key].set(str(count))
            self.job_empty.set("" if data["jobs"] else "Nema spremljenih zadataka.")
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
        self.register_grid(grid,2)
        self.import_path=None
        self.import_label=tk.StringVar(value="Nije odabrana datoteka.")
        ttk.Label(left,text="CSV izvornog formata ili JSON lista poslovnih zapisa do 2 GiB.",wraplength=360).pack(anchor="w",pady=(0,8))
        upload_area=ttk.Frame(left,padding=18,style="Upload.TFrame");upload_area.pack(fill="x",pady=(0,8))
        ttk.Label(upload_area,text="↑",style="UploadIcon.TLabel").pack(pady=(4,8))
        ttk.Label(upload_area,text="Odaberite CSV ili JSON datoteku",style="Upload.TLabel").pack()
        ttk.Label(upload_area,text="UTF-8 · najviše 2 GiB",style="Upload.TLabel").pack(pady=(3,8))
        ttk.Button(upload_area,text="Odaberi datoteku",command=self.choose_import).pack(fill="x",pady=6)
        ttk.Label(left,textvariable=self.import_label,wraplength=360).pack(anchor="w",pady=8)
        self.import_button=ttk.Button(left,text="Uvezi zapise",style="Accent.TButton",state="disabled",command=self.run_import)
        self.import_button.pack(anchor="w")
        ttk.Label(right,text="Preuzmite kopiju svih zapisa u odabranom formatu.",style="PanelMuted.TLabel",wraplength=360).pack(anchor="w",pady=(0,8))
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
        heading=ttk.Frame(view);heading.pack(fill="x")
        copy=ttk.Frame(heading);copy.pack(side="left",fill="x",expand=True)
        self.section_header(copy,"POSLOVNA ANALITIKA","Analitika i izvještaji","Pokrivenost, izvori i evidentirane promjene poslovnih podataka.")
        ttk.Button(heading,text="↓ Izvoz CSV",style="Accent.TButton",command=lambda:self.export_file("/api/export","csv",{})).pack(side="right",padx=(6,0))
        top=ttk.Frame(view);top.pack(fill="x",pady=(0,12))
        self.analytics_values={}
        for col,(key,label) in enumerate((("total","Tvrtke u bazi"),("cities","Gradovi"),("phones","S telefonom"),("websites","S web stranicom"))):
            top.columnconfigure(col,weight=1,uniform="metric")
            panel=Card(top,padding=13);panel.grid(row=0,column=col,sticky="nsew",padx=(0,12 if col<3 else 0))
            ttk.Label(panel,text=label,style="Panel.TLabel").pack(anchor="w")
            var=tk.StringVar(value="—");self.analytics_values[key]=var
            ttk.Label(panel,textvariable=var,style="Metric.TLabel").pack(anchor="w",pady=(8,0))
        self.register_grid(top,4)
        grid=ttk.Frame(view);grid.pack(fill="x",pady=(0,12))
        for col in range(3):grid.columnconfigure(col,weight=1,uniform="analytics")
        self.analytics_canvases={}
        for col,(key,label) in enumerate((("sources","Izvori podataka"),("cities","Najzastupljeniji gradovi"),("coverage","Dostupnost podataka"))):
            card=Card(grid,label,padding=15);card.grid(row=0,column=col,sticky="nsew",padx=(0,14 if col<2 else 0))
            canvas=tk.Canvas(card,width=165,height=135,bg=PANEL,highlightthickness=0)
            canvas.pack(fill="x",expand=True)
            self.analytics_canvases[key]=canvas
            canvas.bind("<Configure>",lambda _e:self.draw_analytics())
        self.analytics_data=None
        self.register_grid(grid,3)
        lower=ttk.Frame(view);lower.pack(fill="x")
        lower.columnconfigure(0,weight=9);lower.columnconfigure(1,weight=8)
        history=self.panel(lower,"Povijest promjena",0)
        ttk.Label(history,text="Evidentirane promjene u zadnjih 30 dana (UTC).",style="PanelMuted.TLabel",wraplength=300).pack(anchor="w")
        self.analytics_history=tk.StringVar(value="—")
        ttk.Label(history,textvariable=self.analytics_history,style="Panel.TLabel",justify="left").pack(anchor="w",pady=(12,0))
        exports=self.panel(lower,"Izvoz podataka",1)
        ttk.Label(exports,text="Izvezi poslovnu bazu ili usporedi snimke podataka.",style="PanelMuted.TLabel",wraplength=300).pack(anchor="w")
        buttons=ttk.Frame(exports,style="PanelInner.TFrame");buttons.pack(fill="x",pady=(12,0))
        for label,route in (("Excel","/api/export-xlsx"),("JSON","/api/export-json")):
            ttk.Button(buttons,text="↓ "+label,style="Accent.TButton" if label=="Excel" else "TButton",command=lambda label=label,route=route:self.export_file(route,FORMATS[label],{})).pack(side="left",padx=(0,6))
        ttk.Button(buttons,text="Usporedba snimki",command=self.snapshot_compare_dialog).pack(side="left")
        self.register_grid(lower,2)

    def snapshot_compare_dialog(self):
        if not self.client:return
        dialog=tk.Toplevel(self.root);dialog.title("Tvrtke – usporedba snimki");dialog.geometry("620x420");dialog.configure(bg="#08131e")
        body=ttk.Frame(dialog,padding=16);body.pack(fill="both",expand=True)
        before=tk.StringVar();after=tk.StringVar()
        boxes=[]
        for label,var in (("Prva snimka",before),("Druga snimka",after)):
            ttk.Label(body,text=label).pack(anchor="w")
            box=ttk.Combobox(body,textvariable=var,state="readonly");box.pack(fill="x",pady=6);boxes.append(box)
        result=tk.StringVar(value="Odaberite dvije dovršene snimke.")
        ttk.Label(body,textvariable=result,wraplength=550,justify="left").pack(fill="x",pady=8)
        table_area=ttk.Frame(body);table_area.pack(fill="both",expand=True)
        table=ttk.Treeview(table_area,columns=("name","added","removed","affected"),show="headings",height=5)
        for key,label,width in (("name","Kategorija",200),("added","Dodano",75),("removed","Uklonjeno",75),("affected","Subjekti",80)):
            table.heading(key,text=label,anchor="w");table.column(key,width=width)
        scroll=ttk.Scrollbar(table_area,orient="vertical",command=table.yview)
        table.configure(yscrollcommand=scroll.set);table.pack(side="left",fill="both",expand=True);scroll.pack(side="right",fill="y")
        def loaded(data):
            if not dialog.winfo_exists():return
            ids=[str(row["snapshot"]) for row in data["runs"] if row["complete"]]
            for box in boxes:box.configure(values=ids)
            if len(ids)>=2:before.set(ids[-2]);after.set(ids[-1]);button.configure(state="normal")
            else:result.set("Za usporedbu su potrebne dvije dovršene snimke.")
        def run():
            if before.get()==after.get():result.set("Odaberite različite snimke.");return
            params={"before":before.get(),"after":after.get()}
            button.configure(state="disabled");result.set("Usporedba je u tijeku…")
            def done(data):
                if not dialog.winfo_exists():return
                table.delete(*table.get_children())
                for row in data["categories"]:
                    table.insert("","end",values=(row["category"].replace("_"," "),row.get("added","—"),row.get("removed","—"),row.get("affected_subjects","—")))
                result.set(f"Usporedba završena: {len(data['categories'])} kategorija.")
                button.configure(state="normal")
            def failed(_exc):
                if dialog.winfo_exists():
                    result.set("Usporedba nije uspjela.");button.configure(state="normal")
            self.submit(lambda:self.client.request("/api/registry/diff",params,timeout=900),done,failed)
        button=ttk.Button(body,text="Usporedi",command=run,state="disabled");button.pack(anchor="w")
        self.submit(lambda:self.client.request("/api/registry"),loaded)

    def draw_analytics(self):
        if not self.analytics_data:return
        stats,providers=self.analytics_data
        for key,canvas in self.analytics_canvases.items():
            canvas.delete("all")
            width=max(100,canvas.winfo_width())
            if key=="sources":
                for i,row in enumerate(providers[:6]):
                    y=15+i*29
                    canvas.create_text(0,y,anchor="w",text=row["label"],fill=TEXT,font=("Segoe UI",-12))
                    canvas.create_text(width-1,y,anchor="e",text=f"{row['n']:,}".replace(",","."),fill=TEXT,font=("Segoe UI",-12,"bold"))
                    canvas.create_line(0,y+13,width,y+13,fill=PANEL2)
            elif key=="cities":
                cities=stats["top_cities"][:6]
                maximum=max(1,max((r["n"] for r in cities),default=1))
                for i,row in enumerate(cities):
                    y=8+i*23
                    canvas.create_text(0,y,anchor="w",text=row["city"],fill=TEXT,font=("Segoe UI",-12))
                    canvas.create_text(width-1,y,anchor="e",text=f"{row['n']:,}".replace(",","."),fill=TEXT,font=("Segoe UI",-12,"bold"))
                    self.chart_bar(canvas,y+13,width,row["n"]/maximum)
            else:
                for i,(field,label) in enumerate((("phones","Telefonski broj"),("websites","Web stranica"))):
                    y=10+i*65
                    ratio=stats[field]/max(1,stats["total"])
                    canvas.create_text(0,y,anchor="w",text=label,fill=TEXT,font=("Segoe UI",-12))
                    canvas.create_text(width-1,y,anchor="e",text=f"{ratio:.0%}",fill=TEXT,font=("Segoe UI",-12,"bold"))
                    self.chart_bar(canvas,y+16,width,ratio)
                    canvas.create_text(0,y+34,anchor="w",text=f"{stats[field]:,} / {stats['total']:,}".replace(",","."),fill=MUTED,font=("Segoe UI",-12))

    def refresh_analytics(self):
        if not self.client:return
        def done(result):
            stats,history,providers=result
            for key,var in self.analytics_values.items():var.set(f"{stats[key]:,}".replace(",","."))
            self.analytics_data=(stats,providers)
            self.draw_analytics()
            self.analytics_history.set("\n".join(f"{r['day']}: {r['n']}" for r in history["days"][-5:]) or "Nema evidentiranih promjena.")
        self.submit(lambda:(self.client.request("/api/stats"),self.client.request("/api/analytics"),self.client.request("/api/providers")),done)

    def build_registry(self):
        view=self.views["registry"]
        self.section_header(view,"TVRTKE","Tvrtke","Osvježavanje i pregled dostupnih skupina poslovnih podataka.")
        metrics=ttk.Frame(view);metrics.pack(fill="x",pady=(0,12))
        self.registry_values={}
        for col,(key,label) in enumerate((("runs","Snimke"),("complete","Dovršene snimke"),("categories","Kategorije"),("rows","Izvorni redci"))):
            metrics.columnconfigure(col,weight=1,uniform="metric")
            panel=Card(metrics,padding=15);panel.grid(row=0,column=col,sticky="nsew",padx=(0,12 if col<3 else 0))
            ttk.Label(panel,text=label,style="Panel.TLabel").pack(anchor="w",pady=(0,8))
            var=tk.StringVar(value="—");self.registry_values[key]=var
            ttk.Label(panel,textvariable=var,font=("Segoe UI",22,"bold")).pack(anchor="w")
        self.register_grid(metrics,4)
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
        self.register_grid(grid,2)
        category_panel=Card(view,"Preuzete kategorije",padding=15);category_panel.pack(fill="both",expand=True)
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
        body=tk.Text(dialog,wrap="word",background="#101f2d",foreground="#edf4fa",relief="flat");body.pack(fill="both",expand=True,padx=8)
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
