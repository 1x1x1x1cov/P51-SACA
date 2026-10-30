"""
SACA app screens: home, assessment (quiz), result, history, patients, contacts, about, staff admin.

Who can see what:
  guest    their own results from this session only
  profile  their own history only
  medic    every patient and assessment on this device; admin also manages staff, contacts and settings
"""
from datetime import date

from flask import (Blueprint, Response, abort, current_app, flash, g, jsonify, redirect, render_template, request,
                   url_for)

import assessment_flow as flow
import conditions as cond
import guidance as guide
import saca_store as store
import speech
from i18n import gettext as _
from saca_auth import (actor_user_id, admin_required, guest_assessment_ids, medic_required,
                       remember_guest_assessment, signed_in)

bp = Blueprint("main", __name__)

LEVEL_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def pipeline():
    return current_app.config["SACA_PIPELINE"]


# --------------------------------------------------------------------------------------------- helpers
def _person_from_form(form):
    """Guest or quick (unsaved) person details from step 1 of the quiz. Returns (person, errors)."""
    clean, errors = store.validate_patient(form, require_pin=False)
    errors.pop("full_name", None)  # a guest may stay anonymous
    errors.pop("pin", None)
    person = {
        "name": clean.get("full_name") or None,
        "date_of_birth": clean.get("date_of_birth"),
        "dob_estimated": clean.get("dob_estimated", 0),
        "sex": clean.get("sex", "U"),
        "pregnant": clean.get("pregnant"),
    }
    return person, errors


def _age_info(date_of_birth):
    years, months = store.age_on(date_of_birth)
    total = None if years is None else years * 12 + months
    return years, total, store.age_group(years)


def can_view(assessment):
    if g.kind == "medic":
        return True
    if g.kind == "profile":
        return assessment["patient_id"] == g.patient["id"]
    if g.kind == "guest":
        return assessment["id"] in guest_assessment_ids()
    return False


def result_view_model(a):
    """Everything the result screen needs, rebuilt from the saved assessment."""
    ctx = a.get("context") or {}
    person = ctx.get("person") or {}
    dob = a.get("date_of_birth") or person.get("date_of_birth")
    estimated = bool(a.get("dob_estimated") if a.get("date_of_birth") else person.get("dob_estimated"))
    years, months_total, group = _age_info(dob)
    pregnant = bool(ctx.get("pregnant"))
    codes = set(a["symptom_list"])
    severity = a["severity"] or "HIGH"
    assessed = bool(a["assessed"])
    advice = guide.build_guidance(severity, assessed, codes, age_group=group, pregnant=pregnant,
                                  duration=flow.duration_group(ctx.get("duration")), age_years=years,
                                  age_months_total=months_total, age_estimated=estimated)
    conditions = {"items": a.get("conditions") or []}
    show_conditions = assessed and bool(conditions["items"])
    return {
        "a": a,
        "ctx": ctx,
        "person_name": a.get("full_name") or person.get("name"),
        "age_text": store.age_label(dob, estimated) if dob else "",
        "advice": advice,
        "conditions": conditions,
        "show_conditions": show_conditions,
        "mismatch": show_conditions and cond.mismatch_warning(conditions, severity),
        "level_key": advice["level_key"],
        "durations": {d[0]: (d[1], d[2]) for d in flow.DURATIONS},
    }


# --------------------------------------------------------------------------------------------- home
@bp.get("/")
@signed_in
def home():
    stats = store.severity_counts(days=7) if g.kind == "medic" else None
    recent = []
    if g.kind == "profile":
        recent = store.list_assessments(limit=3, patient_id=g.patient["id"])
    elif g.kind == "medic":
        recent = store.list_assessments(limit=5)
    return render_template("home.html", stats=stats, recent=recent,
                           patient_total=store.patient_count() if g.kind == "medic" else None)


@bp.get("/healthz")
def healthz():
    return jsonify(status="ok")


# --------------------------------------------------------------------------------------------- assessment
@bp.get("/assess")
@signed_in
def assess():
    raw = request.args.getlist("p") + (request.args.get("prefill") or "").split()
    prefill = []
    for c in raw:
        if c in flow.ALLOWED_SYMPTOM_CODES | flow.CAUSE_CODES and c not in prefill:
            prefill.append(c)
    typed = (request.args.get("typed") or "").strip()[:flow.MAX_TYPED]
    mode = request.args.get("mode") if request.args.get("mode") in ("bodymap", "typed", "pictures") else ""
    patients = store.search_patients(limit=200) if g.kind == "medic" else []
    preselect = request.args.get("patient_id", type=int)
    return render_template("assess.html", flow=flow, prefill=prefill, extra=flow.extra_prefill(prefill), typed=typed,
                           mode=mode, patients=patients, preselect=preselect, errors={}, form={},
                           today=date.today().isoformat())


