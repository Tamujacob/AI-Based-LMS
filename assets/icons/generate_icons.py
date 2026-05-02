"""
generate_icons.py
─────────────────
Run ONCE from your project root to create colourful sidebar icons.

    python generate_icons.py

Requirements: pip install pillow
"""

import os, math
from PIL import Image, ImageDraw

OUT  = "assets/icons"
os.makedirs(OUT, exist_ok=True)
SZ   = 64
PAD  = 8
SW   = 4

def canvas():
    img  = Image.new("RGBA", (SZ, SZ), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    return img, draw

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def save(img, name):
    img.save(os.path.join(OUT, name))
    print(f"  ✔  {name}")

# ── home.png  (green house) ───────────────────────────────────────────────────
def make_home():
    img, d = canvas()
    c = (76, 175, 80, 255)          # green
    cx = SZ//2
    # roof
    d.polygon([(cx, PAD+2), (PAD, 30), (SZ-PAD, 30)], fill=c)
    # body
    d.rectangle([PAD+8, 30, SZ-PAD-8, SZ-PAD], fill=c)
    # door (white)
    dw,dh = 12,16
    dx = cx-dw//2
    d.rounded_rectangle([dx, SZ-PAD-dh, dx+dw, SZ-PAD],
                         radius=2, fill=(255,255,255,220))
    # windows
    for wx in [cx-14, cx+4]:
        d.rectangle([wx, 34, wx+8, 42], fill=(255,255,255,180))
    save(img, "home.png")

# ── users.png  (blue people) ──────────────────────────────────────────────────
def make_users():
    img, d = canvas()
    c = (33, 150, 243, 255)         # blue
    # back person (slightly right, lighter)
    bc = (33, 150, 243, 160)
    d.ellipse([SZ//2-2, PAD+2, SZ//2+18, PAD+22], fill=bc)
    d.ellipse([SZ//2, PAD+24, SZ-PAD+4, SZ-PAD-4], fill=bc)
    # front person
    d.ellipse([PAD+2, PAD+6, PAD+22, PAD+26], fill=c)
    d.ellipse([PAD, PAD+28, SZ//2+6, SZ-PAD], fill=c)
    save(img, "users.png")

# ── dollar-sign.png  (orange coin) ───────────────────────────────────────────
def make_dollar():
    img, d = canvas()
    c  = (255, 152, 0, 255)         # orange
    cl = (255, 200, 100, 255)       # light orange
    # coin
    d.ellipse([PAD, PAD, SZ-PAD, SZ-PAD], fill=c)
    # $ symbol
    cx = SZ//2
    d.line([cx, PAD+10, cx, SZ-PAD-10], fill=(255,255,255,255), width=4)
    d.arc([cx-10, PAD+12, cx+10, PAD+28],  0, 180, fill=(255,255,255,255), width=3)
    d.arc([cx-10, SZ//2-4, cx+10, SZ//2+12], 180, 360, fill=(255,255,255,255), width=3)
    save(img, "dollar-sign.png")

# ── credit-card.png  (purple card) ───────────────────────────────────────────
def make_card():
    img, d = canvas()
    c  = (156, 39, 176, 255)        # purple
    cl = (200, 100, 220, 255)
    d.rounded_rectangle([PAD, PAD+10, SZ-PAD, SZ-PAD-10], radius=6, fill=c)
    # stripe
    d.rectangle([PAD, PAD+18, SZ-PAD, PAD+26], fill=(100,0,120,255))
    # chip
    d.rounded_rectangle([PAD+8, PAD+30, PAD+24, PAD+42],
                         radius=3, fill=(255,215,0,220))
    # dots
    for dx in [PAD+34, PAD+42, PAD+50]:
        d.ellipse([dx-3, PAD+33, dx+3, PAD+39], fill=(255,255,255,160))
    save(img, "credit-card.png")

# ── cpu.png  (cyan chip) ──────────────────────────────────────────────────────
def make_cpu():
    img, d = canvas()
    c  = (0, 188, 212, 255)         # cyan
    cl = (0, 230, 255, 255)
    # body
    d.rounded_rectangle([PAD+8, PAD+8, SZ-PAD-8, SZ-PAD-8], radius=5, fill=c)
    # inner
    d.rounded_rectangle([PAD+16, PAD+16, SZ-PAD-16, SZ-PAD-16],
                         radius=3, fill=(0,150,170,255))
    # pins
    for x in [18, 26, 34, 42]:
        d.rectangle([x-2, PAD, x+2, PAD+8],    fill=cl)
        d.rectangle([x-2, SZ-PAD-8, x+2, SZ-PAD], fill=cl)
    for y in [18, 26, 34, 42]:
        d.rectangle([PAD, y-2, PAD+8, y+2],    fill=cl)
        d.rectangle([SZ-PAD-8, y-2, SZ-PAD, y+2], fill=cl)
    save(img, "cpu.png")

# ── message-circle.png  (pink bubble) ────────────────────────────────────────
def make_chat():
    img, d = canvas()
    c  = (233, 30, 99, 255)         # pink
    cl = (255,255,255,220)
    d.ellipse([PAD, PAD, SZ-PAD, SZ-PAD-8], fill=c)
    # tail
    d.polygon([(SZ//2-6, SZ-PAD-10),
               (SZ//2+4,  SZ-PAD+4),
               (SZ//2+14, SZ-PAD-10)], fill=c)
    # dots
    for dx in [-10, 0, 10]:
        x = SZ//2+dx
        y = SZ//2-6
        d.ellipse([x-4, y-4, x+4, y+4], fill=cl)
    save(img, "message-circle.png")

# ── bar-chart-2.png  (indigo bars) ───────────────────────────────────────────
def make_chart():
    img, d = canvas()
    c  = (63, 81, 181, 255)         # indigo
    cl = (100, 120, 220, 255)
    # baseline
    d.line([PAD, SZ-PAD, SZ-PAD, SZ-PAD], fill=c, width=3)
    bars = [
        (PAD+4,  SZ-PAD-28, 10, c),
        (PAD+18, SZ-PAD-16, 10, cl),
        (PAD+32, SZ-PAD-40, 10, (63,81,181,255)),
        (PAD+46, SZ-PAD-12, 10, cl),
    ]
    for bx, by, bw, bc in bars:
        d.rounded_rectangle([bx, by, bx+bw, SZ-PAD-3], radius=2, fill=bc)
    save(img, "bar-chart-2.png")

# ── key.png  (orange key) ─────────────────────────────────────────────────────
def make_key():
    img, d = canvas()
    c  = (255, 87, 34, 255)         # deep orange
    cl = (255, 160, 100, 255)
    # ring
    d.ellipse([PAD, PAD+6, PAD+30, PAD+36], fill=c)
    d.ellipse([PAD+6, PAD+12, PAD+24, PAD+30], fill=(0,0,0,0))
    # shaft
    d.rectangle([PAD+26, SZ//2-3, SZ-PAD, SZ//2+3], fill=c)
    # teeth
    d.rectangle([SZ-PAD-12, SZ//2+3, SZ-PAD-8,  SZ//2+11], fill=c)
    d.rectangle([SZ-PAD-20, SZ//2+3, SZ-PAD-16, SZ//2+9],  fill=c)
    save(img, "key.png")

# ── clipboard.png  (blue-grey board) ─────────────────────────────────────────
def make_clipboard():
    img, d = canvas()
    c  = (96, 125, 139, 255)        # blue-grey
    cl = (255,255,255,200)
    # board
    d.rounded_rectangle([PAD+4, PAD+8, SZ-PAD-4, SZ-PAD], radius=4, fill=c)
    # clip tab
    d.rounded_rectangle([SZ//2-10, PAD, SZ//2+10, PAD+16],
                         radius=4, fill=(70,95,110,255))
    # lines
    for y in [PAD+24, PAD+33, PAD+42]:
        d.rounded_rectangle([PAD+10, y, SZ-PAD-10, y+5],
                             radius=2, fill=cl)
    save(img, "clipboard.png")

# ── settings.png  (brown gear) ────────────────────────────────────────────────
def make_settings():
    img, d = canvas()
    c  = (121, 85, 72, 255)         # brown
    cl = (180,130,100,255)
    cx, cy = SZ//2, SZ//2
    # outer gear ring
    d.ellipse([cx-18, cy-18, cx+18, cy+18], fill=c)
    # teeth
    for i in range(8):
        a = math.radians(i*45)
        x1 = cx + 14*math.cos(a)
        y1 = cy + 14*math.sin(a)
        x2 = cx + 22*math.cos(a)
        y2 = cy + 22*math.sin(a)
        d.line([x1,y1,x2,y2], fill=c, width=6)
    # inner hole
    d.ellipse([cx-7, cy-7, cx+7, cy+7], fill=(0,0,0,0))
    save(img, "settings.png")

# ── log-out.png  (red exit) ───────────────────────────────────────────────────
def make_logout():
    img, d = canvas()
    c  = (244, 67, 54, 255)         # red
    cl = (255,160,150,255)
    # door frame
    d.rounded_rectangle([PAD, PAD, SZ//2+4, SZ-PAD], radius=4, outline=c, width=4)
    # horizontal line
    ay = SZ//2
    d.line([SZ//2+2, ay, SZ-PAD-4, ay], fill=c, width=4)
    # arrow head
    d.polygon([(SZ-PAD-4, ay-8),
               (SZ-PAD+4, ay),
               (SZ-PAD-4, ay+8)], fill=c)
    save(img, "log-out.png")

print(f"\nGenerating icons → {OUT}/\n")
make_home()
make_users()
make_dollar()
make_card()
make_cpu()
make_chat()
make_chart()
make_key()
make_clipboard()
make_settings()
make_logout()
print(f"\n✔  Done. Restart the app to see colourful icons.\n")