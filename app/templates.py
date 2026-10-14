"""ClassMark Excel templates for mass uploads (learners, marks).

Only files made by these functions can be uploaded. Each template carries a very-hidden
'_classmark' sheet (kind, class, assessment, paper ids), a hidden ID column so rows still match
after sorting, locked headings, and cell validation (gender list, marks 0..out-of)."""
import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import grading as G

MARKER = "CLASSMARK_TEMPLATE"
VERSION = 1
META_SHEET = "_classmark"
BLANK_LEARNER_ROWS = 300

THIN = Side(style="thin", color="9AA3B5")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor="1F3C88")
LOCK_FILL = PatternFill("solid", fgColor="EEF1F8")
INPUT_FILL = PatternFill("solid", fgColor="FFFFFF")
OUTOF_FILL = PatternFill("solid", fgColor="FFF2C4")


class TemplateError(Exception):
    """The file is not a usable ClassMark template."""


def to_number(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ("", "-", "--"):
        return None
    return float(s)  # ValueError for junk


def _clean_adm(v):
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return str(v).strip()


# -- writing ---------------------------------------------------------------
def _meta(wb, **values):
    ws = wb.create_sheet(META_SHEET)
    values = {"marker": MARKER, "version": VERSION,
              "created": datetime.datetime.now().isoformat(timespec="seconds"), **values}
    for i, (k, v) in enumerate(values.items(), start=1):
        ws.cell(i, 1, k)
        ws.cell(i, 2, str(v))
    ws.sheet_state = "veryHidden"


def _title(ws, text, note, n_cols):
    ws.cell(1, 2, text).font = Font(bold=True, size=13, color="1F3C88")
    ws.cell(2, 2, note).font = Font(italic=True, size=9, color="555555")
    ws.cell(2, 2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=max(n_cols, 4))
    ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=max(n_cols, 4))
    ws.row_dimensions[2].height = 42


def _head(cell, text):
    cell.value = text
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = HEAD_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER


def _protect(ws):
    ws.protection.sheet = True
    ws.protection.formatColumns = False   # teachers may still widen columns
    ws.protection.formatRows = False


