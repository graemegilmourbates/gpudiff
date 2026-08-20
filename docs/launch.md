# Launch plan — the owner posts, never the agent

Status: **ready**. Gate cleared (6 days of diffs, 345 changelog entries,
2,652 prices, 28 providers, 407 indexed URLs).

## Timing

Tue–Thu, 8–10am US Eastern is the prime window. What matters more than the
hour: be at the keyboard for the next 3 hours to answer comments. If you
can't, wait for a morning when you can.

## The post

**Title** (pick one, no editorializing — HN dislikes hype in titles):

1. `Show HN: Gpudiff – hourly price changelog for GPU clouds and LLM APIs`
2. `Show HN: I diff GPU cloud and LLM API prices hourly and publish every change`

**Body** (rewritten 2026-08-20 after finding ComputePrices.com — see
"Competitive correction" below; do NOT use the earlier draft that claimed
nobody tracks price changes):

> There are already good cloud price comparison sites — getdeploying,
> gpuperhour, computeprices, gpufinder. Several track changes and some have
> history. What I couldn't find was the raw archive: the actual snapshots,
> openly licensed, with every number linking the page it was scraped from, so
> you can audit the collection or run your own analysis instead of trusting
> mine.
>
> So gpudiff commits every hourly snapshot to a public git repo. The site is
> just a view over it: a changelog, per-model and per-GPU history, RSS, and a
> JSON API with no key and no rate limit. Data is CC BY 4.0. The scrapers,
> the validation rules, and the entire price archive are the repo.
>
> It covers GPU clouds (Vast.ai, RunPod, AWS, Azure — on-demand and spot),
> LLM gateways (OpenRouter, Ramp Router, Requesty, Glama, Novita, DeepInfra),
> and a beta section watching SaaS pricing pages.
>
> A few things it surfaced:
>
> - The same H100 SXM 80GB runs $3.29/hr on RunPod and $12.29/hr on Azure
>   on-demand — 3.7x for identical silicon.
> - Frontier LLM models are priced identically on every gateway (Claude Opus 5
>   is $5/$25 per Mtok on all five carrying it) because gateways pass list
>   pricing through. Open-weight models are the opposite: up to 10x spread for
>   the same weights depending on where you buy.
> - Ramp Router vs OpenRouter: 41 of 50 shared models priced identically,
>   OpenRouter cheaper on 9, so fees decide it rather than token price.
>
> The part I'd most like feedback on is the validation, because the failure
> mode for a price tracker is publishing a confident wrong number: anything
> failing schema validation is dropped rather than published, a >40% daily
> move is quarantined for human review, a provider vanishing from a source
> never emits phantom delistings, and prices with no stock behind them are
> excluded. Missing beats wrong.
>
> Methodology, including what it deliberately doesn't claim:
> https://gpudiff.com/methodology.html
>
> Which providers should I add next?

**First comment (post immediately after, in your own words):**

> Two implementation notes for anyone curious:
>
> Identity turned out to be the whole problem. A GPU memory configuration is a
> product — H100 PCIe 80GB, NVL 94GB and SXM 80GB never share a row — and LLM
> models needed a canonical join because every gateway spells them differently
> (vertex/claude-sonnet-5@eu, anthropic/claude-sonnet-5, and Ramp's bare
> "sonnet-5" are one model).
>
> Also: this is built and operated by an AI agent pipeline, which is exactly
> why the validation gates are strict — the interesting engineering is in what
> the system refuses to publish. Total infrastructure cost is about $1/month.
> Repo: https://github.com/graemegilmourbates/gpudiff

## Rules

- Post from your own account. Never ask anyone for upvotes (instant ban).
- Reply to every substantive comment in the first 3 hours; concede fair points
  ("good catch — filed") rather than arguing.
- Referral links stay disclosed in the footer and methodology. If asked: yes,
  referral-funded, numbers unaffected, repo public, check it.
- If it doesn't take off by hour 3, let it go. The LLM-gateway and SaaS
  angles are separate posts for later weeks.

## Predicted questions

See docs/hn-war-room.md — drafted answers for the seven questions HN reliably
asks (isn't this just X, scraping ethics, p25 defense, negotiated pricing,
how do you make money, why trust an AI pipeline, feature requests).

## After posting

Paste new comments to the agent for drafted replies. Watch traffic at
https://graemebates.goatcounter.com and HN mentions via
https://hn.algolia.com/?query=gpudiff

---

# Blocked: "account too new" (2026-08-20)

HN's spam heuristic gates submissions on account age + activity. It is not a
Show HN rule and it lifts on its own, usually days to a couple of weeks.
Do NOT create another account, ask anyone to post it for you, or buy karma —
all three are bannable and would cost us the channel permanently.

