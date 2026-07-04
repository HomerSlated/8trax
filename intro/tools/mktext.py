#!/usr/bin/env python3
"""Rasterize the credit text and emit it as a signed-distance-field atlas.

Usage: python3 tools/mktext.py <output.frag> <output.inc> [--preview <dir>]

Renders two text blocks with Bauhaus Std Heavy:
    block 1:  "8trax" over "© 2026 Haze N Sparkle"  (5:1 size ratio,
              centre-aligned; the "8" is colour-split for the red fill)
    block 2:  "Music CD Archival Tool"

Each block is rasterized hi-res, converted to a signed distance field
(SDF), downsampled, and stacked into one single-channel atlas. SDFs scale
cleanly from full-size down to the 10% corner watermark and give the
shader anti-aliasing and outlines from a single channel.

The atlas is uploaded as a GL_R8 texture by about.asm — a dynamically
indexed GLSL const array of this size fails to *link* on NVIDIA (C5041:
no suitable resource), so the data must live in a texture.

<output.frag> — GLSL constants: block uv rects, texel dims, red-"8" split,
                and the `uniform sampler2D uText` declaration.
<output.inc>  — NASM include: zlib-compressed atlas bytes + dimensions
                (text_blob, text_blob_zlen, text_atlas_w, text_atlas_h).
SDF encoding: 0.5 = glyph edge, >0.5 inside, spread = ±SPREAD hi-res px.
"""

import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/Adobe/Bauhaus Std/BauhausStd-Heavy.otf"

EM_TITLE = 240          # hi-res em size of "8trax"       (80 pt in the mockup)
EM_SUB   = EM_TITLE // 5  # 16 pt in the mockup → exact 5:1
EM_B2    = 96
GAP_RATIO = 0.15        # title-bottom → sub-top gap, in title bbox heights
MARGIN   = 32           # hi-res px; must exceed SPREAD
SPREAD   = 20           # SDF half-range in hi-res px
DOWN     = 4            # hi-res → SDF downsample factor

TITLE = "8trax"
SUB   = "© 2026 Haze N Sparkle"
B2    = "Music CD Archival Tool"


def render_block1():
    """Two centre-aligned lines; returns (binary array, split_u, split_v)."""
    f_title = ImageFont.truetype(FONT, EM_TITLE)
    f_sub   = ImageFont.truetype(FONT, EM_SUB)

    d = ImageDraw.Draw(Image.new("L", (4, 4)))
    tb = d.textbbox((0, 0), TITLE, font=f_title)   # tight bbox at origin
    sb = d.textbbox((0, 0), SUB, font=f_sub)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    sw, sh = sb[2] - sb[0], sb[3] - sb[1]

    gap = int(th * GAP_RATIO)
    W = max(tw, sw) + 2 * MARGIN
    H = MARGIN + th + gap + sh + MARGIN

    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    tx = (W - tw) // 2
    sx = (W - sw) // 2
    d.text((tx - tb[0], MARGIN - tb[1]), TITLE, font=f_title, fill=255)
    d.text((sx - sb[0], MARGIN + th + gap - sb[1]), SUB, font=f_sub, fill=255)

    # red region: the "8" glyph — everything left of the "t" advance,
    # in the title's row band (upper part of the composite)
    split_u = (tx - tb[0] + f_title.getlength("8")) / W
    split_v = (MARGIN + th + gap * 0.5) / H

    return np.asarray(img) > 127, split_u, split_v


def render_block2():
    f = ImageFont.truetype(FONT, EM_B2)
    d = ImageDraw.Draw(Image.new("L", (4, 4)))
    b = d.textbbox((0, 0), B2, font=f)
    w, h = b[2] - b[0], b[3] - b[1]
    img = Image.new("L", (w + 2 * MARGIN, h + 2 * MARGIN), 0)
    ImageDraw.Draw(img).text((MARGIN - b[0], MARGIN - b[1]), B2, font=f, fill=255)
    return np.asarray(img) > 127


