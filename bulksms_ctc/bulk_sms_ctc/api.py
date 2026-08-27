import json
import re
import frappe
import requests
from frappe import _
from frappe.utils import now_datetime, get_datetime


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_settings():
    return frappe.get_single("BulkSMS CTC Settings")


def _get_user_row(settings, user=None):
    """
    Matches against Click To Call User child table.
    Fields confirmed from DocType JSON:
      user, user_name, agent_number, is_active
    """
    user = user or frappe.session.user
    for r in (settings.user_permissions or []):
        if r.user == user and r.is_active:
            return r
    return None


def _get_dt_row(settings, doctype):
    """
    Matches against CTC Enabled DocType child table.
    Fields confirmed from DocType JSON:
      target_doctype, receiver_field, is_active
    """
    for r in (settings.doctype_config or []):
        if r.target_doctype == doctype and r.is_active:
            return r
    return None


def _sanitize_number(raw):
    """
    Strips +, country code, spaces, special chars.
    Returns last 10 digits only.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def _mask_number(raw):
    clean = _sanitize_number(raw)
    if not clean:
        return ""
    if len(clean) <= 5:
        return clean
    return clean[:2] + "X" * (len(clean) - 5) + clean[-3:]


# ─────────────────────────────────────────────────────────────────────────────
# 1. CHECK ELIGIBILITY  (called by JS on every form open)
# ─────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def check_ctc_eligibility(doctype):
    try:
        settings = _get_settings()
    except Exception:
        return {"allowed": False, "reason": "Settings not found"}

    if not _get_user_row(settings):
        return {"allowed": False, "reason": "User not in allowed list"}

    row = _get_dt_row(settings, doctype)
    if not row:
        return {"allowed": False, "reason": "Doctype not configured"}

    return {
        "allowed": True,
        "receiver_field": row.receiver_field,
        "doctype": doctype,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET CALL DIALOG DATA
# ─────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def get_call_dialog_data(doctype, docname):
    settings = _get_settings()

    u_row = _get_user_row(settings)
    if not u_row:
        frappe.throw(
            _("You are not authorised to use Click-to-Call. "
              "Ask your System Manager to add you in the Click To Call User list."),
            frappe.PermissionError,
        )

    dt_row = _get_dt_row(settings, doctype)
    if not dt_row:
        frappe.throw(_(f"Click-to-Call is not enabled for {doctype}."))

    receiver_number = frappe.db.get_value(doctype, docname, dt_row.receiver_field)

    return {
        "agent_number":           u_row.agent_number or "",
        "agent_number_masked":    _mask_number(u_row.agent_number),
        "receiver_number":        receiver_number or "",
        "receiver_number_masked": _mask_number(receiver_number),
        "receiver_field":         dt_row.receiver_field,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. MAKE CALL
# ─────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def make_call(doctype, docname, scheduled="0", scheduled_datetime=""):
    settings = _get_settings()

    u_row = _get_user_row(settings)
    if not u_row:
        frappe.throw(_("You are not authorised to use Click-to-Call."), frappe.PermissionError)

    dt_row = _get_dt_row(settings, doctype)
    if not dt_row:
        frappe.throw(_(f"Click-to-Call is not enabled for {doctype}."))

    # Sanitize receiver
    raw_receiver = frappe.db.get_value(doctype, docname, dt_row.receiver_field)
    if not raw_receiver:
        frappe.throw(_(f"No phone number found in field '{dt_row.receiver_field}'."))

    receiver_number = _sanitize_number(raw_receiver)
    if len(receiver_number) != 10:
        frappe.throw(_(
            f"Customer number invalid after cleaning '{raw_receiver}': "
            f"got {len(receiver_number)} digits, need 10."
        ))

    # Sanitize agent
    if not u_row.agent_number:
        frappe.throw(_("Your agent number is not set in CTC User settings."))

    agent_number = _sanitize_number(u_row.agent_number)
    if len(agent_number) != 10:
        frappe.throw(_(
            f"Agent number invalid after cleaning '{u_row.agent_number}': "
            f"got {len(agent_number)} digits, need 10."
        ))

    # Scheduled params
    is_scheduled = str(scheduled) in ("1", "true", "True")

    if is_scheduled:
        if not scheduled_datetime:
            frappe.throw(_("Scheduled datetime is required for Schedule call type."))
        try:
            dt_obj     = get_datetime(scheduled_datetime)
            bulksms_dt = dt_obj.strftime("%d-%m-%Y %H:%M:%S")
        except Exception:
            frappe.throw(_("Invalid datetime format. Use: YYYY-MM-DD HH:MM:SS"))
        scheduled_param          = "1"
        scheduled_datetime_param = bulksms_dt
        call_status              = "Queued"
        start_time_value         = dt_obj
    else:
        scheduled_param          = "0"
        scheduled_datetime_param = ""
        call_status              = "In Progress"
        start_time_value         = now_datetime()

    # API call
    params = {
        "api_id":             settings.api_id,
        "api_password":       settings.get_password("api_password"),
        "ivr_number":         settings.ivr_number,
        "dial":               settings.dial or "agent",
        "receiver_number":    receiver_number,
        "agent_number":       agent_number,
        "scheduled":          scheduled_param,
        "timezone_id":        settings.timezone_id or "",
        "scheduled_datetime": scheduled_datetime_param,
    }

    try:
        resp = requests.get(
            "https://www.bulksmsplans.com/api/ivr/makeACall",
            params=params, timeout=30,
        )
        resp.raise_for_status()
        resp_data = resp.json()
    except Exception as exc:
        frappe.throw(_(f"BulkSMS API request failed: {exc}"))

    if resp_data.get("code") != 200:
        frappe.throw(_(
            f"BulkSMS Error: {resp_data.get('message')} | "
            f"Data: {json.dumps(resp_data.get('data', {}))}"
        ))

    submit_note_id = str(resp_data["data"]["submit_note_id"])

    # Call Log
    call_log = frappe.get_doc({
        "doctype":    "Call Log",
        "medium":     "BulkSMS",
        "type":       "Outgoing",
        "status":     call_status,
        "from":       agent_number,
        "to":         receiver_number,
        "start_time": start_time_value,
        "links": [{"link_doctype": doctype, "link_name": docname}],
    })
    call_log.flags.ignore_links = True
    call_log.insert(ignore_permissions=True, set_name=submit_note_id)
    frappe.db.commit()

    return {
        "status":         "success",
        "message":        resp_data.get("message"),
        "call_log":       call_log.name,
        "submit_note_id": submit_note_id,
        "is_scheduled":   is_scheduled,
        "scheduled_for":  scheduled_datetime_param or None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def calldata():
    try:
        ct = frappe.request.content_type or ""
        payload = frappe.request.get_json(force=True) or {} if "application/json" in ct             else frappe.request.form.to_dict()
    except Exception:
        payload = {}

    frappe.log_error(
        title="BulkSMS CTC Webhook — Raw Payload",
        message=(
            f"Method : {frappe.request.method}\n"
            f"Content-Type: {frappe.request.content_type}\n"
            f"URL Args: {dict(frappe.request.args)}\n\n"
            f"Parsed Payload:\n{json.dumps(payload, indent=2)}\n\n"
            f"Raw Body:\n{frappe.request.get_data(as_text=True)}"
        ),
    )

    submit_note_id = str(payload.get("submit_note_id", "")).strip()
    if not submit_note_id:
        frappe.response["http_status_code"] = 400
        return {"status": "error", "message": "submit_note_id missing"}

    if not frappe.db.exists("Call Log", submit_note_id):
        frappe.log_error(
            title="BulkSMS CTC Webhook: Call Log Not Found",
            message=f"id={submit_note_id}\npayload={json.dumps(payload, indent=2)}",
        )
        return {"status": "ok", "message": "not found — logged"}

    status_map = {
        "completed": "Completed", "answered": "Completed",
        "no answer": "No Answer", "no-answer": "No Answer",
        "busy": "Busy", "failed": "Failed",
        "cancelled": "Canceled", "canceled": "Canceled",
    }
    updates = {"status": status_map.get(str(payload.get("status", "")).lower(), "Completed")}
    if payload.get("duration") is not None:
        updates["duration"] = payload["duration"]
    if payload.get("recording_url") or payload.get("record_url"):
        updates["recording_url"] = payload.get("recording_url") or payload.get("record_url")
    for k in ("end_time", "hangup_time", "end_datetime"):
        if payload.get(k):
            try: updates["end_time"] = get_datetime(payload[k])
            except Exception: pass
            break

    frappe.db.set_value("Call Log", submit_note_id, updates)
    frappe.db.commit()
    frappe.publish_realtime(f"call_{submit_note_id}_ended", frappe.get_doc("Call Log", submit_note_id))
    return {"status": "ok", "call_log": submit_note_id, "updated": {k: str(v) for k, v in updates.items()}}
