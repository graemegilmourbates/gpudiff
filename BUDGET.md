# The $100 War Chest

One-time seed: **$100. No further investment.** Operating rule: **the fund pays
for existence; revenue pays for growth.** Nothing recurring is ever charged to
the fund except the domain.

## Allocation

| Line                          | Amount | Notes                                            |
| ----------------------------- | -----: | ------------------------------------------------ |
| Domain, year 1                |   ~$11 | .com at cost (Cloudflare Registrar / Porkbun). Human buys. |
| Domain renewals, years 2–5    |   ~$44 | Reserved. Survival is pre-paid for half a decade. |
| Contingency                   |   ~$45 | Email-tier bridge, a second asset's domain, surprises. |

**Zero-touch renewals:** load a prepaid card with the renewal reserve, attach
it at the registrar as the payment method, turn on auto-renew. The one
mandatory payment then happens by itself for years — no human, no agent.

## Ledger

| Date       | Item                                   | Out    | Fund remaining |
| ---------- | -------------------------------------- | -----: | -------------: |
| 2026-08-14 | Seed                                   |     —  |        $100.00 |
| 2026-08-14 | gpudiff.com, 2-year term (Porkbun)     |  ~$22  |          ~$78  |

Registered through 2028-08-14. Renewal reserve now covers 2028–2031.

Mandatory burn ≈ **$0.92/month**. The fund alone keeps the business alive for
8+ years at zero revenue. **Profitability bar: ~$1/month** — roughly one
referral signup per year.

## Free-tier stack (costs $0 until success forces upgrades)

- **Compute/CI**: GitHub Actions on a public repo — free, unlimited standard minutes.
- **Hosting**: Cloudflare Pages free tier.
- **Distribution**: RSS (free forever, uncapped) + email on Buttondown free tier (≤100 subscribers).
- **Billing later**: Lemon Squeezy merchant of record — % of sales only, no fixed cost.
- **Agent labor**: digest v1 is deterministic Python in CI (no LLM spend); editorial
  polish happens in the team's existing Claude Code sessions, which are a sunk
  subscription cost outside this fund.

## Upgrade triggers (revenue-funded only)

| Trigger                        | Upgrade              | Paid by                     |
| ------------------------------ | -------------------- | --------------------------- |
| >100 email subscribers         | Buttondown ~$9/mo    | First sponsor / referrals   |
| API demand appears             | Keyed API on Workers | API subscriptions           |
| A source needs paid access     | Don't. Find a free one. | —                        |

## Never

Paid ads. Paid SaaS from the fund. Paid data. Capital at risk.
