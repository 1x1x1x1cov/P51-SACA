"""
SACA local data store (SQLite, fully offline).

Holds the things that make SACA an application rather than a single page:
health-worker accounts, patient records, and every assessment linked to the
patient and the person who ran it.

Privacy notes (read before real use)
  * Data stays in one file on the device: %LOCALAPPDATA%\\SACA\\saca_app.db
    (or ~/SACA/saca_app.db). Set SACA_DATA_DIR or SACA_DB_PATH to move it.
  * The file is NOT encrypted at rest. Anyone with access to the computer's
    files can read it. Use disk encryption (BitLocker) on any device that holds
    real patient data, and prefer a patient code over a full name.
  * Passwords are stored only as salted hashes.
  * The audit log records who did what, never symptom text.
"""
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 5
MIN_PASSWORD_LENGTH = 8
PASSWORD_METHOD = "pbkdf2:sha256:600000"

ROLES = ("admin", "worker")
SEXES = ("F", "M", "U")
INPUT_MODES = ("typed", "bodymap", "pictures", "voice", "legacy")

_WEAK_PASSWORDS = {
    "password", "password1", "12345678", "123456789", "1234567890", "qwerty123",
    "admin123", "saca1234", "sacasaca", "letmein1", "11111111", "00000000",
}


# --------------------------------------------------------------------------
# Paths and connection
# --------------------------------------------------------------------------
def data_dir():
    base = os.environ.get("SACA_DATA_DIR")
    if not base:
        base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SACA")
    os.makedirs(base, exist_ok=True)
    return base


def db_path():
    return os.environ.get("SACA_DB_PATH") or os.path.join(data_dir(), "saca_app.db")


@contextmanager
def connect():
    """Open the database for one unit of work: commits on success, rolls back on error, always closes."""
    path = db_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name    TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'worker',
    active          INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code    TEXT UNIQUE,
    full_name       TEXT NOT NULL,
    date_of_birth   TEXT NOT NULL,
    dob_estimated   INTEGER NOT NULL DEFAULT 0,
    sex             TEXT NOT NULL DEFAULT 'U',
    pregnant        INTEGER,
    location        TEXT,
    pin_hash        TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    registered_by   TEXT NOT NULL DEFAULT 'self',
    created_at      TEXT NOT NULL,
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id         INTEGER REFERENCES patients(id) ON DELETE CASCADE,
    user_id            INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at         TEXT NOT NULL,
    input_mode         TEXT NOT NULL DEFAULT 'typed',
    symptom_text       TEXT NOT NULL,
    severity           TEXT,
    assessed           INTEGER NOT NULL DEFAULT 1,
    confidence         REAL,
    reason             TEXT,
    symptoms           TEXT,
    extracted_text     TEXT,
    fallback_used      INTEGER NOT NULL DEFAULT 0,
    raised_by_raw_text INTEGER NOT NULL DEFAULT 0,
    red_flag_rules     TEXT,
    conditions_json    TEXT,
    context_json       TEXT,
    note               TEXT
);

