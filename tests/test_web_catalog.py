import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC=importlib.util.spec_from_file_location('web_catalog_builder',Path(__file__).resolve().parents[1]/'tools/build_web_catalog.py')
builder=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

class WebCatalogTests(unittest.TestCase):
    def test_reviewed_shards_and_minimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'records.jsonl'
            record={'country':'HR','kind':'entrepreneur','name':'Synthetic business','as_of':'2026-01-01','publication_reviewed':True,'tax_number':'12345678903','registration_number':'000000001','email':'private@example.test','director':'Synthetic person'}
            source.write_text(json.dumps(record)+'\n',encoding='utf-8')
            manifest=builder.build(source,root/'data')
            self.assertEqual(manifest['count'],1)
            actual=json.loads((root/'data'/manifest['shards'][0]).read_text(encoding='utf-8'))[0]
            self.assertNotIn('tax_number',actual)
            self.assertNotIn('email',actual)
            self.assertNotIn('director',actual)
            self.assertEqual(actual['registration_number'],'000000001')
            record['publication_reviewed']=False
            with self.assertRaises(ValueError): builder.publish_record(record)
            record.update(publication_reviewed=True,country='HU')
            with self.assertRaises(ValueError): builder.publish_record(record)

    def test_mixed_country_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'records.jsonl'
            base={'kind':'company','name':'Synthetic business','as_of':'2026-01-01','publication_reviewed':True}
            source.write_text('\n'.join(json.dumps(dict(base,country=country)) for country in ('HR','GB')),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Mixed-country'):
                builder.build(source,root/'mixed','HR')
            self.assertFalse((root/'mixed/manifest.json').exists())
