import tempfile
import unittest
from pathlib import Path
from PIL import Image
from tools.native_pixel_compare import compare,VIEWS

class NativePixelCompareTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.reference=self.root/"reference";self.reference.mkdir()
        self.candidate=self.root/"candidate";self.candidate.mkdir()
        self.diff=self.root/"diff"
        for view in VIEWS:
            Image.new("RGB",(4,3),(10,20,30)).save(self.reference/(view+"-dark.png"))
            Image.new("RGB",(4,3),(10,20,30)).save(self.candidate/(view+".png"))
    def test_exact_rgb_match(self):
        results=compare(self.reference,self.candidate,self.diff)
        self.assertEqual(len(results),7)
        self.assertTrue(all(r["exact"] and r["changed_pixels"]==0 for r in results))
    def test_single_channel_one_level_change_counts(self):
        p=self.candidate/"overview.png"
        with Image.open(p) as source:im=source.copy()
        im.putpixel((0,0),(10,20,31));im.save(p)
        result=compare(self.reference,self.candidate,self.diff)[0]
        self.assertEqual(result["changed_pixels"],1)
        self.assertFalse(result["exact"])
    def test_dimensions_cannot_be_rescaled(self):
        Image.new("RGB",(3,4)).save(self.candidate/"overview.png")
        with self.assertRaises(ValueError):compare(self.reference,self.candidate,self.diff)