@bp.post("/assess")
@signed_in
def assess_submit():
    form = request.form
    errors = {}
    patient_id = None
    person = None
    new_patient = None
    age_years = None

    # ---- who is this for
    if g.kind == "profile":
        patient = g.patient
        patient_id = patient["id"]
        if patient["sex"] == "F" and patient["age_years"] is not None and 10 <= patient["age_years"] <= 55:
            answer = form.get("pregnant")
            if answer in ("yes", "no"):
                store.set_pregnancy(patient_id, answer == "yes")
                patient = store.get_patient(patient_id)
        pregnant = bool(patient.get("pregnant"))
        age_years = patient["age_years"]
    elif g.kind == "medic" and form.get("who") == "existing":
        patient = store.get_patient(form.get("patient_id", type=int) or -1)
        if patient is None:
            errors["who"] = "Please choose a patient."
            pregnant = False
        else:
            patient_id = patient["id"]
            answer = form.get("pregnant_existing")
            if answer in ("yes", "no") and patient["sex"] == "F":
                store.set_pregnancy(patient_id, answer == "yes")
                patient = store.get_patient(patient_id)
            pregnant = bool(patient.get("pregnant"))
            age_years = patient["age_years"]
    elif g.kind == "medic" and form.get("who") == "new":
        new_patient, perrors = store.validate_patient(form, require_pin=False)
        perrors.pop("pin", None)
        errors.update(perrors)
        pregnant = bool(new_patient.get("pregnant"))
        age_years = store.age_on(new_patient.get("date_of_birth"))[0]
    else:  # guest, or a medic doing a quick check without a record
        person, perrors = _person_from_form(form)
        errors.update(perrors)
        pregnant = bool(person.get("pregnant"))
        age_years = store.age_on(person.get("date_of_birth"))[0]

    text, picked, context, mode = flow.build_symptom_text(form, age_years=age_years)
    if not text:
        errors["symptoms"] = "Please pick at least one symptom or describe how you feel."

    if errors:
        patients = store.search_patients(limit=200) if g.kind == "medic" else []
        return render_template("assess.html", flow=flow, prefill=picked, extra=flow.extra_prefill(picked),
                               typed=context.get("typed_text") or "",
                               mode=mode, patients=patients, preselect=form.get("patient_id", type=int),
                               errors=errors, form=form.to_dict(), today=date.today().isoformat()), 422

    if new_patient is not None:  # saved only now, so a form with errors never creates a duplicate record
        patient_id = store.create_patient(new_patient, user_id=actor_user_id(), registered_by="worker")
        store.log_event(actor_user_id(), "patient_created", f"P-{patient_id:04d}")

    # Pregnancy is part of the input the safety rules use (e.g. pregnancy + headache -> HIGH).
    classify_text = text
    if pregnant and "pregnancy" not in text.split():
        classify_text = "pregnancy " + text
        context["pregnancy_added"] = True
    context["pregnant"] = pregnant
    if person:
        context["person"] = person
    context["guidance_version"] = guide.GUIDANCE_VERSION

    result = pipeline().classify(classify_text)
    context["unrecognised"] = list(result.get("unrecognised") or [])[:20]
    context["input_source"] = result.get("input_source")
    conditions = cond.possible_conditions(result.get("symptoms") or []) if result.get("assessed", True) else {"items": []}
    assessment_id = store.save_assessment(patient_id, actor_user_id(), classify_text, result, input_mode=mode,
                                          conditions=conditions["items"], context=context)
    if g.kind == "guest" or patient_id is None:
        remember_guest_assessment(assessment_id)
    store.log_event(actor_user_id(), "assessment", f"#{assessment_id} {g.kind}")
    return redirect(url_for("main.result", assessment_id=assessment_id))


@bp.get("/result/<int:assessment_id>")
@signed_in
def result(assessment_id):
    a = store.get_assessment(assessment_id)
    if a is None or not can_view(a):
        abort(404)
    model = result_view_model(a)
    model["speak_text"] = speech.speech_text(model["advice"], g.lang)
    model["offline_voice"] = speech.available(g.lang)
    return render_template("result.html", **model)


@bp.get("/result/<int:assessment_id>/speech.wav")
@signed_in
def result_speech(assessment_id):
    """Read-aloud audio made on this computer (offline voice). Speaks only the result's own advice."""
    a = store.get_assessment(assessment_id)
    if a is None or not can_view(a):
        abort(404)
    lang = request.args.get("lang") if request.args.get("lang") in ("en", "sw") else g.lang
    text = speech.speech_text(result_view_model(a)["advice"], lang)
    audio = speech.synthesize(text, lang)
    if audio is None:
        return jsonify(detail="No offline voice is installed for this language."), 404
    response = Response(audio, mimetype="audio/wav")
    response.headers["Cache-Control"] = "private, max-age=600"
    return response


