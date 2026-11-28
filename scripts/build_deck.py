#!/usr/bin/env python3
"""
Build a "Listening - Presentation" news-listening PPTX from a JSON spec.

Layout system (learned from the reference decks in 时文听力):
  20 x 11.25 in (16:9), cream paper page, blue gradient mat,
  Times New Roman Bold 54/46pt body, red target words, blue masks over them,
  answer slides = same slide with click-to-disappear masks, one audio track
  embedded on the first listening slide.

Usage:
    python build_deck.py --spec deck.json --out deck.pptx

Spec (see references/spec.md for the full schema):
{
  "title": "...",
  "cover_image": "img/x.jpg",
  "cover_credit": "Photo: ... / CC BY 2.0",
  "audio": "audio.mp3",
  "video": null,
  "body_size": 46,
  "pages": [
    {"text": "Sentence one. Sentence two.",
     "targets": [{"word": "extraordinary", "gloss": "非凡的"}, ...],
     "image": "img/y.jpg",
     "credit": "Photo: ... / CC BY 2.0"},
    ...
  ]
}
"""

import argparse
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps
from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.parts.media import MediaPart
from pptx.media import Video
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------- constants
SLIDE_W, SLIDE_H = 20.0, 11.25
PAPER = (0.36, 0.30, 19.28, 10.65)          # x, y, w, h (inches)
TEXT_X, TEXT_Y = 0.66, 0.55
TEXT_W, TEXT_H = 12.45, 9.75
IMG_X, IMG_R, IMG_W = 13.35, 19.32, 5.95
IMG_TOP, IMG_BOTTOM = 3.45, 9.95
FULL_W = 18.90          # width of the first lines that run above the picture

CREAM = RGBColor(0xFF, 0xFB, 0xF0)
INK = RGBColor(0x11, 0x11, 0x11)
RED = RGBColor(0xFF, 0x00, 0x00)
GREY = RGBColor(0x77, 0x70, 0x66)
MASK_BLUE = RGBColor(0x4F, 0x81, 0xBD)
BLUE_DARK = (0x0A, 0x2B, 0x59)
BLUE_LIGHT = (0x3B, 0x77, 0xC9)

LATIN_FONT = "Times New Roman"
CJK_FONT = "宋体"
LINE_FACTOR = 1.164          # PowerPoint single line height / font size
GLOSS_RATIO = 0.78

FONT_PATH = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
BAND_FONT = "Georgia"
BAND_FONT_PATH = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"  # closest installed proxy

_font_cache = {}


# ---------------------------------------------------------------- measuring
def _pil_font(size_pt):
    px = max(1, int(round(size_pt * 96.0 / 72.0)))
    if px not in _font_cache:
        _font_cache[px] = ImageFont.truetype(FONT_PATH, px)
    return _font_cache[px]


def is_cjk(ch):
    o = ord(ch)
    return (
        0x2E80 <= o <= 0x9FFF
        or 0xF900 <= o <= 0xFAFF
        or 0xFF00 <= o <= 0xFFEF
        or 0x3000 <= o <= 0x303F
    )


def run_width_in(text, size_pt):
    """Approximate PowerPoint text advance width in inches.

    Latin text is measured as whole runs (so FreeType applies the font's
    kerning pairs); CJK glyphs are full-width.
    """
    if not text:
        return 0.0
    f = _pil_font(size_pt)
    px_per_em = size_pt * 96.0 / 72.0
    w_px = 0.0
    buf = []
    for ch in text:
        if is_cjk(ch):
            if buf:
                w_px += f.getlength("".join(buf))
                buf = []
            w_px += px_per_em
        else:
            buf.append(ch)
    if buf:
        w_px += f.getlength("".join(buf))
    return w_px / 96.0


# ---------------------------------------------------------------- parsing
def _split_token(tok):
    m = re.match(r"^([^\w’'\-]*)(.*?)([^\w’'\-]*)$", tok)
    if not m:
        return "", tok, ""
    return m.group(1), m.group(2), m.group(3)