def edt(mask):
    """Distance from every False px to the nearest True px (chamfer relax).

    Iterative 8-neighbour relaxation; exact within SPREAD, which is all the
    encoding keeps. ~SPREAD passes of full-grid numpy mins — fast enough.
    """
    BIG = 1e6
    d = np.where(mask, 0.0, BIG)
    shifts = [(0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0),
              (1, 1, 1.41421356), (1, -1, 1.41421356),
              (-1, 1, 1.41421356), (-1, -1, 1.41421356)]
    for _ in range(SPREAD + 2):
        for dy, dx, w in shifts:
            s = np.full_like(d, BIG)
            ys, yd = (slice(dy, None), slice(None, -dy)) if dy > 0 else \
                     (slice(None, dy), slice(-dy, None)) if dy < 0 else \
                     (slice(None), slice(None))
            xs, xd = (slice(dx, None), slice(None, -dx)) if dx > 0 else \
                     (slice(None, dx), slice(-dx, None)) if dx < 0 else \
                     (slice(None), slice(None))
            s[yd, xd] = d[ys, xs] + w
            np.minimum(d, s, out=d)
    return d


def to_sdf(mask):
    """Binary mask → uint8 SDF, downsampled; 128 = edge, >128 inside."""
    signed = edt(mask) - edt(~mask)          # + outside, − inside
    sdf = 0.5 - signed / (2.0 * SPREAD)      # >0.5 inside
    sdf = np.clip(sdf, 0.0, 1.0)
    h, w = sdf.shape
    h4, w4 = (h // DOWN) * DOWN, (w // DOWN) * DOWN
    sdf = sdf[:h4, :w4].reshape(h4 // DOWN, DOWN, w4 // DOWN, DOWN).mean(axis=(1, 3))
    return np.round(sdf * 255).astype(np.uint8)


def main():
    if len(sys.argv) < 3:
        sys.exit(f"usage: {sys.argv[0]} <output.frag> <output.inc> [--preview <dir>]")
    frag_path, inc_path = sys.argv[1], sys.argv[2]
    preview = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--preview" else None

    m1, split_u, split_v = render_block1()
    m2 = render_block2()
    s1, s2 = to_sdf(m1), to_sdf(m2)

    # stack the blocks into one atlas: block1 on top, block2 below.
    # SDF value 0 = far outside, so the padding is inert.
    aw = max(s1.shape[1], s2.shape[1])
    ah = s1.shape[0] + s2.shape[0]
    atlas = np.zeros((ah, aw), np.uint8)
    atlas[:s1.shape[0], :s1.shape[1]] = s1
    atlas[s1.shape[0]:, :s2.shape[1]] = s2

    if preview:
        Image.fromarray((m1 * 255).astype(np.uint8)).save(f"{preview}/block1_mask.png")
        Image.fromarray((m2 * 255).astype(np.uint8)).save(f"{preview}/block2_mask.png")
        Image.fromarray(atlas).save(f"{preview}/atlas_sdf.png")

    # block uv rects inside the atlas (v = 0 is row 0 = top, matching upload order)
    r1 = (0.0, 0.0, s1.shape[1] / aw, s1.shape[0] / ah)
    r2 = (0.0, s1.shape[0] / ah, s2.shape[1] / aw, ah / ah)
    glsl = [
        "// auto-generated by tools/mktext.py — do not edit",
        "uniform sampler2D uText;",
        f"const int T1W = {s1.shape[1]}, T1H = {s1.shape[0]};",
        f"const int T2W = {s2.shape[1]}, T2H = {s2.shape[0]};",
        f"const vec4 T1RECT = vec4({r1[0]:.6f}, {r1[1]:.6f}, {r1[2]:.6f}, {r1[3]:.6f});",
        f"const vec4 T2RECT = vec4({r2[0]:.6f}, {r2[1]:.6f}, {r2[2]:.6f}, {r2[3]:.6f});",
        f"const float T1_SPLIT_U = {split_u:.5f};",
        f"const float T1_SPLIT_V = {split_v:.5f};",
    ]
    open(frag_path, "w").write("\n".join(glsl) + "\n")

    blob = zlib.compress(atlas.tobytes(), level=9)
    inc = [
        "; auto-generated by tools/mktext.py — do not edit",
        f"text_atlas_w    equ {aw}",
        f"text_atlas_h    equ {ah}",
        f"text_blob_zlen  equ {len(blob)}",
        "text_blob:",
    ]
    for i in range(0, len(blob), 16):
        inc.append("    db " + ",".join(f"0x{b:02x}" for b in blob[i:i + 16]))
    open(inc_path, "w").write("\n".join(inc) + "\n")
    print(f"  text: atlas {aw}x{ah} ({aw * ah} B → {len(blob)} B compressed) "
          f"→ {frag_path}, {inc_path}")


if __name__ == "__main__":
    main()
