"""PDF output: Individual Assessment Reports and the class mark sheet."""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepInFrame, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from . import grading as G
from .compute import SHEET_DEFAULTS, mark_sheet_layout

NAVY = colors.HexColor("#1F3C88")
GROUP_BG = {"EE": "#D8F0DC", "ME": "#DDEBF7", "AE": "#FFF2C4", "BE": "#FAD4D4"}
DOTS = (1, 1.5)


def _ps(name, size=9, bold=False, align=0, color=colors.black, leading=None):
    return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica",
                          fontSize=size, leading=leading or size * 1.22, alignment=align,
                          textColor=color)


S_SCHOOL = _ps("school", 21, True, TA_CENTER, NAVY, 25)
S_SUB = _ps("sub", 10, True, TA_CENTER)
S_TITLE = _ps("title", 9.5, False, TA_CENTER)
S_LBL = _ps("lbl", 9, True)
S_TXT = _ps("txt", 9)
S_CELL = _ps("cell", 8.2)
S_CELLB = _ps("cellb", 8.2, True)
S_HEAD = _ps("head", 8.5, True, TA_CENTER)
S_KEY = _ps("key", 7.6, True)
S_CENTER = _ps("center", 8.2, align=TA_CENTER)
S_HEADS = _ps("heads", 7.6, True, TA_CENTER)
S_SUBH = _ps("subh", 6.3, False, TA_CENTER)
S_CELLS = _ps("cells", 7.6)