def build_atoms(text, targets, base_size, inline_gloss=False):
    """Split a sentence into unbreakable atoms.

    A target may be a single word or a phrase ("stock market debut"); phrases
    stay on one line and get one mask covering the whole phrase.
    """
    tokens = re.findall(r"\S+", text)
    infos = [_split_token(t) for t in tokens]
    cores = [c for _, c, _ in infos]

    matches = {}
    taken = set()
    for t in sorted(targets, key=lambda x: len(x["word"].split()), reverse=True):
        words = t["word"].split()
        if not words:
            continue
        for i in range(0, len(tokens) - len(words) + 1):
            if any(j in taken for j in range(i, i + len(words))):
                continue
            if cores[i:i + len(words)] == words:
                matches[i] = (words, t.get("gloss", ""))
                taken.update(range(i, i + len(words)))
                break

    atoms = []
    i = 0
    while i < len(tokens):
        if i in matches:
            words, gloss = matches[i]
            pre, _, _ = infos[i]
            post = infos[i + len(words) - 1][2]
            runs = []
            if pre:
                runs.append({"text": pre, "size": base_size, "color": "ink"})
            phrase_width = 0.0
            for k, w in enumerate(words):
                if k:
                    runs.append({"text": " ", "size": base_size, "color": "ink"})
                    phrase_width += run_width_in(" ", base_size)
                runs.append({"text": w, "size": base_size, "color": "red"})
                phrase_width += run_width_in(w, base_size)
            if post:
                runs.append({"text": post, "size": base_size, "color": "ink"})
            mask = {
                "offset": run_width_in(pre, base_size) if pre else 0.0,
                "width": phrase_width,
            }
            if gloss and inline_gloss:
                gsize = round(base_size * GLOSS_RATIO)
                runs.append({"text": "（%s）" % gloss, "size": gsize, "color": "grey"})
            atoms.append({
                "runs": runs,
                "width": sum(run_width_in(r["text"], r["size"]) for r in runs),
                "mask": mask,
            })
            i += len(words)
            continue

        tok = tokens[i]
        runs = [{"text": tok, "size": base_size, "color": "ink"}]
        atoms.append({
            "runs": runs,
            "width": sum(run_width_in(r["text"], r["size"]) for r in runs),
            "mask": None,
        })
        i += 1
    return atoms


def wrap_around(atoms, size, line_h, full_w, narrow_w, top, img_top):
    """Greedy wrap where the first lines may run full width above the picture."""
    space_w = run_width_in(" ", size)
    lines, cur, cur_w = [], [], 0.0
    for a in atoms:
        y = top + len(lines) * line_h
        width = full_w if (y + line_h) <= img_top + 0.001 else narrow_w
        add = a["width"] + (space_w if cur else 0.0)
        if cur and cur_w + add > width:
            lines.append(cur)
            cur, cur_w = [a], a["width"]
        else:
            cur.append(a)
            cur_w += add
    if cur:
        lines.append(cur)
    return lines, space_w


def wrap_atoms(atoms, width_in):
    space_w = run_width_in(" ", atoms[0]["runs"][0]["size"]) if atoms else 0.0
    lines, cur, cur_w = [], [], 0.0
    for a in atoms:
        add = a["width"] + (space_w if cur else 0.0)
        if cur and cur_w + add > width_in:
            lines.append(cur)
            cur, cur_w = [a], a["width"]
        else:
            cur.append(a)
            cur_w += add
    if cur:
        lines.append(cur)
    return lines, space_w


# ---------------------------------------------------------------- drawing
def add_bg(slide, bg_path):
    slide.shapes.add_picture(bg_path, 0, 0, width=Inches(SLIDE_W), height=Inches(SLIDE_H))


def add_paper(slide):
    x, y, w, h = [Inches(v) for v in PAPER]
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = CREAM
    shp.line.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    shp.line.width = Pt(1.4)
    # soft shadow
    spPr = shp._element.spPr
    shdw = parse_xml(
        '<a:effectLst %s><a:outerShdw blurRad="76200" dist="50800" dir="2700000" '
        'algn="tl" rotWithShape="0"><a:srgbClr val="000000"><a:alpha val="42000"/>'
        "</a:srgbClr></a:outerShdw></a:effectLst>" % nsdecls("a")
    )
    spPr.append(shdw)
    shp.text_frame.word_wrap = False
    return shp


def style_run(run, size, color, bold=True, lang="en-US"):
    f = run.font
    f.name = LATIN_FONT
    f.size = Pt(size)
    f.bold = bold
    if color == "red":
        f.color.rgb = RED
    elif color == "grey":
        f.color.rgb = GREY
    else:
        f.color.rgb = INK
    rPr = run._r.get_or_add_rPr()
    rPr.set("lang", lang)
    rPr.set("altLang", "zh-CN" if lang == "en-US" else "en-US")
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", CJK_FONT)


