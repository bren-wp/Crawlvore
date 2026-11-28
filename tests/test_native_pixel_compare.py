import tempfile
import hashlib
import json
import unittest
from pathlib import Path
from PIL import Image
from tools.native_pixel_compare import compare,VIEWS,meets_threshold,region_diagnostics,dark_color_diagnostics,verify_capture_manifest

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

    def test_signed_dark_color_diagnostics_preserve_direction_and_count(self):
        ref=Image.new("RGB",(5,1))
        actual=Image.new("RGB",(5,1))
        ref.putdata([(10,20,30),(10,20,30),(10,20,30),(100,100,100),(10,20,30)])
        actual.putdata([(11,19,30),(11,19,30),(10,20,30),(101,100,100),(14,20,30)])
        result=dark_color_diagnostics(ref,actual)
        self.assertEqual(result["pixels"],2)
        self.assertEqual(result["signed_candidate_minus_reference"],[{"rgb":[1,-1,0],"pixels":2}])
        self.assertEqual(result["dominant_color_pairs"],[{"reference":[10,20,30],"candidate":[11,19,30],"pixels":2}])

    def test_capture_manifest_verifies_all_png_hashes_and_rejects_tampering(self):
        manifest={"capture_method":"visible-client","platform":"win32",
                  "display_size":[1440,900],"captures":[],"dialogs":[]}
        dialogs=self.candidate/"dialogs"
        dialogs.mkdir()
        for section,key,folder,names in (
            ("captures","view",self.candidate,VIEWS),
            ("dialogs","dialog",dialogs,("profile","backup","sync")),
        ):
            for name in names:
                path=folder/(name+".png")
                if not path.exists():Image.new("RGB",(4,3),(10,20,30)).save(path)
                with Image.open(path) as im:
                    manifest[section].append({key:name,"capture":list(im.size),
                        "stable_frames":2,"rgb_sha256":hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()})
        path=self.candidate/"capture.json"
        path.write_text(json.dumps(manifest),encoding="utf-8")
        self.assertEqual(verify_capture_manifest(self.candidate),manifest)
        Image.new("RGB",(4,3),(10,20,31)).save(self.candidate/"overview.png")
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            verify_capture_manifest(self.candidate)
        manifest["captures"][-1]=manifest["captures"][0]
        path.write_text(json.dumps(manifest),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"duplicate"):
            verify_capture_manifest(self.candidate)

    def test_acceptance_rejects_duplicate_views_even_with_exact_pixels(self):
        results=compare(self.reference,self.candidate,self.diff)
        results[-1]=results[0]
        self.assertFalse(meets_threshold(results,100))
