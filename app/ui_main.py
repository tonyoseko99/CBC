"""Main window and pages."""
import datetime
import os
import shutil

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemDelegate, QAbstractItemView, QCheckBox, QComboBox, QFileDialog,
                               QFormLayout, QFrame, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget, QApplication)

from . import grading as G
from .compute import CombinedResults, Results
from .paths import data_dir, resource, safe_filename, sub_dir
from . import auth
from .ui_auth import ChangePinDialog, RegisterDialog, confirm_pin, sign_in
from . import templates as T
from .ui_dashboard import DashboardPage
from .ui_exports import MarkSheetDialog, RemarksDialog, ReportPrintDialog
from .ui_dialogs import (AssessmentDialog, ClassDialog, LearnerDialog, UploadDialog,
                         NameCodeDialog)

GROUP_COLORS = {"EE": "#D8F0DC", "ME": "#DDEBF7", "AE": "#FFF2C4", "BE": "#FAD4D4"}


def item(text, editable=False, center=False, bold=False, bg=None):
    it = QTableWidgetItem("" if text is None else str(text))
    if not editable:
        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    if center:
        it.setTextAlignment(Qt.AlignCenter)
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if bg:
        it.setBackground(QBrush(QColor(bg)))
    return it


def grade_item(code):
    return item(code or "", center=True, bold=True,
                bg=GROUP_COLORS.get((code or "")[:2]))


def button(text, slot, primary=False):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    b.clicked.connect(slot)
    return b


def page_title(text, sub=None):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 6)
    t = QLabel(text)
    t.setObjectName("pageTitle")
    v.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setObjectName("hint")
        s.setWordWrap(True)
        v.addWidget(s)
    return w


def save_guard(parent, fn):
    """Run a file-writing function; explain instead of crashing if the file is open in Excel."""
    try:
        fn()
        return True
    except PermissionError:
        QMessageBox.warning(parent, "File is open", "Could not save — the file is open in Excel. "
                            "Close it and try again.")
        return False


def open_path(path):
    try:
        os.startfile(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
class Page(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.db = main.db

    @property
    def cid(self):
        return self.main.class_id

    @property
    def aid(self):
        return self.main.assessment_id

    def need(self, assessment=False):
        if not self.cid:
            QMessageBox.information(self, "No class", "Create a class first (top bar → New class).")
            return False
        if assessment and not self.aid:
            QMessageBox.information(self, "No assessment",
                                    "Create an assessment first (top bar → New assessment).")
            return False
        return True

    def refresh(self):
        pass


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
class LearnersPage(Page):
    def __init__(self, main):
        super().__init__(main)
        lay = QVBoxLayout(self)
        lay.addWidget(page_title("Learners", "Add learners one by one or import the class list "
                                             "from Excel. Double-click a learner to edit."))
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search name or adm no…")
        self.search.textChanged.connect(self.filter)
        bar.addWidget(self.search, 1)
        bar.addWidget(button("+ Add learner", self.add, True))
        bar.addWidget(button("Download template", self.download_template))
        bar.addWidget(button("Upload template…", self.upload))
        bar.addWidget(button("Delete", self.delete))
        lay.addLayout(bar)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Adm No", "Name", "Gender"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self.edit)
        lay.addWidget(self.table, 1)
        self.count = QLabel()
        self.count.setObjectName("hint")
        lay.addWidget(self.count)
        self.learners = []

    def refresh(self):
        self.learners = self.db.learners(self.cid) if self.cid else []
        self.table.setRowCount(len(self.learners))
        for r, L in enumerate(self.learners):
            self.table.setItem(r, 0, item(r + 1, center=True))
            self.table.setItem(r, 1, item(L["adm_no"], center=True))
            self.table.setItem(r, 2, item(L["name"]))
            self.table.setItem(r, 3, item(L["gender"], center=True))
        self.table.resizeColumnToContents(0)
        self.count.setText(f"{len(self.learners)} learners")
        self.filter(self.search.text())

    def filter(self, text):
        t = text.strip().upper()
        for r, L in enumerate(self.learners):
            self.table.setRowHidden(r, bool(t) and t not in L["name"].upper()
                                    and t not in (L["adm_no"] or "").upper())

    def selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.learners[r] for r in rows]

    def add(self):
        if self.need():
            LearnerDialog(self, self.db, self.cid).exec()
            self.main.refresh_all()

    def edit(self):
        sel = self.selected()
        if sel and LearnerDialog(self, self.db, self.cid, sel[0]).exec():
            self.main.refresh_all()

    def delete(self):
        sel = self.selected()
        if not sel:
            return
        names = ", ".join(L["name"] for L in sel[:5]) + ("…" if len(sel) > 5 else "")
        if QMessageBox.question(self, "Delete learners",
                                f"Delete {len(sel)} learner(s) and all their marks?\n{names}"
                                ) == QMessageBox.Yes:
            for L in sel:
                self.db.delete_learner(L["id"])
            self.main.refresh_all()

    def upload(self):
        if self.need() and UploadDialog(self, self.db, self.cid, "learners",
                                        self.download_template).exec():
            self.main.refresh_all()

    def download_template(self):
        """Learners template, pre-filled with the current list (edit rows to correct them)."""
        if not self.need():
            return
        k = self.db.get_class(self.cid)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save learners template",
            os.path.join(sub_dir("Templates"), safe_filename(f"Learners template - {k['name']}.xlsx")),
            "Excel (*.xlsx)")
        if path and save_guard(self, lambda: T.write_learners_template(
                path, k, self.db.learners(self.cid))):
            open_path(path)