def add_text_block(slide, page, base_size, mask_override=None):
    inline = page.get("inline_gloss", False)
    atoms = build_atoms(page["text"], page.get("targets", []), base_size, inline)
    line_h = base_size * LINE_FACTOR / 72.0
    content_w = TEXT_W

    size = base_size
    while size >= 34:
        atoms = build_atoms(page["text"], page.get("targets", []), size, inline)
        line_h = size * LINE_FACTOR / 72.0
        lines, space_w = wrap_around(atoms, size, line_h, FULL_W, TEXT_W, TEXT_Y, IMG_TOP)
        if len(lines) * line_h <= TEXT_H:
            break
        size -= 2

    line_h = size * LINE_FACTOR / 72.0
    lines, space_w = wrap_around(atoms, size, line_h, FULL_W, TEXT_W, TEXT_Y, IMG_TOP)
    content_w = FULL_W
    tb = slide.shapes.add_textbox(Inches(TEXT_X), Inches(TEXT_Y), Inches(content_w + 0.2), Inches(TEXT_H))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.line_spacing = 1.0
    p.space_before = Pt(0)
    p.space_after = Pt(0)

    masks = []
    for li, line in enumerate(lines):
        if li:
            p.add_line_break()
        cursor = 0.0
        for ai, a in enumerate(line):
            if ai:
                run = p.add_run()
                run.text = " "
                style_run(run, size, "ink")
                cursor += space_w
            for r in a["runs"]:
                run = p.add_run()
                run.text = r["text"]
                style_run(run, r["size"], r["color"],
                          bold=(r["color"] != "grey"),
                          lang=("zh-CN" if is_cjk(r["text"][0]) else "en-US"))
            if a.get("mask"):
                mh = size / 72.0 * 1.12
                masks.append({
                    "x": TEXT_X + cursor + a["mask"]["offset"] - 0.06,
                    "y": TEXT_Y + li * line_h + size / 72.0 * 0.18,
                    "w": a["mask"]["width"] + 0.04,
                    "h": mh,
                })
            cursor += a["width"]

    if os.environ.get("NO_MASKS"):
        return []
    if mask_override is not None:
        masks = mask_override
    ids = []
    for m in masks:
        if mask_override is not None:
            x, y, w, h = m["x"], m["y"], m["w"], m["h"]
        else:
            x, y, w, h = m["x"] - 0.015, m["y"], m["w"] + 0.03, m["h"]
        shp = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shp.fill.solid()
        shp.fill.fore_color.rgb = MASK_BLUE
        shp.line.fill.background()
        shp.text_frame.word_wrap = False
        ids.append(shp.shape_id)
    return ids


def add_notes(slide, page):
    targets = page.get("targets") or []
    if not targets:
        return
    lines = ["Listening words:"]
    for t in targets:
        g = t.get("gloss", "")
        lines.append("  %s%s" % (t["word"], ("  " + g) if g else ""))
    slide.notes_slide.notes_text_frame.text = "\n".join(lines)


# ---------------------------------------------------------------- images
def prep_cover_image(src, out):
    im = Image.open(src).convert("RGB")
    im = ImageOps.exif_transpose(im)
    target = 1.5
    w, h = im.size
    if w / h > target:
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
    else:
        nh = int(w / target)
        top = max(0, int((h - nh) * 0.32))
        im = im.crop((0, top, w, top + nh))
    im.save(out, quality=92)
    return out


def prep_body_image(src, max_w, max_h, out, crop=True):
    im = Image.open(src).convert("RGB")
    im = ImageOps.exif_transpose(im)
    w, h = im.size
    if crop:
        # cover-crop to the column's aspect so every page has the same picture block
        target = max_w / max_h
        if w / h > target:
            nw = int(h * target)
            left = (w - nw) // 2
            im = im.crop((left, 0, left + nw, h))
        else:
            nh = int(w / target)
            top = int((h - nh) * 0.35)
            im = im.crop((0, top, w, top + nh))
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    w_in, h_in = w * scale, h * scale
    im = im.resize((max(int(w_in * 200), 1), max(int(h_in * 200), 1)), Image.LANCZOS)
    im.save(out, quality=92)
    return out, w_in, h_in


