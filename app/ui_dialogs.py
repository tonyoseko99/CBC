"""Dialogs: class, assessment, learner, subject/paper, template upload."""
import datetime
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QAbstractItemView)

from . import templates as T
from .grading import fmt


def _buttons(dlg, extra=None):
    bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    row = QHBoxLayout()
    if extra:
        row.addWidget(extra)
    row.addStretch(1)
    row.addWidget(bb)
    return row


def _require(parent, widget, label):
    if not widget.text().strip():
        QMessageBox.warning(parent, "Missing information", f"Please enter {label}.")
        widget.setFocus()
        return False
    return True


class ClassDialog(QDialog):
    def __init__(self, parent, db, cid=None, owner=None):
        super().__init__(parent)
        self.db, self.cid, self.deleted, self.owner = db, cid, False, owner
        self.setWindowTitle("Edit class" if cid else "New class")
        row = db.get_class(cid) if cid else None
        self.name = QLineEdit(row["name"] if row else "")
        self.name.setPlaceholderText("e.g. GRADE 7B")
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(row["year"] if row and row["year"] else datetime.date.today().year)
        self.teacher = QLineEdit(row["class_teacher"] if row else
                                 (owner["full_name"] if owner else ""))
        self.teacher.setPlaceholderText("e.g. Mrs. Jane Musa")
        f = QFormLayout()
        f.addRow("Class / Grade:", self.name)
        f.addRow("Year:", self.year)
        f.addRow("Class teacher:", self.teacher)
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        hint = QLabel("The class teacher's name prints automatically on every Individual Assessment Report.")
        hint.setObjectName("hint")
        lay.addWidget(hint)
        delete = None
        if cid:
            delete = QPushButton("Delete class…")
            delete.setObjectName("danger")
            delete.clicked.connect(self._delete)
        lay.addLayout(_buttons(self, delete))
        self.resize(420, 0)

    def _delete(self):
        if QMessageBox.question(
                self, "Delete class",
                "Delete this class together with ALL its learners, assessments and marks?\n"
                "This cannot be undone (unless you have a backup).") == QMessageBox.Yes:
            self.db.delete_class(self.cid)
            self.deleted = True
            super().accept()

    def accept(self):
        if not _require(self, self.name, "the class name"):
            return
        self.cid = self.db.save_class(self.cid, self.name.text().strip().upper(),
                                      self.year.value(), self.teacher.text().strip(),
                                      self.owner["id"] if self.owner else None)
        super().accept()


