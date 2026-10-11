# Production checklist (Railway)

Do these in order. Nothing here needs code changes.

1. **Railway variables** (service -> Variables). Required for the app to boot in production:
   `CYRADUCT_ADMIN_KEY` (long random), `CYRADUCT_PRIVATE_KEY_B64` (from `python generate_key.py`, keep it forever or the signing identity changes).
   Recommended: `CYRADUCT_DATABASE_URL` (Postgres), `CYRADUCT_ALLOWED_ORIGINS=https://cyraduct.com`,
   `CYRADUCT_AUDIT_ANCHOR_URL` (+ token), `CYRADUCT_BACKUP_ENCRYPTION_KEY`.
2. **Check before deploying:** `railway run python scripts/check_production_env.py`. Fix every `FAIL`; read every `WARN`.
3. **Email (Resend):** create an API key, add and verify the `cyraduct.com` domain in Resend (add the SPF and DKIM DNS records it shows), then set
   `RESEND_API_KEY`, `PARTNER_NOTIFICATION_FROM="Cyraduct <notifications@cyraduct.com>"` and (optional) `PARTNER_NOTIFICATION_TO`.
   `hello@cyraduct.com` must already be a real mailbox that receives mail.
4. **Prove delivery:** `curl -X POST https://api.cyraduct.com/api/partners/notifications/test -H "X-Cyraduct-Admin-Key: $KEY"`
   returns `"status":"sent"` and the email arrives. `pending` means the variables are not set; `failed` means the key or domain is wrong.
5. **Prove the form:** submit the partner form on the website, confirm the email arrives and that Reply goes to the visitor.
6. **Recover missed leads:** `GET /api/partners/notifications` shows counts by status;
   `POST /api/partners/retry-notifications` re-sends `pending`/`failed` leads (10 per call, oldest first).
7. **After the first deploy of this version:** `GET /v1/admin/audit-log` should report `"chain_valid": true`.
