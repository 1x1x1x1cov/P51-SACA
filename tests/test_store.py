"""
Data layer: users, passwords, lockout, patients, assessments, legacy import.
Each test uses its own database file, so nothing touches a real SACA database.
"""
import sqlite3

import pytest

import saca_store as store


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SACA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SACA_DB_PATH", str(tmp_path / "saca_app.db"))
    store.init_db()
    return tmp_path


def make_user(name="amina", role="worker", password="Correct-horse-9"):
    user_id, error = store.create_user(name, name.title(), password, role)
    assert error is None, error
    return user_id


# ------------------------------------------------------------------ users
def test_create_user_and_login_round_trip():
    make_user()
    user, error = store.verify_login("amina", "Correct-horse-9")
    assert error is None and user["username"] == "amina" and user["role"] == "worker"


def test_password_is_stored_hashed_not_plain():
    make_user()
    with store.connect() as c:
        stored = c.execute("SELECT password_hash FROM users").fetchone()[0]
    assert "Correct-horse-9" not in stored and stored.startswith("pbkdf2:")


def test_wrong_password_and_unknown_user_look_identical():
    make_user()
    assert store.verify_login("amina", "nope-nope-1") == (None, "invalid")
    assert store.verify_login("nobody", "nope-nope-1") == (None, "invalid")


def test_username_is_case_insensitive_and_unique():
    make_user("Amina")
    _, error = store.create_user("amina", "Other", "Correct-horse-9")
    assert error == "That username is already taken."
    user, _ = store.verify_login("AMINA", "Correct-horse-9")
    assert user is not None


@pytest.mark.parametrize("password", ["short1", "password", "12345678", "aaaaaaaa1"[:0] + "1234567890"])
def test_weak_passwords_are_rejected(password):
    _, error = store.create_user("bob", "Bob", password)
    assert error


def test_password_may_not_equal_username():
    _, error = store.create_user("bobbybob", "Bob", "bobbybob")
    assert error == "The password must be different from the username."


def test_bad_username_is_rejected():
    _, error = store.create_user("a b", "Bob", "Correct-horse-9")
    assert error and "Username" in error


def test_account_locks_after_repeated_failures_even_for_right_password():
    make_user()
    for _ in range(store.MAX_FAILED_LOGINS - 1):
        assert store.verify_login("amina", "wrong-wrong-1")[1] == "invalid"
    assert store.verify_login("amina", "wrong-wrong-1")[1] == "locked"
    assert store.verify_login("amina", "Correct-horse-9")[1] == "locked"


def test_successful_login_resets_failed_attempts():
    make_user()
    store.verify_login("amina", "wrong-wrong-1")
    store.verify_login("amina", "Correct-horse-9")
    with store.connect() as c:
        assert c.execute("SELECT failed_attempts FROM users").fetchone()[0] == 0


def test_inactive_user_cannot_log_in():
    uid = make_user()
    make_user("admin1", "admin")
    assert store.set_active(uid, False) is None
    assert store.verify_login("amina", "Correct-horse-9")[1] == "inactive"


def test_last_active_admin_cannot_be_deactivated():
    admin = make_user("boss", "admin")
    assert "only active administrator" in store.set_active(admin, False)
    make_user("boss2", "admin")
    assert store.set_active(admin, False) is None


def test_set_password_validates_and_works():
    uid = make_user()
    assert store.set_password(uid, "short") is not None
    assert store.set_password(uid, "New-passw0rd!") is None
    assert store.verify_login("amina", "New-passw0rd!")[0] is not None
    assert store.verify_login("amina", "Correct-horse-9")[1] == "invalid"


# --------------------------------------------------------------- patients
from datetime import date

TODAY = date(2026, 10, 29)


def valid_form(**over):
    form = {"full_name": "Juma Mwakyusa", "date_of_birth": "1992-03-14", "sex": "M", "pregnant": "",
            "location": "Mbinga"}
    form.update(over)
    return form


def add_patient(uid=None, **over):
    clean, errors = store.validate_patient(valid_form(**over), today=TODAY)
    assert not errors, errors
    return store.create_patient(clean, uid, registered_by="worker")