# ---------------------------------------------------------------------------
class MarksTable(QTableWidget):
    """Enter moves down a row (like typing marks down a column in Excel)."""

    def closeEditor(self, editor, hint):
        if hint == QAbstractItemDelegate.SubmitModelCache:
            super().closeEditor(editor, QAbstractItemDelegate.NoHint)
            r, c = self.currentRow(), self.currentColumn()
            nxt = r + 1
            while nxt < self.rowCount() and self.isRowHidden(nxt):
                nxt += 1
            if nxt < self.rowCount():
                self.setCurrentCell(nxt, c)
        else:
            super().closeEditor(editor, hint)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.state() != self.State.EditingState:
            for it in self.selectedItems():
                if it.flags() & Qt.ItemIsEditable:
                    it.setText("")
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.state() != self.State.EditingState:
            r = self.currentRow() + 1
            if r < self.rowCount():
                self.setCurrentCell(r, self.currentColumn())
            return
        super().keyPressEvent(e)


class MarksPage(Page):
    FIXED = 2  # Adm, Name

    def __init__(self, main):
        super().__init__(main)
        lay = QVBoxLayout(self)
        lay.addWidget(page_title(
            "Marks entry",
            "Type marks straight into the grid — Enter moves down, Tab moves right. Marks save "
            "automatically. A blank cell counts as 0 once the learner has any mark."))
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Show:"))
        self.filter = QComboBox()
        self.filter.currentIndexChanged.connect(self.apply_filter)
        bar.addWidget(self.filter)
        bar.addStretch(1)
        bar.addWidget(button("Out-of values…", self.edit_assessment))
        bar.addWidget(button("Download template", self.download_template))
        bar.addWidget(button("Upload template…", self.upload))
        lay.addLayout(bar)
        self.table = MarksTable()
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.AnyKeyPressed |
                                   QAbstractItemView.DoubleClicked |
                                   QAbstractItemView.EditKeyPressed)
        self.table.itemChanged.connect(self.changed)
        lay.addWidget(self.table, 1)
        self.status = QLabel()
        self.status.setObjectName("hint")
        lay.addWidget(self.status)
        self.res = None
        self.papers = []
        self.loading = False

    def refresh(self):
        self.loading = True
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        if not (self.cid and self.aid):
            self.status.setText("Select or create a class and an assessment first.")
            self.loading = False
            return
        res = self.res = Results(self.db, self.cid, self.aid)
        self.papers = [(s, p) for s in res.sheet_subjects for p in s["papers"]]
        heads = ["Adm", "Name"] + [f"{p['code'] or p['name']}\n/{G.fmt(float(res.out_of[p['id']]))}"
                                   for s, p in self.papers] + ["Total", "Avg %", "Points", "Level"]
        self.table.setColumnCount(len(heads))
        self.table.setHorizontalHeaderLabels(heads)
        for i, (s, p) in enumerate(self.papers):
            self.table.horizontalHeaderItem(self.FIXED + i).setToolTip(f"{s['name']} — {p['name']}")
        self.table.setRowCount(len(res.rows))
        for r, row in enumerate(res.rows):
            L = row["learner"]
            self.table.setItem(r, 0, item(L["adm_no"], center=True))
            self.table.setItem(r, 1, item(L["name"]))
            for i, (s, p) in enumerate(self.papers):
                v = row["papers"].get(p["id"])
                self.table.setItem(r, self.FIXED + i,
                                   item(G.fmt(v["mark"]) if v else "", editable=True, center=True))
            self.update_row(r, row)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Fixed)
        for c in range(self.table.columnCount()):
            self.table.setColumnWidth(c, 58)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 210)
        cur = self.filter.currentData()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("All learning areas", None)
        for s in res.sheet_subjects:
            self.filter.addItem(s["name"], s["id"])
        i = self.filter.findData(cur)
        self.filter.setCurrentIndex(max(i, 0))
        self.filter.blockSignals(False)
        self.apply_filter()
        self.status.setText(f"{len(res.rows)} learners · {res.assessment['name']}, "
                            f"Term {res.assessment['term']} {res.assessment['year']}")
        self.loading = False

    def apply_filter(self):
        sid = self.filter.currentData()
        for i, (s, p) in enumerate(self.papers):
            self.table.setColumnHidden(self.FIXED + i, sid is not None and s["id"] != sid)

    def update_row(self, r, row):
        base = self.FIXED + len(self.papers)
        was = self.loading
        self.loading = True
        if row["has_marks"]:
            vals = [G.fmt(row["total"]), f"{row['avg_pct']:.1f}",
                    f"{row['points']}/{row['max_points']}"]
            code = row["band"].code
        else:
            vals, code = ["", "", ""], ""
        for i, v in enumerate(vals):
            self.table.setItem(r, base + i, item(v, center=True))
        self.table.setItem(r, base + 3, grade_item(code))
        self.loading = was

    def changed(self, it):
        if self.loading or it.column() < self.FIXED or it.column() >= self.FIXED + len(self.papers):
            return
        r, c = it.row(), it.column()
        s, p = self.papers[c - self.FIXED]
        L = self.res.rows[r]["learner"]
        key = (L["id"], p["id"])
        old = self.res.marks.get(key)
        text = it.text().strip()
        oo = self.res.out_of[p["id"]]
        try:
            mark = T.to_number(text)
            if mark is not None and not 0 <= mark <= oo:
                raise ValueError
        except ValueError:
            self.status.setText(f"<span style='color:#B00020'>'{text}' is not a valid mark for "
                                f"{p['name']} (0 – {G.fmt(float(oo))}). Restored previous value."
                                f"</span>")
            self.loading = True
            it.setText(G.fmt(old) if old is not None else "")
            self.loading = False
            return
        self.db.set_mark(self.aid, L["id"], p["id"], mark)
        if mark is None:
            self.res.marks.pop(key, None)
        else:
            self.res.marks[key] = mark
        self.loading = True
        it.setText(G.fmt(mark) if mark is not None else "")
        self.loading = False
        row = self.res.learner_result(L)
        self.res.rows[r] = row
        self.update_row(r, row)
        self.status.setText(f"Saved ✓  {L['name']} — {p['name']}: "
                            f"{G.fmt(mark) if mark is not None else '(blank)'}")

    def edit_assessment(self):
        if self.need(True):
            self.main.edit_assessment()

    def upload(self):
        if self.need(True) and UploadDialog(self, self.db, self.cid, "marks",
                                            self.download_template, self.aid).exec():
            self.main.refresh_all()

    def download_template(self):
        """Marks template for the selected assessment (learners and existing marks pre-filled)."""
        if not self.need(True):
            return
        res = Results(self.db, self.cid, self.aid)
        a = res.assessment
        name = safe_filename(f"Marks template - {res.klass['name']} - Term {a['term']} "
                             f"{a['name']} {a['year']}.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Save marks template",
                                              os.path.join(sub_dir("Templates"), name),
                                              "Excel (*.xlsx)")
        if path and save_guard(self, lambda: T.write_marks_template(path, res)):
            open_path(path)


