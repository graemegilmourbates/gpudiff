# SEO — what's built, what the owner sets up, what to expect

## Built (automated, $0)

- Search-intent titles/H1s on all GPU pages ("H100 SXM 80GB Cloud Rental Price — from $X/hr, N providers compared")
- FAQ block + FAQPage structured data per GPU page and provider page (answer-box candidates)
- Provider pages: /provider/{vast,runpod,aws,azure}.html — "runpod pricing", "vast.ai pricing" queries
- Comparison pages: /compare/<a>-vs-<b>.html for the ten most-searched pairs (H100 vs H200, A100 vs H100, 4090 vs 5090…)
- Related-GPU internal links on every family page (authority flows between pages)
- Sitemap covers every page; robots allows all; canonicals; OG tags; Dataset JSON-LD; hourly freshness; IndexNow daily

## Owner setup (one-time, ~10 min total)

1. **Google Search Console** — https://search.google.com/search-console → Add property → Domain →
   `gpudiff.com` → copy the TXT record → add it in Porkbun DNS (Type TXT, host blank, answer = the string)
   → Verify. Then Sitemaps → submit `https://gpudiff.com/sitemap.xml`. Within ~1 week you'll see
   the actual queries we rank for; the agent will use those to pick new pages.
2. **Bing Webmaster Tools** — https://www.bing.com/webmasters → Import from Google Search Console (one click).
3. Optional: in GSC, request indexing for the homepage and 3–4 key GPU pages (accelerates first crawl).

## What to expect (honest)

- New domains sit in a Google sandbox for months. Long-tail queries ("rtx pro 6000 cloud price") can rank in
  2–6 weeks; mid-tail ("h200 rental price") 3–6 months; head terms ("gpu cloud pricing") only after real
  backlinks, 12+ months, maybe never against provider-owned pages.
- Backlinks decide it. Every distribution event (Show HN, HF dataset, badges, newsletter citations, community
  answers) is a link-building event first and a traffic event second.
- Never buy links, never spin content, never keyword-stuff — the site's whole moat is trust, and Google's
  penalties are the one thing that could zero the asset overnight.