def test_patient_code_is_sequential_and_readable():
    uid = make_user()
    a, b = add_patient(uid), add_patient(uid, full_name="Asha")
    assert store.get_patient(a)["patient_code"] == "P-0001"
    assert store.get_patient(b)["patient_code"] == "P-0002"


def test_name_and_date_of_birth_are_required():
    _, errors = store.validate_patient(valid_form(full_name="", date_of_birth=""), today=TODAY)
    assert "full_name" in errors and "date_of_birth" in errors


@pytest.mark.parametrize("dob", ["2027-01-01", "1800-01-01", "14/03/1992", "not a date"])
def test_bad_dates_of_birth_are_rejected(dob):
    _, errors = store.validate_patient(valid_form(date_of_birth=dob), today=TODAY)
    assert "date_of_birth" in errors


def test_age_is_worked_out_from_date_of_birth():
    pid = add_patient(date_of_birth="1992-03-14")
    p = store.get_patient(pid)
    assert p["age_group"] == "adult" and p["age_years"] >= 34 and "years" in p["age_text"]
    assert store.age_on("2024-10-30", TODAY) == (1, 11)
    assert store.age_on("2024-10-29", TODAY) == (2, 0)
    assert store.age_on("2026-10-01", TODAY) == (0, 0)


def test_approximate_age_is_accepted_and_marked_as_estimate():
    clean, errors = store.validate_patient(valid_form(date_of_birth="", approx_age_years="5"), today=TODAY)
    assert not errors and clean["dob_estimated"] == 1
    assert store.age_on(clean["date_of_birth"], TODAY)[0] == 5
    assert store.age_label(clean["date_of_birth"], True, TODAY) == "about 5 years"
    assert store.age_label("2026-05-29", False, TODAY) == "5 months"


def test_approximate_age_is_whole_years_only():
    clean, errors = store.validate_patient(valid_form(date_of_birth="", approx_age_years="0"), today=TODAY)
    assert not errors and clean["dob_estimated"] == 1
    assert store.age_label(clean["date_of_birth"], True, TODAY) == "under 1 year"
    # a months field, if an old form still sends one, is ignored
    clean, errors = store.validate_patient(
        valid_form(date_of_birth="", approx_age_years="3", approx_age_months="7"), today=TODAY)
    assert not errors and store.age_on(clean["date_of_birth"], TODAY)[0] == 3
    _, errors = store.validate_patient(valid_form(date_of_birth="", approx_age_years="2.5"), today=TODAY)
    assert "approx_age_years" in errors


def test_real_date_of_birth_wins_over_approximate_age():
    clean, _ = store.validate_patient(valid_form(date_of_birth="1992-03-14", approx_age_years="5"), today=TODAY)
    assert clean["dob_estimated"] == 0 and clean["date_of_birth"] == "1992-03-14"


def test_bad_approximate_age_is_rejected():
    _, errors = store.validate_patient(valid_form(date_of_birth="", approx_age_years="200"), today=TODAY)
    assert "approx_age_years" in errors


def test_sex_must_be_chosen():
    _, errors = store.validate_patient(valid_form(sex=""), today=TODAY)
    assert "sex" in errors


def test_pregnancy_only_recorded_for_females_of_childbearing_age():
    c, _ = store.validate_patient(valid_form(sex="F", pregnant="yes"), today=TODAY)
    assert c["pregnant"] == 1
    c, _ = store.validate_patient(valid_form(sex="M", pregnant="yes"), today=TODAY)
    assert c["pregnant"] is None
    c, _ = store.validate_patient(valid_form(sex="F", date_of_birth="2018-01-01", pregnant="yes"), today=TODAY)
    assert c["pregnant"] is None
    c, _ = store.validate_patient(valid_form(sex="F", pregnant="no"), today=TODAY)
    assert c["pregnant"] == 0


@pytest.mark.parametrize("age,group", [(0, "infant"), (3, "young_child"), (9, "child"), (30, "adult"), (70, "older_adult")])
def test_age_groups(age, group):
    assert store.age_group(age) == group


