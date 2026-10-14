"""SQLite storage. One file (classmark.db) holds everything."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS classes(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, year INTEGER, class_teacher TEXT,
    owner_id INTEGER);
CREATE TABLE IF NOT EXISTS learners(
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    adm_no TEXT, name TEXT NOT NULL, gender TEXT);
CREATE TABLE IF NOT EXISTS subjects(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, code TEXT,
    total_label TEXT DEFAULT 'Total', sort_order INTEGER DEFAULT 0, sheet_order INTEGER);
CREATE TABLE IF NOT EXISTS papers(
    id INTEGER PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name TEXT NOT NULL, code TEXT, sort_order INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS assessments(
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    name TEXT NOT NULL, term INTEGER, year INTEGER, default_out_of REAL DEFAULT 100,
    closing_date TEXT, opening_date TEXT);
CREATE TABLE IF NOT EXISTS paper_out_of(
    assessment_id INTEGER REFERENCES assessments(id) ON DELETE CASCADE,
    paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    out_of REAL, PRIMARY KEY(assessment_id, paper_id));
CREATE TABLE IF NOT EXISTS marks(
    assessment_id INTEGER REFERENCES assessments(id) ON DELETE CASCADE,
    learner_id INTEGER REFERENCES learners(id) ON DELETE CASCADE,
    paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    mark REAL, PRIMARY KEY(assessment_id, learner_id, paper_id));
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE, full_name TEXT,
    pin_hash TEXT NOT NULL, recovery_hash TEXT NOT NULL,
    failed INTEGER DEFAULT 0, locked_until REAL DEFAULT 0, created TEXT);
CREATE TABLE IF NOT EXISTS report_notes(
    assessment_id INTEGER REFERENCES assessments(id) ON DELETE CASCADE,
    learner_id INTEGER REFERENCES learners(id) ON DELETE CASCADE,
    ct_remark TEXT, ht_remark TEXT, discipline TEXT, attention TEXT,
    PRIMARY KEY(assessment_id, learner_id));
"""

DEFAULT_SETTINGS = {
    "header_line": "MINISTRY OF EDUCATION NAIROBI CITY COUNTY MATHARE SUB COUNTY",
    "school_name": "ST. TERESA'S GIRLS' SCHOOL",
    "school_subtitle": "ECDE, SPECIAL UNIT, PRIMARY AND JUNIOR SECONDARY SCHOOL",
    "report_title": "INDIVIDUAL ASSESSMENT REPORT - JUNIOR SCHOOL",
    "head_teacher": "",
    "default_discipline": "",
    "default_attention": "",
    "logo_path": "",
    "report_show_marks": "0",      # marks on the Individual Assessment Report
    "mark_sheet_options": "",      # last class mark sheet export choices (JSON)
}

# Report-form order. name, code, total-row label, [(paper name, paper code)].
# Codes are the column headings on the school's Excel mark sheets.
DEFAULT_SUBJECTS = [
    ("Mathematics", "MATH", "Total", [("Mathematics", "MATH")]),
    ("English & Composition", "ENG", "Total", [("English", "ENG P1"), ("Composition", "ENG P2")]),
    ("Kiswahili & Insha", "KISW", "Jumla", [("Kiswahili", "KISW P1"), ("Insha", "KISW P2")]),
    ("Integrated Science", "INT. SCI", "Total", [("Integrated Science", "INT. SCI")]),
    ("Social Studies & Life Skills", "SST", "Total", [("Social Studies & Life Skills", "SST")]),
    ("Religious Education", "C.R.E.", "Total", [("Religious Education", "C.R.E.")]),
    ("Agriculture & Nutrition", "AGRIC", "Total", [("Agriculture & Nutrition", "AGRIC")]),
    ("Creative Arts", "C/ART", "Total", [("Creative Arts", "C/ART")]),
    ("Pre-Technical Studies", "P.TECH", "Total", [("Pre-Technical Studies", "P.TECH")]),
]
# Column order on the school's mark sheets (P.TECH comes before AGRIC there).
DEFAULT_SHEET_ORDER = ["MATH", "ENG", "KISW", "INT. SCI", "SST", "C.R.E.", "P.TECH", "AGRIC",
                       "C/ART"]
