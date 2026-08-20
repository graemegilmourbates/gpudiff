"""Ramp Router — availability catalog, not prices.

Ramp opened its internal LLM gateway to the public in July 2026: free through
2026, "you pay list price for the tokens you use." No public price endpoint
and no markup to record, so the trackable fact is *which models it carries*.
That still diffs into news nobody else publishes — "Ramp Router added kimi-k3"
— and the watchlist uses it as an availability column.

Extraction is whitelist-based: only tokens matching known model-family
prefixes are accepted, and a page yielding fewer than MIN_MODELS is treated as
broken rather than as a mass delisting."""

import re
import urllib.request

from .base import Source

URL = "https://docs.router.com/supported-models"
UA = "Mozilla/5.0 (compatible; FoundryBot/0.1; +https://gpudiff.com/methodology.html)"
MIN_MODELS = 5

FAMILIES = (
    r"gpt-[45][\w.\-]*", r"claude-[\w.\-]+", r"gemini-[\w.\-]+", r"kimi-[\w.\-]+",
    r"o[34]-[\w.\-]+", r"deepseek-[\w.\-]+", r"llama-[\w.\-]+", r"qwen[\w.\-]+",
    r"glm-[\w.\-]+", r"mistral-[\w.\-]+", r"grok-[\w.\-]+",
    # Ramp lists Anthropic models bare, without the claude- prefix.
    r"(?:sonnet|opus|haiku|fable)-[\w.\-]+",
)
PATTERN = re.compile(r"\b(" + "|".join(FAMILIES) + r")\b", re.I)
# Doc prose picks up stray words after a model name; keep the token itself only.
TRAILING_JUNK = re.compile(r"-(?:and|or|the|for|with|is|are|models?|supported)$", re.I)
# Ramp writes decimal points as "p" (kimi-k2p6 = Kimi K2.6, glm-5p2 = GLM 5.2).
VERSION_P = re.compile(r"(\d)p(\d)")
ANTHROPIC_BARE = re.compile(r"^(sonnet|opus|haiku|fable)-")


def normalize(name):
    """Ramp's spelling -> the canonical name other routers use, so one model is
    one row across the whole site."""
    name = VERSION_P.sub(r"\1.\2", name)
    if ANTHROPIC_BARE.match(name):
        name = "claude-" + name
    return name


class RampCatalogSource(Source):
    name = "ramp"
    kind = "catalog"
    cadence = "daily"

    def fetch(self, observed_at):
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read(4_000_000).decode("utf-8", errors="replace")

        names = set()
        for m in PATTERN.finditer(html):
            name = TRAILING_JUNK.sub("", m.group(1).lower()).strip("-.")
            if 3 <= len(name) <= 48:
                names.add(normalize(name))

        if len(names) < MIN_MODELS:
            raise RuntimeError(f"only {len(names)} models parsed from {URL} — page shape changed")

        return [{
            "provider": "ramp",
            "item": name,
            "attrs": {"gateway": "Ramp Router", "pricing_policy": "list price passthrough"},
            "provenance": {"url": URL, "observed_at": observed_at},
        } for name in sorted(names)]
