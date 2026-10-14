"""Dashboard metrics. Counts, means and lists only — never a ranking of learners."""
from . import grading as G
from .compute import Results


def chronological(db, class_id):
    return sorted(db.assessments(class_id), key=lambda a: (a["year"], a["term"], a["id"]))


def previous_assessment(db, class_id, aid):
    ass = chronological(db, class_id)
    ids = [a["id"] for a in ass]
    i = ids.index(aid) if aid in ids else -1
    return ass[i - 1] if i > 0 else None


# 1. marks entry progress -------------------------------------------------
def entry_progress(res):
    """Per paper: how many learners have a mark. Plus learners with missing papers."""
    learners = [r["learner"] for r in res.rows]
    n = len(learners)
    papers = []
    for s in res.sheet_subjects:
        for p in s["papers"]:
            done = sum(1 for L in learners if (L["id"], p["id"]) in res.marks)
            papers.append({"paper": p, "subject": s, "entered": done, "total": n})
    missing = []
    all_papers = [x["paper"] for x in papers]
    for r in res.rows:
        L = r["learner"]
        gaps = [p for p in all_papers if (L["id"], p["id"]) not in res.marks]
        if gaps:
            missing.append({"learner": L, "papers": gaps, "none": len(gaps) == len(all_papers)})
    cells = n * len(all_papers)
    filled = sum(x["entered"] for x in papers)
    return {"papers": papers, "missing": sorted(missing, key=lambda m: m["learner"]["name"]),
            "filled": filled, "cells": cells, "pct": (filled / cells * 100) if cells else 0}


# 2. ready-to-print checklist ---------------------------------------------
def readiness(res, progress):
    """[(state, text)] with state 'ok', 'todo' or 'info'."""
    a, k, s = res.assessment, res.klass, res.settings
    out = []
    gaps = progress["cells"] - progress["filled"]
    nobody = sum(1 for m in progress["missing"] if m["none"])
    if gaps == 0:
        out.append(("ok", "All marks entered"))
    else:
        txt = f"{gaps} marks still missing"
        if nobody:
            txt += f" ({nobody} learner{'s' if nobody > 1 else ''} with no marks at all)"
        out.append(("todo", txt + " — blanks count as 0"))
    for key, label in (("closing_date", "Closing date"), ("opening_date", "Opening date")):
        out.append(("ok", f"{label} set") if a[key] else
                   ("todo", f"{label} not set (Assessment → Edit)"))
    out.append(("ok", "Class teacher's name set") if k["class_teacher"] else
               ("todo", "Class teacher's name not set (Class → Edit)"))
    out.append(("ok", "Head teacher's name set") if s.get("head_teacher") else
               ("info", "Head teacher's name not set (Settings) — optional"))
    assessed = [r for r in res.rows if r["has_marks"]]
    if assessed:
        n = len(assessed)
        both = sum(1 for r in assessed if r["discipline"] and r["attention"])
        out.append(("ok" if both == n else "todo",
                    f"Discipline & class attention filled for {both} of {n} learners"))
        edited = sum(1 for r in assessed if r["ct_custom"] or r["ht_custom"])
        out.append(("info", f"Remarks personalised for {edited} of {n} learners "
                            "(the rest use the automatic remarks)"))
    return out


# 3 & 5. change since previous assessment, learners needing support --------
def change(res, prev):
    """Per learning area mean now vs before, and how many learners moved level."""
    if prev is None:
        return None
    cur = {st["subject"]["id"]: st for st in res.subject_stats()}
    old = {st["subject"]["id"]: st for st in prev.subject_stats()}
    areas = []
    for s in res.subjects:
        c, o = cur[s["id"]]["mean_pct"], old.get(s["id"], {}).get("mean_pct")
        areas.append({"subject": s, "now": c, "before": o,
                      "delta": (c - o) if c is not None and o is not None else None})
    before = {r["learner"]["id"]: r for r in prev.rows if r["has_marks"]}
    up = same = down = 0
    for r in res.rows:
        b = before.get(r["learner"]["id"])
        if not r["has_marks"] or not b:
            continue
        d = r["band"].points - b["band"].points
        up += d > 0
        same += d == 0
        down += d < 0
    oc = res.overall()["mean_pct"]
    ob = prev.overall()["mean_pct"]
    return {"areas": areas, "up": up, "same": same, "down": down, "overall_now": oc,
            "overall_before": ob, "prev_name": f"Term {prev.assessment['term']} "
                                               f"{prev.assessment['name']} {prev.assessment['year']}"}


