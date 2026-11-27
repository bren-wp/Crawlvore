"""Small, resolution-independent native surface assets (no browser dependency)."""
import math
import struct
import zlib
from functools import lru_cache

@lru_cache(maxsize=64)
def rgb(color):
    if len(color)!=7 or color[0]!="#":
        raise ValueError("Expected RGB hex color")
    return tuple(int(color[i:i+2],16) for i in (1,3,5))

def blend(a,b,t):
    return tuple(round(x+(y-x)*t) for x,y in zip(a,b))

def png(width,height,rows):
    def chunk(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,6,0,0,0))
            +chunk(b"IDAT",zlib.compress(b"".join(b"\0"+row for row in rows),6))+chunk(b"IEND",b""))

@lru_cache(maxsize=32)
def rounded_surface(fill,border,radius=7,size=None):
    """Antialiased compact surface. Maximum cached allocation is bounded."""
    if type(radius) is not int or not 3<=radius<=12:
        raise ValueError("Invalid surface radius")
    size=radius*2+3 if size is None else size
    if type(size) is not int or not radius*2+1<=size<=64:raise ValueError("Invalid surface size")
    inside=rgb(fill);edge=rgb(border)
    rows=[]
    for y in range(size):
        row=bytearray()
        for x in range(size):
            weights=[0,0]
            for sy in range(4):
                for sx in range(4):
                    px=x+(sx+.5)/4;py=y+(sy+.5)/4
                    cx=max(radius,min(size-radius,px))
                    cy=max(radius,min(size-radius,py))
                    dist=math.hypot(px-cx,py-cy)
                    if dist<=radius:
                        weights[int(dist>radius-1)]+=1
            total=sum(weights)
            if total:
                row.extend(blend(inside,edge,weights[1]/total))
                row.append(round(255*total/16))
            else:row.extend((0,0,0,0))
        rows.append(bytes(row))
    return png(size,size,rows)

@lru_cache(maxsize=64)
def stroke_icon(segments,color,size=20):
    """Antialias native vector line art using bounded subpixel coverage."""
    if type(size) is not int or not 12<=size<=32 or len(segments)>100:
        raise ValueError("Invalid icon geometry")
    sample=4
    n=size*sample
    coverage=bytearray(n*n)
    radius=.85
    for x1,y1,x2,y2 in segments:
        vx,vy=x2-x1,y2-y1
        length=vx*vx+vy*vy
        left=max(0,math.floor((min(x1,x2)-radius)*sample))
        right=min(n,math.ceil((max(x1,x2)+radius)*sample))
        top=max(0,math.floor((min(y1,y2)-radius)*sample))
        bottom=min(n,math.ceil((max(y1,y2)+radius)*sample))
        for y in range(top,bottom):
            py=(y+.5)/sample
            for x in range(left,right):
                px=(x+.5)/sample
                t=max(0,min(1,((px-x1)*vx+(py-y1)*vy)/length)) if length else 0
                if (px-x1-vx*t)**2+(py-y1-vy*t)**2<=radius**2:
                    coverage[y*n+x]=1
    ink=rgb(color)
    rows=[]
    for y in range(size):
        row=bytearray()
        for x in range(size):
            total=sum(coverage[(y*sample+dy)*n+x*sample+dx] for dy in range(sample) for dx in range(sample))
            row.extend((*ink,round(total*255/(sample*sample))))
        rows.append(bytes(row))
    return png(size,size,rows)

def surface_color(start,end,width,height,x,y):
    """Sample the reference 145-degree linear gradient at a logical point."""
    angle=math.radians(145)
    dx,dy=math.sin(angle),-math.cos(angle)
    fraction=max(0,min(1,(dx*x+dy*y)/max(1,dx*width+dy*height)))
    return "#"+"".join(f"{channel:02x}" for channel in blend(rgb(start),rgb(end),fraction))

@lru_cache(maxsize=32)
def gradient_bands(start,end):
    """Exact channel-rounding intervals for an opaque sRGB linear gradient."""
    a,b=rgb(start),rgb(end)
    cuts={0.0,1.0}
    for lo,hi in zip(a,b):
        if lo!=hi:
            cuts.update((i+.5)/abs(hi-lo) for i in range(abs(hi-lo)))
    bounds=sorted(cuts)
    return tuple((left,right,"#"+"".join(f"{v:02x}" for v in blend(a,b,(left+right)/2)))
                 for left,right in zip(bounds,bounds[1:]))

HEADER_DX=math.sin(math.radians(161))
HEADER_DY=-math.cos(math.radians(161))

def reference_header_color(bg,accent,width,height,x,y):
    """Composite the two reference header gradients at a logical pixel."""
    base,ink=rgb(bg),rgb(accent)
    # Radial ellipse centered above the header.
    radial=math.hypot((x/width-.83)/.75,(y/height+.8)/1.5)
    opacity=.30*max(0,1-radial/.76)
    # Clip to the polygon in the reference CSS.
    if x/width < .80-.24*y/height:opacity=0
    base=blend(base,ink,opacity)
    # The second layer is a narrow diagonal highlight on the right 57%.
    local=x-.43*width
    if local<0 or y>110:return base
    w=.57*width
    if local/w < max(0,.70*(1-y/110)):return base
    t=(HEADER_DX*local+HEADER_DY*y)/(HEADER_DX*w+HEADER_DY*110)
    stops=((.45,0),(.46,.55),(.49,.14),(.64,0))
    if not .45<t<.64:return base
    for (lo,a),(hi,b) in zip(stops,stops[1:]):
        if lo<=t<=hi:return blend(base,ink,a+(b-a)*(t-lo)/(hi-lo))
    return base

@lru_cache(maxsize=4)
def header_surface(bg,accent,width,height=119):
    if type(width) is not int or not 1<=width<=4096 or height!=119:
        raise ValueError("Invalid header geometry")
    rows=[]
    base_pixel=bytes((*rgb(bg),255))
    rgb(accent)
    for y in range(height):
        py=y+.5
        # Both clipped layers are transparent before their leftmost edge.
        # Leave one pixel of margin for floating-point boundary rounding.
        radial_edge=(.80-.24*py/height)*width
        highlight_edge=(.43+.57*max(0,.70*(1-py/110)))*width if py<=110 else width
        prefix=max(0,int(min(radial_edge,highlight_edge))-1)
        row=bytearray(base_pixel*prefix)
        for x in range(prefix,width):
            row.extend((*reference_header_color(bg,accent,width,height,x+.5,py),255))
        rows.append(bytes(row))
    return png(width,height,rows)
