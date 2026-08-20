"""Ramp Router — the LLM gateway Ramp opened to the public in July 2026.

Its docs publish a full model table: input and output price per million tokens,
context window, and fast-mode availability. Ramp states it bills tokens at
provider list price and charges no gateway fee through 2026, which makes it the
cleanest available proxy for "what does this model cost at list" — and the
reason a Ramp-vs-router comparison is worth publishing.

Two naming quirks are normalized into the shared namespace so one model is one
row site-wide: decimals written as "p" (kimi-k2p6 = Kimi K2.6) and Anthropic
models listed without the claude- prefix (opus-5 = claude-opus-5)."""

import re
import urllib.request

from .base import Source, make_id, slug

URL = "https://docs.router.com/supported-models"
UA = "Mozilla/5.0 (compatible; FoundryBot/0.1; +https://gpudiff.com/methodology.html)"
MIN_MODELS = 10

ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CODE = re.compile(r"<code>([^<]+)</code>")
MONEY = re.compile(r"\$([\d.,]+)")
CREATOR = re.compile(r'data-model-creator="([^"]+)"')
BIGNUM = re.compile(r">([\d,]{4,})<")

VERSION_P = re.compile(r"(\d)p(\d)")
ANTHROPIC_BARE = re.compile(r"^(sonnet|opus|haiku|fable)-")


def normalize(name):
    """Ramp's spelling -> the canonical name the other routers use."""
    name = VERSION_P.sub(r"\1.\2", name.strip().lower())
    if ANTHROPIC_BARE.match(name):
        name = "claude-" + name
    return name


def _money(text):
    try:
        v = float(text.replace(",", ""))
    except ValueError:
        return None
    return v if v > 0 else None


class RampSource(Source):
    name = "ramp"
    cadence = "daily"

    def fetch(self, observed_at):
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read(4_000_000).decode("utf-8", errors="replace")

        offers, seen = [], set()
        for row in ROW.findall(html):
            code = CODE.search(row)
            if not code:
                continue
            canonical = normalize(code.group(1))
            if not canonical or canonical in seen:
                continue
            prices = MONEY.findall(row)
            if len(prices) < 2:
                continue  # a row without both directions tells us nothing
            price_in, price_out = _money(prices[0]), _money(prices[1])
            if not price_in or not price_out:
                continue
            seen.add(canonical)

            nums = [int(n.replace(",", "")) for n in BIGNUM.findall(row)]
            creator = CREATOR.search(row)
            for direction, price in (("input", price_in), ("output", price_out)):
                sku = f"{slug(canonical)}-{direction}"
                offers.append({
                    "id": make_id("ramp", sku, "global", "list"),
                    "provider": "ramp",
                    "sku": sku,
                    "price": round(price, 4),
                    "unit": "usd_per_mtok",
                    "pricing_type": "list",
                    "region": "global",
                    "attrs": {
                        "model_id": code.group(1),
                        "canonical": canonical,
                        "direction": direction,
                        "context_length": nums[0] if nums else None,
                        "lab": creator.group(1) if creator else None,
                        "metric": "gateway_list",
                    },
                    "provenance": {"url": URL, "observed_at": observed_at},
                    "fixture": False,
                })

        if len(seen) < MIN_MODELS:
            raise RuntimeError(f"only {len(seen)} models parsed from {URL} — page shape changed")
        return offers