def support_list(res, prev):
    """Learners at AE/BE overall, or whose overall level dropped. Alphabetical."""
    before = {r["learner"]["id"]: r for r in prev.rows if r["has_marks"]} if prev else {}
    out = []
    for r in res.rows:
        if not r["has_marks"]:
            continue
        b = before.get(r["learner"]["id"])
        dropped = bool(b) and r["band"].points < b["band"].points
        low = r["band"].code[:2] in ("AE", "BE")
        if not (low or dropped):
            continue
        weak = sorted(((v["pct"], s["name"]) for s in res.subjects
                       if (v := r["subjects"].get(s["id"]))))[:2]
        reason = []
        if low:
            reason.append(f"overall {r['band'].code}")
        if dropped:
            reason.append(f"dropped from {b['band'].code}")
        out.append({"learner": r["learner"], "level": r["band"].code,
                    "before": b["band"].code if b else None, "reason": ", ".join(reason),
                    "weak": [f"{n} ({round(p)}%)" for p, n in weak]})
    return sorted(out, key=lambda x: x["learner"]["name"])


# 4. level distribution -----------------------------------------------------
def level_distribution(res):
    assessed = [r for r in res.rows if r["has_marks"]]
    overall = {g: sum(1 for r in assessed if r["band"].code.startswith(g)) for g in G.GROUPS}
    per_area = [(st["subject"], st["groups"]) for st in res.subject_stats()]
    return overall, per_area


# 6. term trend ---------------------------------------------------------------
def trend(db, class_id, upto_aid, limit=8):
    """Class mean (overall and per learning area) for each assessment up to the current one."""
    ass = chronological(db, class_id)
    ids = [a["id"] for a in ass]
    if upto_aid in ids:
        ass = ass[:ids.index(upto_aid) + 1]
    points = []
    for a in ass[-limit:]:
        r = Results(db, class_id, a["id"])
        ov = r.overall()
        if ov["mean_pct"] is None:
            continue
        points.append({"assessment": a,
                       "label": f"T{a['term']} {a['name'].replace(' Assessment', '')}",
                       "overall": ov["mean_pct"],
                       "areas": {st["subject"]["id"]: st["mean_pct"] for st in r.subject_stats()}})
    return points


# 7. strongest / weakest learning areas -------------------------------------
def strongest_weakest(res, n=2):
    stats = [st for st in res.subject_stats() if st["mean_pct"] is not None]
    stats.sort(key=lambda st: st["mean_pct"], reverse=True)
    weakest = stats[::-1][:n] if len(stats) > n else []
    return stats[:n], weakest


# 8. girls vs boys ------------------------------------------------------------
def gender_stats(res):
    out = []
    for code, label in (("F", "Girls"), ("M", "Boys"), ("", "Not recorded")):
        rows = [r for r in res.rows if r["has_marks"] and (r["learner"]["gender"] or "") == code]
        if not rows:
            continue
        mean = sum(r["avg_pct"] for r in rows) / len(rows)
        out.append({"label": label, "n": len(rows), "mean": mean,
                    "band": G.band_for(mean),
                    "points": sum(r["points"] for r in rows) / len(rows),
                    "groups": {g: sum(1 for r in rows if r["band"].code.startswith(g))
                               for g in G.GROUPS}})
    return out


# 9. points summary -----------------------------------------------------------
def points_summary(res):
    assessed = [r for r in res.rows if r["has_marks"]]
    if not assessed:
        return None
    mx = len(res.subjects) * G.MAX_POINTS
    edges = [round(mx * f) for f in (5 / 6, 4 / 6, 3 / 6, 2 / 6)]   # 72 -> 60, 48, 36, 24
    labels = [f"{edges[0]}–{mx}", f"{edges[1]}–{edges[0] - 1}", f"{edges[2]}–{edges[1] - 1}",
              f"{edges[3]}–{edges[2] - 1}", f"0–{edges[3] - 1}"]
    buckets = [0] * 5
    for r in assessed:
        p = r["points"]
        i = next((j for j, e in enumerate(edges) if p >= e), 4)
        buckets[i] += 1
    return {"mean": sum(r["points"] for r in assessed) / len(assessed), "max": mx,
            "buckets": list(zip(labels, buckets))}