## 1. Email the mods (today, 2 minutes)

To: hn@ycombinator.com
Subject: Submission blocked — account too new

> Hi — I tried to submit a Show HN for a project I built and got "account is
> too new to submit". Username: <your username>. URL: https://gpudiff.com —
> it's my own project (open source: github.com/graemegilmourbates/gpudiff),
> an hourly price changelog for GPU clouds and LLM APIs. Attempted around
> <date/time, timezone>. Happy to wait if that's the process — just wanted to
> check whether anything is wrong with the account. Thanks.

Mods usually reply within a day and often clear it.

## 2. Age the account honestly (this week)

Comment substantively on 2–3 HN threads in areas you actually know. Not
"great post" filler — real answers. Karma accrues, the gate lifts, and you
arrive at your own Show HN with a history rather than as a green account
posting a link. Never mention gpudiff in those comments unless it is
genuinely the best answer to someone's question.

## 3. Launch the ungated channels NOW

The HN delay is a scheduling problem, not a launch problem. These have no
account-age gate and each one is a permanent backlink:

**a. Hugging Face dataset** — card drafted in docs/distribution.md. Their
audience is exactly ours. Publishes immediately.

**b. Newsletter pitches** — the highest-ROI ungated channel: direct email to
editors, no gatekeeper, and a citation is worth more than a mid-tier HN
placement. Template and target list in docs/distribution.md. Send 5 today.

**c. Reddit** — post the FINDINGS, not the link. Most subs remove link-only
self-promo, and new Reddit accounts hit their own age gates, so check each
sub's rules first.

r/LocalLLaMA (best fit — they rent GPUs and buy tokens):

> Title: The same LLM costs up to 10x more depending on which gateway you buy
> it through — I diffed six of them
>
> I've been snapshotting per-token prices hourly across OpenRouter, Ramp
> Router, Requesty, Glama, Novita and DeepInfra, and normalizing them so the
> same model lines up across gateways. Two patterns that surprised me:
>
> Frontier models are priced identically everywhere. Claude Opus 5 is $5/$25
> per Mtok on all five gateways that carry it — they pass provider list
> pricing straight through, so there is nothing to shop for.
>
> Open-weight models are the opposite. Same model, same weights, up to 10x
> spread depending on the gateway (ling-2.6-flash), 8.9x on Mistral Nemo.
> DeepSeek V4 Flash is 37% cheaper on OpenRouter than on Ramp Router.
>
> On the GPU side the same thing holds: an H100 SXM is $3.29/hr on RunPod and
> $12.29/hr on Azure on-demand.
>
> Data is CC BY, the API needs no key, and every number links to the page it
> was scraped from: https://gpudiff.com/llm/ — happy to pull any cut you want.

r/SideProject / r/IndieHackers: the $100-business angle instead — what it
cost to build and run ($1/month infrastructure), what it tracks, what broke.

**d. Lobsters** — invite-only. Do not beg for an invite; skip unless someone
offers.

## 4. Then Show HN, stronger

By the time the gate lifts we will have another week of changelog entries,
which makes the post better, not worse — "here's what changed in AI compute
prices over the last two weeks" beats "here is a thing I built yesterday."

---

# Competitive correction (2026-08-20) — READ BEFORE POSTING

A `site:` check for indexing surfaced competitors the Aug 14 scan
under-investigated. Verified:

**ComputePrices.com** — 79 providers, ~304k prices/day, GPU *and* LLM
sections, a "Biggest Drops This Week" panel, a weekly email of notable price
changes, and a free API (750 req/day, hourly) with a paid tier extending
history to 90 days. That is substantially our product at ~10x the coverage,
already shipped, already monetized.

**GPUFinder.dev** — 14-month price history charts, email alerts on price
drops, head-to-head comparison pages, an API, and llms.txt.

**Implication:** the claim "nobody publishes the record of change" is FALSE
and would have been demolished in the first HN comment. The post body above
was rewritten to lead with what is actually differentiated:

1. The full archive is public, versioned git — not a UI over a private DB.
2. CC BY 4.0 with no key and no rate limit, versus free tiers with quotas.
3. Provenance URL on every single datum.
4. The validation rules are published and the pipeline is open, so the
   collection itself is auditable.
5. Sections nobody else combines (SaaS page-scan alongside GPU and LLM).

What is NOT differentiated: coverage (28 providers vs their 79), scale,
polish, or freshness. Do not claim any of those.

**Strategic read:** we are a small late entrant in a crowded niche. The
day-90 gates matter more than they did a week ago. If traffic does not
materialize, hibernating and moving the pipeline to a less contested dataset
is the correct call, not a failure — that is exactly what the Foundry
structure is for.