class AssessmentDialog(QDialog):
    def __init__(self, parent, db, class_id, aid=None):
        super().__init__(parent)
        self.db, self.class_id, self.aid, self.deleted = db, class_id, aid, False
        self.setWindowTitle("Edit assessment" if aid else "New assessment")
        a = db.get_assessment(aid) if aid else None
        k = db.get_class(class_id)
        self.name = QComboBox()
        self.name.setEditable(True)
        self.name.addItems(["Opener Assessment", "Mid Term Assessment", "End Term Assessment",
                            "CAT 1", "CAT 2"])
        self.name.setCurrentText(a["name"] if a else "End Term Assessment")
        self.term = QSpinBox()
        self.term.setRange(1, 3)
        self.term.setValue(a["term"] if a else 1)
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(a["year"] if a else (k["year"] or datetime.date.today().year))
        self.out_of = QDoubleSpinBox()
        self.out_of.setRange(1, 1000)
        self.out_of.setDecimals(0)
        self.out_of.setValue(a["default_out_of"] if a else 100)
        self.closing = QLineEdit(a["closing_date"] if a else "")
        self.closing.setPlaceholderText("e.g. Friday, 4 April 2026")
        self.opening = QLineEdit(a["opening_date"] if a else "")
        self.opening.setPlaceholderText("e.g. Monday, 28 April 2026")
        f = QFormLayout()
        f.addRow("Assessment:", self.name)
        f.addRow("Term:", self.term)
        f.addRow("Year:", self.year)
        f.addRow("Marks out of (default):", self.out_of)
        f.addRow("Closing date:", self.closing)
        f.addRow("Opening date:", self.opening)
        lay = QVBoxLayout(self)
        lay.addLayout(f)

        lay.addWidget(QLabel("<b>Out of, per paper</b> (change only where a paper differs "
                             "from the default, e.g. Insha out of 45):"))
        self.papers = db.papers()
        over = db.out_of_map(aid) if aid else {}
        self.table = QTableWidget(len(self.papers), 2)
        self.table.setHorizontalHeaderLabels(["Paper", "Out of"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.spins = []
        for i, p in enumerate(self.papers):
            it = QTableWidgetItem(p["name"])
            it.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 0, it)
            sp = QDoubleSpinBox()
            sp.setRange(0, 1000)
            sp.setDecimals(0)
            sp.setSpecialValueText("default")
            v = over.get(p["id"])
            sp.setValue(0 if v is None or (a and v == a["default_out_of"]) else v)
            self.table.setCellWidget(i, 1, sp)
            self.spins.append(sp)
        self.table.setMinimumHeight(220)
        lay.addWidget(self.table)
        delete = None
        if aid:
            delete = QPushButton("Delete assessment…")
            delete.setObjectName("danger")
            delete.clicked.connect(self._delete)
        lay.addLayout(_buttons(self, delete))
        self.resize(460, 640)

    def _delete(self):
        if QMessageBox.question(self, "Delete assessment",
                                "Delete this assessment and all its marks?") == QMessageBox.Yes:
            self.db.delete_assessment(self.aid)
            self.deleted = True
            super().accept()

    def accept(self):
        name = self.name.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Missing information", "Please enter the assessment name.")
            return
        self.aid = self.db.save_assessment(
            self.aid, self.class_id, name, self.term.value(), self.year.value(),
            self.out_of.value(), self.closing.text().strip(), self.opening.text().strip())
        self.db.clear_out_of(self.aid)
        for p, sp in zip(self.papers, self.spins):
            if sp.value() > 0 and sp.value() != self.out_of.value():
                self.db.set_out_of(self.aid, p["id"], sp.value())
        super().accept()


class LearnerDialog(QDialog):
    def __init__(self, parent, db, class_id, learner=None):
        super().__init__(parent)
        self.db, self.class_id, self.learner = db, class_id, learner
        self.setWindowTitle("Edit learner" if learner else "Add learner")
        self.adm = QLineEdit(learner["adm_no"] if learner else "")
        self.name = QLineEdit(learner["name"] if learner else "")
        self.gender = QComboBox()
        self.gender.addItems(["", "F", "M"])
        if learner:
            self.gender.setCurrentText(learner["gender"] or "")
        f = QFormLayout()
        f.addRow("Adm No:", self.adm)
        f.addRow("Full name:", self.name)
        f.addRow("Gender:", self.gender)
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        self.again = QCheckBox("Add another after saving")
        self.again.setChecked(learner is None)
        if learner is None:
            lay.addWidget(self.again)
        lay.addLayout(_buttons(self))
        self.resize(400, 0)

    def accept(self):
        if not _require(self, self.name, "the learner's name"):
            return
        self.db.save_learner(self.learner["id"] if self.learner else None, self.class_id,
                             self.adm.text().strip(), " ".join(self.name.text().upper().split()),
                             self.gender.currentText())
        if self.learner is None and self.again.isChecked():
            self.adm.clear()
            self.name.clear()
            self.adm.setFocus()
            self.setWindowTitle("Add learner — saved, add the next one")
            return
        super().accept()


class NameCodeDialog(QDialog):
    def __init__(self, parent, title, name="", code="", label=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.name = QLineEdit(name)
        self.code = QLineEdit(code)
        self.code.setPlaceholderText("short code used on the mark sheet, e.g. MATH")
        f = QFormLayout()
        f.addRow("Name:", self.name)
        f.addRow("Short code:", self.code)
        self.label = None
        if label is not None:
            self.label = QLineEdit(label)
            self.label.setPlaceholderText("Total")
            f.addRow("Total row label:", self.label)
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        if label is not None:
            h = QLabel("The total row label is used when a learning area has more than one "
                       "paper (e.g. 'Jumla' for Kiswahili & Insha).")
            h.setWordWrap(True)
            h.setObjectName("hint")
            lay.addWidget(h)
        lay.addLayout(_buttons(self))
        self.resize(420, 0)

    def accept(self):
        if _require(self, self.name, "a name"):
            super().accept()


class UploadDialog(QDialog):
    """Upload a filled ClassMark template (learners or marks): check, preview, then import."""

    COLORS = {"new": "#D8F0DC", "update": "#DDEBF7", "unchanged": "#F2F2F2", "error": "#FAD4D4"}

    def __init__(self, parent, db, class_id, kind, download, aid=None):
        super().__init__(parent)
        self.db, self.class_id, self.kind, self.aid = db, class_id, kind, aid
        self.parsed = None
        self.setWindowTitle("Upload learners template" if kind == "learners"
                            else "Upload marks template")
        lay = QVBoxLayout(self)
        steps = QLabel("<b>1.</b> Download the template &nbsp;→&nbsp; <b>2.</b> Fill it in Excel and "
                       "save &nbsp;→&nbsp; <b>3.</b> Choose the filled template here, check the "
                       "preview, then click <b>Import</b>.")
        steps.setWordWrap(True)
        lay.addWidget(steps)
        row = QHBoxLayout()
        dl = QPushButton("Download template")
        dl.clicked.connect(download)
        pick = QPushButton("Choose filled template…")
        pick.setObjectName("primary")
        pick.clicked.connect(self.browse)
        self.path = QLabel("No file chosen")
        self.path.setObjectName("hint")
        row.addWidget(dl)
        row.addWidget(pick)
        row.addWidget(self.path, 1)
        lay.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.RichText)
        lay.addWidget(self.status)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        lay.addWidget(self.table, 1)          # only the table grows/scrolls
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.button(QDialogButtonBox.Ok).setText("Import")
        self.bb.button(QDialogButtonBox.Ok).setEnabled(False)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        lay.addWidget(self.bb)                # always visible at the bottom
        scr = (parent.screen() if parent else QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1000, int(scr.width() * 0.9)), min(680, int(scr.height() * 0.85)))

    def _fail(self, msg):
        self.parsed = None
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.status.setText(f"<span style='color:#B00020'>{msg.replace(chr(10), '<br>')}</span>")
        self.bb.button(QDialogButtonBox.Ok).setEnabled(False)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose filled template", "",
                                              "Excel template (*.xlsx)")
        if path:
            self.load(path)

    def load(self, path):
        self.path.setText(os.path.basename(path))
        self.path.setToolTip(path)
        try:
            meta, rows = T.read_template(path, self.kind)
            if self.kind == "learners":
                self.parsed = T.parse_learners(self.db, self.class_id, meta, rows)
                self.show_learners()
            else:
                self.parsed = T.parse_marks(self.db, self.class_id, self.aid, meta, rows)
                self.show_marks()
        except T.TemplateError as e:
            self._fail(str(e))

    def _cell(self, r, c, text, color=None, tip=None):
        it = QTableWidgetItem("" if text is None else str(text))
        if color:
            it.setBackground(QBrush(QColor(color)))
        if tip:
            it.setToolTip(tip)
        self.table.setItem(r, c, it)

    def show_learners(self):
        order = {"error": 0, "new": 1, "update": 2, "unchanged": 3}
        es = sorted(self.parsed, key=lambda e: (order["error" if e["error"] else e["action"]],
                                                e["row"]))  # problems and changes first
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Excel row", "Adm No", "Name", "Gender", "Status"])
        self.table.setRowCount(len(es))
        for r, e in enumerate(es):
            st = "error" if e["error"] else e["action"]
            for c, v in enumerate([e["row"], e["adm"], e["name"], e["gender"]]):
                self._cell(r, c, v)
            self._cell(r, 4, e["error"] or st, self.COLORS[st])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        n = {k: sum(1 for e in es if not e["error"] and e["action"] == k)
             for k in ("new", "update", "unchanged")}
        bad = sum(1 for e in es if e["error"])
        msg = (f"<b>{n['new']}</b> new learners, <b>{n['update']}</b> to update, "
               f"{n['unchanged']} unchanged.")
        if bad:
            msg += f" <span style='color:#B00020'><b>{bad}</b> rows have problems and will be skipped.</span>"
        self.status.setText(msg)
        self.bb.button(QDialogButtonBox.Ok).setEnabled(n["new"] + n["update"] > 0)

    def show_marks(self):
        pm = self.parsed
        papers, es = pm["papers"], pm["entries"]
        self.table.setColumnCount(3 + len(papers))
        self.table.setHorizontalHeaderLabels(["Excel row", "Adm", "Name"] +
                                             [p["code"] or p["name"] for p in papers])
        self.table.setRowCount(len(es))
        marks = problems = 0
        for r, e in enumerate(es):
            self._cell(r, 0, e["row"])
            self._cell(r, 1, e["adm"])
            if e["learner"] is None:
                self._cell(r, 2, e["name"], self.COLORS["error"], e["errors"][0])
                problems += 1
                continue
            self._cell(r, 2, e["name"])
            for c, p in enumerate(papers, start=3):
                if p["id"] in e["errors"]:
                    self._cell(r, c, "✗", self.COLORS["error"], e["errors"][p["id"]])
                    problems += 1
                else:
                    m = e["marks"].get(p["id"])
                    self._cell(r, c, fmt(m) if m is not None else "")
                    marks += m is not None
        self.table.resizeColumnsToContents()
        for c in range(3, self.table.columnCount()):
            self.table.setColumnWidth(c, max(62, self.table.columnWidth(c)))
        msg = f"<b>{marks}</b> marks for <b>{sum(1 for e in es if e['learner'])}</b> learners ready."
        if problems:
            msg += (f" <span style='color:#B00020'><b>{problems}</b> problems (red cells — hover "
                    "to see why) will be skipped.</span>")
        if pm["out_of_changes"]:
            ch = ", ".join(f"{p['code']} /{fmt(float(v))}" for p in papers
                           for pid, v in pm["out_of_changes"].items() if p["id"] == pid)
            msg += f"<br>Out-of values will be updated from the file's OUT OF row: <b>{ch}</b>."
        if pm["missing_papers"]:
            msg += ("<br><span style='color:#8A5A00'>Not in this file (left unchanged): "
                    + ", ".join(p["code"] for p in pm["missing_papers"]) + "</span>")
        if pm["wrong_assessment"]:
            msg += (f"<br><span style='color:#8A5A00'>Note: this template was downloaded for "
                    f"<b>{pm['wrong_assessment']}</b>, not the assessment selected now.</span>")
        self.status.setText(msg)
        self.bb.button(QDialogButtonBox.Ok).setEnabled(marks > 0 or any(
            e["learner"] and e["marks"] for e in es))

    def accept(self):
        if self.parsed is None:
            return
        if self.kind == "learners":
            added, updated = T.apply_learners(self.db, self.class_id, self.parsed)
            QMessageBox.information(self, "Upload complete",
                                    f"{added} learners added, {updated} updated.")
        else:
            wrong = self.parsed["wrong_assessment"]
            a = self.db.get_assessment(self.aid)
            if wrong and QMessageBox.question(
                    self, "Different assessment",
                    f"This template was made for {wrong}.\nImport its marks into "
                    f"Term {a['term']} {a['name']} {a['year']} instead?") != QMessageBox.Yes:
                return
            saved = T.apply_marks(self.db, self.aid, self.parsed)
            QMessageBox.information(self, "Upload complete", f"{saved} marks saved.")
        super().accept()