# ------------------------------------------------------------------ PINs
def test_profile_with_pin_can_sign_in_and_hash_is_not_exposed():
    clean, errors = store.validate_patient(valid_form(pin="4821", pin_confirm="4821"), require_pin=True, today=TODAY)
    assert not errors
    pid = store.create_patient(clean)
    patient, error = store.verify_pin(pid, "4821")
    assert error is None and patient["has_pin"] is True and "pin_hash" not in patient
    with store.connect() as c:
        assert "4821" not in c.execute("SELECT pin_hash FROM patients").fetchone()[0]


@pytest.mark.parametrize("pin,confirm", [("12", "12"), ("1234", "1234"), ("1111", "1111"), ("abcd", "abcd"),
                                         ("1234567", "1234567"), ("4821", "4822")])
def test_bad_pins_are_rejected(pin, confirm):
    _, errors = store.validate_patient(valid_form(pin=pin, pin_confirm=confirm), require_pin=True, today=TODAY)
    assert "pin" in errors


def test_pin_is_required_when_asked_for():
    _, errors = store.validate_patient(valid_form(), require_pin=True, today=TODAY)
    assert "pin" in errors


def test_wrong_pin_and_lockout():
    clean, _ = store.validate_patient(valid_form(pin="4821", pin_confirm="4821"), today=TODAY)
    pid = store.create_patient(clean)
    for _ in range(store.MAX_FAILED_LOGINS - 1):
        assert store.verify_pin(pid, "0000")[1] == "invalid"
    assert store.verify_pin(pid, "0000")[1] == "locked"
    assert store.verify_pin(pid, "4821")[1] == "locked"


def test_profile_without_pin_cannot_sign_in_itself():
    pid = add_patient()
    assert store.verify_pin(pid, "4821") == (None, "nopin")
    assert store.login_profiles() == []


def test_login_picker_lists_only_pin_profiles_and_no_private_fields():
    clean, _ = store.validate_patient(valid_form(full_name="Mama Amina", pin="4821", pin_confirm="4821"), today=TODAY)
    store.create_patient(clean)
    add_patient()  # registered by a worker, no PIN
    profiles = store.login_profiles()
    assert [p["full_name"] for p in profiles] == ["Mama Amina"]
    assert set(profiles[0]) == {"id", "full_name", "patient_code"}


def test_reset_pin_unlocks_and_validates():
    clean, _ = store.validate_patient(valid_form(pin="4821", pin_confirm="4821"), today=TODAY)
    pid = store.create_patient(clean)
    assert store.reset_pin(pid, "12") is not None
    assert store.reset_pin(pid, "7392") is None
    assert store.verify_pin(pid, "7392")[1] is None


def test_update_patient_keeps_pin_unless_a_new_one_is_given():
    clean, _ = store.validate_patient(valid_form(pin="4821", pin_confirm="4821"), today=TODAY)
    pid = store.create_patient(clean)
    edit, _ = store.validate_patient(valid_form(full_name="Juma M."), today=TODAY)
    store.update_patient(pid, edit)
    assert store.get_patient(pid)["full_name"] == "Juma M."
    assert store.verify_pin(pid, "4821")[1] is None


def test_search_by_code_name_and_place():
    uid = make_user()
    add_patient(uid)
    add_patient(uid, full_name="Asha", location="Songea")
    assert len(store.search_patients("Asha")) == 1
    assert len(store.search_patients("P-0001")) == 1
    assert len(store.search_patients("songea")) == 1
    assert len(store.search_patients("")) == 2


def test_search_treats_wildcards_literally():
    add_patient()
    assert len(store.search_patients("zzz%")) == 0
    assert len(store.search_patients("J_ma")) == 0  # "_" is not a one-character wildcard


# ------------------------------------------------------------ assessments
RESULT = {"severity": "HIGH", "assessed": True, "confidence": 0.81, "reason": "Model predicted HIGH",
          "symptoms": ["chest_pain", "cough"], "red_flag_rules": ["RF05"], "fallback_used": True}


