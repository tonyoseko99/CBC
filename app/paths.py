import os
import sys


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource(rel):
    return os.path.join(getattr(sys, "_MEIPASS", app_dir()), rel)


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".probe")
        open(probe, "w").close()
        os.remove(probe)
        return True
    except OSError:
        return False


def data_dir():
    """'ClassMark Data' next to the exe; falls back to %LOCALAPPDATA% if read-only."""
    d = os.path.join(app_dir(), "ClassMark Data")
    if not _writable(d):
        d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ClassMark")
        os.makedirs(d, exist_ok=True)
    return d


def sub_dir(name):
    d = os.path.join(data_dir(), name)
    os.makedirs(d, exist_ok=True)
    return d


def safe_filename(s):
    return "".join(c if c.isalnum() or c in " -_.()" else "_" for c in s).strip()
