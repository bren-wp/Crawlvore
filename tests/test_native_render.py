import io
import unittest
from PIL import Image
from native_render import rounded_surface,stroke_icon

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
