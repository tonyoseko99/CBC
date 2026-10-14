"""Dashboard: progress, readiness, support list, level mix, change, trend, gender, points."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QProgressBar, QScrollArea,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import analytics as A
from . import grading as G
from .compute import Results
from .ui_charts import LEVEL_COLORS, LineChart, SimpleBars, StackedBars

GROUP_BG = {"EE": "#D8F0DC", "ME": "#DDEBF7", "AE": "#FFF2C4", "BE": "#FAD4D4"}
STATE = {"ok": ("✔", "#2E7D32"), "todo": ("✖", "#B00020"), "info": ("ℹ", "#5A6474")}


def _item(text, center=False, bold=False, bg=None, fg=None):
    it = QTableWidgetItem("" if text is None else str(text))
    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    if center:
        it.setTextAlignment(Qt.AlignCenter)
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if bg:
        it.setBackground(QBrush(QColor(bg)))
    if fg:
        it.setForeground(QBrush(QColor(fg)))
    return it


def _table(heads, rows, stretch=0):
    """Read-only table sized to its rows (no inner scrolling)."""
    t = QTableWidget(len(rows), len(heads))
    t.setHorizontalHeaderLabels(heads)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.NoSelection)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    for r, cells in enumerate(rows):
        for c, it in enumerate(cells):
            t.setItem(r, c, it if isinstance(it, QTableWidgetItem) else _item(it, center=c > 0))
    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeToContents)
    hh.setSectionResizeMode(stretch, QHeaderView.Stretch)
    t.resizeRowsToContents()
    t.setFixedHeight(hh.height() + sum(t.rowHeight(i) for i in range(len(rows))) + 4)
    return t


def _note(text):
    lab = QLabel(text)
    lab.setObjectName("hint")
    lab.setWordWrap(True)
    return lab


def _box(title, *widgets):
    g = QGroupBox(title.replace("&", "&&"))   # a single & would become a shortcut underline
    lay = QVBoxLayout(g)
    for w in widgets:
        if isinstance(w, QWidget):
            if type(w) is QWidget:
                w.setObjectName("plain")   # transparent container (see STYLE)
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    lay.addStretch(1)                      # keep content at the top of tall boxes
    return g


def _pct(v):
    return f"{v:.1f}%" if v is not None else "-"


class DashboardPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.db = main.db
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        head = QLabel("Dashboard")
        head.setObjectName("pageTitle")
        lay.addWidget(head)
        self.sub = _note("")
        lay.addWidget(self.sub)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll, 1)
        self.trend_choice = None

    # ---------------------------------------------------------------------
    def refresh(self):
        pos = self.scroll.verticalScrollBar().value()
        content = QWidget()
        self.grid = QGridLayout(content)
        self.grid.setContentsMargins(0, 4, 8, 8)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(10)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        cid, aid = self.main.class_id, self.main.assessment_id
        if not cid:
            self.sub.setText("")
            self.grid.addWidget(_note("Welcome! Start by creating a class (top bar → New class), "
                                      "then add learners, create an assessment and enter marks."),
                                0, 0, 1, 2)
        elif not aid:
            self.sub.setText("")
            self.grid.addWidget(_note("Next: create an assessment (top bar → New assessment)."),
                                0, 0, 1, 2)
        else:
            self.build(cid, aid)
        self.grid.setRowStretch(self.grid.rowCount(), 1)
        self.scroll.setWidget(content)
        self.scroll.verticalScrollBar().setValue(pos)

    def build(self, cid, aid):
        res = Results(self.db, cid, aid)
        prev_a = A.previous_assessment(self.db, cid, aid)
        prev = Results(self.db, cid, prev_a["id"]) if prev_a else None
        if prev and not prev.overall()["with_marks"]:
            prev = None
        a = res.assessment
        self.sub.setText(f"{res.klass['name']} · Term {a['term']} {a['name']} {a['year']}"
                         + (f" · compared with {prev.assessment['name']}" if prev else ""))
        progress = A.entry_progress(res)
        ov = res.overall()
        pts = A.points_summary(res)
        row = 0
        self.grid.addLayout(self.cards(res, ov, pts, progress), row, 0, 1, 2)
        row += 1
        self.grid.addWidget(self.ready_box(res, progress), row, 0, Qt.AlignTop)
        self.grid.addWidget(self.progress_box(progress), row, 1, Qt.AlignTop)
        row += 1
        if not ov["with_marks"]:
            self.grid.addWidget(_note("No marks entered yet for this assessment — the charts "
                                      "below appear once marks are in."), row, 0, 1, 2)
            return
        self.grid.addWidget(self.support_box(res, prev), row, 0, 1, 2)
        row += 1
        self.grid.addWidget(self.levels_box(res), row, 0, Qt.AlignTop)
        self.grid.addWidget(self.points_box(pts), row, 1, Qt.AlignTop)
        row += 1
        self.grid.addWidget(self.change_box(res, prev), row, 0, Qt.AlignTop)
        right = QVBoxLayout()
        right.addWidget(self.strong_weak_box(res))
        right.addWidget(self.gender_box(res))
        right.addStretch(1)
        self.grid.addLayout(right, row, 1)
        row += 1
        self.grid.addWidget(self.trend_box(res, cid, aid), row, 0, 1, 2)
        row += 1
        self.grid.addWidget(self.analysis_box(res), row, 0, 1, 2)

    # -- sections -----------------------------------------------------------
    def cards(self, res, ov, pts, progress):
        lay = QHBoxLayout()
        values = [
            (str(len(res.rows)), "Learners"),
            (str(ov["with_marks"]), "Assessed"),
            (_pct(ov["mean_pct"]), "Class mean"),
            (ov["band"].code if ov["band"] else "-", "Mean level"),
            (f"{pts['mean']:.1f} / {pts['max']}" if pts else "-", "Average points"),
            (f"{progress['pct']:.0f}%", "Marks entered"),
        ]
        for val, label in values:
            f = QFrame()
            f.setObjectName("card")
            v = QVBoxLayout(f)
            a = QLabel(val)
            a.setObjectName("cardValue")
            if label == "Mean level" and ov["band"]:
                a.setStyleSheet(f"color:{LEVEL_COLORS[ov['band'].code[:2]]};")
            b = QLabel(label)
            b.setObjectName("hint")
            v.addWidget(a)
            v.addWidget(b)
            lay.addWidget(f)
        return lay

    def ready_box(self, res, progress):
        items = A.readiness(res, progress)
        todo = sum(1 for s, _ in items if s == "todo")
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        head = QLabel("<b>Ready to print ✔</b>" if not todo else
                      f"<b>{todo} thing{'s' if todo > 1 else ''} to do before printing</b>")
        head.setStyleSheet(f"color:{'#2E7D32' if not todo else '#B00020'}; font-size:11pt;")
        v.addWidget(head)
        for state, text in items:
            sym, color = STATE[state]
            lab = QLabel(f"<span style='color:{color}; font-weight:bold'>{sym}</span>&nbsp; {text}")
            lab.setObjectName("plain")
            lab.setWordWrap(True)
            v.addWidget(lab)
        v.addStretch(1)
        return _box("Ready to print?", w)

    def progress_box(self, progress):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setVerticalSpacing(3)
        for i, x in enumerate(progress["papers"]):
            g.addWidget(QLabel(x["paper"]["code"] or x["paper"]["name"]), i, 0)
            bar = QProgressBar()
            bar.setRange(0, max(x["total"], 1))
            bar.setValue(x["entered"])
            bar.setFormat(f"{x['entered']} / {x['total']}")
            bar.setFixedHeight(16)
            done = x["entered"] == x["total"]
            bar.setStyleSheet("QProgressBar{border:1px solid #D5D9E2;border-radius:3px;"
                              "background:white;text-align:center;font-size:8pt;}"
                              f"QProgressBar::chunk{{background:{'#7CC08A' if done else '#E9B949'};}}")
            g.addWidget(bar, i, 1)
        parts = [w]
        miss = progress["missing"]
        if miss:
            lines = []
            for m in miss[:12]:
                what = "no marks at all" if m["none"] else \
                    "missing " + ", ".join(p["code"] or p["name"] for p in m["papers"])
                lines.append(f"• {m['learner']['name']} — {what}")
            if len(miss) > 12:
                lines.append(f"… and {len(miss) - 12} more")
            parts.append(_note(f"<b>{len(miss)} learner{'s' if len(miss) > 1 else ''} with "
                               "missing marks:</b><br>" + "<br>".join(lines)))
        else:
            parts.append(_note("<b>Every learner has every mark.</b>"))
        return _box("Marks entry progress", *parts)

    def support_box(self, res, prev):
        rows = A.support_list(res, prev)
        if not rows:
            return _box("Learners needing support",
                        _note("No learner is at AE/BE overall" +
                              (" or dropped a level since the last assessment." if prev else ".")))
        cells = []
        for x in rows:
            lv = x["level"]
            cells.append([_item(x["learner"]["name"]),
                          _item(lv, center=True, bold=True, bg=GROUP_BG[lv[:2]]),
                          _item(x["before"] or "-", center=True),
                          _item(x["reason"]),
                          _item(", ".join(x["weak"]))])
        t = _table(["Learner", "Level now", "Before", "Why listed", "Weakest learning areas"],
                   cells, stretch=4)
        return _box(f"Learners needing support ({len(rows)}) — alphabetical", t,
                    _note("Listed if the overall level is AE or BE, or dropped since the previous "
                          "assessment. Consider these for remarks, parent meetings and remedial "
                          "work."))

    def levels_box(self, res):
        overall, per_area = A.level_distribution(res)
        whole = StackedBars(label_width=150, percent=True)
        whole.set_rows([("Whole class", overall)])
        areas = StackedBars(label_width=150)
        areas.set_rows([(s["code"] or s["name"], groups) for s, groups in per_area])
        summary = " · ".join(f"{g}: {overall[g]}" for g in G.GROUPS)
        return _box("Level distribution", whole, _note(f"Overall levels — {summary}"), areas)

    def points_box(self, pts):
        bars = SimpleBars(color="#4A7FC1", label_width=70)
        bars.set_rows(pts["buckets"])
        return _box("Points summary",
                    _note(f"Average total points: <b>{pts['mean']:.1f}</b> out of {pts['max']}. "
                          "Number of learners in each points range:"), bars)

    def change_box(self, res, prev):
        ch = A.change(res, prev)
        if ch is None:
            return _box("Change since previous assessment",
                        _note("This is the first assessment with marks for this class — "
                              "nothing to compare with yet."))
        cells = []
        for x in ch["areas"]:
            d = x["delta"]
            if d is None:
                arrow, color = "-", None
            elif abs(d) < 0.05:
                arrow, color = "= 0.0", "#5A6474"
            else:
                arrow, color = (f"▲ +{d:.1f}", "#2E7D32") if d > 0 else (f"▼ {d:.1f}", "#B00020")
            cells.append([_item(x["subject"]["name"]), _item(_pct(x["before"]), center=True),
                          _item(_pct(x["now"]), center=True),
                          _item(arrow, center=True, bold=True, fg=color)])
        d = (ch["overall_now"] or 0) - (ch["overall_before"] or 0)
        cells.append([_item("Whole class", bold=True), _item(_pct(ch["overall_before"]), center=True),
                      _item(_pct(ch["overall_now"]), center=True, bold=True),
                      _item(f"{'▲ +' if d >= 0 else '▼ '}{d:.1f}", center=True, bold=True,
                            fg="#2E7D32" if d >= 0 else "#B00020")])
        t = _table(["Learning area", "Before", "Now", "Change"], cells)
        moved = QLabel(f"<span style='color:#2E7D32'><b>▲ {ch['up']}</b> moved up a level</span>"
                       f" &nbsp;·&nbsp; <b>= {ch['same']}</b> same level &nbsp;·&nbsp; "
                       f"<span style='color:#B00020'><b>▼ {ch['down']}</b> dropped a level</span>")
        return _box(f"Change since {ch['prev_name']}", moved, t)

    def strong_weak_box(self, res):
        strong, weak = A.strongest_weakest(res)
        lines = ["<b>Strongest:</b> " + ", ".join(f"{s['subject']['name']} ({s['mean_pct']:.0f}%, "
                                                   f"{s['band'].code})" for s in strong)]
        if weak:
            lines.append("<b>Weakest:</b> " + ", ".join(f"{s['subject']['name']} "
                                                        f"({s['mean_pct']:.0f}%, {s['band'].code})"
                                                        for s in weak))
        lab = QLabel("<br>".join(lines))
        lab.setWordWrap(True)
        return _box("Strongest & weakest learning areas (class mean)", lab)

    def gender_box(self, res):
        rows = A.gender_stats(res)
        if not rows or (len(rows) == 1 and rows[0]["label"] == "Not recorded"):
            return _box("Girls & boys", _note("Gender is not recorded for these learners. Add it "
                                              "on the Learners page (or in the learners template)."))
        cells = []
        for x in rows:
            cells.append([_item(x["label"], bold=True), _item(x["n"], center=True),
                          _item(_pct(x["mean"]), center=True),
                          _item(x["band"].code, center=True, bold=True,
                                bg=GROUP_BG[x["band"].code[:2]]),
                          _item(f"{x['points']:.1f}", center=True)]
                         + [_item(x["groups"][g], center=True) for g in G.GROUPS])
        return _box("Girls & boys", _table(["", "Learners", "Mean", "Level", "Avg points"]
                                           + G.GROUPS, cells))

    def trend_box(self, res, cid, aid):
        data = A.trend(self.db, cid, aid)
        chart = LineChart()
        pick = QComboBox()
        pick.addItem("Whole class only", None)
        for s in res.subjects:
            pick.addItem(s["name"], s["id"])
        if self.trend_choice is not None:
            pick.setCurrentIndex(max(pick.findData(self.trend_choice), 0))

        def draw():
            sid = pick.currentData()
            self.trend_choice = sid
            series = [("Whole class", [d["overall"] for d in data], "#1F3C88")]
            if sid is not None:
                series.append((pick.currentText(), [d["areas"].get(sid) for d in data],
                               "#E0703B"))
            chart.set_data([d["label"] for d in data], series)

        pick.currentIndexChanged.connect(draw)
        draw()
        top = QHBoxLayout()
        top.addWidget(QLabel("Also show:"))
        top.addWidget(pick)
        top.addWidget(_note("Blue = whole-class mean, orange = chosen learning area. "
                            "Coloured bands show the EE / ME / AE / BE ranges."), 1)
        return _box("Trend across assessments (class mean %)", top, chart)

    def analysis_box(self, res):
        cells = []
        for st in res.subject_stats():
            code = st["band"].code if st["band"] else ""
            cells.append([_item(st["subject"]["name"]), _item(st["sat"], center=True),
                          _item(_pct(st["mean_pct"]), center=True),
                          _item(code, center=True, bold=True, bg=GROUP_BG.get(code[:2]))]
                         + [_item(st["groups"][g], center=True, bold=True, bg=GROUP_BG[g])
                            for g in G.GROUPS]
                         + [_item(st["counts"][c], center=True) for c in G.CODES])
        return _box("Learning area analysis",
                    _table(["Learning area", "Sat", "Mean", "Level"] + G.GROUPS + G.CODES, cells))