def prep_logo_card(src, out):
    """White Anthropic-style wordmark on a navy card."""
    logo = Image.open(src).convert("RGBA")
    # invert dark pixels to white, keep alpha
    px = logo.load()
    for yy in range(logo.height):
        for xx in range(logo.width):
            r, g, b, a = px[xx, yy]
            px[xx, yy] = (255, 255, 255, a)
    card_w, card_h = 1770, 640
    card = Image.new("RGB", (card_w, card_h), (0x0E, 0x2A, 0x47))
    lw = int(card_w * 0.78)
    lh = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    card.paste(logo, ((card_w - lw) // 2, (card_h - lh) // 2), logo)
    card.save(out, quality=95)
    return out, 5.95, 5.95 * card_h / card_w


def add_image(slide, img_path, max_w=IMG_W, max_h=6.15, logo=False):
    tmpdir = os.environ.get("LISTENING_TMP", "/tmp/listening-ppt")
    os.makedirs(tmpdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(img_path))[0]
    if logo:
        out = os.path.join(tmpdir, base + "_card.jpg")
        path, w, h = prep_logo_card(img_path, out)
    else:
        out = os.path.join(tmpdir, base + "_fit.jpg")
        path, w, h = prep_body_image(img_path, max_w, max_h, out)
    x = IMG_X + (IMG_R - IMG_X - w) / 2
    y = (IMG_TOP + IMG_BOTTOM) / 2 - h / 2
    mat = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(x - 0.07), Inches(y - 0.07),
        Inches(w + 0.14), Inches(h + 0.14))
    mat.fill.solid()
    mat.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    mat.line.color.rgb = RGBColor(0xB9, 0xB0, 0x9C)
    mat.line.width = Pt(0.75)
    mat.text_frame.word_wrap = False
    slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    return y + h


def add_credit(slide, text, color=RGBColor(0x8A, 0x81, 0x72), size=8, x=0.62, y=10.38):
    if not text:
        return
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(9.0), Inches(0.3))
    tf = tb.text_frame
    tf.word_wrap = False
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.name = LATIN_FONT
    run.font.bold = False
    run.font.color.rgb = color


# ---------------------------------------------------------------- audio / timing
def add_audio(slide, icon_path, audio_path, x, y, size_in, num_slides):
    """Embed audio that starts when the speaker icon is clicked (单击时)."""
    pkg = slide.part.package
    media_part = MediaPart.new(pkg, Video.from_path_or_file_like(audio_path, "audio/mpeg"))
    media_rid = slide.part.relate_to(media_part, RT.MEDIA)
    audio_rid = slide.part.relate_to(media_part, RT.AUDIO)
    icon_part, icon_rid = slide.part.get_or_add_image_part(icon_path)

    sid = max(s.shape_id for s in slide.shapes) + 1
    xml = (
        '<p:pic %s xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main">'
        "<p:nvPicPr>"
        '<p:cNvPr id="%d" name="Listening audio">'
        '<a:hlinkClick r:id="" action="ppaction://media"/></p:cNvPr>'
        "<p:cNvPicPr><a:picLocks noChangeAspect=\"1\"/></p:cNvPicPr>"
        "<p:nvPr><a:audioFile r:link=\"%s\"/>"
        '<p:extLst><p:ext uri="{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}">'
        '<p14:media r:embed="%s"/></p:ext></p:extLst>'
        "</p:nvPr></p:nvPicPr>"
        '<p:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        '<p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        "</p:pic>"
        % (nsdecls("p", "a", "r"), sid, audio_rid, media_rid, icon_rid,
           int(Inches(x)), int(Inches(y)), int(Inches(size_in)), int(Inches(size_in)))
    )
    pic = parse_xml(xml)
    slide.shapes._spTree.append(pic)

    timing = (
        '<p:timing %s><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
        "<p:childTnLst>"
        '<p:audio><p:cMediaNode vol="90000" numSld="%d">'
        '<p:cTn id="2" fill="hold" display="1"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>'
        '<p:endCondLst><p:cond evt="onStopAudio"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:endCondLst></p:cTn>'
        '<p:tgtEl><p:spTgt spid="%d"/></p:tgtEl></p:cMediaNode></p:audio>'
        '<p:seq concurrent="1" nextAc="seek">'
        '<p:cTn id="3" restart="whenNotActive" fill="hold" evtFilter="cancelBubble" nodeType="interactiveSeq">'
        '<p:stCondLst><p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="%d"/></p:tgtEl></p:cond></p:stCondLst>'
        '<p:endSync evt="end" delay="0"><p:rtn val="all"/></p:endSync>'
        "<p:childTnLst><p:par><p:cTn id=\"4\" fill=\"hold\"><p:stCondLst><p:cond delay=\"0\"/></p:stCondLst>"
        "<p:childTnLst><p:par><p:cTn id=\"5\" fill=\"hold\"><p:stCondLst><p:cond delay=\"0\"/></p:stCondLst>"
        "<p:childTnLst><p:par><p:cTn id=\"6\" presetID=\"1\" presetClass=\"mediacall\" presetSubtype=\"0\" fill=\"hold\" nodeType=\"clickEffect\">"
        "<p:stCondLst><p:cond delay=\"0\"/></p:stCondLst><p:childTnLst>"
        '<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr additive="base"><p:cTn id="7" dur="1" fill="hold"/>'
        '<p:tgtEl><p:spTgt spid="%d"/></p:tgtEl></p:cBhvr></p:cmd>'
        "</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"
        "</p:childTnLst></p:cTn>"
        '<p:nextCondLst><p:cond evt="onClick" delay="0"><p:tgtEl><p:spTgt spid="%d"/></p:tgtEl></p:cond></p:nextCondLst>'
        "</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"
        % (nsdecls("p", "a", "r"), num_slides, sid, sid, sid, sid)
    )
    slide._element.append(parse_xml(timing))
    return sid


