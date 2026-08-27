## Bulk SMS CTC

Bulk SMS Telephony Integration

#### License

mit

## Install
```bash
cp -r bulksms_ctc ~/frappe-bench/apps/
bench --site yoursite.com install-app bulksms_ctc
bench --site yoursite.com migrate
bench build --app bulksms_ctc
bench restart

------------ First run this in bench ---------------
1. ./env/bin/python3 -m pip install -e ./apps/bulksms_ctc
2. Add 'bulksms_ctc' in ----sites/app.txt file
3. bench --site sitename install-app bulksms_ctc
4. bench --site sitename migrate
5. bench build --app bulksms_ctc
6. bench restart
```

## Webhook URL (register in BulkSMS portal)
https://yoursite.com/api/method/bulksms_ctc.bulk_sms_ctc.api.call_webhook