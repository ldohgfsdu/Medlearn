import struct, zlib, os

def make_png(size, pixels_func):
    raw = b''
    for y in range(size):
        raw += b'\x00'
        for x in range(size):
            r, g, b, a = pixels_func(x, y, size)
            raw += bytes([r, g, b, a])
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

def book_icon(x, y, size, color):
    """Open book shape for knowledge map tab"""
    r, g, b = color
    cx, cy = x / size, y / size
    if abs(cx - 0.5) < 0.05 and 0.2 < cy < 0.8:
        return (r, g, b, 255)
    if 0.15 < cx < 0.48 and 0.2 < cy < 0.8:
        return (r, g, b, 180)
    if 0.52 < cx < 0.85 and 0.2 < cy < 0.8:
        return (r, g, b, 180)
    if 0.12 < cx < 0.88 and abs(cy - 0.82) < 0.04:
        return (r, g, b, 255)
    return (0, 0, 0, 0)

def bulb_icon(x, y, size, color):
    """Lightbulb shape for feynman tab"""
    r, g, b = color
    cx, cy = (x - size/2) / (size/2), (y - size/2) / (size/2)
    d = (cx*cx + cy*cy) ** 0.5
    if d < 0.45 and cy < 0.2:
        return (r, g, b, 255)
    if abs(cx) < 0.06 and 0.2 < cy < 0.32:
        return (r, g, b, 255)
    if abs(cx) < 0.15 and 0.28 < cy < 0.38:
        return (r, g, b, 200)
    if 0.45 < d < 0.6 and cy < -0.05:
        angle = abs(cy / (d + 0.001))
        if angle > 0.65:
            return (r, g, b, 120)
    return (0, 0, 0, 0)

def dot_icon(x, y, size, color):
    """Simple circle - fallback"""
    cx, cy = (x - size/2) / (size/2), (y - size/2) / (size/2)
    d = (cx*cx + cy*cy) ** 0.5
    if d < 0.55:
        return color
    return (0, 0, 0, 0)

SIZE = 81
ACTIVE = (26, 54, 93)      # var(--ink)
INACTIVE = (154, 140, 122)  # #9a8c7a

def user_icon(x, y, size, color):
    """User avatar shape for profile tab"""
    r, g, b = color
    cx, cy = (x - size/2) / (size/2), (y - size/2) / (size/2)
    d = (cx*cx + cy*cy) ** 0.5
    # Head circle
    if d < 0.32 and cy < 0.12:
        return (r, g, b, 255)
    # Body arc
    if abs(cx) < 0.35 and 0.2 < cy < 0.55:
        if abs(cx) < 0.1 or (abs(cx) > 0.1 and cx*cx + (cy-0.2)*(cy-0.2)*3 < 0.12):
            return (r, g, b, 220)
    # Shoulders
    if 0.1 < abs(cx) < 0.48 and 0.35 < cy < 0.5:
        return (r, g, b, 160)
    return (0, 0, 0, 0)

icons = {
    'tab-knowledge': lambda x, y, s: book_icon(x, y, s, INACTIVE),
    'tab-knowledge-active': lambda x, y, s: book_icon(x, y, s, ACTIVE),
    'tab-feynman': lambda x, y, s: bulb_icon(x, y, s, INACTIVE),
    'tab-feynman-active': lambda x, y, s: bulb_icon(x, y, s, ACTIVE),
    'tab-profile': lambda x, y, s: user_icon(x, y, s, INACTIVE),
    'tab-profile-active': lambda x, y, s: user_icon(x, y, s, ACTIVE),
}

for name, fn in icons.items():
    png = make_png(SIZE, fn)
    path = f'../mini-program/src/assets/{name}.png'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(png)
    print(f'{name}.png: {SIZE}x{SIZE}, {len(png)} bytes')
print('Done!')