def test_assessment_saved_against_patient_and_user():
    uid = make_user()
    pid = add_patient(uid)
    aid = store.save_assessment(pid, uid, "chest pain and cough", RESULT, "bodymap",
                                conditions=[{"name": "Pneumonia", "percent": 40}], context={"age_group": "adult"})
    got = store.get_assessment(aid)
    assert got["patient_code"] == "P-0001" and got["worker_name"] == "Amina"
    assert got["severity"] == "HIGH" and got["input_mode"] == "bodymap"
    assert got["symptom_list"] == ["chest_pain", "cough"] and got["red_flags"] == ["RF05"]
    assert got["conditions"][0]["name"] == "Pneumonia" and got["context"]["age_group"] == "adult"


def test_assessment_without_patient_is_allowed():
    uid = make_user()
    aid = store.save_assessment(None, uid, "fever", RESULT)
    assert store.get_assessment(aid)["patient_id"] is None


def test_history_is_per_patient_newest_first():
    uid = make_user()
    p1 = add_patient(uid)
    p2 = add_patient(uid, full_name="Asha")
    store.save_assessment(p1, uid, "first", RESULT)
    store.save_assessment(p2, uid, "other patient", RESULT)
    store.save_assessment(p1, uid, "second", RESULT)
    texts = [a["symptom_text"] for a in store.list_assessments(patient_id=p1)]
    assert texts == ["second", "first"]


def test_filters_by_severity_and_text():
    uid = make_user()
    store.save_assessment(None, uid, "cough", {**RESULT, "severity": "LOW"})
    store.save_assessment(None, uid, "chest pain", RESULT)
    assert [a["symptom_text"] for a in store.list_assessments(severity="HIGH")] == ["chest pain"]
    assert [a["symptom_text"] for a in store.list_assessments(query="cough")] == ["cough"]


def test_deleting_a_patient_removes_their_assessments_but_not_others():
    uid = make_user()
    p1 = add_patient(uid)
    store.save_assessment(p1, uid, "mine", RESULT)
    store.save_assessment(None, uid, "unassigned", RESULT)
    store.delete_patient(p1)
    assert store.get_patient(p1) is None
    assert [a["symptom_text"] for a in store.list_assessments()] == ["unassigned"]


def test_severity_counts():
    uid = make_user()
    store.save_assessment(None, uid, "a", {**RESULT, "severity": "LOW"})
    store.save_assessment(None, uid, "b", RESULT)
    store.save_assessment(None, uid, "c", RESULT)
    assert store.severity_counts() == {"LOW": 1, "MEDIUM": 0, "HIGH": 2, "CRITICAL": 0}


def test_note_is_trimmed_and_can_be_cleared():
    uid = make_user()
    aid = store.save_assessment(None, uid, "a", RESULT)
    store.set_assessment_note(aid, "  referred to Mbinga hospital  ")
    assert store.get_assessment(aid)["note"] == "referred to Mbinga hospital"
    store.set_assessment_note(aid, "   ")
    assert store.get_assessment(aid)["note"] is None


# ------------------------------------------------------------ audit + legacy
def test_audit_log_records_actions():
    uid = make_user()
    store.log_event(uid, "login")
    events = store.recent_events()
    assert events[0]["action"] == "login" and events[0]["username"] == "amina"


def test_legacy_history_is_imported_once(tmp_path):
    legacy = sqlite3.connect(tmp_path / "history.db")
    legacy.execute("""CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, symptom_text TEXT,
                      severity TEXT, confidence REAL, reason TEXT, extracted_text TEXT, symptoms TEXT, fallback_used INTEGER)""")
    legacy.execute("INSERT INTO history (created_at, symptom_text, severity, confidence, reason, symptoms, fallback_used) "
                   "VALUES ('2026-10-01T10:00:00+10:00', 'old fever', 'MEDIUM', 0.7, 'old reason', 'high_fever', 1)")
    legacy.commit()
    legacy.close()
    (tmp_path / "saca_app.db").unlink()
    store.init_db()
    store.init_db()  # second run must not import again
    rows = store.list_assessments()
    assert len(rows) == 1 and rows[0]["input_mode"] == "legacy" and rows[0]["patient_id"] is None
    assert rows[0]["symptom_text"] == "old fever"


