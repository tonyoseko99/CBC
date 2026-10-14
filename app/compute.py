"""Turns raw marks into per-learner results and class analysis. No ranking anywhere."""
from . import grading as G


def apply_remarks(r, subjects, notes, settings):
    """Auto remarks from the learner's level, overridden by anything the teacher typed."""
    L = r["learner"]
    note = notes.get(L["id"], {})
    auto_ct = auto_ht = ""
    if r["band"]:
        ranked = sorted(((v["pct"], s["name"]) for s in subjects
                         if (v := r["subjects"].get(s["id"]))), reverse=True)
        best = [n for p, n in ranked[:2] if p >= 41] or [ranked[0][1]]
        weak = [n for p, n in ranked[::-1][:2] if n not in best] or ["all learning areas"]
        auto_ct = G.class_teacher_remark(L["id"], L["name"], r["band"].code, best, weak)
        auto_ht = G.head_teacher_remark(r["band"].code)
    r["auto_ct"], r["auto_ht"] = auto_ct, auto_ht
    r["ct_remark"] = note.get("ct_remark") or auto_ct
    r["ht_remark"] = note.get("ht_remark") or auto_ht
    r["ct_custom"] = bool(note.get("ct_remark"))
    r["ht_custom"] = bool(note.get("ht_remark"))
    r["discipline"] = note.get("discipline") or settings.get("default_discipline", "")
    r["attention"] = note.get("attention") or settings.get("default_attention", "")


def short_name(a):
    n = a["name"].upper().replace(" ASSESSMENT", "").replace("ASSESSMENT", "").strip()
    return n or a["name"].upper()


class Results:
    combined = False

    def __init__(self, db, class_id, assessment_id):
        self.db = db
        self.settings = db.settings()
        self.klass = db.get_class(class_id)
        self.assessment = db.get_assessment(assessment_id)
        self.subjects = db.subjects()                 # report-form order
        self.sheet_subjects = db.subjects("sheet")    # mark sheet / template column order
        self.out_of = db.out_of_map(assessment_id)
        self.marks = db.marks_map(assessment_id)
        self.notes = db.notes_map(assessment_id)
        self.rows = [self.learner_result(L) for L in db.learners(class_id)]

    # -- per learner -----------------------------------------------------
    def learner_result(self, L, marks=None):
        marks = self.marks if marks is None else marks
        lid = L["id"]
        # r["papers"] holds only marks actually entered. Once a learner has any mark in this
        # assessment, a blank paper counts as 0 (as in the school's Excel mark sheet).
        r = {"learner": L, "papers": {}, "subjects": {}}
        assessed = any((lid, p["id"]) in marks for s in self.subjects for p in s["papers"])
        total = out = points = 0.0
        for s in self.subjects if assessed else ():
            sm = so = 0.0
            for p in s["papers"]:
                m = marks.get((lid, p["id"]))
                oo = self.out_of[p["id"]] or 100
                if m is not None:
                    pct = m / oo * 100
                    r["papers"][p["id"]] = {"mark": m, "out_of": oo, "pct": pct,
                                            "band": G.band_for(pct)}
                    sm += m
                so += oo
            if so:
                pct = sm / so * 100
                b = G.band_for(pct)
                r["subjects"][s["id"]] = {"mark": sm, "out_of": so, "pct": pct, "band": b}
                total += sm
                out += so
                points += b.points
        n = len(r["subjects"])
        r.update(total=total, out_of=out, points=int(points), max_points=n * G.MAX_POINTS,
                 n_subjects=n, has_marks=n > 0)
        if n:
            r["avg_pct"] = sum(v["pct"] for v in r["subjects"].values()) / n
            r["band"] = G.band_for(r["avg_pct"])
        else:
            r["avg_pct"] = None
            r["band"] = None
        self._remarks(r)
        return r

    def _remarks(self, r):
        apply_remarks(r, self.subjects, self.notes, self.settings)

    def term_label(self):
        a = self.assessment
        return f"{a['term']} &nbsp; ({a['name']})"

    # -- class analysis --------------------------------------------------
    def subject_stats(self, rows=None, subjects=None):
        rows = self.rows if rows is None else rows
        out = []
        for s in self.subjects if subjects is None else subjects:
            vals = [r["subjects"][s["id"]] for r in rows if s["id"] in r["subjects"]]
            counts = {c: 0 for c in G.CODES}
            for v in vals:
                counts[v["band"].code] += 1
            groups = {g: sum(n for c, n in counts.items() if c.startswith(g)) for g in G.GROUPS}
            mean = sum(v["pct"] for v in vals) / len(vals) if vals else None
            paper_means = {}
            for p in s["papers"]:
                pm = [r["papers"][p["id"]]["mark"] for r in rows if p["id"] in r["papers"]]
                paper_means[p["id"]] = sum(pm) / len(pm) if pm else None
            out.append({"subject": s, "sat": len(vals), "mean_pct": mean,
                        "band": G.band_for(mean) if mean is not None else None,
                        "counts": counts, "groups": groups, "paper_means": paper_means})
        return out

    def overall(self, rows=None):
        rows = self.rows if rows is None else rows
        sat = [r for r in rows if r["has_marks"]]
        mean = sum(r["avg_pct"] for r in sat) / len(sat) if sat else None
        return {"learners": len(rows), "with_marks": len(sat), "mean_pct": mean,
                "band": G.band_for(mean) if mean is not None else None}

    # -- labels ----------------------------------------------------------
    def title(self):
        a, k, s = self.assessment, self.klass, self.settings
        return f"{s['school_name']}  {k['name']}  TERM {a['term']} {a['name']} {a['year']}".upper()


