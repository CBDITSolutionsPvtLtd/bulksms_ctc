"""
bulksms_ctc/setup/install.py
────────────────────────────
All install / uninstall / migrate logic lives here.
hooks.py points to each function below.

To add more customisations:
  - Custom fields   → add entries to CUSTOM_FIELDS dict
  - Property setters → add entries to PROPERTY_SETTERS list
"""
import os
import frappe
from frappe import _


# ════════════════════════════════════════════════════════════════════════════
# A) CUSTOM FIELDS
#    Add new fields to any existing (standard) DocType.
#    Key   = DocType name
#    Value = list of field definition dicts (same as Custom Field schema)
#    create_custom_fields() is fully IDEMPOTENT — safe to run repeatedly.
# ════════════════════════════════════════════════════════════════════════════
CUSTOM_FIELDS = {
    # No extra fields needed on Call Log — it already has everything:
    #   name (= submit_note_id), from, to, medium, type, status,
    #   start_time, end_time, duration, recording_url, summary,
    #   links (DynamicLink child table → shows call in Activity timeline)
    #
    # Template — uncomment and fill to add fields to any doctype:
    # "Lead": [
    #     {
    #         "fieldname":    "ctc_last_called",
    #         "label":        "Last Called (CTC)",
    #         "fieldtype":    "Datetime",
    #         "insert_after": "mobile_no",
    #         "read_only":    1,
    #         "no_copy":      1,
    #     },
    # ],
}


# ════════════════════════════════════════════════════════════════════════════
# B) PROPERTY SETTERS
#    Override properties of EXISTING fields on standard DocTypes.
#    Use cases: add Select options, make mandatory, change label, hide field.
#    Each entry is IDEMPOTENT — existing ones are updated, not duplicated.
# ════════════════════════════════════════════════════════════════════════════
PROPERTY_SETTERS = [
    # Add "BulkSMS" to the options of the "medium" field in Call Log
    {
        "doctype":       "Call Log",
        "fieldname":     "medium",
        "property":      "options",
        "value":         "\nManual\nCRM\nVoIP\nCloudShope\nBulkSMS",
        "property_type": "Text",
    },
    # ── Templates ──────────────────────────────────────────────────────────
    # Make field mandatory:
    # {"doctype": "Lead", "fieldname": "mobile_no",
    #  "property": "reqd", "value": "1", "property_type": "Check"},
    #
    # Change label:
    # {"doctype": "Customer", "fieldname": "customer_name",
    #  "property": "label", "value": "Company Name", "property_type": "Data"},
    #
    # Hide field:
    # {"doctype": "Lead", "fieldname": "fax",
    #  "property": "hidden", "value": "1", "property_type": "Check"},
    #
    # Make read-only:
    # {"doctype": "Lead", "fieldname": "lead_name",
    #  "property": "read_only", "value": "1", "property_type": "Check"},
]


# ════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _register_in_apps_txt():
    try:
        bench_path = frappe.utils.get_bench_path()
        apps_txt   = os.path.join(bench_path, "sites", "apps.txt")

        if not os.path.exists(apps_txt):
            print(f"  [CTC] apps.txt not found at {apps_txt} — skipping.")
            return

        with open(apps_txt, "r") as f:
            apps = [a.strip() for a in f.read().splitlines() if a.strip()]

        if "bulksms_ctc" not in apps:
            apps.append("bulksms_ctc")
            with open(apps_txt, "w") as f:
                f.write("\n".join(apps) + "\n")
            print("  [CTC] bulksms_ctc added to apps.txt automatically.")
        else:
            print("  [CTC] bulksms_ctc already in apps.txt.")

    except Exception as e:
        print(f"  [CTC] Warning: Could not auto-register in apps.txt: {e}")


def _deregister_from_apps_txt():
    try:
        bench_path = frappe.utils.get_bench_path()
        apps_txt   = os.path.join(bench_path, "sites", "apps.txt")

        if not os.path.exists(apps_txt):
            return

        with open(apps_txt, "r") as f:
            apps = [
                a.strip() for a in f.read().splitlines()
                if a.strip() and a.strip() != "bulksms_ctc"
            ]
        with open(apps_txt, "w") as f:
            f.write("\n".join(apps) + "\n")
        print("  [CTC] bulksms_ctc removed from apps.txt.")

    except Exception as e:
        print(f"  [CTC] Warning: Could not remove from apps.txt: {e}")


# ════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _create_custom_fields():
    if not CUSTOM_FIELDS:
        return
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
    frappe.db.commit()
    print("  [CTC] Custom fields created / verified.")


