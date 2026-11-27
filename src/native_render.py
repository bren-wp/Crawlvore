"""Small, resolution-independent native surface assets (no browser dependency)."""
import math
import struct
import zlib
from functools import lru_cache

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