class CombinedResults:
    """Up to three assessments side by side, plus their average, for one report.

    Each learning area's average is the mean of its % in the exams the learner sat; level,
    points and remarks come from that average. Remarks, discipline and dates are taken from
    the LAST assessment in the list (the 'anchor')."""
    combined = True

    def __init__(self, db, class_id, assessment_ids):
        self.parts = [Results(db, class_id, a) for a in assessment_ids]
        anchor = self.parts[-1]
        self.db = db
        self.settings, self.klass, self.subjects = anchor.settings, anchor.klass, anchor.subjects
        self.assessment, self.notes = anchor.assessment, anchor.notes
        self.assessments = [p.assessment for p in self.parts]
        by_lid = [{r["learner"]["id"]: r for r in p.rows} for p in self.parts]
        self.rows = [self._combine(r["learner"], [b.get(r["learner"]["id"]) for b in by_lid])
                     for r in anchor.rows]

    def _combine(self, L, exams):
        r = {"learner": L, "exams": exams, "subjects": {}}
        sat = [e for e in exams if e and e["has_marks"]]
        points = 0
        for s in self.subjects:
            vals = [e["subjects"][s["id"]]["pct"] for e in sat if s["id"] in e["subjects"]]
            if vals:
                pct = sum(vals) / len(vals)
                b = G.band_for(pct)
                r["subjects"][s["id"]] = {"pct": pct, "band": b, "n": len(vals)}
                points += b.points
        n = len(r["subjects"])
        r.update(points=points, max_points=n * G.MAX_POINTS, n_subjects=n, has_marks=n > 0,
                 exams_sat=len(sat))
        r["avg_pct"] = sum(v["pct"] for v in r["subjects"].values()) / n if n else None
        r["band"] = G.band_for(r["avg_pct"]) if n else None
        apply_remarks(r, self.subjects, self.notes, self.settings)
        return r

    def names(self):
        return [short_name(a) for a in self.assessments]

    def _joined(self):
        n = [short_name(a).title() for a in self.assessments]
        return ", ".join(n[:-1]) + " & " + n[-1] if len(n) > 1 else n[0]

    def term_label(self):
        terms = sorted({a["term"] for a in self.assessments})
        t = " & ".join(str(x) for x in terms)
        return f"{t} &nbsp; ({self._joined()})"

    def title(self):
        a, k, s = self.assessment, self.klass, self.settings
        terms = " & ".join(str(x) for x in sorted({x["term"] for x in self.assessments}))
        return (f"{s['school_name']}  {k['name']}  TERM {terms} "
                f"{self._joined()} {a['year']}").upper()