CREATE INDEX IF NOT EXISTS idx_assessments_patient ON assessments(patient_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_assessments_created ON assessments(id DESC);

CREATE TABLE IF NOT EXISTS contacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    country     TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'local',
    name_en     TEXT NOT NULL,
    name_sw     TEXT NOT NULL,
    number      TEXT NOT NULL,
    note_en     TEXT,
    note_sw     TEXT,
    source      TEXT,
    checked_on  TEXT,
    is_default  INTEGER NOT NULL DEFAULT 0,
    sort        INTEGER NOT NULL DEFAULT 100,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      TEXT NOT NULL,
    user_id INTEGER,
    action  TEXT NOT NULL,
    detail  TEXT
);
"""


def init_db():
    with connect() as connection:
        connection.executescript(SCHEMA)
    seed_default_contacts()
    import_legacy_history()


def get_setting(key, default=None):
    with connect() as connection:
        row = connection.execute("SELECT value FROM meta WHERE key = ?", ("setting:" + key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with connect() as connection:
        connection.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                           "ON CONFLICT(key) DO UPDATE SET value = excluded.value", ("setting:" + key, value))


def import_legacy_history():
    """One-off import of the old history.db rows (pre-login versions) as unassigned assessments."""
    with connect() as connection:
        done = connection.execute("SELECT value FROM meta WHERE key = 'legacy_history_imported'").fetchone()
        if done:
            return 0

        legacy_path = os.path.join(data_dir(), "history.db")
        imported = 0
        if os.path.exists(legacy_path) and os.path.abspath(legacy_path) != os.path.abspath(db_path()):
            try:
                legacy = sqlite3.connect(legacy_path)
                legacy.row_factory = sqlite3.Row
                rows = legacy.execute("SELECT * FROM history ORDER BY id").fetchall()
                legacy.close()
            except sqlite3.Error:
                rows = []
            for row in rows:
                row = dict(row)
                connection.execute(
                    """INSERT INTO assessments
                       (patient_id, user_id, created_at, input_mode, symptom_text, severity, assessed,
                        confidence, reason, symptoms, extracted_text, fallback_used)
                       VALUES (NULL, NULL, ?, 'legacy', ?, ?, 1, ?, ?, ?, ?, ?)""",
                    (row.get("created_at") or now_iso(), row.get("symptom_text") or "",
                     row.get("severity"), row.get("confidence"), row.get("reason"),
                     row.get("symptoms"), row.get("extracted_text"), int(bool(row.get("fallback_used")))),
                )
                imported += 1
        connection.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('legacy_history_imported', ?)",
                           (str(imported),))
        return imported


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------
def log_event(user_id, action, detail=""):
    with connect() as connection:
        connection.execute(
            "INSERT INTO audit_log (at, user_id, action, detail) VALUES (?, ?, ?, ?)",
            (now_iso(), user_id, action, (detail or "")[:200]),
        )


def recent_events(limit=50):
    with connect() as connection:
        rows = connection.execute(
            """SELECT a.id, a.at, a.action, a.detail, u.username
               FROM audit_log a LEFT JOIN users u ON u.id = a.user_id
               ORDER BY a.id DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Users and passwords
# --------------------------------------------------------------------------
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")


def validate_password(password, username=""):
    """Return an error message, or None if the password is acceptable."""
    if password is None or len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > 200:
        return "That password is too long."
    if password.lower() in _WEAK_PASSWORDS:
        return "That password is too easy to guess."
    if username and password.lower() == username.lower():
        return "The password must be different from the username."
    if password.isdigit():
        return "Add some letters as well as numbers."
    return None


