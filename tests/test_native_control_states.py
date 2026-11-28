"""Native control state checks using real Tcl/Tk, never screenshot substitutes."""
import tkinter as tk
from tkinter import ttk
import unittest

from native_theme import install, ACCENT, ACTIVE, BG, PANEL, PANEL2, TEXT, MUTED, NativeTable, NativeDialog, Card, clear_chart, shade_children


class NativeControlStatesTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Display unavailable: {exc}")
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        install(self.root)
        self.style=ttk.Style(self.root)

    def test_button_states_and_commands(self):
        calls=[]
        for name in ("TButton","Small.TButton","Accent.TButton","Nav.TButton","Active.Nav.TButton"):
            with self.subTest(style=name):
                self.assertEqual(self.style.lookup(name,"foreground",("disabled","active")),MUTED)
                self.assertEqual(self.style.lookup(name,"background",("disabled","pressed")),PANEL)
                self.assertEqual(self.style.lookup(name,"bordercolor",("focus",)),ACCENT)
                button=ttk.Button(self.root,style=name,command=lambda:calls.append(1))
                button.invoke()
                button.state(["disabled"])
                button.invoke()
                button.destroy()
        self.assertEqual(len(calls),5)

    def test_inputs_and_dropdown_palette(self):
        for name in ("TEntry","TCombobox","TSpinbox"):
            with self.subTest(style=name):
                self.assertEqual(self.style.lookup(name,"bordercolor",("focus",)),ACCENT)
                self.assertEqual(self.style.lookup(name,"fieldbackground",("readonly","focus")),BG)
                self.assertEqual(self.style.lookup(name,"fieldbackground",("disabled","focus")),PANEL)
        box=ttk.Combobox(self.root,values=("Prvi","Drugi"),state="readonly")
        box.current(1)
        self.assertEqual(box.get(),"Drugi")
        pop=box.tk.call("ttk::combobox::PopdownWindow",str(box))
        self.assertEqual(box.tk.call(pop+".f.l","cget","-background"),BG)
        self.assertEqual(box.tk.call(pop+".f.l","cget","-foreground"),TEXT)

    def test_table_tabs_and_selection_controls(self):
        self.assertEqual(self.style.lookup("Treeview","background",("selected",)),ACTIVE)
        self.assertEqual(self.style.lookup("TNotebook.Tab","background",("selected",)),ACTIVE)
        self.assertEqual(self.style.lookup("TNotebook.Tab","background",()),PANEL2)
        for name in ("TCheckbutton","Panel.TCheckbutton","TRadiobutton"):
            self.assertEqual(self.style.lookup(name,"indicatorforeground",("selected",)),ACCENT)
            self.assertEqual(self.style.lookup(name,"indicatorforeground",("disabled","selected")),MUTED)
        value=tk.BooleanVar(self.root)
        check=ttk.Checkbutton(self.root,variable=value)
        check.invoke()
        self.assertTrue(value.get())
        check.state(["disabled"])
        check.invoke()
        self.assertTrue(value.get())

    def test_table_hover_preserves_tags_and_selection(self):
        from types import SimpleNamespace
        self.root.deiconify()
        table=NativeTable(self.root,columns=("name",),show="headings",height=3)
        table.pack(fill="both",expand=True)
        a=table.insert("","end",values=("Prvi",),tags=("custom",))
        b=table.insert("","end",values=("Drugi",))
        table.selection_set(a)
        self.root.update()
        for row in (a,b):
            x,y,w,h=table.bbox(row,"name")
            table._pointer(SimpleNamespace(x=x+w//2,y=y+h//2))
            self.assertIn(table._hover_tag,table.item(row,"tags"))
        self.assertEqual(table.item(a,"tags"),("custom",))
        self.assertEqual(table.selection(),(a,))
        table.delete(b)
        self.assertEqual(table._hover_row,"")
        self.assertEqual(table.selection(),(a,))

    def test_shared_dialog_preserves_geometry_and_close(self):
        self.root.deiconify()
        self.root.geometry("500x400+40+40")
        self.root.update()
        dialog=NativeDialog(self.root)
        dialog.geometry("320x220")
        dialog.update()
        self.assertEqual(dialog.cget("background"),BG)
        self.assertEqual((dialog.winfo_width(),dialog.winfo_height()),(320,220))
        dialog.destroy()
        self.assertFalse(dialog.winfo_exists())

    def test_chart_compositing_preserves_live_items_and_checkbox(self):
        self.root.deiconify()
        self.root.geometry("480x360")
        card=Card(self.root,padding=15)
        card.pack(fill="both",expand=True)
        chart=tk.Canvas(card,width=160,height=80,background=PANEL,highlightthickness=0)
        chart.pack(fill="x")
        value=tk.BooleanVar(self.root)
        check=ttk.Checkbutton(card,text="Odabir",variable=value,style="Panel.TCheckbutton")
        check.pack(anchor="w")
        self.root.update()
        surface=next(w for w in card.winfo_children() if getattr(w,"_surface_decoration",False))
        line=chart.create_line(0,0,20,20,fill=ACCENT)
        shade_children(card,surface,PANEL,"#0c1a26",surface.winfo_width(),surface.winfo_height())
        background=chart._chart_background_item
        self.assertIsNotNone(background)
        self.assertEqual(chart.find_all(),(background,line))
        clear_chart(chart)
        self.assertEqual(chart.find_all(),(background,))
        shade_children(card,surface,PANEL,"#0c1a26",surface.winfo_width(),surface.winfo_height())
        self.assertEqual(chart.find_all(),(background,))
        check.invoke()
        self.assertTrue(value.get())
        self.assertEqual(self.style.lookup(check.cget("style"),"indicatorforeground",("selected",)),ACCENT)
        card.destroy()
