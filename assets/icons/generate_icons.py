"""
generate_icons.py
─────────────────
Run this script ONCE from your project root to generate
colourful sidebar icons in assets/icons/.

    python generate_icons.py

Requirements: pip install pillow
"""

import os
import math
from PIL import Image, ImageDraw

OUTPUT_DIR = "assets/icons"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SIZE    = 64          # icon canvas size (px)
PAD     = 8           # inner padding
STROKE  = 4           # line stroke width
BG      = (0, 0, 0, 0)  # transparent background

# ── Colour palette (vivid, screen-friendly) ────────────────────────────────────
C = {
    "home":    "#4CAF50",   # green
    "users":   "#2196F3",   # blue
    "loan":    "#FF9800",   # orange
    "card":    "#9C27B0",   # purple
    "cpu":     "#00BCD4",   # cyan
    "chat":    "#E91E63",   # pink
    "chart":   "#3F51B5",   # indigo
    "key":     "#FF5722",   # deep orange
    "clip":    "#607D8B",   # blue-grey
    "cog":     "#795548",   # brown
    "logout":  "#F44336",   # red
}

def new_canvas():
    img  = Image.new("RGBA", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)
    return img, draw

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def save(img, name):
    img.save(os.path.join(OUTPUT_DIR, name))
    print(f"  ✔  {name}")

def stroke_rect(draw, x0, y0, x1, y1, color, sw=STROKE, radius=0):
    if radius:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius,
                                outline=color, width=sw)
    else:
        draw.rectangle([x0, y0, x1, y1], outline=color, width=sw)

def fill_rect(draw, x0, y0, x1, y1, color, radius=0):
    if radius:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=color)
    else:
        draw.rectangle([x0, y0, x1, y1], fill=color)

