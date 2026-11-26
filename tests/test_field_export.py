import csv
import json
import tempfile
import unittest
from pathlib import Path

from core import Store
from field_export import export_selected, selected_fields


class FieldExportTests(unittest.TestCase):
    def test_selection_formats_and_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            store=Store(root/'data.sqlite3')
            store.import_json(json.dumps([{'title':'Alpha','city':'Rijeka','email':'business@example.test','phone':'00123'},{'title':'Beta','city':'Zagreb','email':'business@example.test'},{'title':'Gamma'}]))
            path=root/'out.csv'
            export_selected(store,path,['email'],'csv',distinct=True)
            with path.open(encoding='utf-8-sig',newline='') as stream:
                self.assertEqual(list(csv.reader(stream)),[['email'],['business@example.test']])
            path=root/'out.json'
            export_selected(store,path,['title','phone'],'json',city='Rijeka')
            self.assertEqual(json.loads(path.read_text()),[{'title':'Alpha','phone':'00123'}])
            path=root/'out.xlsx'
            export_selected(store,path,['phone'],'xlsx')
            from openpyxl import load_workbook
            wb=load_workbook(path,read_only=True)
            try: self.assertEqual(list(wb.active.values),[('phone',),('00123',)])
            finally: wb.close()

    def test_allowlist(self):
        for value in ('','email,email','password','email FROM companies'):
            with self.assertRaises(ValueError): selected_fields(value)
