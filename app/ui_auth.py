"""Login, registration and PIN dialogs."""
from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout)

from . import auth


def pin_field(placeholder="4–6 digits"):
    e = QLineEdit()
    e.setEchoMode(QLineEdit.Password)
    e.setMaxLength(auth.PIN_MAX)
    e.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,6}"), e))
    e.setPlaceholderText(placeholder)
    e.setAlignment(Qt.AlignCenter)
    e.setObjectName("pin")
    return e


def _header(lay, title, sub):
    t = QLabel(title)
    t.setObjectName("pageTitle")
    t.setAlignment(Qt.AlignCenter)
    lay.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setObjectName("hint")
        s.setWordWrap(True)
        s.setAlignment(Qt.AlignCenter)
        lay.addWidget(s)
    lay.addSpacing(8)


def _error_label():
    e = QLabel()
    e.setStyleSheet("color:#B00020; background:transparent;")
    e.setWordWrap(True)
    e.setAlignment(Qt.AlignCenter)
    return e


def show_recovery_code(parent, name, code):
    QApplication.clipboard().setText(code)
    QMessageBox.information(
        parent, "Your recovery code",
        f"<p>Hello {name}, write this recovery code down and keep it safe:</p>"
        f"<p style='font-size:20pt; font-weight:bold; letter-spacing:3px'>{code}</p>"
        "<p>If you ever forget your PIN, this code lets you set a new one. "
        "It is shown only once (it has also been copied to the clipboard).</p>")


class RegisterDialog(QDialog):
    def __init__(self, parent, db, first=False):
        super().__init__(parent)
        self.db, self.user_id = db, None
        self.setWindowTitle("ClassMark — Register")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        n = len(db.users())
        _header(lay, "Create account" if not first else "Welcome to ClassMark",
                ("Set up your account to get started. " if first else "") +
                f"User {n + 1} of {auth.MAX_USERS}. You will use your PIN each time you open "
                "the system.")
        self.full = QLineEdit()
        self.full.setPlaceholderText("e.g. Jane Musa")
        self.username = QLineEdit()
        self.username.setPlaceholderText("e.g. jmusa")
        self.pin = pin_field()
        self.pin2 = pin_field("repeat PIN")
        f = QFormLayout()
        f.addRow("Full name:", self.full)
        f.addRow("Username:", self.username)
        f.addRow("PIN:", self.pin)
        f.addRow("Confirm PIN:", self.pin2)
        lay.addLayout(f)
        self.err = _error_label()
        lay.addWidget(self.err)
        b = QPushButton("Create account")
        b.setObjectName("primary")
        b.setDefault(True)
        b.clicked.connect(self.submit)
        lay.addWidget(b)
        self.setMinimumWidth(420)

    def submit(self):
        try:
            self.user_id, code = auth.register(self.db, self.username.text(), self.full.text(),
                                               self.pin.text(), self.pin2.text())
        except auth.AuthError as e:
            self.err.setText(str(e))
            return
        show_recovery_code(self, self.full.text().split()[0], code)
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, db, locked_user=None):
        super().__init__()
        self.db, self.user = db, None
        self.setWindowTitle("ClassMark — Sign in")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 22)
        school = db.settings().get("school_name", "")
        _header(lay, "ClassMark", school or None)
        self.who = QComboBox()
        for u in db.users():
            self.who.addItem(f"{u['full_name']}  ({u['username']})", u["id"])
        if locked_user:
            self.who.setCurrentIndex(max(self.who.findData(locked_user), 0))
        self.pin = pin_field("Enter PIN")
        self.pin.returnPressed.connect(self.submit)
        f = QFormLayout()
        f.addRow("User:", self.who)
        f.addRow("PIN:", self.pin)
        lay.addLayout(f)
        self.err = _error_label()
        lay.addWidget(self.err)
        b = QPushButton("Sign in")
        b.setObjectName("primary")
        b.setDefault(True)
        b.clicked.connect(self.submit)
        lay.addWidget(b)
        forgot = QPushButton("Forgot PIN?")
        forgot.setFlat(True)
        forgot.setObjectName("link")
        forgot.clicked.connect(self.forgot)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(forgot)
        lay.addLayout(row)
        self.setMinimumWidth(400)
        self.pin.setFocus()

    def submit(self):
        try:
            self.user = auth.login(self.db, self.who.currentData(), self.pin.text())
        except auth.AuthError as e:
            self.err.setText(str(e))
            self.pin.clear()
            self.pin.setFocus()
            return
        self.accept()

    def forgot(self):
        ResetPinDialog(self, self.db, self.who.currentData()).exec()


