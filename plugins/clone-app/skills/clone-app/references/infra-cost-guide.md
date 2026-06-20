# Infrastructure Cost Guide (Phase 5)

Estimate **monthly USD** at three scales: MVP (<1k MAU), Growth (~50k MAU),
Scale (~500k MAU). Use round heuristics; mark assumptions.

## Components
| Component | MVP | Growth | Scale | Notes |
|---|---|---|---|---|
| App hosting/backend | $0-20 | $50-200 | $500-2k | Railway/Render/Fly → AWS/GCP |
| Managed DB (Postgres) | $0-15 | $50-150 | $300-1k | Supabase/Neon/RDS |
| Object storage/CDN | $0-5 | $20-80 | $200-800 | S3+CloudFront/Cloudflare |
| Auth (managed) | $0 | $0-100 | $200-500 | Supabase/Auth0 tiers |
| Push notifications | $0 | $0-50 | $50-300 | FCM free; OneSignal paid tiers |
| Third-party APIs | varies | varies | varies | maps, SMS, payments % |
| Monitoring | $0 | $20-50 | $100-300 | Sentry/Datadog |

## Third-party cost flags from RE
- Maps SDK → Google Maps billing after free tier.
- Payment SDK → % per transaction (Stripe ~2.9%+30¢).
- SMS/OTP → per-message (Twilio).
List each detected paid dependency explicitly.

## Output
A 3-column (MVP/Growth/Scale) monthly cost table + a one-line "biggest cost driver".