def add_exit_animations(slide, shape_ids):
    """One click-to-disappear exit effect per mask (structure from the reference decks)."""
    if not shape_ids:
        return
    cid = 3  # 1 = tmRoot, 2 = mainSeq
    effects = []
    blds = []
    for sid in shape_ids:
        base = cid
        effects.append(
            '<p:par><p:cTn id="%d" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>'
            "<p:childTnLst><p:par><p:cTn id=\"%d\" fill=\"hold\"><p:stCondLst><p:cond delay=\"0\"/></p:stCondLst>"
            "<p:childTnLst><p:par>"
            '<p:cTn id="%d" presetID="2" presetClass="exit" presetSubtype="4" fill="hold" grpId="0" nodeType="clickEffect">'
            '<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            '<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base"><p:cTn id="%d" dur="500"/>'
            '<p:tgtEl><p:spTgt spid="%d"/></p:tgtEl><p:attrNameLst><p:attrName>ppt_x</p:attrName></p:attrNameLst></p:cBhvr>'
            '<p:tavLst><p:tav tm="0"><p:val><p:strVal val="ppt_x"/></p:val></p:tav>'
            '<p:tav tm="100000"><p:val><p:strVal val="ppt_x"/></p:val></p:tav></p:tavLst></p:anim>'
            '<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base"><p:cTn id="%d" dur="500"/>'
            '<p:tgtEl><p:spTgt spid="%d"/></p:tgtEl><p:attrNameLst><p:attrName>ppt_y</p:attrName></p:attrNameLst></p:cBhvr>'
            '<p:tavLst><p:tav tm="0"><p:val><p:strVal val="ppt_y"/></p:val></p:tav>'
            '<p:tav tm="100000"><p:val><p:strVal val="1+ppt_h/2"/></p:val></p:tav></p:tavLst></p:anim>'
            '<p:set><p:cBhvr><p:cTn id="%d" dur="1" fill="hold"><p:stCondLst><p:cond delay="499"/></p:stCondLst></p:cTn>'
            '<p:tgtEl><p:spTgt spid="%d"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>'
            '</p:cBhvr><p:to><p:strVal val="hidden"/></p:to></p:set>'
            "</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"
            % (base, base + 1, base + 2, base + 3, sid, base + 4, sid, base + 5, sid)
        )
        blds.append('<p:bldP spid="%d" grpId="0" bldLvl="0" animBg="1"/>' % sid)
        cid += 6
    timing = (
        '<p:timing %s><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
        "<p:childTnLst><p:seq concurrent=\"1\" nextAc=\"seek\">"
        '<p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
        "%s"
        "</p:childTnLst></p:cTn>"
        '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
        "</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>"
        "<p:bldLst>%s</p:bldLst></p:timing>"
        % (nsdecls("p", "a", "r"), "".join(effects), "".join(blds))
    )
    slide._element.append(parse_xml(timing))


