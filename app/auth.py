"""User accounts: registration, PIN login with lockout, recovery codes. Max 2 users."""
import hashlib
import hmac
import math
import secrets
import time

MAX_USERS = 2
PIN_MIN, PIN_MAX = 4, 6
MAX_TRIES = 5          # wrong PINs before a temporary lock
LOCK_SECONDS = 60      # doubles with each further lock
ITERATIONS = 200_000


class AuthError(Exception):
    pass


def _hash(secret, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"{salt}${dk.hex()}"


def _check(secret, stored):
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(_hash(secret, salt), stored)


def _norm_code(code):
    return "".join(c for c in code.upper() if c.isalnum())


def new_recovery_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def validate_pin(pin, confirm=None):
    if not pin.isdigit() or not PIN_MIN <= len(pin) <= PIN_MAX:
        raise AuthError(f"PIN must be {PIN_MIN}-{PIN_MAX} digits.")
    if len(set(pin)) == 1 or pin in "0123456789" or pin in "9876543210":
        raise AuthError("PIN is too easy to guess (e.g. 1111 or 1234). Choose another.")
    if confirm is not None and pin != confirm:
        raise AuthError("The two PINs do not match.")


def can_register(db):
    return len(db.users()) < MAX_USERS


def register(db, username, full_name, pin, confirm):
    """Create a user. Returns (user_id, recovery_code) — show the code once."""
    username = username.strip()
    if not can_register(db):
        raise AuthError(f"This system allows only {MAX_USERS} users.")
    if len(username) < 3 or not username.replace(".", "").replace("_", "").isalnum():
        raise AuthError("Username must be at least 3 letters/numbers (no spaces).")
    if any(u["username"].lower() == username.lower() for u in db.users()):
        raise AuthError("That username is already taken.")
    if not full_name.strip():
        raise AuthError("Please enter your full name.")
    validate_pin(pin, confirm)
    code = new_recovery_code()
    uid = db.add_user(username, " ".join(full_name.split()), _hash(pin), _hash(_norm_code(code)))
    return uid, code


def _locked_message(seconds):
    return f"Too many wrong PINs. Try again in {math.ceil(seconds)} seconds."


def login(db, uid, pin):
    u = db.get_user(uid)
    if not u:
        raise AuthError("Unknown user.")
    now = time.time()
    if u["locked_until"] and u["locked_until"] > now:
        raise AuthError(_locked_message(u["locked_until"] - now))
    if _check(pin, u["pin_hash"]):
        db.update_user(uid, failed=0, locked_until=0)
        return db.get_user(uid)
    failed = (u["failed"] or 0) + 1
    if failed % MAX_TRIES == 0:
        wait = LOCK_SECONDS * 2 ** (failed // MAX_TRIES - 1)
        db.update_user(uid, failed=failed, locked_until=now + wait)
        raise AuthError(_locked_message(wait))
    db.update_user(uid, failed=failed)
    left = MAX_TRIES - failed % MAX_TRIES
    raise AuthError(f"Wrong PIN. {left} attempt{'s' if left > 1 else ''} left before a lock.")


def change_pin(db, uid, old, new, confirm):
    login(db, uid, old)
    validate_pin(new, confirm)
    db.update_user(uid, pin_hash=_hash(new))


def reset_pin(db, uid, recovery_code, new, confirm):
    """Forgot PIN: verify recovery code, set new PIN. Returns a NEW recovery code."""
    u = db.get_user(uid)
    now = time.time()
    if u["locked_until"] and u["locked_until"] > now:
        raise AuthError(_locked_message(u["locked_until"] - now))
    if not _check(_norm_code(recovery_code), u["recovery_hash"]):
        failed = (u["failed"] or 0) + 1
        lock = now + LOCK_SECONDS if failed % MAX_TRIES == 0 else 0
        db.update_user(uid, failed=failed, locked_until=lock)
        raise AuthError("Recovery code is not correct.")
    validate_pin(new, confirm)
    code = new_recovery_code()
    db.update_user(uid, pin_hash=_hash(new), recovery_hash=_hash(_norm_code(code)),
                   failed=0, locked_until=0)
    return code
