"""Export windows: learner picker, class mark sheet options, report printing, remarks editor."""
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
                               QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QRadioButton, QVBoxLayout)

from . import excel_io as X
from . import grading as G
from . import pdf_reports as R
from .compute import PER_SUBJECT, SHEET_DEFAULTS, SHEET_PRESETS, SUMMARY_KEYS, TOTAL_KEYS
from .paths import safe_filename, sub_dir

GROUP_COLORS = {"EE": "#D8F0DC", "ME": "#DDEBF7", "AE": "#FFF2C4", "BE": "#FAD4D4"}
CHARACTER_CHOICES = ["", "Excellent", "Very good", "Good", "Fair", "Needs improvement"]


def _fit(dlg, parent, w, h):
    scr = (parent.screen() if parent else QApplication.primaryScreen()).availableGeometry()
    dlg.resize(min(w, int(scr.width() * 0.92)), min(h, int(scr.height() * 0.88)))


def _open(path):
    try:
        os.startfile(path)
    except OSError:
        pass


def _write(parent, fn):
    """Run a file-writing function; explain instead of crashing if the file is open."""
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        fn()
        return True
    except PermissionError:
        QApplication.restoreOverrideCursor()
        QMessageBox.warning(parent, "File is open", "Could not save — the file is open in "
                            "another program (Excel or a PDF viewer). Close it and try again.")
        return False
    finally:
        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()


# ---------------------------------------------------------------------------
class LearnerPicker(QGroupBox):
    """Tick the learners to include. Quick picks: all, none, with marks, by overall level."""

    def __init__(self, rows, preselect=None, title="Learners"):
        super().__init__(title)
        self.rows = rows
        lay = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name or adm no…")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        quick = QGridLayout()
        for i, (text, fn) in enumerate([("All", lambda: self._set(lambda r: True)),
                                        ("None", lambda: self._set(lambda r: False)),
                                        ("With marks", lambda: self._set(lambda r: r["has_marks"])),
                                        ("Invert", self._invert)]):
            b = QPushButton(text)
            b.clicked.connect(fn)
            quick.addWidget(b, 0, i)
        for i, g in enumerate(G.GROUPS):
            b = QPushButton(f"Only {g}")
            b.setToolTip(f"Tick only learners whose overall level is {g}1 or {g}2")
            b.setStyleSheet(f"background:{GROUP_COLORS[g]};")
            b.clicked.connect(lambda _=False, g=g: self._set(
                lambda r: bool(r["band"]) and r["band"].code.startswith(g)))
            quick.addWidget(b, 1, i)
        lay.addLayout(quick)
        self.list = QListWidget()
        self.list.itemChanged.connect(self._count)
        lay.addWidget(self.list, 1)
        self.count = QLabel()
        self.count.setObjectName("hint")
        lay.addWidget(self.count)
        self.list.blockSignals(True)
        for r in rows:
            L = r["learner"]
            lvl = r["band"].code if r["band"] else "no marks"
            it = QListWidgetItem(f"{L['adm_no'] or '-':>5}   {L['name']}   ({lvl})")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            on = r["has_marks"] if preselect is None else L["id"] in preselect
            it.setCheckState(Qt.Checked if on else Qt.Unchecked)
            if r["band"]:
                it.setBackground(QBrush(QColor(GROUP_COLORS[r["band"].code[:2]]).lighter(108)))
            self.list.addItem(it)
        self.list.blockSignals(False)
        self._count()

    def _set(self, pred):
        self.list.blockSignals(True)
        for i, r in enumerate(self.rows):
            if not self.list.item(i).isHidden():
                self.list.item(i).setCheckState(Qt.Checked if pred(r) else Qt.Unchecked)
        self.list.blockSignals(False)
        self._count()

    def _invert(self):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            it = self.list.item(i)
            if not it.isHidden():
                it.setCheckState(Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked)
        self.list.blockSignals(False)
        self._count()

    def _filter(self, text):
        t = text.strip().upper()
        for i, r in enumerate(self.rows):
            L = r["learner"]
            self.list.item(i).setHidden(bool(t) and t not in L["name"].upper()
                                        and t not in (L["adm_no"] or "").upper())

    def _count(self, *_):
        self.count.setText(f"{len(self.selected_ids())} of {len(self.rows)} learners ticked")

    def selected_ids(self):
        return {r["learner"]["id"] for i, r in enumerate(self.rows)
                if self.list.item(i).checkState() == Qt.Checked}


