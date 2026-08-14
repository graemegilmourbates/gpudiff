# Revenue accounts — human checklist

Both programs verified 2026-08-14. Accounts must belong to the human (revenue
lands with the owner; the agent never holds money or credentials).

## Vast.ai — 3% of referred lifetime spend

- Terms: 3% of referred users' lifetime spend, paid as credits; **up to 75%
  withdrawable as cash**. Docs: https://docs.vast.ai/guides/reference/referral-program
- Steps: create a vast.ai account → Settings → Referral Link → copy.
- Paste the link into `monetize.json` → `referral_links.vast` (or hand it to
  the agent). Every outbound Vast link on the site starts carrying it on the
  next hourly deploy.

## RunPod — 3–5% for 6 months, then a 10% cash affiliate tier

- Terms: referral link pays 3% (pods) / 5% (serverless) of referred spend for
  their first 6 months, in credits. After **25 referred paying users** you're
  invited to the affiliate tier: 10%, cash payout option.
  https://www.runpod.io/referral-and-affiliate-program
- Steps: create a runpod.io account → referral section → copy link → paste
  into `monetize.json` → `referral_links.runpod`.

## Analytics (needed before launch — the day-90 gate is unmeasurable without it)

- **GoatCounter** (free, privacy-friendly, no cookies): create an account at
  goatcounter.com (~2 min), pick a code (e.g. `gpudiff`), put it in
  `monetize.json` → `goatcounter_code`. The counter script appears sitewide on
  the next deploy. GitHub Pages has no server logs — without this, launch
  traffic is invisible.

## Later (traffic-gated, ignore until ~100 subscribers / sponsor interest)

- **Buttondown** (free ≤100 subs): create account, set
  `buttondown_username` in `monetize.json` — the email form appears on the
  site automatically.
- **Sponsor slot**: inquiries arrive via the GitHub issue link on the site;
  swap `sponsor_url` for a mailto when preferred.

## Cash-flow honesty

First revenue is credits-denominated at RunPod until the affiliate tier;
Vast allows 75% cash withdrawal from the start. Expect first *cash* from
Vast referrals or a sponsor, not RunPod, in the early months.
