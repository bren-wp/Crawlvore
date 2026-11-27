import io
import unittest
from PIL import Image
from native_render import rounded_surface,stroke_icon,surface_color

class RoundedSurfaceTests(unittest.TestCase):
    def test_antialiased_edge_and_opaque_center(self):
        image=Image.open(io.BytesIO(rounded_surface("#102030","#405060")))
        self.assertEqual(image.mode,"RGBA")
        self.assertEqual(image.size,(17,17))
        self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertEqual(image.getpixel((8,8)),(16,32,48,255))
        self.assertTrue(any(0<a<255 for a in image.getchannel("A").get_flattened_data()))
        self.assertEqual(image.getpixel((8,0))[:3],(64,80,96))
    def test_bounded_cache_and_validation(self):
        rounded_surface.cache_clear()
        for i in range(40):
            rounded_surface(f"#{i:06x}","#123456")
        self.assertLessEqual(rounded_surface.cache_info().currsize,32)
        with self.assertRaises(ValueError):rounded_surface("#123456","#abcdef",100)
        with self.assertRaises(ValueError):rounded_surface("#xxxxxx","#abcdef")

    def test_native_icon_preserves_transparency_and_ink(self):
        image=Image.open(io.BytesIO(stroke_icon(((2,2,17,17),(2,17,17,2)),"#36ebba")))
        self.assertEqual(image.size,(20,20))
        self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertEqual(image.getpixel((9,9))[:3],(54,235,186))
        self.assertTrue(any(0<a<255 for a in image.getchannel("A").get_flattened_data()))
        with self.assertRaises(ValueError):stroke_icon((),"#123456",100)

    def test_surface_sampling_matches_reference_gradient(self):
        args=("#101f2d","#0c1a26",400,200)
        self.assertEqual(surface_color(*args,0,0),"#101f2d")
        self.assertEqual(surface_color(*args,400,200),"#0c1a26")
        self.assertEqual(surface_color(*args,200,100),"#0e1c2a")
        self.assertEqual(surface_color(*args,-100,-100),"#101f2d")
        self.assertEqual(surface_color(*args,600,300),"#0c1a26")
