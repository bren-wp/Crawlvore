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
    """Antialias 20-unit vector line art at the requested bounded raster size."""
    if type(size) is not int or not 12<=size<=64 or len(segments)>100:
        raise ValueError("Invalid icon geometry")
    sample=4
    n=size*sample
    coverage=bytearray(n*n)
    scale=size/20
    radius=.85*scale
    for x1,y1,x2,y2 in segments:
        x1,y1,x2,y2=(value*scale for value in (x1,y1,x2,y2))
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

@lru_cache(maxsize=64)
def card_corner(start,end,outer,border,width,height,radius,corner):
    """Opaque supersampled corner patch; the interior stays a native canvas."""
    if (type(width) is not int or type(height) is not int or
            type(radius) is not int or not 1<=radius<=32 or
            min(width,height)<2*radius or corner not in range(4)):
        raise ValueError("Invalid card corner geometry")
    a,b,background=rgb(start),rgb(end),rgb(outer)
    edge=rgb(border) if border else None
    dx,dy=math.sin(math.radians(145)),-math.cos(math.radians(145))
    span=max(1,dx*width+dy*height)
    ox=width-radius if corner in (1,2) else 0
    oy=height-radius if corner in (2,3) else 0
    cx=width-radius if ox else radius
    cy=height-radius if oy else radius
    rows=[]
    for y in range(radius):
        row=bytearray()
        for x in range(radius):
            px,py=ox+x+.5,oy+y+.5
            fill=blend(a,b,max(0,min(1,(dx*px+dy*py)/span)))
            totals=[0,0,0]
            for sy in range(4):
                for sx in range(4):
                    dist=(ox+x+(sx+.5)/4-cx)**2+(oy+y+(sy+.5)/4-cy)**2
                    color=background if dist>radius**2 else (
                        edge if edge is not None and dist>(radius-1)**2 else fill)
                    for i,value in enumerate(color):
                        totals[i]+=value
            row.extend((*[round(value/16) for value in totals],255))
        rows.append(bytes(row))
    return png(radius,radius,rows)

@lru_cache(maxsize=8)
def gradient_surface(start,end,border,width,height):
    """Pixel-center sRGB gradient with straight edges; corners are separate.
    
    Monotonic rounded channels allow whole runs of identical pixels to be
    emitted without supersampling the rectangular interior. Bound the raw
    raster allocation independently of the compressed PNG cache.
    """
    if (type(width) is not int or type(height) is not int or
            not 3<=width<=4096 or not 3<=height<=4096 or width*height>2_000_000):
        raise ValueError("Invalid gradient surface dimensions")
    a,b=rgb(start),rgb(end)
    edge=bytes((*rgb(border),255)) if border else None
    dx,dy=math.sin(math.radians(145)),-math.cos(math.radians(145))
    span=max(1,dx*width+dy*height)
    bands=gradient_bands(start,end)
    runs=tuple((right,bytes((*rgb(color),255))) for _,right,color in bands)
    rows=[]
    for y in range(height):
        if edge and y in (0,height-1):
            rows.append(edge*width)
            continue
        row=bytearray()
        previous=0
        py=y+.5
        for right,pixel in runs:
            boundary=(right*span-dy*py)/dx-.5
            stop=min(width,max(previous,math.ceil(boundary)))
            row.extend(pixel*(stop-previous))
            previous=stop
        if previous<width:
            row.extend(runs[-1][1]*(width-previous))
        # At a rounding boundary two channels can round in opposite
        # directions. Evaluate that pixel exactly, including floating ties.
        for right,_ in runs[:-1]:
            boundary=(right*span-dy*py)/dx-.5
            x=round(boundary)
            if 0<=x<width and abs(boundary-x)<1e-8:
                color=blend(a,b,max(0,min(1,(dx*(x+.5)+dy*py)/span)))
                row[x*4:x*4+4]=bytes((*color,255))
        if edge:
            row[:4]=edge
            row[-4:]=edge
        rows.append(bytes(row))
    return png(width,height,rows)