SHEET_DEFAULTS = {
    "learners": None,      # set of learner ids, or None for everyone
    "subjects": None,      # set of subject ids, or None for all learning areas
    "sort": "adm",         # "adm" or "name" (no ranking)
    # per learning area
    "marks": True, "pct": True, "points": False, "level": True,
    # totals (always over all learning areas)
    "total": True, "outof": True, "gtotal": True, "avg": True, "tpoints": True, "olevel": True,
    # summary rows
    "counts": True, "groups": True, "sat": True, "totals_row": True, "mean_row": True,
    "analysis": True,      # subject-analysis sheet/page
}
PER_SUBJECT = ("marks", "pct", "points", "level")
TOTAL_KEYS = ("total", "outof", "gtotal", "avg", "tpoints", "olevel")
SUMMARY_KEYS = ("counts", "groups", "sat", "totals_row", "mean_row")
_OFF = {k: False for k in PER_SUBJECT + TOTAL_KEYS + SUMMARY_KEYS}
SHEET_PRESETS = {
    "Full mark sheet": {**SHEET_DEFAULTS},
    "Points only": {**_OFF, "points": True, "tpoints": True, "sat": True, "totals_row": True,
                    "mean_row": True},
    "Levels only": {**_OFF, "level": True, "olevel": True, "counts": True, "groups": True,
                    "sat": True, "mean_row": True},
    "Points & levels": {**_OFF, "points": True, "level": True, "tpoints": True, "olevel": True,
                        "counts": True, "groups": True, "sat": True, "totals_row": True,
                        "mean_row": True},
    "Marks & % only": {**_OFF, "marks": True, "pct": True, "total": True, "outof": True,
                       "gtotal": True, "avg": True, "sat": True, "totals_row": True,
                       "mean_row": True},
}


def sheet_rows(res, opts):
    """The learners chosen for an export, in Adm No or name order."""
    ids = opts.get("learners")
    rows = [r for r in res.rows if ids is None or r["learner"]["id"] in ids]
    if opts.get("sort") == "name":
        return sorted(rows, key=lambda r: r["learner"]["name"])
    return rows  # results are already in Adm No order