def P(markup, style=S_TXT):
    """Paragraph from markup; callers escape user text with esc()."""
    return Paragraph(str(markup or ""), style)


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _header(res, width):
    s = res.settings
    parts = [Paragraph(esc(s["school_name"]), S_SCHOOL)]
    if s.get("school_subtitle"):
        parts.append(Paragraph(esc(s["school_subtitle"]), S_SUB))
    if s.get("report_title"):
        parts.append(Spacer(1, 2))
        parts.append(Paragraph(esc(s["report_title"]), S_TITLE))
    logo = s.get("logo_path")
    if logo and os.path.exists(logo):
        side = 22 * mm
        t = Table([[Image(logo, side, side, kind="proportional"), parts, ""]],
                  colWidths=[side + 2 * mm, width - 2 * (side + 2 * mm), side + 2 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return [t]
    return parts


def _dotted_line_table(cells, widths):
    """Label/value pairs with dotted underline under the values (like the paper form)."""
    t = Table([cells], colWidths=widths)
    st = [("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
          ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
          ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]
    for i in range(1, len(cells), 2):
        st.append(("LINEBELOW", (i, 0), (i, 0), 0.6, colors.black, "butt", DOTS))
    t.setStyle(TableStyle(st))
    return t


def show_marks(res):
    return res.settings.get("report_show_marks") == "1"


def _learning_table(res, r, width):
    """The learning-areas table: LEARNING AREAS | RATINGS ([MARKS,] POINTS, LEVEL) | REMARKS.

    POINTS are the rubric points of each learning area (EE1 = 8 … BE2 = 1) and LEVEL its code.
    MARKS appear only when 'Show marks on the Individual Assessment Report' is on in Settings.
    A learning area with two papers keeps its own row (paper marks, e.g. '44 + 45', when marks
    are shown) followed by its total row ('Total' / 'Jumla') carrying points, level and remark.
    For a combined report, POINTS is split into one column per exam plus AVG (with each % in
    small print when marks are shown); level and remark come from the average."""
    combined = res.combined
    marks = show_marks(res)
    exams = r["exams"] if combined else [r]
    single_marks = marks and not combined
    m = len(exams) + 1 if combined else 1          # number of POINTS columns
    mk = 1 if single_marks else 0                  # MARKS column (single report only)
    w_area = 50 * mm if combined else (54 * mm if mk else 62 * mm)
    w_pts = (17 * mm if marks else 15 * mm) if combined else (17 * mm if mk else 22 * mm)
    w_mark = 22 * mm
    w_lvl = 17 * mm if (combined or mk) else 22 * mm
    widths = ([w_area] + [w_mark] * mk + [w_pts] * m
              + [w_lvl, width - w_area - mk * w_mark - m * w_pts - w_lvl])
    p0 = 1 + mk                                    # first POINTS column
    lc = p0 + m                                    # LEVEL column
    rem = lc + 1                                   # REMARKS column
    style = [("GRID", (0, 0), (-1, -1), 0.8, colors.black),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("ALIGN", (1, 0), (lc, -1), "CENTER"),
             ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6)]
    if combined:
        names = [esc(n) for n in res.names()] + ["AVG"]
        data = [[P("LEARNING AREAS", S_HEAD), P("RATINGS", S_HEAD)] + [""] * m
                + [P("REMARKS", S_HEAD)],
                ["", P("POINTS (MARKS %)" if marks else "POINTS", S_HEAD)] + [""] * (m - 1)
                + [P("LEVEL", S_HEAD), ""],
                [""] + [P(n, S_SUBH) for n in names] + ["", ""]]
        hdr = 3
        style += [("SPAN", (0, 0), (0, 2)), ("SPAN", (1, 0), (lc, 0)),
                  ("SPAN", (rem, 0), (rem, 2)), ("SPAN", (1, 1), (m, 1)),
                  ("SPAN", (lc, 1), (lc, 2)),
                  ("BACKGROUND", (m, 2), (m, -1), colors.HexColor("#F3F5FA"))]
    else:
        heads = ([P("MARKS", S_HEAD)] if mk else []) + [P("POINTS", S_HEAD), P("LEVEL", S_HEAD)]
        data = [[P("LEARNING AREAS", S_HEAD), P("RATINGS", S_HEAD)] + [""] * (len(heads) - 1)
                + [P("REMARKS", S_HEAD)],
                [""] + heads + [""]]
        hdr = 2
        style += [("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (lc, 0)),
                  ("SPAN", (rem, 0), (rem, 1))]
    remark_style = S_CELLS if combined else S_CELL

    def level(row, i, band, remark):
        row[lc] = band.code
        row[rem] = P(esc(remark), remark_style) if remark else ""
        style.extend([("BACKGROUND", (lc, i), (lc, i), colors.HexColor(GROUP_BG[band.code[:2]])),
                      ("FONTNAME", (lc, i), (lc, i), "Helvetica-Bold")])

    def pts_cell(v, bold=False):
        """Points, plus the % in small print for a combined report with marks shown."""
        if not v:
            return "-"
        b0, b1 = ("<b>", "</b>") if bold else ("", "")
        if combined and marks:
            return P(f"{b0}{v['band'].points}{b1} <font size=6.3 color='#555555'>"
                     f"{round(v['pct'])}%</font>", S_CENTER)
        return P(f"{b0}{v['band'].points}{b1}", S_CENTER) if bold else str(v["band"].points)

    def paper_marks(s):
        if not r["has_marks"]:
            return "-"
        return " + ".join(G.fmt(r["papers"][p["id"]]["mark"]) if p["id"] in r["papers"] else "0"
                          for p in s["papers"])

    def blank_row():
        return [""] * (rem + 1)

    def fill(row, i, s, v):
        if mk:
            row[1] = f"{G.fmt(v['mark'])}/{G.fmt(v['out_of'])}" if v else "-"
        for j, e in enumerate(exams):
            row[p0 + j] = pts_cell(e["subjects"].get(s["id"]) if e else None)
        if combined:
            row[p0 + m - 1] = pts_cell(v, bold=True)
        if v:
            level(row, i, v["band"], v["band"].remark)

    for s in res.subjects:
        v = r["subjects"].get(s["id"])
        row = blank_row()
        row[0] = P(esc(s["name"]), S_CELL)
        if len(s["papers"]) > 1:   # learning-area row, then its Total / Jumla row
            if mk:
                row[1] = paper_marks(s)
            data.append(row)
            row = blank_row()
            row[0] = P(esc(s["total_label"] or "Total"), S_CELL)
        fill(row, len(data), s, v)
        data.append(row)
    # TOTAL row: total points (per exam and for the average) and the overall level
    row = blank_row()
    i = len(data)
    row[0] = P("TOTAL", S_CELLB)
    if r["has_marks"]:
        if mk:
            row[1] = f"{G.fmt(r['total'])}/{G.fmt(r['out_of'])}"
        for j, e in enumerate(exams):
            row[p0 + j] = str(e["points"]) if e and e["has_marks"] else "-"
        if combined:
            row[p0 + m - 1] = str(r["points"])
        level(row, i, r["band"], "")
    data.append(row)
    style += [("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
              ("FONTSIZE", (1, hdr), (lc, -1), 8.5 if combined else 9.5)]
    if not combined:
        style.append(("FONTNAME", (p0, hdr), (p0, -1), "Helvetica-Bold"))
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle(style))
    return t


def _keys(width):
    left, right = G.BANDS[:4], G.BANDS[4:]
    rows = [[P(f"{a.code} - {a.descriptor.upper()} {a.low}-{a.high} &nbsp;({a.points} POINTS)",
               S_KEY),
             P(f"{b.code} - {b.descriptor.upper()} {b.low}-{b.high} &nbsp;({b.points} "
               f"POINT{'S' if b.points > 1 else ''})", S_KEY)]
            for a, b in zip(left, right)]
    t = Table(rows, colWidths=[width / 2] * 2)
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 1),
                           ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5)]))
    return t


