import io
import unittest
from PIL import Image
from native_render import rounded_surface,stroke_icon,surface_color,gradient_bands,header_surface,reference_header_color,rgb,blend,card_corner,gradient_surface

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

    def test_header_fast_path_matches_every_reference_pixel(self):
        for bg,accent in (("#08131e","#36ebba"),("#ffffff","#000000"),("#000000","#ffffff")):
            for width in (1,37,320,1024):
                with self.subTest(bg=bg,accent=accent,width=width):
                    actual=Image.open(io.BytesIO(header_surface(bg,accent,width))).tobytes()
                    expected=bytes(c for y in range(119) for x in range(width)
                                   for c in (*reference_header_color(bg,accent,width,119,x+.5,y+.5),255))
                    self.assertEqual(actual,expected)

    def test_antialiased_card_corners_are_opaque_and_bounded(self):
        card_corner.cache_clear()
        args=("#102030","#102030","#000000","#405060",320,200,12)
        corners=[Image.open(io.BytesIO(card_corner(*args,i))) for i in range(4)]
        self.assertEqual(corners[0].size,(12,12))
        self.assertEqual(corners[0].getpixel((0,0)),(0,0,0,255))
        self.assertEqual(corners[0].getpixel((11,11)),(16,32,48,255))
        self.assertTrue(all(c.getchannel("A").getextrema()==(255,255) for c in corners))
        self.assertTrue(any(p not in ((0,0,0,255),(16,32,48,255),(64,80,96,255))
                            for p in corners[0].get_flattened_data()))
        from PIL import ImageOps
        self.assertEqual(ImageOps.mirror(corners[0]).tobytes(),corners[1].tobytes())
        self.assertEqual(ImageOps.flip(corners[0]).tobytes(),corners[3].tobytes())
        for width in range(100,170):
            card_corner(*args[:4],width,200,12,0)
        self.assertLessEqual(card_corner.cache_info().currsize,64)
        with self.assertRaises(ValueError):card_corner(*args[:4],20,20,12,0)
        with self.assertRaises(ValueError):card_corner(*args[:4],320,200,33,0)

    def test_card_corner_samples_gradient_at_actual_position(self):
        args=("#102030","#8090a0","#000000",None,320,200,12)
        upper=Image.open(io.BytesIO(card_corner(*args,0)))
        lower=Image.open(io.BytesIO(card_corner(*args,2)))
        self.assertEqual(upper.getpixel((11,11))[:3],rgb(surface_color(args[0],args[1],320,200,11.5,11.5)))
        self.assertEqual(lower.getpixel((0,0))[:3],rgb(surface_color(args[0],args[1],320,200,308.5,188.5)))

    def test_icon_geometry_scales_instead_of_clipping_or_shrinking(self):
        for size in (12,20,32,40,60,64):
            with self.subTest(size=size):
                image=Image.open(io.BytesIO(stroke_icon(((2,2,18,18),),"#36ebba",size)))
                self.assertEqual(image.size,(size,size))
                alpha=image.getchannel("A")
                left,top,right,bottom=alpha.getbbox()
                self.assertEqual(left,top)
                self.assertEqual(right,bottom)
                self.assertLessEqual(left,size*.15)
                self.assertGreaterEqual(right,size*.85)
                self.assertEqual(alpha.getpixel((0,size-1)),0)

    def test_gradient_raster_matches_every_pixel_center(self):
        for start,end in (("#101f2d","#0c1a26"),("#000000","#ffffff"),
                          ("#ffffff","#000000"),("#ff0080","#0080ff"),("#112233","#112233")):
            for w,h in ((3,3),(37,19),(128,71)):
                with self.subTest(start=start,end=end,width=w,height=h):
                    image=Image.open(io.BytesIO(gradient_surface(start,end,None,w,h)))
                    expected=bytes(c for y in range(h) for x in range(w)
                                   for c in (*rgb(surface_color(start,end,w,h,x+.5,y+.5)),255))
                    self.assertEqual(image.tobytes(),expected)

    def test_gradient_surface_border_and_resource_bound(self):
        gradient_surface.cache_clear()
        args=("#101f2d","#0c1a26","#2a4355",320,200)
        data=gradient_surface(*args)
        image=Image.open(io.BytesIO(data))
        edge=(*rgb(args[2]),255)
        self.assertEqual(image.getpixel((0,100)),edge)
        self.assertEqual(image.getpixel((319,100)),edge)
        self.assertEqual(image.getpixel((160,199)),edge)
        self.assertEqual(image.getpixel((160,100))[:3],rgb(surface_color(*args[:2],320,200,160.5,100.5)))
        self.assertIs(data,gradient_surface(*args))
        for w in range(20,40):
            gradient_surface(*args[:3],w,20)
        self.assertLessEqual(gradient_surface.cache_info().currsize,8)
        with self.assertRaises(ValueError):gradient_surface(*args[:3],4096,4096)