# ---------------------------------------------------------------------------
class ReportsPage(Page):
    COLS = ["Adm", "Name", "Avg %", "Points", "Level", "Class teacher's remarks",
            "Head teacher's remarks", "Discipline", "Class attention"]
    FIELDS = {5: "ct_remark", 6: "ht_remark", 7: "discipline", 8: "attention"}
    SLOTS = 3

    def __init__(self, main):
        super().__init__(main)
        lay = QVBoxLayout(self)
        lay.addWidget(page_title(
            "Reports",
            "Remarks are written automatically from each learner's results. To change them, "
            "double-click a learner (or select one and click 'Edit remarks…'); "
            "'Reset to automatic' undoes your edits."))
        cov = QGroupBox("Assessments on the Individual Assessment Report (up to 3 + average)")
        cv = QVBoxLayout(cov)
        cl = QHBoxLayout()
        self.exam_combos = []
        for i in range(self.SLOTS):
            cl.addWidget(QLabel(f"Exam {i + 1}:"))
            cb = QComboBox()
            cb.setMinimumWidth(230)
            cb.currentIndexChanged.connect(self.coverage_changed)
            cl.addWidget(cb)
            self.exam_combos.append(cb)
        cl.addStretch(1)
        cv.addLayout(cl)
        h = QLabel("Choose 2–3 exams to show each exam with the average (grade, points and "
                   "remarks come from the average), or just one exam for a single report. "
                   "Remarks typed below are saved with the last exam chosen.")
        h.setWordWrap(True)
        h.setObjectName("hint")
        cv.addWidget(h)
        lay.addWidget(cov)
        g = QGroupBox("Generate")
        gl = QHBoxLayout(g)
        gl.addWidget(button("Individual Assessment Reports (PDF)…", self.print_reports, True))
        gl.addWidget(button("Class mark sheet (Excel / PDF)…", self.mark_sheet))
        gl.addStretch(1)
        gl.addWidget(button("Open reports folder", lambda: open_path(sub_dir("Reports"))))
        lay.addWidget(g)
        bar = QHBoxLayout()
        bar.addWidget(button("Edit remarks…", self.edit_remarks, True))
        bar.addWidget(button("Reset selected remarks to automatic", self.reset))
        bar.addWidget(button("Set discipline / attention for all…", self.set_all))
        bar.addStretch(1)
        lay.addLayout(bar)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.doubleClicked.connect(lambda ix: self.edit_remarks(ix.row()))
        hh = self.table.horizontalHeader()
        for c, w in enumerate([50, 180, 55, 55, 50, 360, 240, 100, 100]):
            self.table.setColumnWidth(c, w)
        hh.setSectionResizeMode(5, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        self.rows = []
        self.res = None
        self.ctx = None
        self.loading = False

    # -- which exams the report covers -----------------------------------
    def fill_exam_combos(self):
        """Default: the current assessment plus up to two earlier ones from the same term."""
        ass = sorted(self.db.assessments(self.cid) if self.cid else [],
                     key=lambda a: (a["year"], a["term"], a["id"]))
        cur = self.db.get_assessment(self.aid) if self.aid else None
        same = [a["id"] for a in ass if cur and a["term"] == cur["term"]
                and a["year"] == cur["year"] and a["id"] <= cur["id"]][-self.SLOTS:]
        for i, cb in enumerate(self.exam_combos):
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("— none —", None)
            for a in ass:
                cb.addItem(f"Term {a['term']} {a['year']} — {a['name']}", a["id"])
            cb.setCurrentIndex(max(cb.findData(same[i]), 0) if i < len(same) else 0)
            cb.blockSignals(False)

    def chosen(self):
        ids = []
        for cb in self.exam_combos:
            v = cb.currentData()
            if v and v not in ids:
                ids.append(v)
        return ids

    def coverage_changed(self):
        self.load_table()

    def refresh(self):
        if (self.cid, self.aid) != self.ctx:
            self.ctx = (self.cid, self.aid)
            self.fill_exam_combos()
        self.load_table()

    def load_table(self):
        self.loading = True
        self.table.setRowCount(0)
        self.rows = []
        self.res = None
        ids = self.chosen() if self.cid else []
        if ids:
            self.res = (Results(self.db, self.cid, ids[0]) if len(ids) == 1
                        else CombinedResults(self.db, self.cid, ids))
            self.rows = self.res.rows
        self.table.setRowCount(len(self.rows))
        italic = QFont()
        italic.setItalic(True)
        for r, row in enumerate(self.rows):
            L = row["learner"]
            has = row["has_marks"]
            vals = [L["adm_no"], L["name"], f"{row['avg_pct']:.1f}" if has else "",
                    f"{row['points']}/{row['max_points']}" if has else ""]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, item(v, center=c != 1))
            self.table.setItem(r, 4, grade_item(row["band"].code if has else ""))
            for c, f in self.FIELDS.items():
                it = item(row[f], editable=has)
                if c == 5 and not row["ct_custom"] or c == 6 and not row["ht_custom"]:
                    it.setForeground(QBrush(QColor("#555555")))
                self.table.setItem(r, c, it)
        self.table.resizeRowsToContents()
        self.loading = False

    def reset(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        for r in rows:
            lid = self.rows[r]["learner"]["id"]
            self.db.set_note(self.res.assessment["id"], lid, "ct_remark", None)
            self.db.set_note(self.res.assessment["id"], lid, "ht_remark", None)
        self.load_table()

    def set_all(self):
        from PySide6.QtWidgets import QInputDialog
        if not self.need(True) or not self.res:
            return
        field, ok = QInputDialog.getItem(self, "Set for all learners", "Field:",
                                         ["Discipline", "Class attention and seriousness"], 0, False)
        if not ok:
            return
        value, ok = QInputDialog.getItem(
            self, "Set for all learners", f"{field}:",
            ["Excellent", "Very good", "Good", "Fair", "Needs improvement", ""], 2, True)
        if not ok:
            return
        key = "discipline" if field == "Discipline" else "attention"
        for row in self.rows:
            self.db.set_note(self.res.assessment["id"], row["learner"]["id"], key, value)
        self.load_table()

    def selected_ids(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return {self.rows[r]["learner"]["id"] for r in rows}

    def print_reports(self):
        if not self.need(True):
            return
        if not self.res:
            QMessageBox.information(self, "Choose exams", "Choose at least one exam above.")
            return
        d = ReportPrintDialog(self, self.db, self.res, self.selected_ids() or None)
        if d.exec() and d.count:
            self.main.statusBar().showMessage(
                f"{d.count} Individual Assessment Reports saved to {d.path}", 8000)

    def mark_sheet(self):
        """Class mark sheet for the assessment selected in the top bar, with filters."""
        if self.need(True):
            MarkSheetDialog(self, self.db, Results(self.db, self.cid, self.aid)).exec()

    def edit_remarks(self, row=None):
        if not self.need(True) or not self.res:
            return
        if not any(r["has_marks"] for r in self.rows):
            QMessageBox.information(self, "No marks", "Enter marks first — remarks are "
                                    "written from the results.")
            return
        if row is None or isinstance(row, bool):
            sel = sorted({i.row() for i in self.table.selectedIndexes()})
            row = sel[0] if sel else 0
        RemarksDialog(self, self.db, self.res, row).exec()
        self.load_table()


# ---------------------------------------------------------------------------
class SettingsPage(Page):
    KEYS = [("school_name", "School name"), ("school_subtitle", "Subtitle"),
            ("report_title", "Report title"), ("header_line", "Mark sheet header line"),
            ("head_teacher", "Head teacher's name"),
            ("default_discipline", "Default discipline"),
            ("default_attention", "Default class attention")]

    def __init__(self, main):
        super().__init__(main)
        outer = QVBoxLayout(self)
        outer.addWidget(page_title("Settings"))
        row = QHBoxLayout()
        outer.addLayout(row, 1)

        left = QVBoxLayout()
        g = QGroupBox("School details (printed on reports)")
        f = QFormLayout(g)
        self.edits = {}
        for k, label in self.KEYS:
            e = QLineEdit()
            self.edits[k] = e
            f.addRow(label + ":", e)
        logo_row = QHBoxLayout()
        self.logo = QLabel()
        self.logo.setObjectName("hint")
        logo_row.addWidget(self.logo, 1)
        logo_row.addWidget(button("Choose logo…", self.choose_logo))
        logo_row.addWidget(button("Remove", self.clear_logo))
        f.addRow("School logo:", logo_row)
        f.addRow("", button("Save school details", self.save, True))
        left.addWidget(g)

        ro = QGroupBox("Individual Assessment Report")
        rl = QVBoxLayout(ro)
        self.show_marks = QCheckBox("Show marks on the report (otherwise points and levels only)")
        self.show_marks.toggled.connect(lambda on: (
            self.db.set_setting("report_show_marks", "1" if on else "0"),
            self.main.statusBar().showMessage("Report option saved ✓", 2500)))
        rl.addWidget(self.show_marks)
        left.addWidget(ro)

        b = QGroupBox("Backup")
        bl = QVBoxLayout(b)
        h = QLabel("All data is stored in this one file. Back up regularly to a flash disk "
                   "or email it to yourself.")
        h.setWordWrap(True)
        h.setObjectName("hint")
        bl.addWidget(h)
        self.loc = QLineEdit()
        self.loc.setReadOnly(True)
        bl.addWidget(self.loc)
        br = QHBoxLayout()
        br.addWidget(button("Back up now…", self.backup))
        br.addWidget(button("Restore from backup…", self.restore))
        br.addStretch(1)
        bl.addLayout(br)
        left.addWidget(b)

        ug = QGroupBox(f"Users (maximum {auth.MAX_USERS})")
        ul = QVBoxLayout(ug)
        self.user_list = QLabel()
        self.user_list.setTextFormat(Qt.RichText)
        ul.addWidget(self.user_list)
        ur = QHBoxLayout()
        ur.addWidget(button("Change my PIN…", self.change_pin))
        self.add_user_btn = button("+ Add second user…", self.add_user)
        ur.addWidget(self.add_user_btn)
        self.remove_user_btn = button("Remove other user…", self.remove_user)
        ur.addWidget(self.remove_user_btn)
        ur.addStretch(1)
        ul.addLayout(ur)
        left.addWidget(ug)
        left.addStretch(1)
        row.addLayout(left, 1)

        sg = QGroupBox("Learning areas and papers")
        sl = QVBoxLayout(sg)
        orow = QHBoxLayout()
        orow.addWidget(QLabel("Order shown (▲ ▼ change it):"))
        self.order = QComboBox()
        self.order.addItem("Individual Assessment Report rows", "report")
        self.order.addItem("Mark sheet & marks template columns", "sheet")
        self.order.currentIndexChanged.connect(lambda *_: self.load_tree(self.current()))
        orow.addWidget(self.order, 1)
        sl.addLayout(orow)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Learning area / paper", "Code"])
        self.tree.setColumnWidth(0, 260)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit_node())
        sl.addWidget(self.tree, 1)
        r1 = QHBoxLayout()
        r1.addWidget(button("+ Learning area", self.add_subject))
        r1.addWidget(button("+ Paper", self.add_paper))
        r1.addWidget(button("Edit", self.edit_node))
        r1.addWidget(button("Delete", self.delete_node))
        r1.addWidget(button("▲", lambda: self.move(-1)))
        r1.addWidget(button("▼", lambda: self.move(1)))
        sl.addLayout(r1)
        h = QLabel("A learning area with two papers (e.g. English + Composition) shows each "
                   "paper and a total row on the Individual Assessment Report. Codes are the column "
                   "headings on the marks template (e.g. KISW P2).")
        h.setWordWrap(True)
        h.setObjectName("hint")
        sl.addWidget(h)
        row.addWidget(sg, 1)

    def refresh(self):
        s = self.db.settings()
        for k, e in self.edits.items():
            e.setText(s.get(k, ""))
        self.show_marks.blockSignals(True)
        self.show_marks.setChecked(s.get("report_show_marks") == "1")
        self.show_marks.blockSignals(False)
        self.logo_path = s.get("logo_path", "")
        self.logo.setText(os.path.basename(self.logo_path) if self.logo_path else "(none)")
        self.loc.setText(self.db.path)
        me = self.main.user["id"]
        users = self.db.users()
        self.user_list.setText("<br>".join(
            f"{'<b>' if u['id'] == me else ''}{u['full_name']} ({u['username']})"
            f"{' — signed in</b>' if u['id'] == me else ''}" for u in users))
        self.add_user_btn.setVisible(len(users) < auth.MAX_USERS)
        self.remove_user_btn.setVisible(len(users) > 1)
        self.load_tree()

    def load_tree(self, select=None):
        self.tree.clear()
        for s in self.db.subjects(self.order.currentData()):
            top = QTreeWidgetItem([s["name"], s["code"] or ""])
            top.setData(0, Qt.UserRole, ("subjects", s["id"]))
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            self.tree.addTopLevelItem(top)
            for p in s["papers"]:
                ch = QTreeWidgetItem([p["name"], p["code"] or ""])
                ch.setData(0, Qt.UserRole, ("papers", p["id"]))
                top.addChild(ch)
                if select == ("papers", p["id"]):
                    self.tree.setCurrentItem(ch)
            if select == ("subjects", s["id"]):
                self.tree.setCurrentItem(top)
        self.tree.expandAll()

    def save(self):
        for k, e in self.edits.items():
            self.db.set_setting(k, e.text().strip())
        self.main.statusBar().showMessage("School details saved ✓", 3000)

    def choose_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose logo", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            dest = os.path.join(data_dir(), "logo" + os.path.splitext(path)[1].lower())
            shutil.copyfile(path, dest)
            self.db.set_setting("logo_path", dest)
            self.refresh()

    def clear_logo(self):
        self.db.set_setting("logo_path", "")
        self.refresh()

    def current(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def add_subject(self):
        d = NameCodeDialog(self, "New learning area", label="Total")
        if d.exec():
            sid = self.db.save_subject(None, d.name.text().strip(), d.code.text().strip(),
                                       d.label.text().strip() or "Total")
            self.load_tree(("subjects", sid))
            self.main.refresh_all()

    def add_paper(self):
        cur = self.current()
        if not cur:
            QMessageBox.information(self, "Select", "Select the learning area first.")
            return
        sid = cur[1] if cur[0] == "subjects" else \
            self.db.one("SELECT subject_id FROM papers WHERE id=?", (cur[1],))[0]
        d = NameCodeDialog(self, "New paper")
        if d.exec():
            pid = self.db.save_paper(None, sid, d.name.text().strip(), d.code.text().strip())
            self.load_tree(("papers", pid))
            self.main.refresh_all()

    def edit_node(self):
        cur = self.current()
        if not cur:
            return
        table, rid = cur
        row = self.db.one(f"SELECT * FROM {table} WHERE id=?", (rid,))
        if table == "subjects":
            d = NameCodeDialog(self, "Edit learning area", row["name"], row["code"] or "",
                               row["total_label"] or "Total")
            if d.exec():
                self.db.save_subject(rid, d.name.text().strip(), d.code.text().strip(),
                                     d.label.text().strip() or "Total")
        else:
            d = NameCodeDialog(self, "Edit paper", row["name"], row["code"] or "")
            if d.exec():
                self.db.save_paper(rid, row["subject_id"], d.name.text().strip(),
                                   d.code.text().strip())
        self.load_tree(cur)
        self.main.refresh_all()

    def delete_node(self):
        cur = self.current()
        if not cur:
            return
        table, rid = cur
        if table == "subjects":
            pids = [r[0] for r in self.db.q("SELECT id FROM papers WHERE subject_id=?", (rid,))]
        else:
            pids = [rid]
            if self.db.one("SELECT count(*) FROM papers WHERE subject_id=(SELECT subject_id FROM "
                           "papers WHERE id=?)", (rid,))[0] <= 1:
                QMessageBox.information(self, "Last paper", "A learning area needs at least one "
                                        "paper. Delete the learning area instead.")
                return
        n = self.db.count_marks_for(pids)
        msg = "Delete this item?" + (f"\n\n{n} marks already entered for it will be deleted too."
                                     if n else "")
        if QMessageBox.question(self, "Delete", msg) == QMessageBox.Yes:
            (self.db.delete_subject if table == "subjects" else self.db.delete_paper)(rid)
            self.load_tree()
            self.main.refresh_all()

    def move(self, delta):
        cur = self.current()
        if cur:
            self.db.move(cur[0], cur[1], delta, self.order.currentData())
            self.load_tree(cur)
            self.main.refresh_all()

    def change_pin(self):
        ChangePinDialog(self, self.db, self.main.user["id"]).exec()

    def add_user(self):
        if not auth.can_register(self.db):
            QMessageBox.information(self, "Users", f"Only {auth.MAX_USERS} users are allowed.")
            return
        if not confirm_pin(self, self.db, self.main.user["id"],
                           "Enter YOUR PIN to allow a new user to register:"):
            return
        if RegisterDialog(self, self.db).exec():
            self.refresh()

    def remove_user(self):
        others = [u for u in self.db.users() if u["id"] != self.main.user["id"]]
        if not others:
            return
        o = others[0]
        if QMessageBox.question(self, "Remove user",
                                f"Remove {o['full_name']} ({o['username']})? They will no longer "
                                "be able to sign in. Their classes, learners and marks will be "
                                "moved to your account."
                                ) != QMessageBox.Yes:
            return
        if confirm_pin(self, self.db, self.main.user["id"], "Enter YOUR PIN to confirm:"):
            self.db.delete_user(o["id"], give_classes_to=self.main.user["id"])
            self.main.load_classes()
            self.refresh()

    def backup(self):
        name = f"ClassMark backup {datetime.datetime.now():%Y-%m-%d %H%M}.db"
        path, _ = QFileDialog.getSaveFileName(self, "Save backup",
                                              os.path.join(sub_dir("Backups"), name),
                                              "ClassMark backup (*.db)")
        if path:
            self.db.backup_to(path)
            QMessageBox.information(self, "Backup", f"Backup saved:\n{path}")

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose backup", sub_dir("Backups"),
                                              "ClassMark backup (*.db)")
        if not path:
            return
        if QMessageBox.question(self, "Restore",
                                "Replace ALL current data with this backup?") != QMessageBox.Yes:
            return
        safety = os.path.join(sub_dir("Backups"),
                              f"Before restore {datetime.datetime.now():%Y-%m-%d %H%M%S}.db")
        self.db.backup_to(safety)
        try:
            self.db.restore_from(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Restore failed", f"Not a valid ClassMark backup.\n{e}")
            return
        self.main.class_id = self.main.assessment_id = None
        QMessageBox.information(self, "Restore", "Data restored. Please sign in again "
                                "(users and PINs come from the backup).")
        self.main.lock()


# ---------------------------------------------------------------------------
class IdleWatcher(QObject):
    """Locks the app after a period with no mouse/keyboard activity."""
    EVENTS = {QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel, QEvent.MouseMove}

    def __init__(self, minutes, on_idle):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(minutes * 60_000)
        self.timer.timeout.connect(on_idle)
        self.timer.start()

    def eventFilter(self, obj, ev):
        if ev.type() in self.EVENTS:
            self.timer.start()
        return False


class MainWindow(QMainWindow):
    IDLE_MINUTES = 15

    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.class_id = None
        self.assessment_id = None
        self.setWindowTitle("ClassMark — Class Teacher's Assessment System")
        icon = resource("assets/icon.ico")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QFrame()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        brand = QLabel("ClassMark")
        brand.setObjectName("brand")
        tl.addWidget(brand)
        tl.addSpacing(20)
        tl.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(170)
        self.class_combo.currentIndexChanged.connect(self.class_changed)
        tl.addWidget(self.class_combo)
        tl.addWidget(button("Edit", self.edit_class))
        tl.addWidget(button("+ New class", self.new_class))
        tl.addSpacing(20)
        tl.addWidget(QLabel("Assessment:"))
        self.ass_combo = QComboBox()
        self.ass_combo.setMinimumWidth(280)
        self.ass_combo.currentIndexChanged.connect(self.assessment_changed)
        tl.addWidget(self.ass_combo)
        tl.addWidget(button("Edit", self.edit_assessment))
        tl.addWidget(button("+ New assessment", self.new_assessment))
        tl.addStretch(1)
        self.user_label = QLabel()
        tl.addWidget(self.user_label)
        tl.addWidget(button("Lock", self.lock))
        root.addWidget(top)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        root.addLayout(body, 1)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(180)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body.addWidget(self.nav)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        self.pages = [DashboardPage(self), LearnersPage(self), MarksPage(self),
                      ReportsPage(self), SettingsPage(self)]
        for name, page in zip(["  Dashboard", "  Learners", "  Marks entry", "  Reports",
                               "  Settings"], self.pages):
            QListWidgetItem(name, self.nav)
            wrap = QWidget()
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(18, 14, 18, 10)
            wl.addWidget(page)
            self.stack.addWidget(wrap)
        self.nav.currentRowChanged.connect(self.go)
        for i in range(5):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.nav.setCurrentRow(i))
        self.statusBar()
        self.db.claim_unowned_classes(self.user["id"])
        self.show_user()
        self.idle = IdleWatcher(self.IDLE_MINUTES, self.lock)
        QApplication.instance().installEventFilter(self.idle)
        self.load_classes()
        self.nav.setCurrentRow(0)
        if not self.class_id:
            self.nav.setCurrentRow(0)

    # -- session -----------------------------------------------------------
    def show_user(self):
        self.user_label.setText(f"Signed in: <b>{self.user['full_name']}</b>")

    def lock(self):
        if not self.isVisible():
            return
        self.idle.timer.stop()
        self.hide()
        user = sign_in(self.db, locked_user=self.user["id"])
        if user is None:
            QApplication.instance().quit()
            return
        switched = user["id"] != self.user["id"]
        self.user = user
        self.db.claim_unowned_classes(user["id"])
        self.show_user()
        if switched:
            self.class_id = self.assessment_id = None
        self.load_classes()
        self.showMaximized()
        self.idle.timer.start()

    # -- navigation -------------------------------------------------------
    def go(self, i):
        self.stack.setCurrentIndex(i)
        self.pages[i].refresh()

    def refresh_all(self):
        self.pages[self.stack.currentIndex()].refresh()

    # -- class / assessment context --------------------------------------
    def load_classes(self, select=None):
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        for k in self.db.classes(self.user["id"]):
            self.class_combo.addItem(f"{k['name']} ({k['year']})", k["id"])
        i = self.class_combo.findData(select or self.class_id)
        self.class_combo.setCurrentIndex(i if i >= 0 else 0)
        self.class_combo.blockSignals(False)
        self.class_changed()

    def class_changed(self, *_):
        self.class_id = self.class_combo.currentData()
        self.load_assessments()

    def load_assessments(self, select=None):
        self.ass_combo.blockSignals(True)
        self.ass_combo.clear()
        if self.class_id:
            for a in self.db.assessments(self.class_id):
                self.ass_combo.addItem(f"Term {a['term']} {a['year']} — {a['name']}", a["id"])
        i = self.ass_combo.findData(select) if select else 0
        self.ass_combo.setCurrentIndex(max(i, 0))
        self.ass_combo.blockSignals(False)
        self.assessment_changed()

    def assessment_changed(self, *_):
        self.assessment_id = self.ass_combo.currentData()
        self.refresh_all()

    def new_class(self):
        d = ClassDialog(self, self.db, owner=self.user)
        if d.exec():
            self.load_classes(d.cid)
            if not self.db.assessments(d.cid):
                self.new_assessment()

    def edit_class(self):
        if not self.class_id:
            return self.new_class()
        d = ClassDialog(self, self.db, self.class_id)
        if d.exec():
            if d.deleted:
                self.class_id = None
            self.load_classes()

    def new_assessment(self):
        if not self.class_id:
            QMessageBox.information(self, "No class", "Create a class first.")
            return
        d = AssessmentDialog(self, self.db, self.class_id)
        if d.exec():
            self.load_assessments(d.aid)

    def edit_assessment(self):
        if not self.assessment_id:
            return self.new_assessment()
        d = AssessmentDialog(self, self.db, self.class_id, self.assessment_id)
        if d.exec():
            self.load_assessments(None if d.deleted else d.aid)


STYLE = """
* { font-family: "Segoe UI"; font-size: 10pt; color: #1E1E1E; }
QMainWindow, QWidget { background: #F6F7FB; }
#topbar { background: #1F3C88; }
#topbar QLabel { color: white; background: transparent; }
#topbar QComboBox, #topbar QComboBox QAbstractItemView { color: #1E1E1E; }
#topbar QPushButton { background: #2E4FA8; color: white; border: 1px solid #5272C7; }
#topbar QPushButton:hover { background: #3B5CB8; }
#topbar QComboBox { background: white; }
#pin { font-size: 16pt; letter-spacing: 6px; padding: 6px; }
QPushButton#link { border: none; color: #1F3C88; background: transparent; text-decoration: underline; }
#brand { font-size: 15pt; font-weight: 700; padding: 6px 4px; }
#nav { background: #FFFFFF; border: none; border-right: 1px solid #E1E4EC; padding-top: 10px; }
#nav::item { padding: 11px 8px; color: #333; }
#nav::item:selected { background: #E7EDFB; color: #1F3C88; font-weight: 600;
                      border-left: 4px solid #1F3C88; }
#pageTitle { font-size: 17pt; font-weight: 600; color: #1F3C88; }
#section { font-size: 11pt; font-weight: 600; color: #333; }
#hint { color: #666; }
#card { background: white; border: 1px solid #E1E4EC; border-radius: 8px; padding: 6px; }
#cardValue { font-size: 20pt; font-weight: 700; color: #1F3C88; }
#card QLabel, #plain { background: transparent; }
QPushButton { background: white; border: 1px solid #C8CDD8; border-radius: 5px;
              padding: 6px 12px; }
QPushButton:hover { background: #EEF2FB; }
QPushButton#primary { background: #1F3C88; color: white; border-color: #1F3C88; font-weight: 600; }
QPushButton#primary:hover { background: #2B4DA6; }
QPushButton#danger { color: #B00020; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; border: 1px solid #C8CDD8;
              border-radius: 4px; padding: 4px 6px; }
QTableWidget, QTreeWidget { background: white; gridline-color: #E3E6EE; border: 1px solid #DDE1EA;
              selection-background-color: #CFDCF7; selection-color: black; }
QHeaderView::section { background: #EEF1F8; border: none; border-right: 1px solid #DDE1EA;
              border-bottom: 1px solid #DDE1EA; padding: 4px; font-weight: 600; }
QGroupBox { background: white; border: 1px solid #E1E4EC; border-radius: 8px; margin-top: 14px;
            padding: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #1F3C88; }
QGroupBox QLabel, QGroupBox QCheckBox { background: transparent; font-weight: normal; }
QDialog QLabel, QDialog QCheckBox { background: transparent; }
QStatusBar { background: white; }
QCheckBox::indicator, QRadioButton::indicator { width: 15px; height: 15px; }
QCheckBox::indicator { border: 1px solid #8A93A6; border-radius: 3px; background: white; }
QCheckBox::indicator:checked { border-color: #1F3C88; image: url(CHECK_IMG); }
QCheckBox::indicator:hover { border-color: #1F3C88; }
QPlainTextEdit { background: white; border: 1px solid #C8CDD8; border-radius: 4px; }
"""


def apply_theme(app):
    """Always light, regardless of the Windows dark-mode setting."""
    from PySide6.QtGui import QPalette
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in [(QPalette.Window, "#F6F7FB"), (QPalette.WindowText, "#1E1E1E"),
                        (QPalette.Base, "#FFFFFF"), (QPalette.AlternateBase, "#F3F5FA"),
                        (QPalette.Text, "#1E1E1E"), (QPalette.Button, "#FFFFFF"),
                        (QPalette.ButtonText, "#1E1E1E"), (QPalette.Highlight, "#CFDCF7"),
                        (QPalette.HighlightedText, "#000000"), (QPalette.ToolTipBase, "#FFFFE1"),
                        (QPalette.ToolTipText, "#1E1E1E"), (QPalette.PlaceholderText, "#8A8F99")]:
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    check = resource("assets/check.png").replace("\\", "/")  # blue tick for checkboxes
    app.setStyleSheet(STYLE.replace("CHECK_IMG", check))