def _report_form(res, r, width):
    L, a, k = r["learner"], res.assessment, res.klass
    f = []
    f += _header(res, width)
    f.append(Spacer(1, 7))
    f.append(_dotted_line_table([P("LEARNER'S NAME:", S_LBL), P(esc(L["name"]).upper(), S_LBL)],
                                [33 * mm, width - 33 * mm]))
    f.append(_dotted_line_table(
        [P("CLASS TEACHER:", S_LBL), P(esc(k["class_teacher"]), S_TXT),
         P("YEAR:", S_LBL), P(str(a["year"] or k["year"] or ""), S_TXT)],
        [31 * mm, width - 31 * mm - 14 * mm - 45 * mm, 14 * mm, 45 * mm]))
    f.append(_dotted_line_table(
        [P("GRADE:", S_LBL), P(esc(k["name"]), S_TXT), P("TERM:", S_LBL),
         P(res.term_label(), S_TXT)],
        [16 * mm, width - 16 * mm - 14 * mm - 76 * mm, 14 * mm, 76 * mm]))
    f.append(Spacer(1, 7))
    f.append(_learning_table(res, r, width))
    f.append(Spacer(1, 7))

    sign = Table([["", P("Sign:", S_LBL), ""]], colWidths=[width - 92 * mm, 16 * mm, 55 * mm])
    sign.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                              ("LINEBELOW", (2, 0), (2, 0), 0.6, colors.black, "butt", DOTS)]))
    box = Table([[Paragraph("CLASS TEACHER'S GENERAL REMARKS", S_LBL)],
                 [Paragraph(esc(r["ct_remark"]) or "&nbsp;", _ps("ctr", 9.2, leading=12))],
                 [sign]], colWidths=[width], cornerRadii=[7, 7, 7, 7])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.1, colors.black),
                             ("LEFTPADDING", (0, 0), (-1, -1), 10),
                             ("TOPPADDING", (0, 0), (-1, -1), 3),
                             ("BOTTOMPADDING", (0, -1), (-1, -1), 5)]))
    f.append(box)
    f.append(Spacer(1, 6))
    f.append(Paragraph("LEARNER'S CHARACTER", S_LBL))
    f.append(_dotted_line_table([P("Discipline:", S_LBL), P(esc(r["discipline"]), S_TXT)],
                                [20 * mm, width - 20 * mm]))
    f.append(_dotted_line_table([P("Class attention and seriousness:", S_LBL),
                                 P(esc(r["attention"]), S_TXT)], [56 * mm, width - 56 * mm]))
    f.append(_dotted_line_table([P("Closing Date:", S_LBL), P(esc(a["closing_date"]), S_TXT),
                                 P("Opening Date:", S_LBL), P(esc(a["opening_date"]), S_TXT)],
                                [24 * mm, width / 2 - 24 * mm, 25 * mm, width / 2 - 25 * mm]))
    f.append(_dotted_line_table([P("Parent's/Guardian:", S_LBL), "", P("Sign:", S_LBL), ""],
                                [33 * mm, width / 2 - 33 * mm, 11 * mm, width / 2 - 11 * mm]))
    f.append(Spacer(1, 3))
    f.append(_dotted_line_table([P("Head teacher's:", S_LBL), P(esc(r["ht_remark"]), S_TXT),
                                 P("Sign:", S_LBL), ""],
                                [27 * mm, width - 27 * mm - 11 * mm - 40 * mm, 11 * mm, 40 * mm]))
    f.append(Spacer(1, 5))
    pts = f"{r['points']} / {r['max_points']}" if r["has_marks"] else ""
    if show_marks(res):
        if not r["has_marks"]:
            tm = oo = ""
        elif res.combined:  # average % per learning area, summed (like G. TOTAL)
            tm = str(round(sum(x["pct"] for x in r["subjects"].values())))
            oo = str(r["n_subjects"] * 100)
        else:
            tm, oo = G.fmt(r["total"]), G.fmt(r["out_of"])
        f.append(_dotted_line_table(
            [P("TOTAL MARKS:", S_LBL), P(tm, S_LBL), P("OUT OF:", S_LBL), P(oo, S_LBL),
             P("POINTS:", S_LBL), P(pts, S_LBL)],
            [27 * mm, 30 * mm, 17 * mm, 30 * mm, 17 * mm, width - 121 * mm]))
    else:
        lvl = r["band"].code if r["has_marks"] else ""
        f.append(_dotted_line_table(
            [P("TOTAL POINTS:", S_LBL), P(pts, S_LBL), P("OVERALL LEVEL:", S_LBL), P(lvl, S_LBL)],
            [28 * mm, 40 * mm, 31 * mm, width - 99 * mm]))
    f.append(Spacer(1, 6))
    f.append(Paragraph("<u>KEYS:</u>", S_LBL))
    f.append(_keys(width))
    return f


