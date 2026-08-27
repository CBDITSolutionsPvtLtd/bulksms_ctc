(function () {
    "use strict";

    const SKIP_DOCTYPES = [
        "BulkSMS CTC Settings",
        "CTC Enabled DocType",
        "Click To Call User",
        "Call Log",
    ];

    const BTN_ID = "bulksms-ctc-float-btn";
    const CSS_ID = "bulksms-ctc-styles";
    const _cache = {};

    // ── Helpers ───────────────────────────────────────────────────────────────
    function sanitizeNumber(raw) {
        if (!raw) return "";
        let d = String(raw).replace(/\D/g, "");
        if (d.length > 10) d = d.slice(-10);
        return d;
    }
    function maskNumber(raw) {
        const c = sanitizeNumber(raw);
        if (!c) return "";
        if (c.length <= 5) return c;
        return c.slice(0, 2) + "X".repeat(c.length - 5) + c.slice(-3);
    }

    // ── Route check — THE KEY GUARD ───────────────────────────────────────────
    // Returns true ONLY if browser is currently on Form/<doctype>/<docname>
    function isOnForm(doctype, docname) {
        try {
            const r = frappe.get_route();
            return r && r[0] === "Form" && r[1] === doctype && r[2] === docname;
        } catch (e) { return false; }
    }

    // ── CSS ───────────────────────────────────────────────────────────────────
    function injectCSS() {
        if (document.getElementById(CSS_ID)) return;
        const s = document.createElement("style");
        s.id = CSS_ID;
        s.textContent = `
            #${BTN_ID} {
                position: fixed; bottom: 30px; right: 30px;
                width: 56px; height: 56px; border-radius: 50%;
                background: #28a745; color: #fff; font-size: 24px;
                border: none; cursor: pointer; z-index: 9999;
                box-shadow: 0 4px 16px rgba(40,167,69,0.45);
                display: flex; align-items: center; justify-content: center;
                transition: background .2s, transform .15s, box-shadow .2s;
                outline: none; user-select: none;
            }
            #${BTN_ID}:hover {
                background: #218838; transform: scale(1.10);
                box-shadow: 0 6px 20px rgba(40,167,69,0.55);
            }
            #${BTN_ID}:active { transform: scale(0.96); }
            #${BTN_ID} .ctc-tip {
                position: absolute; bottom: 64px; right: 0;
                background: #333; color: #fff; padding: 4px 10px;
                border-radius: 4px; font-size: 12px; white-space: nowrap;
                opacity: 0; pointer-events: none; transition: opacity .2s;
            }
            #${BTN_ID}:hover .ctc-tip { opacity: 1; }
            .ctc-dialog-info {
                background: #f0fff4; border: 1px solid #b2dfdb;
                border-radius: 6px; padding: 14px 16px; margin-top: 4px;
                font-size: 13px; line-height: 1.8; color: #444;
            }
            .ctc-dialog-info strong { display:block; margin-bottom:4px; color:#333; }
            .ctc-field-label { font-size:12px; font-weight:600; color:#555; margin-bottom:4px; }
            .ctc-field-label .ctc-req { color:red; margin-left:2px; }
            .ctc-masked-input {
                width:100%; padding:7px 10px; border:1px solid #d1d8dd;
                border-radius:4px; background:#f9f9f9; color:#333;
                font-size:14px; cursor:default; box-sizing:border-box;
            }
            .ctc-error-msg { color:#e74c3c; font-size:12px; margin-top:3px; display:none; }
        `;
        document.head.appendChild(s);
    }

    // ── Button ────────────────────────────────────────────────────────────────
    function showFloatButton(frm, config) {
        removeFloatButton();
        injectCSS();
        const btn = document.createElement("button");
        btn.id = BTN_ID;
        btn.title = "Click to Call (BulkSMS)";
        btn.innerHTML = `&#x260E;<span class="ctc-tip">Click to Call</span>`;
        btn.setAttribute("aria-label", "Click to Call");
        btn.addEventListener("click", function () { openCallDialog(frm, config); });
        document.body.appendChild(btn);
        console.log("[CTC] ✅ Button shown →", frm.doctype, frm.docname);
    }

    function removeFloatButton() {
        const el = document.getElementById(BTN_ID);
        if (el) { el.remove(); console.log("[CTC] Button removed"); }
    }

    // ── Dialog ────────────────────────────────────────────────────────────────
    function openCallDialog(frm, config) {
        frappe.call({
            method: "bulksms_ctc.bulk_sms_ctc.api.get_call_dialog_data",
            args: { doctype: frm.doctype, docname: frm.docname },
            callback: function (r) { if (r.message) renderDialog(frm, config, r.message); },
        });
    }

    function renderDialog(frm, config, data) {
        const agentClean    = sanitizeNumber(data.agent_number);
        const receiverClean = sanitizeNumber(data.receiver_number);
        const agentMasked   = maskNumber(data.agent_number);
        const recvMasked    = maskNumber(data.receiver_number);
        const agentBad      = !agentClean    || agentClean.length    !== 10;
        const recvBad       = !receiverClean || receiverClean.length !== 10;

        const agentErr = agentBad
            ? (!agentClean ? "Agent number not configured. Contact System Manager."
               : "Agent number invalid \u2014 " + agentClean.length + " digits found, need 10.") : "";
        const recvErr = recvBad
            ? (!receiverClean ? "No phone in field <b>" + config.receiver_field + "</b>."
               : "Customer number invalid \u2014 " + receiverClean.length + " digits found, need 10.") : "";

        const dialog = new frappe.ui.Dialog({
            title: "BulkSMS Click to Call",
            fields: [
                {
                    fieldtype: "HTML", fieldname: "number_row",
                    options: `
                    <div style="display:flex;gap:16px;margin-bottom:12px;">
                        <div style="flex:1;">
                            <div class="ctc-field-label">From Number (Your Phone)<span class="ctc-req">*</span></div>
                            <input class="ctc-masked-input" readonly value="${agentMasked}" placeholder="Not configured"
                                style="${agentBad ? "border-color:#e74c3c;" : ""}"/>
                            ${agentBad
                                ? `<div class="ctc-error-msg" style="display:block;">${agentErr}</div>`
                                : `<div style="font-size:11px;color:#888;margin-top:3px;">Your phone from CTC User settings</div>`}
                        </div>
                        <div style="flex:1;">
                            <div class="ctc-field-label">To Number (Customer Phone)<span class="ctc-req">*</span></div>
                            <input class="ctc-masked-input" readonly value="${recvMasked}" placeholder="No number on record"
                                style="${recvBad ? "border-color:#e74c3c;" : ""}"/>
                            ${recvBad ? `<div class="ctc-error-msg" style="display:block;">${recvErr}</div>` : ""}
                        </div>
                    </div>`
                },
                {
                    fieldtype: "Select", fieldname: "call_type",
                    label: "Call Type", options: "Current\nSchedule",
                    default: "Current", reqd: 1,
                    onchange: function () {
                        const $row = dialog.$wrapper.find(".ctc-schedule-row");
                        if (dialog.get_value("call_type") === "Schedule") {
                            $row.show();
                        } else {
                            $row.hide();
                            $row.find("input[type='datetime-local']").val("");
                            const e = document.getElementById("ctc-dt-error");
                            if (e) e.style.display = "none";
                        }
                    },
                },
                {
                    fieldtype: "HTML", fieldname: "schedule_row",
                    options: `
                    <div class="ctc-schedule-row" style="display:none;margin-bottom:12px;">
                        <div class="ctc-field-label">Schedule Date &amp; Time<span class="ctc-req">*</span></div>
                        <input type="datetime-local" id="ctc-scheduled-dt"
                            style="width:100%;padding:7px 10px;border:1px solid #d1d8dd;
                            border-radius:4px;font-size:14px;color:#333;background:#fff;box-sizing:border-box;"/>
                        <div id="ctc-dt-error" class="ctc-error-msg">Please select a schedule date &amp; time.</div>
                    </div>`
                },
                {
                    fieldtype: "HTML", fieldname: "how_it_works",
                    options: `
                    <div class="ctc-dialog-info">
                        <strong>How it works:</strong>
                        1. First, you will receive a call on your number<br>
                        2. After you answer, the customer will be called<br>
                        3. Both calls will be connected
                    </div>`
                },
            ],
            primary_action_label: "Call",
            primary_action: function () {
                if (agentBad) { frappe.msgprint({ title: __("Invalid Agent Number"), message: __(agentErr), indicator: "red" }); return; }
                if (recvBad)  { frappe.msgprint({ title: __("Invalid Customer Number"), message: __(recvErr), indicator: "red" }); return; }

                const isScheduled = dialog.get_value("call_type") === "Schedule";
                let scheduledDt = "";
                if (isScheduled) {
                    const inp = document.getElementById("ctc-scheduled-dt");
                    const raw = inp ? inp.value : "";
                    const err = document.getElementById("ctc-dt-error");
                    if (!raw) { if (err) err.style.display = "block"; if (inp) inp.style.borderColor = "#e74c3c"; return; }
                    scheduledDt = raw.replace("T", " ") + ":00";
                    if (err) err.style.display = "none";
                    if (inp) inp.style.borderColor = "#d1d8dd";
                }
                dialog.get_primary_btn().prop("disabled", true).text(__("Calling\u2026"));
                frappe.call({
                    method: "bulksms_ctc.bulk_sms_ctc.api.make_call",
                    args: {
                        doctype: frm.doctype, docname: frm.docname,
                        scheduled: isScheduled ? "1" : "0",
                        scheduled_datetime: scheduledDt,
                    },
                    callback: function (r) {
                        dialog.get_primary_btn().prop("disabled", false).text(__("Call"));
                        if (r.message && r.message.status === "success") {
                            dialog.hide();
                            frappe.show_alert({
                                message: isScheduled
                                    ? __("\uD83D\uDCC5 Call scheduled for {0} to {1}!", [r.message.scheduled_for, recvMasked])
                                    : __("\u2705 Call initiated to {0}!", [recvMasked]),
                                indicator: isScheduled ? "blue" : "green",
                            }, 6);
                        }
                    },
                    error: function () { dialog.get_primary_btn().prop("disabled", false).text(__("Call")); },
                });
            },
        });
        if (agentBad || recvBad) dialog.get_primary_btn().prop("disabled", true);
        dialog.show();
    }

    // ── Core handler ──────────────────────────────────────────────────────────
    function handleRefresh(frm) {
        removeFloatButton();

        if (!frm || !frm.doctype || !frm.docname) return;
        if (frm.is_new && frm.is_new()) return;
        if (SKIP_DOCTYPES.includes(frm.doctype)) return;

        // ✅ CRITICAL: Verify browser is actually on this form right now
        if (!isOnForm(frm.doctype, frm.docname)) {
            console.log("[CTC] Route mismatch — not showing button");
            return;
        }

        console.log("[CTC] handleRefresh →", frm.doctype, frm.docname);

        if (_cache[frm.doctype] === false) return;

        if (_cache[frm.doctype] && _cache[frm.doctype].allowed) {
            showFloatButton(frm, _cache[frm.doctype]);
            return;
        }

        frappe.call({
            method: "bulksms_ctc.bulk_sms_ctc.api.check_ctc_eligibility",
            args: { doctype: frm.doctype },
            callback: function (r) {
                if (!r.message) return;
                _cache[frm.doctype] = r.message.allowed ? r.message : false;
                // ✅ Double-check route AGAIN after async call returns
                if (r.message.allowed && isOnForm(frm.doctype, frm.docname)) {
                    showFloatButton(frm, r.message);
                } else {
                    console.log("[CTC] Route changed during API call — button suppressed");
                }
            },
        });
    }

    // ── Patch form refresh ────────────────────────────────────────────────────
    var _patchApplied = false;
    function applyPatch() {
        if (!frappe || !frappe.ui || !frappe.ui.Form || _patchApplied) return;
        const _orig = frappe.ui.Form.prototype.refresh;
        frappe.ui.Form.prototype.refresh = function () {
            const result = _orig.apply(this, arguments);
            try { handleRefresh(this); } catch (e) { console.warn("[CTC] patch error:", e); }
            return result;
        };
        _patchApplied = true;
        console.log("[CTC] ✅ Form.prototype.refresh patched");
    }

    // ── NAVIGATION: remove button on ANY route change ─────────────────────────
    // Covers: sidebar, breadcrumb, home, workspace, browser back, list view
    function setupRouteWatcher() {
        // 1. Intercept frappe.set_route (programmatic navigation)
        if (!frappe._ctc_route_intercepted) {
            const _orig = frappe.set_route.bind(frappe);
            frappe.set_route = function () {
                removeFloatButton();
                return _orig.apply(frappe, arguments);
            };
            frappe._ctc_route_intercepted = true;
            console.log("[CTC] frappe.set_route intercepted");
        }

        // 2. page-change event (covers ALL navigation including browser back)
        $(document).on("page-change", function () {
            removeFloatButton();
            // After short delay, check if new page is a form
            setTimeout(function () {
                try {
                    const r = frappe.get_route();
                    if (r && r[0] === "Form" && typeof cur_frm !== "undefined" && cur_frm
                        && cur_frm.doctype === r[1] && cur_frm.docname === r[2]) {
                        handleRefresh(cur_frm);
                    }
                } catch (e) {}
            }, 250);
        });

        // 3. hashchange — catches browser back/forward button
        $(window).on("hashchange", function () {
            removeFloatButton();
        });
    }

    // ── Realtime ──────────────────────────────────────────────────────────────
    function setupRealtime() {
        if (!frappe.realtime) return;
        frappe.realtime.on("bulksms_ctc_settings_updated", function () {
            Object.keys(_cache).forEach(function (k) { delete _cache[k]; });
            console.log("[CTC] Settings updated → cache cleared");
            if (typeof cur_frm !== "undefined" && cur_frm && isOnForm(cur_frm.doctype, cur_frm.docname)) {
                handleRefresh(cur_frm);
            }
        });
    }

    // ── Boot ──────────────────────────────────────────────────────────────────
    $(document).ready(function () {
        frappe.after_ajax(function () {
            applyPatch();
            setupRouteWatcher();
            setupRealtime();
            // Handle direct URL access
            if (typeof cur_frm !== "undefined" && cur_frm && cur_frm.doctype) {
                handleRefresh(cur_frm);
            }
        });
    });

})();
