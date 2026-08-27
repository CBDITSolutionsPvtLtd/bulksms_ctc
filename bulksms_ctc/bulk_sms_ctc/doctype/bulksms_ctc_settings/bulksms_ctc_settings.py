import frappe
from frappe.model.document import Document


class BulkSMSCTCSettings(Document):
    def on_update(self):
        """
        When admin saves Settings (adds/removes doctypes or users),
        fire a realtime event so ALL connected browsers wipe their JS
        eligibility cache immediately — no reload needed.
        """
        frappe.publish_realtime(
            event="bulksms_ctc_settings_updated",
            message={"updated_by": frappe.session.user},
            after_commit=True,
        )
