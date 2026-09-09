# OgrowNT

## About

This repository is under active development. More details will be added here as the project takes shape.

## Production deployment (Vercel)

The `ogrownt` Vercel project deploys `apps/web` from this repo's `main` branch. To stand up a new environment:

1. Provision a Postgres database (e.g. Neon) and add its connection string as `DATABASE_URL` in the Vercel project's Environment Variables (Production scope).
2. Add `CRON_SECRET` (any random string) — it gates the scheduled job routes and the one-time bootstrap route below.
3. Push to `main`. `apps/web`'s build script runs `prisma migrate deploy` before `next build`, so schema setup is automatic once `DATABASE_URL` exists.
4. Once the deploy is `READY`, populate the catalog once: `GET /api/admin/jobs/bootstrap-seed?secret=<CRON_SECRET>`. It's a no-op if the database already has any `Assessment` row, so it's safe to call more than once. See `packages/db/src/seed.ts`.
5. (Optional) Add `NEXT_PUBLIC_META_PIXEL_ID` for paid-traffic attribution — see `components/MetaPixel.tsx`. `NEXT_PUBLIC_` vars are inlined at build time, so a redeploy is required after adding one.
6. Add `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `RESEND_API_KEY`, and `ANTHROPIC_API_KEY` for live payments, email delivery, and AI report generation (see `/admin/settings` for live status of each). **Every env var — not just `NEXT_PUBLIC_` ones — is baked into the Serverless Function at build time**, so adding or changing any of them always requires a new deployment before it takes effect; Vercel does not read env vars from a live config store per-request.