# Old default codes -> mark-sheet headings (only changed if the user never edited them).
OLD_PAPER_CODES = {"ENG": "ENG P1", "COMP": "ENG P2", "KISW": "KISW P1", "INSHA": "KISW P2",
                   "INT.SCI": "INT. SCI", "AGR/NUT": "AGRIC"}
OLD_SUBJECT_CODES = {"INT.SCI": "INT. SCI", "AGR/NUT": "AGRIC"}


class DB:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self._seed()

    # -- low level -------------------------------------------------------
    def q(self, sql, args=()):
        return self.conn.execute(sql, args).fetchall()

    def one(self, sql, args=()):
        return self.conn.execute(sql, args).fetchone()

    def x(self, sql, args=()):
        cur = self.conn.execute(sql, args)
        self.conn.commit()
        return cur.lastrowid

    def _migrate(self):
        cols = {r["name"] for r in self.q("PRAGMA table_info(classes)")}
        if "owner_id" not in cols:  # databases created before per-user classes
            self.conn.execute("ALTER TABLE classes ADD COLUMN owner_id INTEGER")
            self.conn.commit()
        cols = {r["name"] for r in self.q("PRAGMA table_info(subjects)")}
        if "sheet_order" not in cols:  # before the separate mark-sheet column order
            self.conn.execute("ALTER TABLE subjects ADD COLUMN sheet_order INTEGER")
            for old, new in OLD_SUBJECT_CODES.items():
                self.conn.execute("UPDATE subjects SET code=? WHERE code=?", (new, old))
            for old, new in OLD_PAPER_CODES.items():
                self.conn.execute("UPDATE papers SET code=? WHERE code=?", (new, old))
            self.conn.commit()
        self._default_sheet_order()

    def _default_sheet_order(self):
        """Give subjects without a mark-sheet position one (school order where codes match)."""
        if not self.one("SELECT 1 FROM subjects WHERE sheet_order IS NULL"):
            return
        subs = self.q("SELECT id, code FROM subjects ORDER BY sort_order, id")
        rank = {c: i for i, c in enumerate(DEFAULT_SHEET_ORDER)}
        ordered = sorted(enumerate(subs), key=lambda t: (rank.get(t[1]["code"], 100), t[0]))
        for n, (_, s) in enumerate(ordered):
            self.conn.execute("UPDATE subjects SET sheet_order=? WHERE id=?", (n, s["id"]))
        self.conn.commit()

    def _seed(self):
        for k, v in DEFAULT_SETTINGS.items():
            self.conn.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
        self.conn.execute("UPDATE settings SET value=? WHERE key='report_title' AND value=?",
                          (DEFAULT_SETTINGS["report_title"],
                           "INDIVIDUAL CONTINUOUS ASSESSMENT - JUNIOR SCHOOL"))
        if not self.one("SELECT 1 FROM subjects"):
            for i, (name, code, label, papers) in enumerate(DEFAULT_SUBJECTS):
                sid = self.conn.execute(
                    "INSERT INTO subjects(name,code,total_label,sort_order) VALUES(?,?,?,?)",
                    (name, code, label, i)).lastrowid
                for j, (pn, pc) in enumerate(papers):
                    self.conn.execute(
                        "INSERT INTO papers(subject_id,name,code,sort_order) VALUES(?,?,?,?)",
                        (sid, pn, pc, j))
            self.conn.commit()
            self._default_sheet_order()
        self.conn.commit()

    def backup_to(self, dest):
        out = sqlite3.connect(dest)
        with out:
            self.conn.backup(out)
        out.close()

    def restore_from(self, src):
        inp = sqlite3.connect(src)
        inp.execute("SELECT count(*) FROM learners")  # sanity check it is ours
        with self.conn:
            inp.backup(self.conn)
        inp.close()
        self._migrate()

    # -- users -----------------------------------------------------------
    def users(self):
        return self.q("SELECT * FROM users ORDER BY id")

    def get_user(self, uid):
        return self.one("SELECT * FROM users WHERE id=?", (uid,))

    def add_user(self, username, full_name, pin_hash, recovery_hash):
        return self.x("INSERT INTO users(username,full_name,pin_hash,recovery_hash,created) "
                      "VALUES(?,?,?,?,datetime('now'))",
                      (username, full_name, pin_hash, recovery_hash))

    def update_user(self, uid, **fields):
        allowed = {"full_name", "pin_hash", "recovery_hash", "failed", "locked_until"}
        assert set(fields) <= allowed
        sets = ",".join(f"{k}=?" for k in fields)
        self.x(f"UPDATE users SET {sets} WHERE id=?", (*fields.values(), uid))

    def delete_user(self, uid, give_classes_to=None):
        """Remove a user; their classes move to another user (or become unowned)."""
        self.conn.execute("UPDATE classes SET owner_id=? WHERE owner_id=?", (give_classes_to, uid))
        self.x("DELETE FROM users WHERE id=?", (uid,))

    # -- settings --------------------------------------------------------
    def settings(self):
        return {r["key"]: r["value"] or "" for r in self.q("SELECT * FROM settings")}

    def set_setting(self, key, value):
        self.x("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, value))

    # -- classes ---------------------------------------------------------
    def classes(self, owner_id):
        return self.q("SELECT * FROM classes WHERE owner_id=? ORDER BY year DESC, name",
                      (owner_id,))

    def claim_unowned_classes(self, owner_id):
        """Classes made before accounts existed (or left by a removed user) go to owner_id."""
        n = self.conn.execute("UPDATE classes SET owner_id=? WHERE owner_id IS NULL OR owner_id "
                              "NOT IN (SELECT id FROM users)", (owner_id,)).rowcount
        self.conn.commit()
        return n

    def get_class(self, cid):
        return self.one("SELECT * FROM classes WHERE id=?", (cid,))

    def save_class(self, cid, name, year, teacher, owner_id=None):
        if cid:
            self.x("UPDATE classes SET name=?,year=?,class_teacher=? WHERE id=?",
                   (name, year, teacher, cid))
            return cid
        return self.x("INSERT INTO classes(name,year,class_teacher,owner_id) VALUES(?,?,?,?)",
                      (name, year, teacher, owner_id))

    def delete_class(self, cid):
        self.x("DELETE FROM classes WHERE id=?", (cid,))

    # -- learners --------------------------------------------------------
    def learners(self, class_id):
        return self.q(
            "SELECT * FROM learners WHERE class_id=? "
            "ORDER BY CAST(adm_no AS INTEGER), adm_no, name", (class_id,))

    def save_learner(self, lid, class_id, adm, name, gender):
        if lid:
            self.x("UPDATE learners SET adm_no=?,name=?,gender=? WHERE id=?",
                   (adm, name, gender, lid))
            return lid
        return self.x("INSERT INTO learners(class_id,adm_no,name,gender) VALUES(?,?,?,?)",
                      (class_id, adm, name, gender))

    def delete_learner(self, lid):
        self.x("DELETE FROM learners WHERE id=?", (lid,))

    # -- subjects & papers ----------------------------------------------
    def subjects(self, order="report"):
        """[{id,name,code,total_label,papers:[{id,name,code}]}] in report or mark-sheet order."""
        col = "sheet_order" if order == "sheet" else "sort_order"
        subs = [dict(r) for r in self.q(f"SELECT * FROM subjects ORDER BY {col}, id")]
        papers = self.q("SELECT * FROM papers ORDER BY sort_order, id")
        for s in subs:
            s["papers"] = [dict(p) for p in papers if p["subject_id"] == s["id"]]
        return subs

    def papers(self, order="sheet"):
        return [p for s in self.subjects(order) for p in s["papers"]]

    def save_subject(self, sid, name, code, label):
        if sid:
            self.x("UPDATE subjects SET name=?,code=?,total_label=? WHERE id=?",
                   (name, code, label, sid))
            return sid
        n = self.one("SELECT COALESCE(MAX(sort_order),0)+1 FROM subjects")[0]
        m = self.one("SELECT COALESCE(MAX(sheet_order),0)+1 FROM subjects")[0]
        sid = self.x("INSERT INTO subjects(name,code,total_label,sort_order,sheet_order) "
                     "VALUES(?,?,?,?,?)", (name, code, label, n, m))
        self.save_paper(None, sid, name, code)
        return sid

    def save_paper(self, pid, subject_id, name, code):
        if pid:
            self.x("UPDATE papers SET name=?,code=? WHERE id=?", (name, code, pid))
            return pid
        n = self.one("SELECT COALESCE(MAX(sort_order),0)+1 FROM papers WHERE subject_id=?",
                     (subject_id,))[0]
        return self.x("INSERT INTO papers(subject_id,name,code,sort_order) VALUES(?,?,?,?)",
                      (subject_id, name, code, n))

    def delete_subject(self, sid):
        self.x("DELETE FROM subjects WHERE id=?", (sid,))

    def delete_paper(self, pid):
        self.x("DELETE FROM papers WHERE id=?", (pid,))

    def count_marks_for(self, paper_ids):
        if not paper_ids:
            return 0
        qs = ",".join("?" * len(paper_ids))
        return self.one(f"SELECT count(*) FROM marks WHERE paper_id IN ({qs})", paper_ids)[0]

    def move(self, table, rid, delta, order="report"):
        """Move a subject (in report or mark-sheet order) or a paper within its subject."""
        row = self.one(f"SELECT * FROM {table} WHERE id=?", (rid,))
        col = "sheet_order" if table == "subjects" and order == "sheet" else "sort_order"
        if table == "papers":
            sib = self.q("SELECT id FROM papers WHERE subject_id=? "
                         "ORDER BY sort_order, id", (row["subject_id"],))
        else:
            sib = self.q(f"SELECT id FROM subjects ORDER BY {col}, id")
        ids = [r["id"] for r in sib]
        i = ids.index(rid)
        j = i + delta
        if not 0 <= j < len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        for n, k in enumerate(ids):
            self.conn.execute(f"UPDATE {table} SET {col}=? WHERE id=?", (n, k))
        self.conn.commit()

    # -- assessments -----------------------------------------------------
    def assessments(self, class_id):
        return self.q("SELECT * FROM assessments WHERE class_id=? "
                      "ORDER BY year DESC, term DESC, id DESC", (class_id,))

    def get_assessment(self, aid):
        return self.one("SELECT * FROM assessments WHERE id=?", (aid,))

    def save_assessment(self, aid, class_id, name, term, year, out_of, closing, opening):
        if aid:
            self.x("UPDATE assessments SET name=?,term=?,year=?,default_out_of=?,"
                   "closing_date=?,opening_date=? WHERE id=?",
                   (name, term, year, out_of, closing, opening, aid))
            return aid
        return self.x("INSERT INTO assessments(class_id,name,term,year,default_out_of,"
                      "closing_date,opening_date) VALUES(?,?,?,?,?,?,?)",
                      (class_id, name, term, year, out_of, closing, opening))

    def delete_assessment(self, aid):
        self.x("DELETE FROM assessments WHERE id=?", (aid,))

    def out_of_map(self, aid):
        a = self.get_assessment(aid)
        default = a["default_out_of"] if a else 100
        over = {r["paper_id"]: r["out_of"] for r in
                self.q("SELECT * FROM paper_out_of WHERE assessment_id=?", (aid,))}
        return {p["id"]: over.get(p["id"], default) for p in self.papers()}

    def set_out_of(self, aid, paper_id, value):
        self.x("INSERT OR REPLACE INTO paper_out_of VALUES(?,?,?)", (aid, paper_id, value))

    def clear_out_of(self, aid):
        self.x("DELETE FROM paper_out_of WHERE assessment_id=?", (aid,))

    # -- marks -----------------------------------------------------------
    def marks_map(self, aid):
        return {(r["learner_id"], r["paper_id"]): r["mark"] for r in
                self.q("SELECT * FROM marks WHERE assessment_id=?", (aid,))}

    def set_mark(self, aid, lid, pid, mark, commit=True):
        if mark is None:
            self.conn.execute("DELETE FROM marks WHERE assessment_id=? AND learner_id=? "
                              "AND paper_id=?", (aid, lid, pid))
        else:
            self.conn.execute("INSERT OR REPLACE INTO marks VALUES(?,?,?,?)",
                              (aid, lid, pid, mark))
        if commit:
            self.conn.commit()

    # -- report notes ----------------------------------------------------
    def notes_map(self, aid):
        return {r["learner_id"]: dict(r) for r in
                self.q("SELECT * FROM report_notes WHERE assessment_id=?", (aid,))}

    def set_note(self, aid, lid, field, value):
        assert field in ("ct_remark", "ht_remark", "discipline", "attention")
        self.conn.execute("INSERT OR IGNORE INTO report_notes(assessment_id,learner_id) "
                          "VALUES(?,?)", (aid, lid))
        self.x(f"UPDATE report_notes SET {field}=? WHERE assessment_id=? AND learner_id=?",
               (value or None, aid, lid))
