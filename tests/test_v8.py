import unittest
from detection import inspect_html
from network import public_ip
from sources import parse_html

class DetectionTests(unittest.TestCase):
    def test_mixed_classes_navigation(self):
        html='<nav>'+''.join(f'<li><h2>Link {i}</h2></li>' for i in range(25))+'</nav><main>'+''.join(f'<article class="result tone-{i}"><header><h2>Business {i}</h2></header><span class="address-city">Zagreb</span><a href="tel:01{i}">Call</a></article>' for i in range(4))+'</main>'
        r=inspect_html(html); self.assertEqual(r['selector'],'article.result'); self.assertEqual(len(r['preview']),4); self.assertEqual(r['preview'][1]['phone'],'011'); self.assertEqual(r['confidence'],'high')
    def test_label_value_and_attributes(self):
        html='<main>'+''.join(f'<div class="record" data-company-name="Firm {i}"><dl><dt>OIB</dt><dd>1234567890{i}</dd><dt>Grad</dt><dd>Split</dd></dl></div>' for i in range(3))+'</main>'
        r=inspect_html(html); self.assertEqual(r['preview'][1]['title'],'Firm 1'); self.assertEqual(r['preview'][1]['oib'],'12345678901'); self.assertEqual(r['preview'][1]['city'],'Split'); self.assertEqual(list(parse_html(html,r['selector'],r['mapping']))[:10],r['preview'])
    def test_table_hr_labels(self):
        r=inspect_html('<table><tr><th>Poštanski broj</th><th>Naziv tvrtke</th></tr><tr><td>00100</td><td>A</td></tr><tr><td>21000</td><td>B</td></tr></table>'); self.assertEqual(r['preview'][0]['postal'],'00100'); self.assertEqual(r['preview'][0]['title'],'A')
    def test_no_arbitrary_titles(self):
        r=inspect_html('<div><span>one</span></div><div><span>two</span></div>'); self.assertEqual(r['preview'],[]); self.assertEqual(r['confidence'],'low')
    def test_invalid_inputs(self):
        for kwargs in ({'selector':'['},{'mapping':{'title':5}},{'selector':'a'*501}):
            with self.assertRaises(ValueError): inspect_html('<article><h2>A</h2></article>',**kwargs)
    def test_public_ip_rejects_multicast(self):
        for ip in ('224.0.0.1','ff02::1','127.0.0.1','169.254.1.1','::1','192.168.0.1'):
            self.assertFalse(public_ip(ip),ip)
        self.assertTrue(public_ip('8.8.8.8'))
    def test_preview_bounded(self):
        html=''.join(f'<article><h2>Company {i}</h2></article>' for i in range(30)); self.assertEqual(len(inspect_html(html)['preview']),10)