# ---------------------------------------------------------------- background
def make_bg(path):
    w, h = 1920, 1080
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for yy in range(h):
        for_ = yy / h
        r = int(BLUE_DARK[0] + (BLUE_LIGHT[0] - BLUE_DARK[0]) * (0.25 + 0.75 * (1 - for_)))
        g = int(BLUE_DARK[1] + (BLUE_LIGHT[1] - BLUE_DARK[1]) * (0.25 + 0.75 * (1 - for_)))
        b = int(BLUE_DARK[2] + (BLUE_LIGHT[2] - BLUE_DARK[2]) * (0.25 + 0.75 * (1 - for_)))
        d.line([(0, yy), (w, yy)], fill=(r, g, b))
    # very subtle grain: blend a low-contrast noise layer
    noise = Image.effect_noise((w, h), 10).convert("L").point(lambda v: int(128 + (v - 128) * 0.06))
    im = Image.blend(im, Image.merge("RGB", (noise, noise, noise)), 0.05)
    im.save(path, quality=92)
    return path


# ---------------------------------------------------------------- slides
def add_cover(prs, spec, bg_path):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, bg_path)

    # stacked paper frames
    for (x, y, w, h, rot, shade) in [
        (0.92, 0.72, 17.5, 9.45, -2.4, 0xE8E1D2),
        (1.12, 0.88, 17.45, 9.35, -1.1, 0xF6F0E3),
        (1.35, 1.02, 17.35, 9.2, 0.0, None),
    ]:
        shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shp.rotation = rot
        shp.fill.solid()
        shp.fill.fore_color.rgb = CREAM if shade is None else RGBColor(
            (shade >> 16) & 255, (shade >> 8) & 255, shade & 255)
        shp.line.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
        shp.line.width = Pt(1.2)

    # blue band
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.15), Inches(1.32), Inches(15.75), Inches(2.55))
    band.fill.solid()
    band.fill.fore_color.rgb = RGBColor(0x00, 0x4A, 0xAD)
    band.line.fill.background()

    # title band label
    tb = slide.shapes.add_textbox(Inches(2.15), Inches(1.36), Inches(15.75), Inches(2.45))
    tf = tb.text_frame
    tf.word_wrap = False
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = 2  # center
    run = p.add_run()
    run.text = spec.get("band_text", "Latest News")
    run.font.name = BAND_FONT
    run.font.size = Pt(118)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xF6, 0xF1, 0xE5)

    # two hairlines
    for yy in (4.02, 4.14):
        ln = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.3), Inches(yy), Inches(15.45), Inches(0.035))
        ln.fill.solid()
        ln.fill.fore_color.rgb = RGBColor(0x00, 0x4A, 0xAD)
        ln.line.fill.background()

    # article title
    title = spec["title"]
    size = 54
    tw = 7.9
    while size > 30:
        words = title.split()
        # quick wrap estimate
        lines, cur = 1, 0.0
        for wd in words:
            ww = run_width_in(wd + " ", size)
            if cur + ww > tw:
                lines += 1
                cur = ww
            else:
                cur += ww
        if lines * size * LINE_FACTOR / 72.0 <= 3.75:
            break
        size -= 2
    tb = slide.shapes.add_textbox(Inches(2.32), Inches(4.62), Inches(7.95), Inches(3.9))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.line_spacing = 1.0
    p.space_before = Pt(0)
    p.space_after = Pt(0)
    run = p.add_run()
    run.text = title
    run.font.name = LATIN_FONT
    run.font.size = Pt(size)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)

    # cover photo
    tmpdir = os.environ.get("LISTENING_TMP", "/tmp/listening-ppt")
    os.makedirs(tmpdir, exist_ok=True)
    cimg = prep_cover_image(spec["cover_image"], os.path.join(tmpdir, "cover_fit.jpg"))
    px, py, pw, ph = 10.35, 4.72, 6.95, 4.63
    mat = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(px - 0.09), Inches(py - 0.09),
                                 Inches(pw + 0.18), Inches(ph + 0.18))
    mat.fill.solid()
    mat.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    mat.line.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    mat.line.width = Pt(1.0)
    slide.shapes.add_picture(cimg, Inches(px), Inches(py), Inches(pw), Inches(ph))

    # small footer credit
    if spec.get("cover_credit"):
        add_credit(slide, spec["cover_credit"], RGBColor(0x6B, 0x63, 0x56), 7, x=10.42, y=9.44)
    return slide


