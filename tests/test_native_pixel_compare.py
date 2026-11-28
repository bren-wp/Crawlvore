import tempfile
import unittest
from pathlib import Path
from PIL import Image
from tools.native_pixel_compare import compare,VIEWS,meets_threshold,region_diagnostics

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

    def test_intermediate_threshold_never_changes_exact_gate(self):
        results=compare(self.reference,self.candidate,self.diff)
        results[0]["changed_pixels"]=3
        self.assertTrue(meets_threshold(results,30))
        self.assertFalse(meets_threshold(results))
        results[0]["changed_pixels"]=4
        self.assertFalse(meets_threshold(results,30))
        self.assertFalse(meets_threshold(results[:1],30))
        with self.assertRaises(ValueError):meets_threshold(results,101)

    def test_diagnostics_partition_every_pixel_without_changing_acceptance(self):
        delta=Image.new("RGB",(5,7),(0,0,0))
        for x,y,color in ((0,0,(1,0,0)),(4,6,(0,8,0)),(2,3,(0,0,40))):
            delta.putpixel((x,y),color)
        result=region_diagnostics(delta)
        regions=result["regions"]
        self.assertEqual(len(regions),16)
        self.assertEqual(sum(r["total_pixels"] for r in regions),35)
        self.assertEqual(sum(r["changed_pixels"] for r in regions),3)
        self.assertEqual(result["max_channel_error_histogram"],
                         {"0":32,"1_to_2":1,"3_to_8":1,"9_to_32":0,"33_to_255":1})
        self.assertFalse(meets_threshold([{"changed_pixels":3,"total_pixels":35}]*7,0))