# ── home.png ──────────────────────────────────────────────────────────────────
def make_home():
    img, draw = new_canvas()
    col = C["home"]
    # roof triangle
    pts = [(SIZE//2, PAD+4), (PAD, 28), (SIZE-PAD, 28)]
    draw.polygon(pts, fill=col)
    # house body
    fill_rect(draw, PAD+6, 28, SIZE-PAD-6, SIZE-PAD, col, radius=3)
    # door (white cutout)
    door_w, door_h = 12, 16
    dx = SIZE//2 - door_w//2
    dy = SIZE - PAD - door_h
    fill_rect(draw, dx, dy, dx+door_w, dy+door_h, (255,255,255,200), radius=2)
    save(img, "home.png")

# ── users.png ─────────────────────────────────────────────────────────────────
def make_users():
    img, draw = new_canvas()
    col = hex_to_rgb(C["users"]) + (255,)
    # two person silhouettes
    for ox in (-10, 8):
        cx = SIZE//2 + ox
        # head
        r = 7
        draw.ellipse([cx-r, PAD+2, cx+r, PAD+2+r*2], fill=col)
        # body arc
        draw.arc([cx-10, PAD+18, cx+10, PAD+38], 180, 360,
                 fill=col, width=STROKE+1)
    save(img, "users.png")

# ── dollar-sign.png ───────────────────────────────────────────────────────────
def make_dollar():
    img, draw = new_canvas()
    col = C["loan"]
    # circle
    draw.ellipse([PAD, PAD, SIZE-PAD, SIZE-PAD], outline=col, width=STROKE)
    # $ sign — two arcs + vertical bar
    cx = SIZE // 2
    # vertical bar
    draw.line([cx, PAD+8, cx, SIZE-PAD-8], fill=col, width=STROKE+1)
    # top arc
    draw.arc([cx-10, PAD+10, cx+10, PAD+26], 0, 180, fill=col, width=STROKE)
    # bottom arc
    draw.arc([cx-10, SIZE//2-4, cx+10, SIZE//2+12], 180, 360,
             fill=col, width=STROKE)
    save(img, "dollar-sign.png")

# ── credit-card.png ───────────────────────────────────────────────────────────
def make_card():
    img, draw = new_canvas()
    col = C["card"]
    # card outline
    draw.rounded_rectangle([PAD, PAD+8, SIZE-PAD, SIZE-PAD-8],
                            radius=5, outline=col, width=STROKE)
    # stripe
    fill_rect(draw, PAD, PAD+16, SIZE-PAD, PAD+24, col)
    # chip
    fill_rect(draw, PAD+8, PAD+28, PAD+22, PAD+38,
              hex_to_rgb(C["card"]) + (200,), radius=2)
    save(img, "credit-card.png")

# ── cpu.png ───────────────────────────────────────────────────────────────────
def make_cpu():
    img, draw = new_canvas()
    col = C["cpu"]
    # chip body
    draw.rounded_rectangle([PAD+8, PAD+8, SIZE-PAD-8, SIZE-PAD-8],
                            radius=4, outline=col, width=STROKE)
    # inner square
    draw.rounded_rectangle([PAD+16, PAD+16, SIZE-PAD-16, SIZE-PAD-16],
                            radius=2, outline=col, width=STROKE-1)
    # pins top & bottom
    for x in [PAD+16, PAD+24, PAD+32]:
        draw.line([x, PAD, x, PAD+8], fill=col, width=STROKE-1)
        draw.line([x, SIZE-PAD-8, x, SIZE-PAD], fill=col, width=STROKE-1)
    # pins left & right
    for y in [PAD+16, PAD+24, PAD+32]:
        draw.line([PAD, y, PAD+8, y], fill=col, width=STROKE-1)
        draw.line([SIZE-PAD-8, y, SIZE-PAD, y], fill=col, width=STROKE-1)
    save(img, "cpu.png")

# ── message-circle.png ────────────────────────────────────────────────────────
def make_chat():
    img, draw = new_canvas()
    col = C["chat"]
    # bubble
    draw.ellipse([PAD, PAD, SIZE-PAD, SIZE-PAD-8], outline=col, width=STROKE)
    # tail
    tail = [(SIZE//2-6, SIZE-PAD-10), (SIZE//2+4, SIZE-PAD+2),
            (SIZE//2+14, SIZE-PAD-10)]
    draw.polygon(tail, fill=col)
    # dots
    for dx in (-10, 0, 10):
        cx = SIZE//2 + dx
        cy = SIZE//2 - 4
        draw.ellipse([cx-3, cy-3, cx+3, cy+3], fill=col)
    save(img, "message-circle.png")

# ── bar-chart-2.png ───────────────────────────────────────────────────────────
def make_chart():
    img, draw = new_canvas()
    col = C["chart"]
    # baseline
    draw.line([PAD, SIZE-PAD, SIZE-PAD, SIZE-PAD], fill=col, width=STROKE)
    # bars
    bars = [(PAD+4,  SIZE-PAD-28),
            (PAD+16, SIZE-PAD-18),
            (PAD+28, SIZE-PAD-36),
            (PAD+40, SIZE-PAD-12)]
    w = 10
    for bx, by in bars:
        fill_rect(draw, bx, by, bx+w, SIZE-PAD-2,
                  hex_to_rgb(col) + (255,), radius=2)
    save(img, "bar-chart-2.png")

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ── key.png ───────────────────────────────────────────────────────────────────
def make_key():
    img, draw = new_canvas()
    col = C["key"]
    # key ring (circle)
    draw.ellipse([PAD, PAD+4, PAD+28, PAD+32], outline=col, width=STROKE)
    # key shaft
    draw.line([PAD+22, PAD+20, SIZE-PAD, PAD+20], fill=col, width=STROKE)
    # key teeth
    draw.line([SIZE-PAD-10, PAD+20, SIZE-PAD-10, PAD+28],
              fill=col, width=STROKE)
    draw.line([SIZE-PAD-18, PAD+20, SIZE-PAD-18, PAD+26],
              fill=col, width=STROKE)
    save(img, "key.png")

# ── clipboard.png ─────────────────────────────────────────────────────────────
def make_clipboard():
    img, draw = new_canvas()
    col = C["clip"]
    # board
    draw.rounded_rectangle([PAD+4, PAD+8, SIZE-PAD-4, SIZE-PAD],
                            radius=4, outline=col, width=STROKE)
    # clip tab
    fill_rect(draw, SIZE//2-10, PAD, SIZE//2+10, PAD+14,
              hex_to_rgb(col) + (255,), radius=3)
    # lines
    for y in [PAD+22, PAD+30, PAD+38]:
        draw.line([PAD+12, y, SIZE-PAD-12, y], fill=col, width=STROKE-1)
    save(img, "clipboard.png")

# ── settings.png ──────────────────────────────────────────────────────────────
def make_settings():
    img, draw = new_canvas()
    col = C["cog"]
    cx, cy, r = SIZE//2, SIZE//2, 14
    # outer gear teeth
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + (r-2) * math.cos(angle)
        y1 = cy + (r-2) * math.sin(angle)
        x2 = cx + (r+7) * math.cos(angle)
        y2 = cy + (r+7) * math.sin(angle)
        draw.line([x1, y1, x2, y2], fill=col, width=STROKE+2)
    # gear ring
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=col, width=STROKE)
    # centre hole
    draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=col)
    save(img, "settings.png")

# ── log-out.png ───────────────────────────────────────────────────────────────
def make_logout():
    img, draw = new_canvas()
    col = C["logout"]
    # door frame (left part)
    draw.rounded_rectangle([PAD, PAD, SIZE//2+4, SIZE-PAD],
                            radius=4, outline=col, width=STROKE)
    # arrow →
    ay = SIZE // 2
    draw.line([SIZE//2+2, ay, SIZE-PAD-2, ay], fill=col, width=STROKE+1)
    draw.polygon([(SIZE-PAD-2, ay-7),
                  (SIZE-PAD+4, ay),
                  (SIZE-PAD-2, ay+7)], fill=col)
    # horizontal lines inside door
    draw.line([PAD+6, ay, SIZE//2-2, ay], fill=col, width=STROKE-1)
    save(img, "log-out.png")

# ── Generate all ───────────────────────────────────────────────────────────────
print(f"\nGenerating icons → {OUTPUT_DIR}/\n")
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
print(f"\n✔  All icons saved to {OUTPUT_DIR}/")
print("Restart the app to see the new icons.\n")