# ---------------------------------------------------------------------------
class MarkSheetDialog(QDialog):
    """Class mark sheet with filters: learners, learning areas, columns, summary rows, paper."""

    LABELS = {
        "marks": "Marks (each paper)", "pct": "%", "points": "Points", "level": "Level",
        "total": "Total marks", "outof": "Out of", "gtotal": "G. Total (sum of %)",
        "avg": "Average %", "tpoints": "Total points", "olevel": "Overall level",
        "counts": "Level counts (EE1 … BE2)", "groups": "EE / ME / AE / BE totals",
        "sat": "Number who sat", "totals_row": "TOTAL row", "mean_row": "MEAN SCORE row",
    }

    def __init__(self, parent, db, res):
        super().__init__(parent)
        self.db, self.res = db, res
        a = res.assessment
        self.setWindowTitle(f"Class mark sheet — {res.klass['name']}, Term {a['term']} "
                            f"{a['name']} {a['year']}")
        try:
            saved = json.loads(db.settings().get("mark_sheet_options") or "{}")
        except ValueError:
            saved = {}
        o = {**SHEET_DEFAULTS, **saved}
        root = QHBoxLayout(self)
        self.picker = LearnerPicker(res.rows)
        root.addWidget(self.picker, 4)

        right = QVBoxLayout()
        root.addLayout(right, 6)
        pr = QHBoxLayout()
        pr.addWidget(QLabel("<b>Preset:</b>"))
        self.preset = QComboBox()
        self.preset.addItem("— choose —")
        self.preset.addItems(list(SHEET_PRESETS))
        self.preset.activated.connect(self.apply_preset)
        pr.addWidget(self.preset, 1)
        right.addLayout(pr)

        self.checks = {}
        subj = QGroupBox("Learning areas")
        sl = QGridLayout(subj)
        self.subject_checks = {}
        chosen = set(saved.get("subjects_codes") or [])
        for i, s in enumerate(res.sheet_subjects):
            cb = QCheckBox(s["code"] or s["name"])
            cb.setToolTip(s["name"])
            cb.setChecked(not chosen or (s["code"] or s["name"]) in chosen)
            self.subject_checks[s["id"]] = cb
            sl.addWidget(cb, i // 5, i % 5)
        row = QHBoxLayout()
        for text, val in (("All", True), ("None", False)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, v=val: [c.setChecked(v)
                                                      for c in self.subject_checks.values()])
            row.addWidget(b)
        row.addStretch(1)
        sl.addLayout(row, 2, 0, 1, 5)
        right.addWidget(subj)

        for title, keys in (("For each learning area show", PER_SUBJECT),
                            ("Totals (always over all learning areas)", TOTAL_KEYS),
                            ("Summary rows at the bottom", SUMMARY_KEYS)):
            g = QGroupBox(title)
            gl = QGridLayout(g)
            for i, k in enumerate(keys):
                cb = QCheckBox(self.LABELS[k])
                cb.setChecked(bool(o[k]))
                self.checks[k] = cb
                gl.addWidget(cb, i // 3, i % 3)
            right.addWidget(g)

        other = QGroupBox("Other")
        ol = QFormLayout(other)
        srt = QHBoxLayout()
        self.sort_adm = QRadioButton("Adm No")
        self.sort_name = QRadioButton("Name (A–Z)")
        bg = QButtonGroup(self)
        bg.addButton(self.sort_adm)
        bg.addButton(self.sort_name)
        (self.sort_name if o["sort"] == "name" else self.sort_adm).setChecked(True)
        srt.addWidget(self.sort_adm)
        srt.addWidget(self.sort_name)
        srt.addStretch(1)
        ol.addRow("Order learners by:", srt)
        self.analysis = QCheckBox("Add the subject analysis sheet / page")
        self.analysis.setChecked(bool(o["analysis"]))
        ol.addRow("", self.analysis)
        self.paper = QComboBox()
        self.paper.addItems(list(R.PAGES))
        self.paper.setCurrentText(saved.get("paper", "A4 landscape"))
        ol.addRow("PDF paper:", self.paper)
        right.addWidget(other)
        right.addStretch(1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        for text, fn, primary in (("Export Excel", self.export_xlsx, False),
                                  ("Export PDF", self.export_pdf, True)):
            b = QPushButton(text)
            if primary:
                b.setObjectName("primary")
            b.clicked.connect(fn)
            btns.addWidget(b)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        btns.addWidget(close)
        right.addLayout(btns)
        _fit(self, parent, 1150, 760)

    def apply_preset(self, i):
        name = self.preset.itemText(i)
        if name in SHEET_PRESETS:
            for k, cb in self.checks.items():
                cb.setChecked(bool(SHEET_PRESETS[name][k]))

    def options(self):
        o = {k: cb.isChecked() for k, cb in self.checks.items()}
        o["sort"] = "name" if self.sort_name.isChecked() else "adm"
        o["analysis"] = self.analysis.isChecked()
        o["subjects"] = {sid for sid, cb in self.subject_checks.items() if cb.isChecked()}
        o["learners"] = self.picker.selected_ids()
        return o

    def _ready(self):
        o = self.options()
        if not o["learners"]:
            QMessageBox.information(self, "No learners", "Tick at least one learner.")
            return None
        has_cols = (o["subjects"] and any(o[k] for k in PER_SUBJECT)) or \
            any(o[k] for k in TOTAL_KEYS)
        if not has_cols:
            QMessageBox.information(self, "Nothing to show",
                                    "Choose at least one learning area column or total.")
            return None
        remember = {k: v for k, v in o.items() if k not in ("learners", "subjects")}
        remember["paper"] = self.paper.currentText()
        remember["subjects_codes"] = [s["code"] or s["name"] for s in self.res.sheet_subjects
                                      if s["id"] in o["subjects"]]
        self.db.set_setting("mark_sheet_options", json.dumps(remember))
        return o

    def _path(self, ext):
        a = self.res.assessment
        name = safe_filename(f"Mark Sheet - {self.res.klass['name']} - Term {a['term']} "
                             f"{a['name']} {a['year']}.{ext}")
        path, _ = QFileDialog.getSaveFileName(self, "Save mark sheet",
                                              os.path.join(sub_dir("Reports"), name),
                                              f"{ext.upper()} (*.{ext})")
        return path

    def export_xlsx(self):
        o = self._ready()
        if o is not None and (path := self._path("xlsx")):
            if _write(self, lambda: X.export_mark_sheet(path, self.res, o)):
                _open(path)

    def export_pdf(self):
        o = self._ready()
        if o is not None and (path := self._path("pdf")):
            if _write(self, lambda: R.mark_sheet(path, self.res, o, self.paper.currentText())):
                _open(path)


# ---------------------------------------------------------------------------
class ReportPrintDialog(QDialog):
    """Pick learners for Individual Assessment Reports; marks on/off switch."""

    def __init__(self, parent, db, res, preselect=None):
        super().__init__(parent)
        self.db, self.res, self.path, self.count = db, res, None, 0
        self.setWindowTitle("Print Individual Assessment Reports")
        lay = QVBoxLayout(self)
        what = (" & ".join(n.title() for n in res.names()) if res.combined
                else res.assessment["name"])
        lay.addWidget(QLabel(f"<b>{res.klass['name']}</b> — {what}, "
                             f"Term {res.assessment['term']} {res.assessment['year']}"))
        self.picker = LearnerPicker(res.rows, preselect, "Learners to print")
        lay.addWidget(self.picker, 1)
        self.marks = QCheckBox("Show marks on the report (otherwise points and levels only)")
        self.marks.setChecked(db.settings().get("report_show_marks") == "1")
        lay.addWidget(self.marks)
        btns = QHBoxLayout()
        btns.addStretch(1)
        go = QPushButton("Generate PDF")
        go.setObjectName("primary")
        go.clicked.connect(self.generate)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(go)
        btns.addWidget(cancel)
        lay.addLayout(btns)
        _fit(self, parent, 560, 720)

    def generate(self):
        ids = self.picker.selected_ids()
        if not ids:
            QMessageBox.information(self, "No learners", "Tick at least one learner.")
            return
        self.db.set_setting("report_show_marks", "1" if self.marks.isChecked() else "0")
        self.res.settings["report_show_marks"] = "1" if self.marks.isChecked() else "0"
        a, res = self.res.assessment, self.res
        exams = " & ".join(n.title() for n in res.names()) if res.combined else a["name"]
        name = safe_filename(f"Individual Assessment Reports - {res.klass['name']} - Term "
                             f"{a['term']} {exams} {a['year']}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Save", os.path.join(sub_dir("Reports"), name),
                                              "PDF (*.pdf)")
        if not path:
            return
        out = {}
        if not _write(self, lambda: out.setdefault("n", R.report_forms(path, res, ids))):
            return
        if not out.get("n"):
            QMessageBox.information(self, "Nothing to print",
                                    "None of the ticked learners have marks for these exams.")
            return
        self.path, self.count = path, out["n"]
        _open(path)
        self.accept()


# ---------------------------------------------------------------------------
class RemarksDialog(QDialog):
    """Edit one learner's remarks at a time, with Previous / Next through the class."""

    FIELDS = ("ct_remark", "ht_remark", "discipline", "attention")

    def __init__(self, parent, db, res, index):
        super().__init__(parent)
        self.db, self.res = db, res
        self.rows = [r for r in res.rows if r["has_marks"]]
        lids = [r["learner"]["id"] for r in self.rows]
        target = res.rows[index]["learner"]["id"] if 0 <= index < len(res.rows) else None
        self.i = lids.index(target) if target in lids else 0
        self.aid = res.assessment["id"]
        self.setWindowTitle("Edit remarks")
        lay = QVBoxLayout(self)
        self.head = QLabel()
        self.head.setTextFormat(Qt.RichText)
        lay.addWidget(self.head)
        self.ct = QPlainTextEdit()
        self.ht = QPlainTextEdit()
        self.auto_ct, self.auto_ht = QLabel(), QLabel()
        for title, edit, auto, key in (("Class teacher's general remarks", self.ct, self.auto_ct, "ct"),
                                       ("Head teacher's remarks", self.ht, self.auto_ht, "ht")):
            g = QGroupBox(title)
            gl = QVBoxLayout(g)
            edit.setFixedHeight(76 if key == "ct" else 52)
            gl.addWidget(edit)
            row = QHBoxLayout()
            auto.setWordWrap(True)
            auto.setObjectName("hint")
            row.addWidget(auto, 1)
            b = QPushButton("Use automatic")
            b.clicked.connect(lambda _=False, k=key: self.use_auto(k))
            row.addWidget(b)
            gl.addLayout(row)
            lay.addWidget(g)
        ch = QGroupBox("Learner's character")
        cf = QFormLayout(ch)
        self.discipline = QComboBox()
        self.attention = QComboBox()
        for cb in (self.discipline, self.attention):
            cb.setEditable(True)
            cb.addItems(CHARACTER_CHOICES)
        cf.addRow("Discipline:", self.discipline)
        cf.addRow("Class attention and seriousness:", self.attention)
        lay.addWidget(ch)
        nav = QHBoxLayout()
        self.prev = QPushButton("◀ Previous")
        self.prev.clicked.connect(lambda: self.go(-1))
        self.next = QPushButton("Next ▶")
        self.next.clicked.connect(lambda: self.go(1))
        self.pos = QLabel()
        nav.addWidget(self.prev)
        nav.addWidget(self.next)
        nav.addWidget(self.pos)
        nav.addStretch(1)
        done = QPushButton("Save && close")
        done.setObjectName("primary")
        done.clicked.connect(self.finish)
        cancel = QPushButton("Close without saving")
        cancel.clicked.connect(self.reject)
        nav.addWidget(done)
        nav.addWidget(cancel)
        lay.addLayout(nav)
        _fit(self, parent, 720, 640)
        if self.rows:
            self.load()
        else:  # nobody has marks yet, so there is nothing to write remarks about
            for wdg in (self.ct, self.ht, self.discipline, self.attention, done, self.prev,
                        self.next):
                wdg.setEnabled(False)
            self.head.setText("No learner has marks for these exams yet.")

    def load(self):
        r = self.rows[self.i]
        L = r["learner"]
        self.head.setText(f"<span style='font-size:13pt'><b>{L['name']}</b></span> &nbsp; "
                          f"Adm {L['adm_no'] or '-'} &nbsp;·&nbsp; Level <b>{r['band'].code}</b>"
                          f" &nbsp;·&nbsp; {r['points']}/{r['max_points']} points")
        self.ct.setPlainText(r["ct_remark"])
        self.ht.setPlainText(r["ht_remark"])
        self.auto_ct.setText(f"Automatic: {r['auto_ct']}")
        self.auto_ht.setText(f"Automatic: {r['auto_ht']}")
        self.discipline.setCurrentText(r["discipline"])
        self.attention.setCurrentText(r["attention"])
        self.prev.setEnabled(self.i > 0)
        self.next.setEnabled(self.i < len(self.rows) - 1)
        self.pos.setText(f"{self.i + 1} of {len(self.rows)}")

    def use_auto(self, key):
        r = self.rows[self.i]
        (self.ct if key == "ct" else self.ht).setPlainText(r["auto_" + key])

    def save(self):
        r = self.rows[self.i]
        lid = r["learner"]["id"]
        vals = {"ct_remark": self.ct.toPlainText().strip(),
                "ht_remark": self.ht.toPlainText().strip(),
                "discipline": self.discipline.currentText().strip(),
                "attention": self.attention.currentText().strip()}
        auto = {"ct_remark": r["auto_ct"], "ht_remark": r["auto_ht"]}
        default = {"discipline": self.res.settings.get("default_discipline", ""),
                   "attention": self.res.settings.get("default_attention", "")}
        for f, v in vals.items():
            same = v == auto.get(f, default.get(f, ""))
            self.db.set_note(self.aid, lid, f, None if same else v)
            r[f] = v or auto.get(f, default.get(f, ""))
        r["ct_custom"] = vals["ct_remark"] not in ("", r["auto_ct"])
        r["ht_custom"] = vals["ht_remark"] not in ("", r["auto_ht"])

    def go(self, step):
        self.save()
        self.i += step
        self.load()

    def finish(self):
        self.save()
        self.accept()