def _create_property_setters():
    for ps in PROPERTY_SETTERS:
        existing = frappe.db.get_value(
            "Property Setter",
            {
                "doc_type":   ps["doctype"],
                "field_name": ps["fieldname"],
                "property":   ps["property"],
            },
            ["name", "value"],
            as_dict=True,
        )
        if existing:
            if existing.value != ps["value"]:
                frappe.db.set_value("Property Setter", existing.name, "value", ps["value"])
                print(f"  [CTC] Updated PS: {ps['doctype']}.{ps['fieldname']}.{ps['property']}")
        else:
            frappe.get_doc({
                "doctype":          "Property Setter",
                "doctype_or_field": "DocField",
                "doc_type":         ps["doctype"],
                "field_name":       ps["fieldname"],
                "property":         ps["property"],
                "value":            ps["value"],
                "property_type":    ps.get("property_type", "Data"),
                "module":           "Bulk SMS CTC",
            }).insert(ignore_permissions=True)
            print(f"  [CTC] Created PS: {ps['doctype']}.{ps['fieldname']}.{ps['property']}")
    frappe.db.commit()
    print("  [CTC] Property setters synced.")


def _remove_custom_fields():
    for doctype, fields in CUSTOM_FIELDS.items():
        for field in fields:
            cf = frappe.db.get_value(
                "Custom Field",
                {"dt": doctype, "fieldname": field["fieldname"]},
                "name",
            )
            if cf:
                frappe.delete_doc("Custom Field", cf, ignore_permissions=True)
                print(f"  [CTC] Removed CF: {doctype}.{field['fieldname']}")
    frappe.db.commit()


def _remove_property_setters():
    for ps in PROPERTY_SETTERS:
        name = frappe.db.get_value(
            "Property Setter",
            {
                "doc_type":   ps["doctype"],
                "field_name": ps["fieldname"],
                "property":   ps["property"],
            },
            "name",
        )
        if name:
            frappe.delete_doc("Property Setter", name, ignore_permissions=True)
            print(f"  [CTC] Removed PS: {ps['doctype']}.{ps['fieldname']}.{ps['property']}")
    frappe.db.commit()


# ════════════════════════════════════════════════════════════════════════════
# LIFECYCLE HOOKS — called by hooks.py
# ════════════════════════════════════════════════════════════════════════════

def before_install():
    """
    Runs BEFORE app DocTypes are created.
    1. Auto-registers in apps.txt (so install-app never fails).
    2. Checks ERPNext dependency (Call Log must exist).
    """
    print("[CTC] before_install: checking dependencies…")

    # Auto-register in apps.txt — MUST be first
    _register_in_apps_txt()

    # Check ERPNext is installed
    if not frappe.db.exists("DocType", "Call Log"):
        frappe.throw(
            _("ERPNext must be installed before BulkSMS CTC (requires Call Log DocType).")
        )

    print("[CTC] before_install: all checks passed.")


def after_install():
    """Runs AFTER app DocTypes and fixtures are installed."""
    print("[CTC] after_install: setting up…")
    _create_custom_fields()
    _create_property_setters()
    if not frappe.db.exists("BulkSMS CTC Settings", "BulkSMS CTC Settings"):
        frappe.get_doc({"doctype": "BulkSMS CTC Settings"}).insert(ignore_permissions=True)
        frappe.db.commit()
        print("[CTC] Default Settings doc created.")
    print("[CTC] after_install: done!")


def after_migrate():
    """
    Runs after every bench migrate.
    Re-applies custom fields and property setters — fully idempotent.
    Ensures they survive ERPNext version upgrades.
    """
    print("[CTC] after_migrate: syncing customisations…")
    _create_custom_fields()
    _create_property_setters()
    print("[CTC] after_migrate: done.")


def before_uninstall():
    """Runs BEFORE app DocTypes are dropped. Warn about existing data."""
    count = frappe.db.count("Call Log", {"medium": "BulkSMS"})
    if count:
        print(
            f"[CTC] WARNING: {count} Call Log records with medium=BulkSMS exist. "
            "They will remain in Call Log after uninstall."
        )
    print("[CTC] before_uninstall: done.")


def after_uninstall():
    """Runs AFTER app DocTypes are dropped. Remove all customisations."""
    print("[CTC] after_uninstall: removing customisations…")
    _remove_custom_fields()
    _remove_property_setters()
    _deregister_from_apps_txt()
    print("[CTC] after_uninstall: cleanup complete.")