# ------------------------------------------------------------------ one login form for everyone
def make_profile(name="Mama Neema", pin="2580", sex="F", dob="1990-05-01"):
    clean, errors = store.validate_patient(
        {"full_name": name, "date_of_birth": dob, "sex": sex, "pin": pin, "pin_confirm": pin}, require_pin=True)
    assert not errors, errors
    return store.create_patient(clean)


def test_unified_login_profile_by_name_and_pin():
    pid = make_profile()
    kind, record, err = store.unified_login("  mama neema ", "2580")
    assert (kind, err) == ("profile", None) and record["id"] == pid
    assert "pin_hash" not in record


def test_unified_login_medic_by_username_and_password():
    make_user("nurse.joy", role="worker")
    kind, record, err = store.unified_login("NURSE.JOY", "Correct-horse-9")
    assert kind == "medic" and record["username"] == "nurse.joy" and err is None


def test_unified_login_failures_look_the_same():
    make_profile()
    make_user("nurse.joy")
    assert store.unified_login("Mama Neema", "9999") == (None, None, "invalid")
    assert store.unified_login("nurse.joy", "wrong-pass-1") == (None, None, "invalid")
    assert store.unified_login("nobody", "2580") == (None, None, "invalid")


def test_unified_login_profile_without_pin_cannot_sign_in():
    clean, _ = store.validate_patient({"full_name": "Baba", "date_of_birth": "1980-01-01", "sex": "M"})
    store.create_patient(clean, registered_by="worker")
    assert store.unified_login("Baba", "")[2] == "invalid"


def test_unified_login_profile_lockout():
    make_profile()
    for _ in range(store.MAX_FAILED_LOGINS - 1):
        assert store.unified_login("Mama Neema", "1111")[2] == "invalid"
    assert store.unified_login("Mama Neema", "1111")[2] == "locked"
    assert store.unified_login("Mama Neema", "2580")[2] == "locked"


def test_pin_names_are_unique_and_do_not_clash_with_staff():
    make_profile("Neema")
    assert store.pin_name_problem("neema ")
    assert store.pin_name_problem("Juma") is None
    make_user("juma")
    assert store.pin_name_problem("Juma")
    _, error = store.create_user("neema", "Neema", "Correct-horse-9")
    assert error and "profile" in error


def test_pin_name_check_ignores_own_record():
    pid = make_profile("Neema")
    assert store.pin_name_problem("Neema", exclude_patient_id=pid) is None


# ------------------------------------------------------------------ settings and contacts
def test_settings_round_trip():
    assert store.get_setting("country", "TZ") == "TZ"
    store.set_setting("country", "KE")
    store.set_setting("country", "KE")
    assert store.get_setting("country") == "KE"


def test_default_contacts_seeded_once():
    store.init_db()
    store.init_db()
    tz = store.list_contacts("TZ")
    numbers = [c["number"] for c in tz]
    assert numbers.count("112") == 1 and "114" in numbers and "199" in numbers and "116" in numbers
    ke = [c["number"] for c in store.list_contacts("KE")]
    assert "999 / 112" in ke and "1199" in ke
    for c in tz + store.list_contacts("KE"):
        assert c["source"] and c["checked_on"] and c["name_sw"]


def test_list_contacts_uses_country_setting():
    store.set_setting("country", "KE")
    assert any(c["number"] == "1199" for c in store.list_contacts())


def test_add_and_delete_local_contact():
    cid, err = store.add_contact("TZ", "Mbinga District Hospital", "+255 700 000 000", note_en="Main gate")
    assert err is None
    first = store.list_contacts("TZ")[0]
    assert first["id"] == cid and first["category"] == "local"
    assert store.delete_contact(cid) is None
    assert all(c["id"] != cid for c in store.list_contacts("TZ"))


def test_contact_validation_and_default_protection():
    assert store.add_contact("TZ", "", "123")[1]
    assert store.add_contact("TZ", "Clinic", "call me")[1]
    assert store.add_contact("XX", "Clinic", "123")[1]
    default_id = store.list_contacts("TZ")[0]["id"]
    assert store.delete_contact(default_id) == "National numbers cannot be deleted."