def report_forms(path, res, learner_ids=None, skip_empty=True):
    """One A4 page per learner. Returns number of pages written."""
    margin = 13 * mm
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=10 * mm, bottomMargin=8 * mm,
                            title=f"Individual Assessment Reports - {res.title()}")
    width, height = A4[0] - 2 * margin, A4[1] - 18 * mm - 2
    story = []
    n = 0
    for r in res.rows:
        if learner_ids is not None and r["learner"]["id"] not in learner_ids:
            continue
        if skip_empty and not r["has_marks"]:
            continue
        if story:
            story.append(PageBreak())
        story.append(KeepInFrame(width, height, _report_form(res, r, width), mode="shrink"))
        n += 1
    if n:
        doc.build(story)
    return n


PAGES = {"A4 landscape": landscape(A4), "A4 portrait": A4, "A3 landscape": landscape(A3)}


def mark_sheet(path, res, opts=None, page="A4 landscape"):
    from .excel_io import sheet_title
    o = {**SHEET_DEFAULTS, **(opts or {})}
    lay = mark_sheet_layout(res, o)
    page = PAGES.get(page, landscape(A4))
    margin = 7 * mm
    title = sheet_title(res, lay)
    doc = SimpleDocTemplate(path, pagesize=page, leftMargin=margin, rightMargin=margin,
                            topMargin=8 * mm, bottomMargin=8 * mm, title=title)
    width = page[0] - 2 * margin
    kinds = lay["kinds"]
    small = {"adm": 11 * mm, "name": 42 * mm}
    rest = width - sum(small.values())
    other = [k for k in kinds if k not in small]
    wide = ("points", "total", "outof", "gtotal", "avg", "level")
    unit = min(rest / max(sum(1.3 if k in wide else 1 for k in other), 1), 14 * mm)
    widths = [small.get(k) or unit * (1.3 if k in wide else 1) for k in kinds]
    fs = 6.2 if len(kinds) > 30 else 7 if len(kinds) > 18 else 8
    hs = _ps("mh", fs - 0.4, True, TA_CENTER, leading=fs + 0.6)

    def cellv(v):
        return G.fmt(v) if isinstance(v, float) else ("" if v is None else str(v))

    data = [[Paragraph(esc(v), hs) for v in row] for row in lay["header"]]
    for row in lay["body"]:
        data.append([cellv(v) for v in row])
    first_sum = len(data)
    for row in lay["summary"]:
        data.append([cellv(v) for v in row])
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#777777")),
          ("FONTSIZE", (0, 0), (-1, -1), fs), ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
          ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("ALIGN", (1, 2), (1, -1), "LEFT"),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
          ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
          ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#DCE6F1")),
          ("BACKGROUND", (0, first_sum), (-1, -1), colors.HexColor("#F2F2F2")),
          ("FONTNAME", (1, first_sum), (1, -1), "Helvetica-Bold"),
          ("LINEABOVE", (0, first_sum), (-1, first_sum), 1.2, colors.black)]
    for r0, c0, r1, c1 in lay["spans"]:
        if (r0, c0) != (r1, c1):
            st.append(("SPAN", (c0, r0), (c1, r1)))
    for ci, k in enumerate(kinds):
        if k in ("pts", "points"):
            st.append(("FONTNAME", (ci, 2), (ci, -1), "Helvetica-Bold"))
        if k in ("grd", "level"):
            st.append(("FONTNAME", (ci, 2), (ci, -1), "Helvetica-Bold"))
            for ri in range(2, first_sum):
                v = data[ri][ci]
                if v[:2] in GROUP_BG:
                    st.append(("BACKGROUND", (ci, ri), (ci, ri), colors.HexColor(GROUP_BG[v[:2]])))
    t = Table(data, colWidths=widths, repeatRows=2)
    t.setStyle(TableStyle(st))

    s = res.settings
    story = [Paragraph(esc(s.get("header_line", "")), _ps("h1", 9, True, TA_CENTER)),
             Paragraph(esc(title), _ps("h2", 10.5, True, TA_CENTER)), Spacer(1, 4), t]
    if not o["analysis"]:
        doc.build(story)
        return

    # page 2: subject analysis (chosen learners and learning areas)
    story.append(PageBreak())
    story.append(Paragraph(esc(title) + " - SUBJECT ANALYSIS", _ps("h3", 11, True, TA_CENTER)))
    story.append(Spacer(1, 6))
    head = ["LEARNING AREA", "SAT", "MEAN %", "LEVEL"] + G.CODES + G.GROUPS
    rows = [head]
    for x in res.subject_stats(lay["rows"], lay["subjects"]):
        rows.append([x["subject"]["name"], x["sat"],
                     f"{x['mean_pct']:.1f}" if x["mean_pct"] is not None else "-",
                     x["band"].code if x["band"] else "-"]
                    + [x["counts"][c] for c in G.CODES] + [x["groups"][g] for g in G.GROUPS])
    ov = res.overall(lay["rows"])
    rows.append(["CLASS", ov["with_marks"],
                 f"{ov['mean_pct']:.1f}" if ov["mean_pct"] is not None else "-",
                 ov["band"].code if ov["band"] else "-"] + [""] * 12)
    aw = [60 * mm, 14 * mm, 17 * mm, 15 * mm] + [12 * mm] * 12
    k = min(1, width / sum(aw))                 # shrink to fit portrait pages
    at = Table(rows, colWidths=[w * k for w in aw])
    at.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 8.5 if k == 1 else 7),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                            ("BACKGROUND", (-4, 1), (-1, -2), colors.HexColor("#F7F7F7"))]))
    story.append(at)
    doc.build(story)
