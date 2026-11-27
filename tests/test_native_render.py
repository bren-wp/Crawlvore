import io
import unittest
from PIL import Image
from native_render import rounded_surface,stroke_icon,surface_color,gradient_bands,header_surface,reference_header_color,rgb,blend

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

    def test_gradient_bands_cover_all_channel_transitions(self):
        start,end="#101f2d","#0c1a26"
        bands=gradient_bands(start,end)
        self.assertEqual(bands[0][0],0)
        self.assertEqual(bands[-1][1],1)
        self.assertLess(len(bands),48)
        for i,(lo,hi,color) in enumerate(bands):
            self.assertLess(lo,hi)
            if i:self.assertEqual(lo,bands[i-1][1])
            for t in (lo+(hi-lo)*.1,(lo+hi)/2,hi-(hi-lo)*.1):
                self.assertEqual(rgb(color),blend(rgb(start),rgb(end),t))
        self.assertEqual(gradient_bands(start,start),((0.0,1.0,start),))

    def test_header_surface_bounds_and_cache(self):
        header_surface.cache_clear()
        args=("#08131e","#36ebba",320)
        data=header_surface(*args)
        image=Image.open(io.BytesIO(data))
        self.assertEqual(image.size,(320,119))
        self.assertEqual(image.getpixel((0,0)),(8,19,30,255))
        self.assertEqual(image.getpixel((280,30))[:3],reference_header_color(*args,119,280.5,30.5))
        self.assertIs(header_surface(*args),data)
        self.assertEqual(header_surface.cache_info().hits,1)
        self.assertEqual(header_surface.cache_info().maxsize,4)
        for width in (0,4097):
            with self.assertRaises(ValueError):header_surface(args[0],args[1],width)