def mark_sheet_layout(res, opts=None):
    """Rows/columns for the class mark sheet, shared by the Excel and PDF exports.

    opts: see SHEET_DEFAULTS. Returns dict(header=[rowA,rowB], spans=[(r0,c0,r1,c1)],
    body, summary, kinds (one per column), n_cols, rows (chosen learners), subjects)."""
    o = {**SHEET_DEFAULTS, **(opts or {})}
    rows = sheet_rows(res, o)
    subjects = [s for s in res.sheet_subjects if o["subjects"] is None or s["id"] in o["subjects"]]
    cols = [("adm", None, None), ("name", None, None)]
    rowA, rowB = ["ADM NO", "NAME OF LEARNER"], ["", ""]
    spans = [(0, 0, 1, 0), (0, 1, 1, 1)]
    for s in subjects:
        start = len(cols)
        multi = len(s["papers"]) > 1
        block = []
        if o["marks"]:
            for p in s["papers"]:
                oo = G.fmt(float(res.out_of[p["id"]]))
                block.append(("mark", p, f"{p['code'] or p['name']}/{oo}" if multi else f"MKS/{oo}"))
        if o["pct"]:
            block.append(("pct", None, "%"))
        if o["points"]:
            block.append(("pts", None, "PTS"))
        if o["level"]:
            block.append(("grd", None, "LVL"))
        for kind, p, label in block:
            cols.append((kind, s, p))
            rowA.append(s["code"] or s["name"])
            rowB.append(label)
        if len(block) > 1:
            spans.append((0, start, 0, len(cols) - 1))
    n_subj = len(res.sheet_subjects)
    tail = [("total", "total", "TOTAL MARKS"), ("outof", "outof", "OUT OF"),
            ("gtotal", "gtotal", f"G. TOTAL /{n_subj * 100}"), ("avg", "avg", "AVG %"),
            ("tpoints", "points", f"POINTS /{n_subj * G.MAX_POINTS}"),
            ("olevel", "level", "LEVEL")]
    for key, kind, label in tail:
        if o[key]:
            spans.append((0, len(cols), 1, len(cols)))
            cols.append((kind, None, None))
            rowA.append(label)
            rowB.append("")
    kinds = [c[0] for c in cols]

    def value(r, kind, s, p):
        L = r["learner"]
        if kind == "adm":
            return L["adm_no"] or ""
        if kind == "name":
            return L["name"]
        if s is not None:
            if kind == "mark":
                v = r["papers"].get(p["id"])
                return v["mark"] if v else ""
            v = r["subjects"].get(s["id"])
            if not v:
                return ""
            return {"pct": round(v["pct"]), "pts": v["band"].points, "grd": v["band"].code}[kind]
        if not r["has_marks"]:
            return ""
        return {"total": r["total"], "outof": r["out_of"],
                "gtotal": round(sum(v["pct"] for v in r["subjects"].values()), 1),
                "avg": round(r["avg_pct"], 1), "points": r["points"],
                "level": r["band"].code}[kind]

    body = [[value(r, *c) for c in cols] for r in rows]

    # summary rows, worked out from the chosen learners only
    n_cols = len(cols)
    anchor = {}   # subject id -> column used for counts / SAT
    for i, (kind, s, p) in enumerate(cols):
        if s is not None:
            rank = {"grd": 4, "pts": 3, "pct": 2, "mark": 1}[kind]
            if s["id"] not in anchor or rank >= anchor[s["id"]][1]:
                anchor[s["id"]] = (i, rank)
    tail_anchor = next((i for i, k in enumerate(kinds) if k == "level"), None)
    if tail_anchor is None:
        tail_anchor = next((i for i, k in enumerate(kinds) if k == "points"), None)
    assessed = [r for r in rows if r["has_marks"]]

    def blank(label):
        return ["", label] + [""] * (n_cols - 2)

    def by_level(match):
        row_counts = {}
        for sid, (i, _) in anchor.items():
            row_counts[i] = sum(1 for r in rows if sid in r["subjects"]
                                and match(r["subjects"][sid]["band"].code))
        if tail_anchor is not None:
            row_counts[tail_anchor] = sum(1 for r in assessed if match(r["band"].code))
        return row_counts

    summary = []
    if o["counts"]:
        for code in G.CODES:
            row = blank(code)
            for i, n in by_level(lambda c, code=code: c == code).items():
                row[i] = n
            summary.append(row)
    if o["groups"]:
        for g in G.GROUPS:
            row = blank(f"TOTAL {g}")
            for i, n in by_level(lambda c, g=g: c.startswith(g)).items():
                row[i] = n
            summary.append(row)
    if o["sat"]:
        row = blank("SAT")
        for sid, (i, _) in anchor.items():
            row[i] = sum(1 for r in rows if sid in r["subjects"])
        if tail_anchor is not None:
            row[tail_anchor] = len(assessed)
        summary.append(row)
    numeric = ("mark", "pct", "pts", "total", "gtotal", "points")
    if o["totals_row"]:
        row = blank("TOTAL")
        for i, k in enumerate(kinds):
            if k in numeric:
                vals = [b[i] for b in body if isinstance(b[i], (int, float))]
                row[i] = round(sum(vals), 1) if vals else ""
        summary.append(row)
    if o["mean_row"]:
        row = blank("MEAN SCORE")
        for i, (kind, s, p) in enumerate(cols):
            if kind in numeric or kind == "avg":
                vals = [b[i] for b in body if isinstance(b[i], (int, float))]
                row[i] = round(sum(vals) / len(vals), 1) if vals else ""
            elif kind == "grd":
                vals = [r["subjects"][s["id"]]["pct"] for r in rows if s["id"] in r["subjects"]]
                row[i] = G.band_for(sum(vals) / len(vals)).code if vals else ""
            elif kind == "level" and assessed:
                row[i] = G.band_for(sum(r["avg_pct"] for r in assessed) / len(assessed)).code
        summary.append(row)
    return {"header": [rowA, rowB], "spans": spans, "body": body, "summary": summary,
            "kinds": kinds, "n_cols": n_cols, "rows": rows, "subjects": subjects}