@bp.post("/result/<int:assessment_id>/note")
@medic_required
def result_note(assessment_id):
    if store.get_assessment(assessment_id) is None:
        abort(404)
    store.set_assessment_note(assessment_id, request.form.get("note"))
    store.log_event(actor_user_id(), "note", f"#{assessment_id}")
    flash(_("Note saved."))
    return redirect(url_for("main.result", assessment_id=assessment_id))


@bp.get("/body-map")
@signed_in
def body_map():
    return render_template("body_map.html", flow=flow)


# --------------------------------------------------------------------------------------------- history
@bp.get("/history")
@signed_in
def history():
    severity = request.args.get("severity") if request.args.get("severity") in LEVEL_ORDER else None
    query = (request.args.get("q") or "").strip()[:60]
    if g.kind == "medic":
        items = store.list_assessments(limit=300, severity=severity, query=query or None)
    elif g.kind == "profile":
        items = store.list_assessments(limit=300, patient_id=g.patient["id"], severity=severity)
    else:
        ids = set(guest_assessment_ids())
        items = [store.get_assessment(i) for i in sorted(ids, reverse=True)]
        items = [a for a in items if a and (not severity or a["severity"] == severity)]
    return render_template("history.html", items=items, severity=severity, q=query)


@bp.get("/history/<int:record_id>")
def legacy_history_detail(record_id):
    return redirect(url_for("main.history"))


# --------------------------------------------------------------------------------------------- patients (medic)
@bp.get("/patients")
@medic_required
def patients():
    q = (request.args.get("q") or "").strip()[:60]
    return render_template("patients.html", items=store.search_patients(q, limit=300), q=q)


@bp.route("/patients/new", methods=["GET", "POST"])
@medic_required
def patient_new():
    form, errors = {}, {}
    if request.method == "POST":
        form = request.form.to_dict()
        clean, errors = store.validate_patient(form, require_pin=False)
        if not errors and clean.get("pin"):
            problem = store.pin_name_problem(clean["full_name"])
            if problem:
                errors["full_name"] = problem
        if not errors:
            pid = store.create_patient(clean, user_id=actor_user_id(), registered_by="worker")
            store.log_event(actor_user_id(), "patient_created", f"P-{pid:04d}")
            flash(_("Patient saved."))
            return redirect(url_for("main.patient_detail", patient_id=pid))
    return render_template("patient_form.html", form=form, errors=errors, patient=None,
                           today=date.today().isoformat())


@bp.get("/patients/<int:patient_id>")
@medic_required
def patient_detail(patient_id):
    patient = store.get_patient(patient_id)
    if patient is None:
        abort(404)
    return render_template("patient_detail.html", patient=patient,
                           items=store.list_assessments(limit=300, patient_id=patient_id))


@bp.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
@medic_required
def patient_edit(patient_id):
    patient = store.get_patient(patient_id)
    if patient is None:
        abort(404)
    errors = {}
    form = {"full_name": patient["full_name"], "date_of_birth": patient["date_of_birth"], "sex": patient["sex"],
            "pregnant": {1: "yes", 0: "no"}.get(patient["pregnant"], ""), "location": patient["location"] or ""}
    if request.method == "POST":
        form = request.form.to_dict()
        clean, errors = store.validate_patient(form, require_pin=False)
        if not errors and (patient["has_pin"] or clean.get("pin")):
            problem = store.pin_name_problem(clean["full_name"], exclude_patient_id=patient_id)
            if problem:
                errors["full_name"] = problem
        if not errors:
            store.update_patient(patient_id, clean)
            store.log_event(actor_user_id(), "patient_updated", patient["patient_code"])
            flash(_("Patient updated."))
            return redirect(url_for("main.patient_detail", patient_id=patient_id))
    return render_template("patient_form.html", form=form, errors=errors, patient=patient,
                           today=date.today().isoformat())


@bp.post("/patients/<int:patient_id>/delete")
@admin_required
def patient_delete(patient_id):
    patient = store.get_patient(patient_id)
    if patient is None:
        abort(404)
    if (request.form.get("confirm_code") or "").strip().upper() != patient["patient_code"]:
        flash(_("Type the patient code exactly to confirm deletion."))
        return redirect(url_for("main.patient_detail", patient_id=patient_id))
    store.delete_patient(patient_id)
    store.log_event(actor_user_id(), "patient_deleted", patient["patient_code"])
    flash(_("Patient and their assessments were deleted."))
    return redirect(url_for("main.patients"))