def user_count():
    with connect() as connection:
        return connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(username, display_name, password, role="worker"):
    """Create a user. Returns (user_id, error). error is a message or None."""
    username = (username or "").strip()
    display_name = (display_name or "").strip() or username
    if not USERNAME_RE.match(username):
        return None, "Username must be 3 to 32 letters, numbers, dots, dashes or underscores."
    if role not in ROLES:
        return None, "Unknown role."
    problem = validate_password(password, username)
    if problem:
        return None, problem
    with connect() as connection:
        if connection.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            return None, "That username is already taken."
        if connection.execute("SELECT 1 FROM patients WHERE pin_hash IS NOT NULL AND TRIM(full_name) = ? COLLATE NOCASE",
                              (username,)).fetchone():
            return None, "A personal profile on this device already uses that name. Choose another username."
        cursor = connection.execute(
            """INSERT INTO users (username, display_name, password_hash, role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (username, display_name[:60], generate_password_hash(password, method=PASSWORD_METHOD),
             role, now_iso()),
        )
        return cursor.lastrowid, None


def get_user(user_id):
    if user_id is None:
        return None
    with connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users():
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, username, display_name, role, active, created_at, last_login_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def verify_login(username, password):
    """
    Check a login. Returns (user_dict, None) on success, or (None, code) where code is one of
    'invalid', 'locked', 'inactive'. A wrong password and an unknown username give the same code.
    """
    username = (username or "").strip()
    with connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            # Spend similar time as a real check so the response time does not reveal valid usernames.
            check_password_hash(generate_password_hash("x", method="pbkdf2:sha256:1000"), password or "")
            return None, "invalid"
        user = dict(row)

        if user["locked_until"]:
            try:
                if datetime.fromisoformat(user["locked_until"]) > datetime.now().astimezone():
                    return None, "locked"
            except ValueError:
                pass

        if not check_password_hash(user["password_hash"], password or ""):
            attempts = user["failed_attempts"] + 1
            locked_until = None
            if attempts >= MAX_FAILED_LOGINS:
                locked_until = (datetime.now().astimezone() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
                attempts = 0
            connection.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                               (attempts, locked_until, user["id"]))
            return None, ("locked" if locked_until else "invalid")

        if not user["active"]:
            return None, "inactive"

        connection.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
            (now_iso(), user["id"]))
        user["failed_attempts"] = 0
        return user, None


def set_password(user_id, new_password):
    user = get_user(user_id)
    if user is None:
        return "No such user."
    problem = validate_password(new_password, user["username"])
    if problem:
        return problem
    with connect() as connection:
        connection.execute(
            "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (generate_password_hash(new_password, method=PASSWORD_METHOD), user_id))
    return None


def check_password(user_id, password):
    user = get_user(user_id)
    return bool(user) and check_password_hash(user["password_hash"], password or "")


def set_active(user_id, active):
    """Activate or deactivate an account. The last active admin cannot be deactivated."""
    user = get_user(user_id)
    if user is None:
        return "No such user."
    with connect() as connection:
        if not active and user["role"] == "admin":
            others = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1 AND id != ?", (user_id,)
            ).fetchone()[0]
            if others == 0:
                return "You cannot deactivate the only active administrator."
        connection.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
    return None


# --------------------------------------------------------------------------
# Patients (people with a profile on this device)
# --------------------------------------------------------------------------
PIN_MIN, PIN_MAX = 4, 6


def _today():
    return date.today()


def age_on(date_of_birth, today=None):
    """Age as (years, months) for an ISO date of birth. Returns (None, None) if the date is unusable."""
    today = today or _today()
    try:
        born = date.fromisoformat(date_of_birth)
    except (TypeError, ValueError):
        return None, None
    months = (today.year - born.year) * 12 + (today.month - born.month) - (1 if today.day < born.day else 0)
    months = max(months, 0)
    return months // 12, months % 12


def age_group(age_years):
    """A coarse age band used for guidance wording (the model itself does not use age)."""
    if age_years is None:
        return "unknown"
    if age_years < 1:
        return "infant"
    if age_years < 5:
        return "young_child"
    if age_years < 15:
        return "child"
    if age_years >= 65:
        return "older_adult"
    return "adult"


def age_label(date_of_birth, estimated=False, today=None):
    years, months = age_on(date_of_birth, today)
    if years is None:
        return ""
    if estimated:
        # an estimate is whole years only
        return "under 1 year" if years < 1 else f"about {years} years"
    if years < 2:
        return f"{years * 12 + months} months"
    return f"{years} years"


def _weak_pin(pin):
    if len(set(pin)) == 1:
        return True
    return pin in ("1234", "12345", "123456", "4321", "54321", "654321", "0123", "01234", "012345")


def validate_pin(pin, confirm=None):
    """Return an error message, or None."""
    pin = (pin or "").strip()
    if not pin.isdigit() or not PIN_MIN <= len(pin) <= PIN_MAX:
        return f"The PIN must be {PIN_MIN} to {PIN_MAX} numbers."
    if _weak_pin(pin):
        return "That PIN is too easy to guess. Avoid repeats and 1234."
    if confirm is not None and pin != (confirm or "").strip():
        return "The two PINs do not match."
    return None


def validate_patient(form, require_pin=False, today=None):
    """
    Validate a profile form. Returns (clean_dict, errors_dict).
    Date of birth is preferred; if it is not known, an approximate age (years and/or months) is accepted
    and the profile is marked as an estimate.
    """
    today = today or _today()
    errors, clean = {}, {}

    name = (form.get("full_name") or "").strip()
    if not name:
        errors["full_name"] = "Please enter a name (a first name or nickname is enough)."
    elif len(name) > 80:
        errors["full_name"] = "Keep the name under 80 characters."
    clean["full_name"] = name

    dob_text = (form.get("date_of_birth") or "").strip()
    approx_years = (form.get("approx_age_years") or "").strip()
    clean["dob_estimated"] = 0
    if dob_text:
        try:
            born = date.fromisoformat(dob_text)
            if born > today:
                errors["date_of_birth"] = "The date of birth cannot be in the future."
            elif (today - born).days > 120 * 366:
                errors["date_of_birth"] = "Please check the year of birth."
            else:
                clean["date_of_birth"] = born.isoformat()
        except ValueError:
            errors["date_of_birth"] = "Enter the date of birth as day, month and year."
    elif approx_years:
        # Age in whole years only (asking for months as well was extra work for little gain).
        try:
            years = int(approx_years)
            if not 0 <= years <= 120:
                raise ValueError
            born = today - timedelta(days=round(years * 365.25))
            clean["date_of_birth"] = born.isoformat()
            clean["dob_estimated"] = 1
        except ValueError:
            errors["approx_age_years"] = "Enter the age in whole years (0 to 120). Enter 0 for a baby under 1 year."
    else:
        errors["date_of_birth"] = "Enter the date of birth, or an approximate age if it is not known."

    sex = (form.get("sex") or "").strip().upper()
    if sex not in SEXES:
        errors["sex"] = "Please choose female, male or prefer not to say."
        sex = "U"
    clean["sex"] = sex

    years, _ = age_on(clean.get("date_of_birth"), today)
    pregnant = (form.get("pregnant") or "").strip().lower()
    if sex == "F" and years is not None and 10 <= years <= 55:
        clean["pregnant"] = {"yes": 1, "1": 1, "no": 0, "0": 0}.get(pregnant)
    else:
        clean["pregnant"] = None

    location = (form.get("location") or "").strip()
    if len(location) > 80:
        errors["location"] = "Keep the place under 80 characters."
    clean["location"] = location or None

    clean["pin"] = None
    pin = (form.get("pin") or "").strip()
    if require_pin or pin:
        problem = validate_pin(pin, form.get("pin_confirm"))
        if problem:
            errors["pin"] = problem
        else:
            clean["pin"] = pin
    return clean, errors


def create_patient(clean, user_id=None, registered_by="self"):
    stamp = now_iso()
    pin_hash = generate_password_hash(clean["pin"], method=PASSWORD_METHOD) if clean.get("pin") else None
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO patients (patient_code, full_name, date_of_birth, dob_estimated, sex, pregnant, location,
                                     pin_hash, registered_by, created_at, created_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("tmp-" + secrets.token_hex(4), clean["full_name"], clean["date_of_birth"], clean["dob_estimated"],
             clean["sex"], clean["pregnant"], clean["location"], pin_hash, registered_by, stamp, user_id, stamp))
        patient_id = cursor.lastrowid
        connection.execute("UPDATE patients SET patient_code = ? WHERE id = ?",
                           (f"P-{patient_id:04d}", patient_id))
    return patient_id


def update_patient(patient_id, clean):
    with connect() as connection:
        connection.execute(
            """UPDATE patients SET full_name = ?, date_of_birth = ?, dob_estimated = ?, sex = ?, pregnant = ?,
                                   location = ?, updated_at = ? WHERE id = ?""",
            (clean["full_name"], clean["date_of_birth"], clean["dob_estimated"], clean["sex"], clean["pregnant"],
             clean["location"], now_iso(), patient_id))
        if clean.get("pin"):
            connection.execute("UPDATE patients SET pin_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
                               (generate_password_hash(clean["pin"], method=PASSWORD_METHOD), patient_id))


def _decorate_patient(row):
    patient = dict(row)
    patient["has_pin"] = bool(patient.get("pin_hash"))
    patient.pop("pin_hash", None)
    years, months = age_on(patient["date_of_birth"])
    patient["age_years"], patient["age_months"] = years, months
    patient["age_group"] = age_group(years)
    patient["age_text"] = age_label(patient["date_of_birth"], bool(patient["dob_estimated"]))
    return patient


def get_patient(patient_id):
    with connect() as connection:
        row = connection.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return _decorate_patient(row) if row else None


def set_pregnancy(patient_id, pregnant):
    with connect() as connection:
        connection.execute("UPDATE patients SET pregnant = ?, updated_at = ? WHERE id = ?",
                           (None if pregnant is None else int(bool(pregnant)), now_iso(), patient_id))


def verify_pin(patient_id, pin):
    """Check a profile PIN. Returns (patient_dict, None) or (None, 'invalid' | 'locked' | 'nopin')."""
    with connect() as connection:
        row = connection.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if row is None:
            return None, "invalid"
        if not row["pin_hash"]:
            return None, "nopin"
        if row["locked_until"]:
            try:
                if datetime.fromisoformat(row["locked_until"]) > datetime.now().astimezone():
                    return None, "locked"
            except ValueError:
                pass
        if not check_password_hash(row["pin_hash"], (pin or "").strip()):
            attempts = row["failed_attempts"] + 1
            locked_until = None
            if attempts >= MAX_FAILED_LOGINS:
                locked_until = (datetime.now().astimezone() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
                attempts = 0
            connection.execute("UPDATE patients SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                               (attempts, locked_until, patient_id))
            return None, ("locked" if locked_until else "invalid")
        connection.execute("UPDATE patients SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (patient_id,))
    return get_patient(patient_id), None


def reset_pin(patient_id, new_pin):
    problem = validate_pin(new_pin)
    if problem:
        return problem
    with connect() as connection:
        connection.execute("UPDATE patients SET pin_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
                           (generate_password_hash(new_pin.strip(), method=PASSWORD_METHOD), patient_id))
    return None


def login_profiles():
    """Profiles that can sign themselves in (they have a PIN), for the profile picker. No private fields."""
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, full_name, patient_code FROM patients WHERE pin_hash IS NOT NULL ORDER BY full_name COLLATE NOCASE"
        ).fetchall()
    return [dict(r) for r in rows]


def pin_name_problem(name, exclude_patient_id=None):
    """
    A profile that signs in with name + PIN needs a name nobody else on this device signs in with,
    so that a login is never ambiguous. Returns an error message or None.
    """
    name = (name or "").strip()
    with connect() as connection:
        if connection.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone():
            return "That name is used by a staff account on this device. Add a surname or initial."
        row = connection.execute(
            "SELECT id FROM patients WHERE pin_hash IS NOT NULL AND TRIM(full_name) = ? COLLATE NOCASE AND id != ?",
            (name, exclude_patient_id or -1)).fetchone()
    if row:
        return "Someone on this device already signs in with that name. Add a surname or initial."
    return None


def find_pin_profile(name):
    name = (name or "").strip()
    if not name:
        return None
    with connect() as connection:
        row = connection.execute(
            "SELECT id FROM patients WHERE pin_hash IS NOT NULL AND TRIM(full_name) = ? COLLATE NOCASE "
            "ORDER BY id LIMIT 1", (name,)).fetchone()
    return row["id"] if row else None


def unified_login(name, secret):
    """
    One login form for everyone: "name or username" + "PIN or password".
    Returns (kind, record, None) with kind 'medic' or 'profile', or (None, None, code) with code
    'invalid' | 'locked' | 'inactive'. Staff usernames are checked first; names are unique across both.
    """
    name = (name or "").strip()
    with connect() as connection:
        is_user = connection.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone() is not None
    if is_user:
        user, problem = verify_login(name, secret)
        return ("medic", user, None) if user else (None, None, problem)
    patient_id = find_pin_profile(name)
    if patient_id is None:
        check_password_hash(generate_password_hash("x", method="pbkdf2:sha256:1000"), secret or "")
        return None, None, "invalid"
    patient, problem = verify_pin(patient_id, secret)
    if patient:
        return "profile", patient, None
    return None, None, ("invalid" if problem == "nopin" else problem)


def search_patients(query="", limit=100):
    query = (query or "").strip()
    sql = """SELECT p.*,
                    (SELECT COUNT(*) FROM assessments a WHERE a.patient_id = p.id) AS assessment_count,
                    (SELECT severity FROM assessments a WHERE a.patient_id = p.id ORDER BY a.id DESC LIMIT 1) AS last_severity,
                    (SELECT created_at FROM assessments a WHERE a.patient_id = p.id ORDER BY a.id DESC LIMIT 1) AS last_assessed
             FROM patients p"""
    params = []
    if query:
        like = "%" + query.replace("%", "").replace("_", "") + "%"
        sql += " WHERE p.patient_code LIKE ? OR p.full_name LIKE ? OR IFNULL(p.location, '') LIKE ?"
        params += [like, like, like]
    sql += " ORDER BY p.id DESC LIMIT ?"
    params.append(limit)
    with connect() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_decorate_patient(r) | {"assessment_count": r["assessment_count"], "last_severity": r["last_severity"],
                                    "last_assessed": r["last_assessed"]} for r in rows]


def delete_patient(patient_id):
    """Permanently delete a patient and all of their assessments."""
    with connect() as connection:
        connection.execute("DELETE FROM assessments WHERE patient_id = ?", (patient_id,))
        connection.execute("DELETE FROM patients WHERE id = ?", (patient_id,))


def patient_count():
    with connect() as connection:
        return connection.execute("SELECT COUNT(*) FROM patients").fetchone()[0]


# --------------------------------------------------------------------------
# Assessments
# --------------------------------------------------------------------------
def _row_to_assessment(row):
    item = dict(row)
    item["conditions"] = json.loads(item["conditions_json"]) if item.get("conditions_json") else []
    item["context"] = json.loads(item["context_json"]) if item.get("context_json") else {}
    item["symptom_list"] = [s.strip() for s in (item.get("symptoms") or "").split(",") if s.strip()]
    item["red_flags"] = [s.strip() for s in (item.get("red_flag_rules") or "").split(",") if s.strip()]
    return item


def save_assessment(patient_id, user_id, symptom_text, result, input_mode="typed", conditions=None, context=None):
    if input_mode not in INPUT_MODES:
        input_mode = "typed"
    rules = result.get("red_flag_rules") or []
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO assessments
               (patient_id, user_id, created_at, input_mode, symptom_text, severity, assessed, confidence,
                reason, symptoms, extracted_text, fallback_used, raised_by_raw_text, red_flag_rules,
                conditions_json, context_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, user_id, now_iso(), input_mode, symptom_text, result.get("severity"),
             int(bool(result.get("assessed", True))), result.get("confidence"), result.get("reason"),
             ", ".join(str(s) for s in result.get("symptoms", [])), result.get("extracted_text"),
             int(bool(result.get("fallback_used"))), int(bool(result.get("raised_by_raw_text"))),
             ", ".join(str(r) for r in rules),
             json.dumps(conditions or []), json.dumps(context or {})))
        return cursor.lastrowid


def get_assessment(assessment_id):
    with connect() as connection:
        row = connection.execute(
            """SELECT a.*, p.patient_code, p.full_name, p.date_of_birth, p.dob_estimated, p.sex, p.pregnant AS patient_pregnant,
                      p.location, u.display_name AS worker_name
               FROM assessments a
               LEFT JOIN patients p ON p.id = a.patient_id
               LEFT JOIN users u ON u.id = a.user_id
               WHERE a.id = ?""", (assessment_id,)).fetchone()
    return _row_to_assessment(row) if row else None


def list_assessments(limit=100, patient_id=None, severity=None, query=None):
    sql = """SELECT a.*, p.patient_code, p.full_name, u.display_name AS worker_name
             FROM assessments a
             LEFT JOIN patients p ON p.id = a.patient_id
             LEFT JOIN users u ON u.id = a.user_id"""
    where, params = [], []
    if patient_id is not None:
        where.append("a.patient_id = ?")
        params.append(patient_id)
    if severity:
        where.append("a.severity = ?")
        params.append(severity)
    if query:
        like = "%" + query.replace("%", "").replace("_", "") + "%"
        where.append("(IFNULL(p.patient_code, '') LIKE ? OR IFNULL(p.full_name, '') LIKE ? OR a.symptom_text LIKE ?)")
        params += [like, like, like]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.id DESC LIMIT ?"
    params.append(limit)
    with connect() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_row_to_assessment(r) for r in rows]


def set_assessment_note(assessment_id, note):
    with connect() as connection:
        connection.execute("UPDATE assessments SET note = ? WHERE id = ?", ((note or "").strip()[:500] or None, assessment_id))


def severity_counts(days=None):
    sql = "SELECT severity, COUNT(*) AS n FROM assessments"
    params = []
    if days:
        since = (datetime.now().astimezone() - timedelta(days=days)).isoformat(timespec="seconds")
        sql += " WHERE created_at >= ?"
        params.append(since)
    sql += " GROUP BY severity"
    with connect() as connection:
        rows = connection.execute(sql, params).fetchall()
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for row in rows:
        if row["severity"] in counts:
            counts[row["severity"]] = row["n"]
    return counts


# --------------------------------------------------------------------------
# Contacts ("Contact community")
# --------------------------------------------------------------------------
COUNTRIES = {"TZ": "Tanzania", "KE": "Kenya"}
DEFAULT_COUNTRY = "TZ"   # keywords.py: Mbinga District, Ruvuma Region, Tanzania
CONTACT_CATEGORIES = ("emergency", "health", "support", "local")
CONTACTS_CHECKED_ON = "2026-10-29"

# National numbers, each checked against the source named. Numbers change: re-check before a real deployment.
DEFAULT_CONTACTS = [
    # Tanzania
    ("TZ", "emergency", "Police and general emergency", "Polisi na dharura", "112",
     "Free. May not connect everywhere outside big towns. If it fails, go straight to the nearest health facility.",
     "Bure. Huenda isipatikane kila mahali nje ya miji mikubwa. Ikishindikana, nenda moja kwa moja kituo cha afya kilicho karibu.",
     "France Diplomatie, Tanzania 'In case of emergency' (updated 8 Jan 2026); Trek Medics Tanzania programme page", 10),
    ("TZ", "emergency", "Fire and rescue", "Zimamoto na uokoaji", "114", "", "",
     "France Diplomatie, Tanzania 'In case of emergency' (updated 8 Jan 2026); Trek Medics Tanzania programme page", 20),
    ("TZ", "health", "Afya Call Center (Ministry of Health)", "Afya Call Center (Wizara ya Afya)", "199",
     "Free, 24 hours. Health advice from doctors and nurses, and where to go for care.",
     "Bure, saa 24. Ushauri wa afya kutoka kwa madaktari na wauguzi, na mahali pa kupata huduma.",
     "VillageReach, 'Tanzania's Afya Call Center' (18 Aug 2025); findahelpline.com (verified by moh.go.tz)", 30),
    ("TZ", "support", "National Child Helpline (C-Sema)", "Simu ya Msaada kwa Mtoto (C-Sema)", "116",
     "Free. For children at risk and the adults worried about them.",
     "Bure. Kwa watoto walio hatarini na watu wazima wanaowajali.",
     "C-Sema (sematanzania.org)", 40),
    # Kenya
    ("KE", "emergency", "Police and general emergency", "Polisi na dharura", "999 / 112",
     "Free from any phone.", "Bure kutoka simu yoyote.",
     "HapaKenya, 'How to contact emergency services' (9 Mar 2026)", 10),
    ("KE", "emergency", "Kenya Red Cross (emergencies and counselling)", "Shirika la Msalaba Mwekundu Kenya (dharura na ushauri)", "1199",
     "Toll free.", "Bila malipo.",
     "Kenya Red Cross contact page (redcross.or.ke): 'Toll Free: 1199'", 20),
    ("KE", "support", "Gender-based violence helpline", "Simu ya msaada wa ukatili wa kijinsia", "1195",
     "Toll free, 24 hours.", "Bila malipo, saa 24.",
     "UN Women Africa, 'Kenya's national toll-free helpline 1195' (Oct 2024)", 30),
    ("KE", "support", "Childline Kenya", "Childline Kenya", "116",
     "Toll free, 24 hours.", "Bila malipo, saa 24.",
     "Child Helpline International, Childline Kenya page", 40),
]


def seed_default_contacts():
    """Insert the national numbers once. Re-running does not duplicate them."""
    with connect() as connection:
        if connection.execute("SELECT 1 FROM meta WHERE key = 'contacts_seeded'").fetchone():
            return
        for (country, category, name_en, name_sw, number, note_en, note_sw, source, sort) in DEFAULT_CONTACTS:
            connection.execute(
                """INSERT INTO contacts (country, category, name_en, name_sw, number, note_en, note_sw, source,
                                         checked_on, is_default, sort)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (country, category, name_en, name_sw, number, note_en or None, note_sw or None, source,
                 CONTACTS_CHECKED_ON, sort))
        connection.execute("INSERT INTO meta (key, value) VALUES ('contacts_seeded', ?)", (now_iso(),))


