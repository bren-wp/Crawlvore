"""Native control state checks using real Tcl/Tk, never screenshot substitutes."""
import tkinter as tk
from tkinter import ttk
import unittest

from native_theme import install, ACCENT, ACTIVE, BG, PANEL, PANEL2, TEXT, MUTED


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