def add_content_slide(prs, page, bg_path, base_size, is_answer=False, first_listening=False,
                      audio=None, audio_icon=None, audio_span=0, mask_boxes=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, bg_path)
    add_paper(slide)
    mask_ids = add_text_block(slide, page, base_size, mask_boxes)
    if page.get("image"):
        add_image(slide, page["image"], logo=page.get("logo", False))
    add_credit(slide, page.get("credit", ""))
    add_notes(slide, page)
    if first_listening and audio:
        add_audio(slide, audio_icon, audio, 18.98, 10.08, 0.58, audio_span)
        tb = slide.shapes.add_textbox(Inches(17.6), Inches(10.2), Inches(1.35), Inches(0.3))
        tf = tb.text_frame
        tf.margin_left = 0
        tf.margin_right = 0
        p = tf.paragraphs[0]
        p.alignment = 2
        r = p.add_run()
        r.text = "LISTEN"
        r.font.name = LATIN_FONT
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x8A, 0x81, 0x72)
    if is_answer:
        add_exit_animations(slide, mask_ids)
    return slide


def add_video_slide(prs, video_path, bg_path, aspect=16 / 9, poster=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide, bg_path)
    max_w, max_h = 18.2, 10.0
    if aspect >= max_w / max_h:
        w = max_w
        h = w / aspect
    else:
        h = max_h
        w = h * aspect
    x, y = (SLIDE_W - w) / 2, (SLIDE_H - h) / 2
    mat = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x - 0.08), Inches(y - 0.08),
                                 Inches(w + 0.16), Inches(h + 0.16))
    mat.fill.solid()
    mat.fill.fore_color.rgb = RGBColor(0x0A, 0x0A, 0x0A)
    mat.line.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    mat.line.width = Pt(1.2)
    mat.text_frame.word_wrap = False
    slide.shapes.add_movie(video_path, Inches(x), Inches(y), Inches(w), Inches(h),
                           poster_frame_image=poster, mime_type="video/mp4")
    return slide


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bg", default=None)
    ap.add_argument("--masks", default=None, help="calibrated mask boxes JSON")
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)

    # resolve every relative asset path against the spec file's folder
    spec_dir = os.path.dirname(os.path.abspath(args.spec))

    def abspath(p):
        if p and not os.path.isabs(p):
            return os.path.normpath(os.path.join(spec_dir, p))
        return p

    for key in ("cover_image", "audio", "audio_icon", "video", "video_poster"):
        if spec.get(key):
            spec[key] = abspath(spec[key])
    for pg in spec["pages"]:
        if pg.get("image"):
            pg["image"] = abspath(pg["image"])

    tmpdir = os.environ.get("LISTENING_TMP", "/tmp/listening-ppt")
    os.makedirs(tmpdir, exist_ok=True)
    bg_path = args.bg or make_bg(os.path.join(tmpdir, "bg.jpg"))

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)

    add_cover(prs, spec, bg_path)

    pages = spec["pages"]
    base_size = spec.get("body_size", 46)

    mask_pages = None
    if args.masks:
        with open(args.masks, encoding="utf-8") as f:
            mask_pages = json.load(f)["pages"]
        if len(mask_pages) != len(pages):
            raise SystemExit("masks.json page count != spec page count")
    for i, pg in enumerate(pages):
        add_content_slide(prs, pg, bg_path, base_size, is_answer=False,
                          first_listening=(pg is pages[0]),
                          audio=spec.get("audio"), audio_icon=spec.get("audio_icon"),
                          audio_span=len(pages),
                          mask_boxes=(mask_pages[i] if mask_pages else None))
    for i, pg in enumerate(pages):
        add_content_slide(prs, pg, bg_path, base_size, is_answer=True,
                          mask_boxes=(mask_pages[i] if mask_pages else None))

    if spec.get("video"):
        add_video_slide(prs, spec["video"], bg_path,
                        aspect=float(spec.get("video_aspect", 16 / 9)),
                        poster=spec.get("video_poster"))

    cp = prs.core_properties
    cp.title = spec["title"]
    cp.subject = "English listening practice (Latest News)"
    cp.author = "Listening - Presentation"

    prs.save(args.out)
    print("saved", args.out, "slides:", len(prs.slides))


if __name__ == "__main__":
    main()
