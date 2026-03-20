"""
Top21News — Card Generator
Produces 1080x1350 JPEG cards for Instagram carousel posting.
"""

from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_COND = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"

BG_TOP     = (8,  14, 30)
BG_BOT     = (18, 26, 50)
ACCENT     = (0, 200, 255)
ACCENT_DIM = (0, 110, 150)
WHITE      = (255, 255, 255)
LIGHT_GRAY = (200, 210, 225)
MID_GRAY   = (120, 135, 158)
DARK_CARD  = (20, 30, 55)
DIVIDER    = (35, 50, 85)
W, H = 1080, 1350
PAD  = 72


def _gradient(img):
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _rr(draw, x1, y1, x2, y2, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r,
                            fill=fill, outline=outline, width=width)


def _wrap(text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if font.getlength(test) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _centered(draw, text, font, y, color):
    w = int(font.getlength(text))
    draw.text(((W - w) // 2, y), text, font=font, fill=color)


def create_cover_card(
    date_str: str,
    part_num: int = 1,
    total_parts: int = 3,
    story_start: int = 1,
    story_end: int = 7,
    output_path: str = "cover.jpg",
) -> str:
    img = Image.new("RGB", (W, H), BG_TOP)
    _gradient(img)
    draw = ImageDraw.Draw(img)

    draw.rectangle([28, 0, 34, H], fill=ACCENT)

    hf = ImageFont.truetype(FONT_BOLD, 38)
    _centered(draw, "@Top21News", hf, PAD, ACCENT)
    draw.rectangle([PAD * 3, PAD + 52, W - PAD * 3, PAD + 54], fill=ACCENT_DIM)

    nf  = ImageFont.truetype(FONT_BOLD, 280)
    nw  = int(nf.getlength("21"))
    draw.text(((W - nw) // 2, H // 2 - 310), "21", font=nf, fill=WHITE)

    sf = ImageFont.truetype(FONT_BOLD, 56)
    _centered(draw, "NEWS STORIES", sf, H // 2 + 10, ACCENT)

    div_y = H // 2 + 86
    draw.rectangle([PAD * 2, div_y, W - PAD * 2, div_y + 4], fill=ACCENT)

    pf   = ImageFont.truetype(FONT_BOLD, 34)
    ptxt = f"PART {part_num} OF {total_parts}  ·  STORIES {story_start} – {story_end}"
    _centered(draw, ptxt, pf, div_y + 22, LIGHT_GRAY)

    shf = ImageFont.truetype(FONT_COND, 36)
    _centered(draw, "Swipe left to read  ›", shf, div_y + 76, MID_GRAY)

    df = ImageFont.truetype(FONT_COND, 32)
    _centered(draw, date_str, df, H - PAD - 36, MID_GRAY)

    img.save(output_path, "JPEG", quality=95)
    return output_path


def create_news_card(
    headline: str,
    summary: str,
    category: str = "NEWS",
    source: str = "",
    date_str: str = "",
    slide_num: int = 1,
    total_slides: int = 21,
    output_path: str = "card.jpg",
) -> str:
    img = Image.new("RGB", (W, H), BG_TOP)
    _gradient(img)
    draw = ImageDraw.Draw(img)

    draw.rectangle([28, 0, 34, H], fill=ACCENT)

    top_y = PAD + 8

    bf   = ImageFont.truetype(FONT_BOLD, 30)
    blbl = f"  #{category.upper()}  "
    bw   = int(bf.getlength(blbl))
    _rr(draw, PAD, top_y, PAD + bw + 10, top_y + 50, r=8, fill=ACCENT_DIM)
    draw.text((PAD + 6, top_y + 10), blbl, font=bf, fill=WHITE)

    cf   = ImageFont.truetype(FONT_BOLD, 34)
    ctxt = f"{slide_num}  /  {total_slides}"
    cw   = int(cf.getlength(ctxt))
    draw.text((W - PAD - cw, top_y + 8), ctxt, font=cf, fill=ACCENT)

    if slide_num == 1:
        sf0  = ImageFont.truetype(FONT_COND, 26)
        hint = "swipe for more  ›"
        hw   = int(sf0.getlength(hint))
        draw.text((W - PAD - hw, top_y + 46), hint, font=sf0, fill=MID_GRAY)

    line_y = top_y + 72
    draw.rectangle([PAD, line_y, W - PAD, line_y + 1], fill=DIVIDER)

    hf_lg = ImageFont.truetype(FONT_BOLD, 66)
    hf_sm = ImageFont.truetype(FONT_BOLD, 54)
    max_w = W - PAD * 2
    hlines = _wrap(headline, hf_lg, max_w)
    if len(hlines) > 4:
        hlines = _wrap(headline, hf_sm, max_w)
        hf = hf_sm
    else:
        hf = hf_lg

    h_y = line_y + 38
    for line in hlines:
        draw.text((PAD, h_y), line, font=hf, fill=WHITE)
        h_y += hf.size + 14

    acc_y = h_y + 16
    draw.rectangle([PAD, acc_y, PAD + 90, acc_y + 4], fill=ACCENT)
    draw.rectangle([PAD + 100, acc_y, PAD + 134, acc_y + 4], fill=ACCENT_DIM)

    card_y  = acc_y + 38
    card_x2 = W - PAD
    card_y2 = H - PAD - 108
    _rr(draw, PAD - 10, card_y, card_x2 + 10, card_y2, r=18, fill=DARK_CARD)

    cp    = 36
    sf_lg = ImageFont.truetype(FONT_REG, 43)
    sf_sm = ImageFont.truetype(FONT_REG, 37)
    sw    = (card_x2 - PAD) - cp * 2 + 10
    slines = _wrap(summary, sf_lg, sw)
    if len(slines) > 7:
        slines = _wrap(summary, sf_sm, sw)
        sff = sf_sm
    else:
        sff = sf_lg

    s_y = card_y + cp
    lh  = sff.size + 18
    for sl in slines:
        if s_y + lh > card_y2 - cp:
            draw.text((PAD - 10 + cp, s_y), "…", font=sff, fill=MID_GRAY)
            break
        draw.text((PAD - 10 + cp, s_y), sl, font=sff, fill=LIGHT_GRAY)
        s_y += lh

    f_y = H - PAD - 66
    draw.rectangle([PAD, f_y, W - PAD, f_y + 1], fill=DIVIDER)
    ff  = ImageFont.truetype(FONT_COND, 30)
    if source:
        draw.text((PAD, f_y + 16), f"Source: {source}", font=ff, fill=MID_GRAY)
    if date_str:
        dw2 = int(ff.getlength(date_str))
        draw.text((W - PAD - dw2, f_y + 16), date_str, font=ff, fill=MID_GRAY)

    brf  = ImageFont.truetype(FONT_BOLD, 25)
    brtx = "TOP21NEWS  •  21 STORIES DAILY"
    brw  = int(brf.getlength(brtx))
    draw.text(((W - brw) // 2, H - 32), brtx, font=brf, fill=ACCENT_DIM)

    img.save(output_path, "JPEG", quality=95)
    return output_path