def list_contacts(country=None):
    country = country or get_setting("country", DEFAULT_COUNTRY)
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM contacts WHERE country = ? ORDER BY CASE category WHEN 'local' THEN 0 ELSE 1 END, sort, id",
            (country,)).fetchall()
    return [dict(r) for r in rows]


PHONE_RE = re.compile(r"^[0-9+ ()/-]{3,25}$")


def add_contact(country, name_en, number, name_sw="", note_en="", note_sw="", user_id=None):
    """Add a local contact (clinic, community health worker, transport). Returns (id, error)."""
    name_en = (name_en or "").strip()
    number = (number or "").strip()
    if country not in COUNTRIES:
        return None, "Unknown country."
    if not name_en or len(name_en) > 80:
        return None, "Enter a name (under 80 characters)."
    if not PHONE_RE.match(number):
        return None, "Enter a phone number using digits, spaces, + or -."
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO contacts (country, category, name_en, name_sw, number, note_en, note_sw, source,
                                     checked_on, is_default, sort, created_by)
               VALUES (?, 'local', ?, ?, ?, ?, ?, 'Added on this device', ?, 0, 5, ?)""",
            (country, name_en, (name_sw or "").strip() or name_en, number, (note_en or "").strip()[:200] or None,
             (note_sw or "").strip()[:200] or None, date.today().isoformat(), user_id))
        return cursor.lastrowid, None


def delete_contact(contact_id):
    """Delete a contact added on this device. National default numbers cannot be deleted."""
    with connect() as connection:
        row = connection.execute("SELECT is_default FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if row is None:
            return "No such contact."
        if row["is_default"]:
            return "National numbers cannot be deleted."
        connection.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    return None
