# Launch plan — needs owner approval before anything is posted

Nothing here gets posted by the agent. The owner posts under their own
accounts, on their own judgment. Target: when the changelog has ≥5 days of
visible diffs and sparklines have shape (est. week of Aug 31).

## Show HN draft

**Title (pick one):**
1. `Show HN: Gpudiff – a changelog for GPU cloud prices`
2. `Show HN: I track every GPU cloud price change (4 providers, hourly, open data)`

**Post text:**

> Cloud GPU prices move constantly — marketplaces reprice hourly, providers
> quietly cut list prices — but every comparison site only shows you *now*.
> I wanted the record of *what changed*, so I built gpudiff.
>
> It snapshots prices hourly from Vast.ai, RunPod, AWS, and Azure into a public
> git repo, validates them (anything failing checks is dropped, not published;
> >40% daily moves get quarantined for human review), and publishes the diff:
> a changelog, per-GPU history, RSS, and a free JSON API (CC BY 4.0).
>
> Some things it surfaces already: identical H100 silicon spans a ~2.6× price
> range depending on where you rent it; spot floors on marketplaces sit far
> below list. Every number links the page it was observed on.
>
> Methodology (including what it deliberately doesn't claim):
> https://gpudiff.com/methodology.html
>
> The whole pipeline is a public repo run by GitHub Actions on cron — happy to
> answer anything about the scraping/validation design.

**First comment (post immediately after):** short note on the family model —
memory config = identity, and why cross-GPU "cheapest" rankings mislead — plus
an ask: "which providers should be next?"

## Rules for the owner

- Post from your account, morning US Eastern, Tue–Thu.
- Never solicit upvotes anywhere, ever (HN bans this).
- Reply to every substantive comment in the first 3 hours (the agent can draft
  replies live if you paste comments in).
- Referral links stay as they are — the footer + methodology disclose them.
  If HN asks, answer plainly: yes, referral-funded, numbers unaffected, repo
  public.

## Cross-posts (staggered over the following week, owner's accounts)

- r/LocalLLaMA — angle: spot floors + $/GB lens for local-vs-cloud decisions
- r/MachineLearning (rules permitting) — the open dataset angle
- lobste.rs if a member invites; do not beg invites

## Pre-launch checklist

- [ ] ≥5 days of changelog entries visible
- [ ] Enforce HTTPS ticked (STILL pending)
- [x] GoatCounter wired (`graemebates`, 2026-08-14) — dashboard: https://graemebates.goatcounter.com
- [ ] GoatCounter Settings → enable **public counter** (30 sec) so the weekly analyst can read visit totals without your login
- [ ] Buttondown created if email capture wanted for launch (optional; RSS works)
- [ ] Owner reads methodology page top to bottom (you will be quizzed by HN)