def write_learners_template(path, class_row, learners=()):
    """Headings: ADM NO | FULL NAME | GENDER. Existing learners are pre-filled (edit to update)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Learners"
    hdr = 3
    _title(ws, f"ClassMark — Learners template: {class_row['name']} ({class_row['year']})",
           "Type one learner per row below the blue headings. Do not change, move or delete the "
           "headings. Gender: choose F or M. Rows already filled are existing learners — edit "
           "them to correct names. Save, then upload in ClassMark → Learners → Upload template.", 4)
    for c, t in enumerate(["ID", "ADM NO", "FULL NAME", "GENDER (F/M)"], start=1):
        _head(ws.cell(hdr, c), t)
    rows = list(learners) + [None] * BLANK_LEARNER_ROWS
    for i, L in enumerate(rows, start=hdr + 1):
        vals = [L["id"], L["adm_no"], L["name"], L["gender"]] if L else [None] * 4
        for c, v in enumerate(vals, start=1):
            x = ws.cell(i, c, v or None)
            x.border = BORDER
            x.protection = Protection(locked=c == 1)
            x.fill = INPUT_FILL
    last = hdr + len(rows)
    dv = DataValidation(type="list", formula1='"F,M"', allow_blank=True, showErrorMessage=True,
                        errorTitle="Gender", error="Choose F or M.")
    ws.add_data_validation(dv)
    dv.add(f"D{hdr + 1}:D{last}")
    ws.column_dimensions["A"].hidden = True
    for col, w in zip("BCD", (12, 38, 15)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = ws.cell(hdr + 1, 2)
    _protect(ws)
    _meta(wb, kind="learners", class_id=class_row["id"], header_row=hdr)
    wb.save(path)


def write_marks_template(path, res):
    """The school's mark-sheet layout (as in 7BB.xlsx).

    Row 1 'OUT OF', row 2 headings (PUPIL'S NAME, MATH, MATH, ENG P1, ENG P2, TOTAL, ...,
    G. TOTAL), one row per learner in alphabetical order, then TOTAL and MEAN rows. Teachers type
    only in the mark cells; the % columns, G. TOTAL, TOTAL and MEAN are live formulas."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    a, k = res.assessment, res.klass
    plan = []                                   # (kind, subject, paper) for columns B..
    for s in res.sheet_subjects:
        for p in s["papers"]:
            plan.append(("mark", s, p))
        plan.append(("pct", s, None))
    plan.append(("gtotal", None, None))
    id_col = len(plan) + 2                      # hidden learner-id column after G. TOTAL
    rows = sorted(res.rows, key=lambda r: r["learner"]["name"])
    first = 3
    last = first + max(len(rows), 1) - 1
    bold = Font(bold=True, size=12)
    center = Alignment(horizontal="center", vertical="center")

    def put(r, c, v, fill=None, locked=True, fmt=None):
        x = ws.cell(r, c, v)
        x.font = bold
        x.alignment = center
        x.border = BORDER
        x.protection = Protection(locked=locked)
        if fill:
            x.fill = fill
        if fmt:
            x.number_format = fmt
        return x

    put(1, 1, "OUT OF")
    put(2, 1, "PUPIL'S NAME", LOCK_FILL)
    n_subj = len(res.sheet_subjects)
    for c, (kind, s, p) in enumerate(plan, start=2):
        if kind == "mark":
            put(1, c, res.out_of[p["id"]], OUTOF_FILL, fmt="0.##")
            put(2, c, p["code"] or p["name"], LOCK_FILL)
        elif kind == "pct":
            put(1, c, "%")
            label = (s["code"] or s["name"]) if len(s["papers"]) == 1 else \
                (s["total_label"] or "Total").upper()
            put(2, c, label, LOCK_FILL)
        else:
            put(1, c, n_subj * 100)
            put(2, c, "G. TOTAL", LOCK_FILL)
    ws.cell(2, id_col, "ID")

    for i, r in enumerate(rows, start=first):
        L = r["learner"]
        put(i, 1, L["name"])
        ws.cell(i, id_col, L["id"])
        start = None
        pct_cells = []
        for c, (kind, s, p) in enumerate(plan, start=2):
            col = get_column_letter(c)
            if kind == "mark":
                v = r["papers"].get(p["id"])
                put(i, c, v["mark"] if v else None, INPUT_FILL, locked=False, fmt="0.##")
                start = start or col
            elif kind == "pct":
                prev = get_column_letter(c - 1)
                if start == prev:
                    f = f"=IFERROR({prev}{i}/{prev}$1*100,0)"
                else:
                    f = f"=IFERROR(SUM({start}{i}:{prev}{i})/SUM({start}$1:{prev}$1)*100,0)"
                put(i, c, f, LOCK_FILL, fmt="0.##")
                pct_cells.append(f"{col}{i}")
                start = None
            else:
                put(i, c, f"=SUM({','.join(pct_cells)})", LOCK_FILL, fmt="0.##")
    # TOTAL and MEAN rows, as on the school's sheet
    for row, label, fn in ((last + 2, "TOTAL", "SUM"), (last + 3, "MEAN", "AVERAGE")):
        put(row, 1, label)
        for c in range(2, len(plan) + 2):
            col = get_column_letter(c)
            put(row, c, f'=IFERROR({fn}({col}{first}:{col}{last}),"")', LOCK_FILL, fmt="0.##")
    for c, (kind, s, p) in enumerate(plan, start=2):
        col = get_column_letter(c)
        ws.column_dimensions[col].width = 11 if kind == "gtotal" else 9
        if kind == "mark":
            oo = res.out_of[p["id"]]
            dv = DataValidation(type="decimal", operator="between", formula1="0",
                                formula2=str(oo), allow_blank=True, showErrorMessage=True,
                                errorTitle="Invalid mark",
                                error=f"{p['name']}: enter a mark from 0 to {G.fmt(float(oo))}.")
            ws.add_data_validation(dv)
            dv.add(f"{col}{first}:{col}{last}")
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions[get_column_letter(id_col)].hidden = True
    ws.freeze_panes = "B3"
    _protect(ws)
    _meta(wb, kind="marks", layout="v2", class_id=k["id"], assessment_id=a["id"],
          assessment=f"Term {a['term']} {a['name']} {a['year']}", header_row=2,
          first_row=first, id_col=id_col - 1,
          paper_cols=",".join(f"{p['id']}:{c - 1}" for c, (kind, s, p) in
                              enumerate(plan, start=2) if kind == "mark"))
    wb.save(path)


# -- reading ---------------------------------------------------------------
NOT_TEMPLATE = ("This file is not a ClassMark template.\n\nClick 'Download template', fill it in "
                "Excel (without changing the headings), save it, then upload that file.")
