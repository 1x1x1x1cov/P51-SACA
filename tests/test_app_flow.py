"""
End-to-end tests of the SACA app through Flask's test client: sign-in kinds, who can see what, the quiz,
the result cards, contacts, security. Uses the real classifier (no LLM extractor, no network) and a fresh
database per test.
"""
import importlib.util
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import saca_store as store  # noqa: E402
from classifier.pipeline import SACAPipeline  # noqa: E402


def _load_app_module():
    spec = importlib.util.spec_from_file_location("saca_app_entry", ROOT / "logistic_regression.app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pipeline():
    p = SACAPipeline()
    p.classifier.train()
    return p


@pytest.fixture
def app(tmp_path, monkeypatch, pipeline):
    monkeypatch.setenv("SACA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SACA_DB_PATH", str(tmp_path / "saca_app.db"))
    monkeypatch.setenv("SACA_SECRET_KEY", "test-secret-key-" + "x" * 40)
    module = _load_app_module()
    application = module.create_app(pipeline=pipeline, config={"TESTING": True})
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def token(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, f"no CSRF token on {path}"
    return m.group(1)


def as_guest(client):
    r = client.post("/guest", data={"csrf_token": token(client)})
    assert r.status_code == 302


def make_admin(username="admin1", password="Clinic-pass-77"):
    uid, err = store.create_user(username, "Admin One", password, role="admin")
    assert err is None
    return uid


def make_profile(name="Mama Neema", pin="2580", sex="F", dob="1990-05-01"):
    clean, errors = store.validate_patient(
        {"full_name": name, "date_of_birth": dob, "sex": sex, "pin": pin, "pin_confirm": pin}, require_pin=True)
    assert not errors
    return store.create_patient(clean)


def login(client, name, secret):
    return client.post("/login", data={"csrf_token": token(client), "name": name, "secret": secret})


def submit(client, **fields):
    data = {"csrf_token": token(client, "/assess"), "duration": "1-3d"}
    data.update(fields)
    return client.post("/assess", data=data)


def result_html(client, response):
    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    r = client.get(response.headers["Location"])
    assert r.status_code == 200
    return r.get_data(as_text=True), int(response.headers["Location"].rsplit("/", 1)[1])


def level(html):
    return re.search(r'id="level-title">([^<]+)<', html).group(1).strip()


GUEST_PERSON = {"date_of_birth": "1990-01-01", "sex": "M"}


# ------------------------------------------------------------------ entry and login screen
def test_anonymous_is_sent_to_login(client):
    r = client.get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_login_screen_has_two_fields_and_guest_button(client):
    html = client.get("/login").get_data(as_text=True)
    assert 'name="name"' in html and 'name="secret"' in html
    assert "Continue as guest" in html and "Create my profile" in html
    assert "Set up the first staff account" in html  # no staff yet


def test_post_without_csrf_is_rejected(client):
    assert client.post("/guest").status_code == 400
    assert client.post("/login", data={"name": "x", "secret": "y"}).status_code == 400


def test_first_run_setup_creates_admin_once(client):
    t = token(client, "/setup")
    r = client.post("/setup", data={"csrf_token": t, "display_name": "Dr A", "username": "dra",
                                    "password": "Clinic-pass-77", "password_confirm": "Clinic-pass-77"})
    assert r.status_code == 302
    assert store.get_user(1)["role"] == "admin"
    assert client.get("/setup").status_code == 302  # gone once a user exists
    assert "Patients" in client.get("/").get_data(as_text=True)


def test_wrong_login_shows_message_and_401(client):
    make_profile()
    r = login(client, "Mama Neema", "1111")
    assert r.status_code == 401
    assert "do not match" in r.get_data(as_text=True)


def test_open_redirect_is_ignored(client):
    make_profile()
    r = client.post("/login", data={"csrf_token": token(client), "name": "Mama Neema", "secret": "2580",
                                    "next": "//evil.example.com/x"})
    assert r.status_code == 302 and r.headers["Location"] == "/"


# ------------------------------------------------------------------ guest
def test_guest_full_flow_and_result_cards(client):
    as_guest(client)
    home = client.get("/").get_data(as_text=True)
    assert "Start assessment" in home and "Contact community" in home
    html, _ = result_html(client, submit(client, symptom=["cough", "runny_nose"], **GUEST_PERSON))
    assert level(html) == "LOW"
    for card in ("Possible condition", "Medicine information", "Doctor or clinic", "Self-care", "Start new assessment"):
        assert card in html
    assert "Common cold" in html and "Not a diagnosis." in html


def test_guest_sees_only_own_results(app, client):
    as_guest(client)
    _, aid = result_html(client, submit(client, symptom=["headache"], **GUEST_PERSON))
    other = app.test_client()
    as_guest(other)
    assert other.get(f"/result/{aid}").status_code == 404
    assert "class=\"item\"" not in other.get("/history").get_data(as_text=True)
    assert client.get("/history").get_data(as_text=True).count('class="item"') == 1


def test_guest_requires_age_and_sex(client):
    as_guest(client)
    r = submit(client, symptom=["cough"])
    assert r.status_code == 422
    html = r.get_data(as_text=True)
    assert "Enter the date of birth" in html and "Please choose female, male" in html


def test_no_symptom_is_rejected(client):
    as_guest(client)
    r = submit(client, **GUEST_PERSON)
    assert r.status_code == 422 and "Please pick at least one symptom" in r.get_data(as_text=True)


def test_tampered_symptom_code_is_dropped(client):
    as_guest(client)
    r = submit(client, symptom=["drop table", "cough"], **GUEST_PERSON)
    html, aid = result_html(client, r)
    assert store.get_assessment(aid)["symptom_text"] == "cough"


def test_danger_question_yes_makes_it_critical(client):
    as_guest(client)
    html, _ = result_html(client, submit(client, symptom=["mild_fever"], q_fits="yes", **GUEST_PERSON))
    assert level(html) == "CRITICAL"
    assert "anything in the mouth" in html
    assert "Do not delay care for medicine" in html


def test_cause_snakebite_gives_first_aid(client):
    as_guest(client)
    html, _ = result_html(client, submit(client, symptom=["dizziness"], cause=["snake_bite"], **GUEST_PERSON))
    assert level(html) in ("HIGH", "CRITICAL")
    assert "Snakebite" in html and "suck" in html


def test_pregnancy_answer_changes_the_level(client):
    as_guest(client)
    plain, _ = result_html(client, submit(client, symptom=["headache"], date_of_birth="1995-01-01", sex="F",
                                          pregnant="no"))
    preg, aid = result_html(client, submit(client, symptom=["headache"], date_of_birth="1995-01-01", sex="F",
                                           pregnant="yes"))
    assert level(plain) == "LOW"
    assert level(preg) == "HIGH"
    assert store.get_assessment(aid)["context"]["pregnancy_added"] is True


def test_unreadable_text_is_not_assessed(client):
    as_guest(client)
    html, _ = result_html(client, submit(client, typed_text="asdfgh qwerty", **GUEST_PERSON))
    assert level(html) == "NOT ASSESSED"
    assert "asdfgh" in html
    assert "cannot suggest conditions" in html


def test_body_map_codes_prefill_the_quiz(client):
    as_guest(client)
    html = client.get("/assess?mode=bodymap&p=blurred_and_distorted_vision&p=headache&p=bogus").get_data(as_text=True)
    assert 'value="blurred_and_distorted_vision" data-label="Blurry vision" checked' in html
    assert re.search(r'value="headache"[^>]*checked', html)
    assert 'value="bogus"' not in html
    assert 'name="input_mode" id="input_mode" value="bodymap"' in html


def test_body_map_page_is_big_and_posts_codes(client):
    as_guest(client)
    html = client.get("/body-map").get_data(as_text=True)
    assert 'action="/assess"' in html and 'name="p"' in html and 'id="free-text"' in html
    assert html.count('class="part-btn"') == 10  # one big coloured button per body part


# ------------------------------------------------------------------ family profiles
def test_register_profile_and_history_is_private(app, client):
    t = token(client, "/register")
    r = client.post("/register", data={"csrf_token": t, "full_name": "Baba Juma", "date_of_birth": "1980-02-02",
                                       "sex": "M", "pin": "2580", "pin_confirm": "2580"})
    assert r.status_code == 302
    html, aid = result_html(client, submit(client, symptom=["cough"]))
    a = store.get_assessment(aid)
    assert a["patient_id"] is not None and a["full_name"] == "Baba Juma"

    other = app.test_client()
    make_profile("Mama Neema", "2468")
    login(other, "mama neema", "2468")
    assert other.get(f"/result/{aid}").status_code == 404
    assert "class=\"item\"" not in other.get("/history").get_data(as_text=True)
    assert other.get("/patients").status_code == 403


def test_register_rejects_duplicate_sign_in_name(client):
    make_profile("Neema")
    t = token(client, "/register")
    r = client.post("/register", data={"csrf_token": t, "full_name": "neema", "date_of_birth": "1980-02-02",
                                       "sex": "F", "pin": "2580", "pin_confirm": "2580"})
    assert r.status_code == 200 and "already signs in with that name" in r.get_data(as_text=True)


def test_profile_pregnancy_answer_is_saved(client):
    pid = make_profile()
    login(client, "Mama Neema", "2580")
    html = client.get("/assess").get_data(as_text=True)
    assert "Are you pregnant now?" in html
    result_html(client, submit(client, symptom=["headache"], pregnant="yes"))
    assert store.get_patient(pid)["pregnant"] == 1


# ------------------------------------------------------------------ medic
def test_medic_sees_everyone(app, client):
    make_admin()
    as_guest(client)
    _, guest_aid = result_html(client, submit(client, symptom=["cough"], **GUEST_PERSON))
    pid = make_profile()
    fam = app.test_client()
    login(fam, "Mama Neema", "2580")
    _, fam_aid = result_html(fam, submit(fam, symptom=["headache"]))

    medic = app.test_client()
    assert login(medic, "admin1", "Clinic-pass-77").status_code == 302
    assert medic.get(f"/result/{guest_aid}").status_code == 200
    assert medic.get(f"/result/{fam_aid}").status_code == 200
    assert medic.get("/history").get_data(as_text=True).count('class="item"') == 2
    assert "Mama Neema" in medic.get("/patients").get_data(as_text=True)
    assert medic.get(f"/patients/{pid}").status_code == 200


def test_medic_registers_new_patient_during_assessment(client):
    make_admin()
    login(client, "admin1", "Clinic-pass-77")
    html, aid = result_html(client, submit(client, who="new", full_name="Asha", date_of_birth="2015-03-03",
                                           sex="F", symptom=["mild_fever", "headache"]))
    a = store.get_assessment(aid)
    assert a["patient_code"] and a["full_name"] == "Asha"
    assert "This is a child" in html


def test_medic_note_and_staff_admin(client):
    make_admin()
    login(client, "admin1", "Clinic-pass-77")
    _, aid = result_html(client, submit(client, who="quick", symptom=["cough"], **GUEST_PERSON))
    t = token(client, f"/result/{aid}")
    client.post(f"/result/{aid}/note", data={"csrf_token": t, "note": "Referred to clinic"})
    assert store.get_assessment(aid)["note"] == "Referred to clinic"
    t = token(client, "/admin/users")
    r = client.post("/admin/users", data={"csrf_token": t, "username": "nurse.joy", "display_name": "Joy",
                                          "password": "Ward-round-12", "role": "worker"})
    assert r.status_code == 302 and store.verify_login("nurse.joy", "Ward-round-12")[0]


def test_worker_cannot_open_admin_pages(app):
    store.create_user("nurse.joy", "Joy", "Ward-round-12", role="worker")
    c = app.test_client()
    login(c, "nurse.joy", "Ward-round-12")
    assert c.get("/admin/users").status_code == 403
    assert c.post("/contacts/add", data={"csrf_token": token(c, "/contacts"), "name_en": "X",
                                         "number": "123"}).status_code == 403


# ------------------------------------------------------------------ contacts
def test_contacts_show_tanzania_numbers_by_default(client):
    as_guest(client)
    html = client.get("/contacts").get_data(as_text=True)
    for number in ("112", "114", "199", "116"):
        assert f'<div class="number">{number}</div>' in html
    assert 'href="tel:112"' in html


def test_admin_adds_local_contact_and_switches_country(client):
    make_admin()
    login(client, "admin1", "Clinic-pass-77")
    t = token(client, "/contacts")
    client.post("/contacts/add", data={"csrf_token": t, "name_en": "Mbinga clinic", "number": "+255 700 111 222"})
    assert "Mbinga clinic" in client.get("/contacts").get_data(as_text=True)
    client.post("/settings/country", data={"csrf_token": t, "country": "KE"})
    html = client.get("/contacts").get_data(as_text=True)
    assert "1199" in html and "Mbinga clinic" not in html


# ------------------------------------------------------------------ security and language
def test_security_headers(client):
    r = client.get("/login")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_idle_timeout_signs_out(client):
    as_guest(client)
    with client.session_transaction() as s:
        s["seen"] = int(time.time()) - 31 * 60
    r = client.get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_transcribe_needs_a_session(client):
    assert client.post("/transcribe").status_code == 403


def test_swahili_interface(client):
    as_guest(client)
    client.get("/lang/sw?next=/")
    html = client.get("/").get_data(as_text=True)
    assert "Anza tathmini" in html and "Wasiliana na jamii" in html
    html, _ = result_html(client, submit(client, symptom=["cough"], **GUEST_PERSON))
    assert "CHINI" in html and "Taarifa za dawa" in html


def test_legacy_history_link_redirects(client):
    as_guest(client)
    assert client.get("/history/7").status_code == 302


def test_debug_is_off_by_default():
    source = (ROOT / "logistic_regression.app.py").read_text(encoding="utf-8")
    assert 'debug=os.environ.get("SACA_DEBUG") == "1"' in source
    assert "debug=True" not in source


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_age_form_asks_whole_years_only(client):
    as_guest(client)
    html = client.get("/assess").get_data(as_text=True)
    assert 'name="approx_age_years"' in html
    assert "approx_age_months" not in html
    html, _ = result_html(client, submit(client, symptom=["mild_fever"], approx_age_years="0", sex="F"))
    assert "under 1 year" in html
    assert "For a baby under 1 year, ask a health worker before giving any medicine." in html


# ------------------------------------------------------------------ baby-only question, voice, confidence
def test_breastfeed_question_is_hidden_until_the_age_is_known(client):
    as_guest(client)
    html = client.get("/assess").get_data(as_text=True)
    assert re.search(r'data-q="q_breastfeed" data-baby-only hidden', html)


def test_breastfeed_answer_counts_only_for_a_baby(client):
    as_guest(client)
    adult, aid = result_html(client, submit(client, symptom=["cough"], q_breastfeed="yes", **GUEST_PERSON))
    assert "unable_to_breastfeed" not in store.get_assessment(aid)["symptom_text"]
    assert level(adult) == "LOW"
    baby, bid = result_html(client, submit(client, symptom=["cough"], q_breastfeed="yes",
                                           approx_age_years="0", sex="M"))
    assert "unable_to_breastfeed" in store.get_assessment(bid)["symptom_text"]
    assert level(baby) == "CRITICAL"


def test_baby_by_date_of_birth_also_counts(client):
    as_guest(client)
    young = (time.localtime().tm_year - 0)
    dob = f"{young}-01-01" if time.localtime().tm_yday > 1 else f"{young - 1}-12-31"
    _, aid = result_html(client, submit(client, symptom=["mild_fever"], q_breastfeed="yes", date_of_birth=dob,
                                        sex="F"))
    assert "unable_to_breastfeed" in store.get_assessment(aid)["symptom_text"]


def test_voice_is_offered_on_the_quiz_and_the_body_map(client):
    as_guest(client)
    quiz = client.get("/assess").get_data(as_text=True)
    assert 'id="speak-btn"' in quiz and 'src="/voice.js" data-target="typed_text"' in quiz
    bm = client.get("/body-map").get_data(as_text=True)
    assert 'src="/voice.js" data-target="free-text"' in bm
    assert client.get("/voice.js").status_code == 200


def test_voice_mode_is_recorded(client):
    as_guest(client)
    _, aid = result_html(client, submit(client, typed_text="cough and runny nose", input_mode="voice", **GUEST_PERSON))
    assert store.get_assessment(aid)["input_mode"] == "voice"


def test_very_high_confidence_is_shown_as_over_99_with_explanation(client):
    as_guest(client)
    html, aid = result_html(client, submit(client, symptom=["breathlessness", "chest_pain", "convulsions",
                                                            "altered_sensorium"], **GUEST_PERSON))
    assert store.get_assessment(aid)["confidence"] >= 0.99
    assert "&gt; 99%" in html and "100.0%" not in html
    assert "not the chance that the person is this sick" in html


def test_medic_new_patient_is_not_created_when_the_form_has_errors(client):
    make_admin()
    login(client, "admin1", "Clinic-pass-77")
    before = store.patient_count()
    r = submit(client, who="new", full_name="Asha", date_of_birth="2015-03-03", sex="F")  # no symptom
    assert r.status_code == 422
    assert store.patient_count() == before
