"""ClassMark - offline class teacher assessment system (CBC Junior School)."""
import os
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from app.db import DB
from app.paths import data_dir, sub_dir
from app.ui_auth import sign_in
from app.ui_main import MainWindow, apply_theme


def excepthook(kind, value, tb):
    text = "".join(traceback.format_exception(kind, value, tb))
    try:
        with open(os.path.join(sub_dir("Logs"), "errors.log"), "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass
    QMessageBox.critical(None, "Something went wrong",
                         f"{value}\n\nYour data is safe. Details were saved to the Logs folder.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ClassMark")
    apply_theme(app)
    sys.excepthook = excepthook
    db = DB(os.path.join(data_dir(), "classmark.db"))
    user = sign_in(db)
    if user is None:
        return
    w = MainWindow(db, user)
    w.resize(1360, 820)
    w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
