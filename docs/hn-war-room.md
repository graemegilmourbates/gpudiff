# HN war room — predicted questions, drafted answers

For launch day. Owner posts and replies from their account; agent live-drafts
during the thread. These are starting points — personalize, never paste blindly.

**"Isn't this just gputracker.dev / gpuperhour / getdeploying?"**
> Those are good snapshot sites — they answer "what does it cost now." gpudiff
> answers "what changed": every move is diffed, dated, and kept forever, with
> the history in public git. Different product. (Also: alerts-by-RSS, per-token
> LLM prices, and SaaS pricing pages in the same changelog.)

**"Scraping — is this against ToS?"**
> Sources are public, unauthenticated endpoints or public pages; we identify
> ourselves in the user-agent, fetch respectfully (hourly for small JSON, daily
> for big files), store the provenance URL on every datum, and honor takedowns.
> AWS/Azure pricing comes from their official public pricing APIs/files.

**"Marketplace p25 is made up / why not the minimum?"**
> The single cheapest Vast listing is often a trap (bad host, no availability).
> p25 across verified listings is "what a careful buyer can actually get."
> Methodology page documents it; the raw distribution is in the data if you
> want a different cut.

**"Prices are negotiated anyway; list prices are meaningless."**
> True at enterprise scale, and the methodology says so. List and marketplace
> prices are what individuals and small teams actually pay, and their *changes*
> are directional signal for everyone — that's the product.

**"How do you make money?"**
> Provider links may carry referral codes (disclosed in the footer,
> rel=sponsored). The codes never touch the numbers — pipeline's open source,
> check. Data itself is CC BY, free, forever.

**"Why should I trust an AI-run pipeline?"**
> Trust the gates, not the agent: schema validation, 40% moves quarantined for
> human review, missing-beats-wrong policy, provenance on every datum, and
> every snapshot in public git history — the archive can't be quietly
> rewritten. Broken scrapers page a human instead of publishing garbage.

**"Feature request: provider X / alerts / API webhooks"**
> Best possible comment. Answer: sources are one file each (link the repo),
> webhooks/alerts are the planned paid tier, and ask what they'd pay for.

## Launch-day protocol

1. Post between 8–10am US Eastern, Tue–Thu.
2. First comment: the family-model explanation + "which providers next?"
3. Owner pastes new comments to the agent; agent drafts replies in their
   voice; owner edits and posts. Target: every substantive comment answered
   inside an hour for the first 3 hours.
4. Never argue tone, always concede fair points ("good catch — filed").
   HN respects operators who update.
5. If the post doesn't front-page by hour 3: let it go, no reposting the same
   day. The LLM and SaaS announcements are the next two shots.

## Standing monitoring (automated)

The weekly analyst checks HN's public search API for gpudiff mentions and
links them in its report. Between reports, anyone can check:
https://hn.algolia.com/?query=gpudiff
