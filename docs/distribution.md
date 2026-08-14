# Distribution playbook — drafts for the owner's click

The agent builds and drafts; the owner posts. Nothing below is sent or posted
by automation.

## HuggingFace dataset mirror (one-time, ~10 min)

Why: HF's audience is exactly ours; a dataset listing earns permanent
discovery + backlink.

1. Create/log into huggingface.co account → New Dataset → name: `gpudiff/gpu-cloud-prices`
   (or under your username), license **CC BY 4.0**.
2. Dataset card (paste):

> # GPU cloud price history — gpudiff.com
> Hourly snapshots of GPU cloud rental prices (Vast.ai, RunPod, AWS, Azure —
> on-demand and spot), plus LLM API per-token prices, with provenance URLs on
> every record. Collected and validated by the open pipeline at
> https://github.com/graemegilmourbates/gpudiff ; browse the live changelog at
> https://gpudiff.com. Refreshed continuously; every change is diffed and
> recorded. License CC BY 4.0 — cite gpudiff.com.

3. Upload: `data/offers/*.json` + `data/changelog.json` (or connect the GitHub
   repo). Update cadence: whenever — even stale, the card links the live site.

## Newsletter pitch (send from your email, personalize the first line)

Targets (find contact/submission forms on their sites): TLDR AI, Ben's Bites,
The Rundown AI, AlphaSignal, Latent Space, Superhuman AI, The Neuron,
Import AI's tips inbox — plus any GPU/infra newsletter you read.

> Subject: free citable stat: GPU cloud prices moved X% this week
>
> Hi — I run gpudiff.com, an open tracker that snapshots GPU cloud, LLM API,
> and SaaS prices hourly and publishes the diffs (CC BY, provenance on every
> number). This week's example: [one concrete stat from the changelog].
> If you ever need a "what does an H100 actually cost right now / how has it
> moved" number, it's free to cite — happy to pull any custom cut for you.
> RSS of every change: https://gpudiff.com/rss.xml

## Community answers (ongoing, 10 min/week)

When r/LocalLLaMA, r/MachineLearning, or HN threads ask "cheapest H100?" /
"is GPU cloud getting cheaper?" — answer with the actual numbers and link the
relevant family page. The data is the value; the link is incidental. Never
post the site without an answer attached.

## Search consoles (one-time, optional but useful)

- Google Search Console: add property gpudiff.com (DNS TXT verification at
  Porkbun), submit sitemap https://gpudiff.com/sitemap.xml
- Bing Webmaster Tools: import from GSC. (IndexNow pings already run daily
  from CI.)