class ResetPinDialog(QDialog):
    def __init__(self, parent, db, uid):
        super().__init__(parent)
        self.db, self.uid = db, uid
        u = db.get_user(uid)
        self.setWindowTitle("Reset PIN")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        _header(lay, "Reset PIN", f"For {u['full_name']}. Enter the recovery code you were "
                                  "given when you registered.")
        self.code = QLineEdit()
        self.code.setPlaceholderText("XXXX-XXXX")
        self.pin = pin_field()
        self.pin2 = pin_field("repeat PIN")
        f = QFormLayout()
        f.addRow("Recovery code:", self.code)
        f.addRow("New PIN:", self.pin)
        f.addRow("Confirm PIN:", self.pin2)
        lay.addLayout(f)
        self.err = _error_label()
        lay.addWidget(self.err)
        b = QPushButton("Set new PIN")
        b.setObjectName("primary")
        b.clicked.connect(self.submit)
        lay.addWidget(b)
        self.setMinimumWidth(400)

    def submit(self):
        try:
            code = auth.reset_pin(self.db, self.uid, self.code.text(), self.pin.text(),
                                  self.pin2.text())
        except auth.AuthError as e:
            self.err.setText(str(e))
            return
        u = self.db.get_user(self.uid)
        QMessageBox.information(self, "PIN changed", "Your PIN has been reset. Your old "
                                "recovery code no longer works — here is a new one.")
        show_recovery_code(self, u["full_name"].split()[0], code)
        self.accept()


class ChangePinDialog(QDialog):
    def __init__(self, parent, db, uid):
        super().__init__(parent)
        self.db, self.uid = db, uid
        self.setWindowTitle("Change PIN")
        lay = QVBoxLayout(self)
        self.old = pin_field("current PIN")
        self.pin = pin_field("new PIN")
        self.pin2 = pin_field("repeat new PIN")
        f = QFormLayout()
        f.addRow("Current PIN:", self.old)
        f.addRow("New PIN:", self.pin)
        f.addRow("Confirm:", self.pin2)
        lay.addLayout(f)
        self.err = _error_label()
        lay.addWidget(self.err)
        b = QPushButton("Change PIN")
        b.setObjectName("primary")
        b.clicked.connect(self.submit)
        lay.addWidget(b)
        self.setMinimumWidth(360)

    def submit(self):
        try:
            auth.change_pin(self.db, self.uid, self.old.text(), self.pin.text(), self.pin2.text())
        except auth.AuthError as e:
            self.err.setText(str(e))
            return
        QMessageBox.information(self, "Change PIN", "PIN changed.")
        self.accept()


def confirm_pin(parent, db, uid, reason):
    """Ask the signed-in user to re-enter their PIN before a sensitive action."""
    d = QDialog(parent)
    d.setWindowTitle("Confirm with your PIN")
    lay = QVBoxLayout(d)
    lay.addWidget(QLabel(reason))
    pin = pin_field("your PIN")
    lay.addWidget(pin)
    err = _error_label()
    lay.addWidget(err)
    b = QPushButton("Confirm")
    b.setObjectName("primary")
    lay.addWidget(b)

    def go():
        try:
            auth.login(db, uid, pin.text())
            d.accept()
        except auth.AuthError as e:
            err.setText(str(e))
            pin.clear()

    b.clicked.connect(go)
    pin.returnPressed.connect(go)
    return d.exec() == QDialog.Accepted


def sign_in(db, parent=None, locked_user=None):
    """Startup gate: register the first user, otherwise ask for a PIN. Returns user row or None."""
    if not db.users():
        d = RegisterDialog(parent, db, first=True)
        if not d.exec():
            return None
        return db.get_user(d.user_id)
    d = LoginDialog(db, locked_user)
    return d.user if d.exec() else None