NOT_TEMPLATE_MARKS = ("This file is not in the marks template layout.\n\nThe first row must be "
                      "OUT OF and the second row must start with PUPIL'S NAME followed by the "
                      "subject headings (as in the downloaded template).")


def _norm(s):
    return "".join(ch for ch in str(s or "").upper() if ch.isalnum())


def _is_classic_marks(rows):
    """The school's own mark sheet layout without ClassMark's hidden marker."""
    return (len(rows) > 2 and rows[0] and rows[1] and _norm(rows[0][0]) == "OUTOF"
            and "NAME" in _norm(rows[1][0]))


def read_template(path, kind):
    """Open and check a template. Returns (meta dict, rows of the first sheet as tuples)."""
    if not path.lower().endswith((".xlsx", ".xlsm")):
        raise TemplateError(NOT_TEMPLATE)
    try:
        wb = load_workbook(path, data_only=True)
    except Exception as e:  # noqa: BLE001 - any unreadable file
        raise TemplateError(f"Could not open the file: {e}") from e
    rows = [tuple(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    if META_SHEET not in wb.sheetnames:
        wb.close()
        if kind == "marks" and _is_classic_marks(rows):
            return {"layout": "classic"}, rows
        raise TemplateError(NOT_TEMPLATE_MARKS if kind == "marks" else NOT_TEMPLATE)
    meta = {str(r[0]): str(r[1]) for r in wb[META_SHEET].iter_rows(values_only=True)
            if r and r[0] is not None}
    wb.close()
    if meta.get("marker") != MARKER:
        raise TemplateError(NOT_TEMPLATE)
    if meta.get("kind") != kind:
        is_learners = meta.get("kind") == "learners"
        raise TemplateError(f"This is {'a learners' if is_learners else 'a marks'} template. "
                            f"Upload it on the {'Learners' if is_learners else 'Marks entry'} "
                            "page instead.")
    if kind == "marks" and meta.get("layout") != "v2":
        raise TemplateError("This marks template is from an older version of ClassMark. "
                            "Click 'Download template' for the current one.")
    return meta, rows


def parse_learners(db, class_id, meta, rows):
    """Returns (entries, file_problems). Entry: dict(row, id, adm, name, gender, action, error)."""
    if int(meta.get("class_id", 0)) != class_id:
        k = db.get_class(int(meta.get("class_id", 0)))
        raise TemplateError("This template was made for another class"
                            f"{' (' + k['name'] + ')' if k else ''}. Download a new template "
                            "for this class.")
    hdr = int(meta["header_row"])
    head = [str(c or "").strip().upper() for c in rows[hdr - 1][:4]]
    if head[1:3] != ["ADM NO", "FULL NAME"]:
        raise TemplateError("The headings have been changed. Download a fresh template.")
    existing = {L["id"]: L for L in db.learners(class_id)}
    by_adm = {L["adm_no"]: L for L in existing.values() if L["adm_no"]}
    entries, seen_adm = [], {}
    for n, row in enumerate(rows[hdr:], start=hdr + 1):
        row = tuple(row) + (None,) * 4
        lid, adm, name, gender = row[0], _clean_adm(row[1]), row[2], row[3]
        name = " ".join(str(name or "").upper().split())
        gender = str(gender or "").strip().upper()[:1]
        if not name and not adm:
            continue
        e = {"row": n, "id": None, "adm": adm, "name": name, "gender": gender, "error": ""}
        L = existing.get(int(lid)) if isinstance(lid, (int, float)) else None
        if not L and adm in by_adm:
            L = by_adm[adm]
        if not name:
            e["error"] = "Name is missing"
        elif gender not in ("", "F", "M"):
            e["error"] = "Gender must be F or M"
        elif adm and adm in seen_adm:
            e["error"] = f"Adm No {adm} repeated (row {seen_adm[adm]})"
        if adm:
            seen_adm.setdefault(adm, n)
        if L:
            e["id"] = L["id"]
            same = (L["adm_no"] or "", L["name"], L["gender"] or "") == (adm, name, gender)
            e["action"] = "unchanged" if same else "update"
        else:
            e["action"] = "new"
        entries.append(e)
    return entries


def apply_learners(db, class_id, entries):
    added = updated = 0
    for e in entries:
        if e["error"] or e["action"] == "unchanged":
            continue
        db.save_learner(e["id"], class_id, e["adm"], e["name"], e["gender"])
        added += e["action"] == "new"
        updated += e["action"] == "update"
    return added, updated


SUMMARY_ROWS = ("TOTAL", "MEAN", "OUTOF", "AVERAGE", "GTOTAL")


def _name_key(s):
    return " ".join(str(s or "").upper().split())


def parse_marks(db, class_id, assessment_id, meta, rows):
    """Check a marks file (ClassMark template or the school's own sheet in the same layout).

    Returns dict(papers, entries, wrong_assessment, out_of_changes, missing_papers).
    Entry: dict(row, learner, name, marks={paper_id: value|None}, errors={paper_id: msg})."""
    papers = {p["id"]: p for p in db.papers()}
    head = rows[1] if len(rows) > 1 else ()
    if meta.get("layout") == "v2":
        if int(meta.get("class_id", 0)) != class_id:
            raise TemplateError("This marks template was made for another class. Download a new "
                                "template from this class's Marks entry page.")
        cols = [(int(c), papers[int(pid)]) for pid, c in
                (x.split(":") for x in meta.get("paper_cols", "").split(",") if x)
                if int(pid) in papers]
        id_col = int(meta["id_col"])
        aid = int(meta.get("assessment_id", 0))
        wrong = meta.get("assessment") if aid != assessment_id else None
    else:  # the school's own sheet: match headings to paper codes/names (first match wins)
        cols, used = [], set()
        for p in papers.values():
            keys = {_norm(p["code"]), _norm(p["name"])} - {""}
            for c, h in enumerate(head):
                if c and c not in used and _norm(h) in keys:
                    cols.append((c, p))
                    used.add(c)
                    break
        id_col, wrong = None, None
    if not cols:
        raise TemplateError("No subject headings in row 2 match this system's papers "
                            f"({', '.join(p['code'] for p in papers.values())}).")
    if "NAME" not in _norm(head[0] if head else ""):
        raise TemplateError("Row 2 must start with PUPIL'S NAME. Download a fresh template.")
    found = {p["id"] for _, p in cols}
    missing = [p for p in papers.values() if p["id"] not in found]
    # 'OUT OF' row (row 1) of the file is used to check marks and update the assessment
    current = db.out_of_map(assessment_id)
    out_of, changes = dict(current), {}
    for c, p in cols:
        try:
            v = to_number(rows[0][c] if c < len(rows[0]) else None)
        except ValueError:
            v = None
        if v and v > 0:
            out_of[p["id"]] = v
            if v != current[p["id"]]:
                changes[p["id"]] = v
    learners = {L["id"]: L for L in db.learners(class_id)}
    by_name = {_name_key(L["name"]): L for L in learners.values()}
    entries = []
    width = max([c for c, _ in cols] + [id_col or 0]) + 1
    for n, row in enumerate(rows[2:], start=3):
        row = tuple(row) + (None,) * width
        name = _name_key(row[0])
        if not name or _norm(name).startswith(SUMMARY_ROWS):
            continue
        lid = row[id_col] if id_col is not None else None
        L = learners.get(int(lid)) if isinstance(lid, (int, float)) else None
        L = L or by_name.get(name)
        if not L:
            entries.append({"row": n, "learner": None, "name": name, "adm": "", "marks": {},
                            "errors": {0: "Not in this class — check the spelling or add the "
                                          "learner on the Learners page first"}})
            continue
        e = {"row": n, "learner": L, "name": L["name"], "adm": L["adm_no"], "marks": {},
             "errors": {}}
        for c, p in cols:
            raw = row[c]
            try:
                m = to_number(raw)
            except ValueError:
                e["errors"][p["id"]] = f"'{raw}' is not a number"
                continue
            if m is not None and not 0 <= m <= out_of[p["id"]]:
                e["errors"][p["id"]] = f"{G.fmt(m)} is outside 0–{G.fmt(float(out_of[p['id']]))}"
                continue
            e["marks"][p["id"]] = m
        entries.append(e)
    return {"papers": [p for _, p in sorted(cols)], "entries": entries,
            "wrong_assessment": wrong, "out_of_changes": changes, "missing_papers": missing}


def apply_marks(db, assessment_id, parsed):
    """Updates out-of values from the file, then writes valid marks (an empty cell clears a
    mark). Returns the number of marks saved."""
    for pid, v in parsed["out_of_changes"].items():
        db.set_out_of(assessment_id, pid, v)
    saved = 0
    for e in parsed["entries"]:
        if not e["learner"]:
            continue
        for pid, m in e["marks"].items():
            db.set_mark(assessment_id, e["learner"]["id"], pid, m, commit=False)
            saved += m is not None
    db.conn.commit()
    return saved
