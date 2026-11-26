import importlib.util
import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

SPEC=importlib.util.spec_from_file_location('companies_house',Path(__file__).resolve().parents[1]/'tools/import_companies_house.py')
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CompaniesHouseTests(unittest.TestCase):
    def test_all_seven_parts_and_unique_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archives=[]
            headers=['CompanyName',' CompanyNumber']+[f'Field{i}' for i in range(53)]
            for n in range(1,8):
                name=f'BasicCompanyData-2026-11-01-part{n}_7'
                path=root/(name+'.zip')
                stream=io.StringIO()
                writer=csv.writer(stream)
                writer.writerow(headers)
                writer.writerow(['Synthetic organization',f'{n:08d}']+['']*53)
                with zipfile.ZipFile(path,'w') as archive:
                    archive.writestr(name+'.csv',stream.getvalue())
                archives.append(path)
            with self.assertRaises(ValueError):
                module.build(archives[:-1],root/'missing')
            report=module.build(archives,root/'GB')
            self.assertEqual(report['rows'],7)
            self.assertEqual(report['country'],'GB')
            self.assertTrue((root/'GB/united-kingdom.sqlite3').exists())