# --------------------------------------------------------------------------------------------- contacts
@bp.get("/contacts")
@signed_in
def contacts():
    country = store.get_setting("country", store.DEFAULT_COUNTRY)
    return render_template("contacts.html", items=store.list_contacts(country), country=country,
                           countries=store.COUNTRIES, checked_on=store.CONTACTS_CHECKED_ON)


@bp.post("/contacts/add")
@admin_required
def contact_add():
    country = store.get_setting("country", store.DEFAULT_COUNTRY)
    _id, error = store.add_contact(country, request.form.get("name_en"), request.form.get("number"),
                                   request.form.get("name_sw"), request.form.get("note_en"),
                                   request.form.get("note_sw"), user_id=actor_user_id())
    if error:
        flash(_(error))
    else:
        store.log_event(actor_user_id(), "contact_added")
        flash(_("Contact added."))
    return redirect(url_for("main.contacts"))


@bp.post("/contacts/<int:contact_id>/delete")
@admin_required
def contact_delete(contact_id):
    error = store.delete_contact(contact_id)
    flash(_(error) if error else _("Contact removed."))
    if not error:
        store.log_event(actor_user_id(), "contact_deleted")
    return redirect(url_for("main.contacts"))


@bp.post("/settings/country")
@admin_required
def set_country():
    code = request.form.get("country")
    if code in store.COUNTRIES:
        store.set_setting("country", code)
        store.log_event(actor_user_id(), "country_set", code)
    return redirect(url_for("main.contacts"))


# --------------------------------------------------------------------------------------------- about
@bp.get("/about")
@signed_in
def about():
    return render_template("about.html", guidance_status=guide.GUIDANCE_STATUS, guidance_version=guide.GUIDANCE_VERSION,
                           sources=guide.SOURCES + guide.MEDICINE_SOURCES)


# --------------------------------------------------------------------------------------------- staff admin
@bp.get("/admin/users")
@admin_required
def admin_users():
    return render_template("admin_users.html", users=store.list_users(), events=store.recent_events(30),
                           error=None, form={})


@bp.post("/admin/users")
@admin_required
def admin_user_create():
    form = request.form.to_dict()
    role = form.get("role") if form.get("role") in store.ROLES else "worker"
    user_id, error = store.create_user(form.get("username"), form.get("display_name"), form.get("password"), role)
    if error:
        return render_template("admin_users.html", users=store.list_users(), events=store.recent_events(30),
                               error=error, form=form), 422
    store.log_event(actor_user_id(), "user_created", form.get("username"))
    flash(_("Staff account created."))
    return redirect(url_for("main.admin_users"))


@bp.post("/admin/users/<int:user_id>/active")
@admin_required
def admin_user_active(user_id):
    active = request.form.get("active") == "1"
    if user_id == actor_user_id() and not active:
        flash(_("You cannot switch off your own account."))
        return redirect(url_for("main.admin_users"))
    error = store.set_active(user_id, active)
    flash(_(error) if error else _("Account updated."))
    if not error:
        store.log_event(actor_user_id(), "user_active" if active else "user_inactive", str(user_id))
    return redirect(url_for("main.admin_users"))


@bp.route("/account", methods=["GET", "POST"])
@medic_required
def account():
    error = None
    if request.method == "POST":
        if not store.check_password(g.user["id"], request.form.get("current_password")):
            error = "Your current password is not right."
        elif request.form.get("new_password") != request.form.get("new_password_confirm"):
            error = "The two passwords do not match."
        else:
            error = store.set_password(g.user["id"], request.form.get("new_password"))
            if not error:
                store.log_event(g.user["id"], "password_changed")
                flash(_("Password changed."))
                return redirect(url_for("main.home"))
    return render_template("account.html", error=error)


@bp.post("/patients/<int:patient_id>/reset-pin")
@medic_required
def patient_reset_pin(patient_id):
    patient = store.get_patient(patient_id)
    if patient is None:
        abort(404)
    pin = request.form.get("pin")
    if pin != request.form.get("pin_confirm"):
        flash(_("The two PINs do not match."))
    else:
        problem = store.pin_name_problem(patient["full_name"], exclude_patient_id=patient_id)
        error = problem or store.reset_pin(patient_id, pin)
        flash(_(error) if error else _("PIN set. The person can now sign in with their name and this PIN."))
        if not error:
            store.log_event(actor_user_id(), "pin_reset", patient["patient_code"])
    return redirect(url_for("main.patient_detail", patient_id=patient_id))


def init_app(app):
    app.register_blueprint(bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message=_("You do not have access to this page.")), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message=_("That page or record was not found.")), 404

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, message=_(
            "The form expired. Please go back, reload the page and try again.")), 400
