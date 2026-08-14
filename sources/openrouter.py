"""OpenRouter model catalog: public no-auth JSON with per-token prices for
hundreds of models across providers. This is the volatile layer of LLM API
pricing — model adds/removals and repricing happen constantly, which is
exactly what a changelog wants. Two offers per model (input and output, in
USD per million tokens) so each direction diffs independently. Official
provider list pages (Anthropic/OpenAI/Google docs) are a later, slower layer."""

import json
import urllib.request

from .base import Source, make_id, slug

API = "https://openrouter.ai/api/v1/models"
UA = "FoundryBot/0.1 (pricing aggregator; gpudiff.com)"


class OpenRouterSource(Source):
    name = "openrouter"
    cadence = "hourly"

    def fetch(self, observed_at):
        req = urllib.request.Request(API, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)

        offers = []
        for model in payload.get("data", []):
            mid = model.get("id")
            pricing = model.get("pricing") or {}
            if not mid:
                continue
            base = slug(mid)
            for field, direction in (("prompt", "input"), ("completion", "output")):
                try:
                    per_tok = float(pricing.get(field) or 0)
                except (TypeError, ValueError):
                    continue
                if per_tok <= 0:
                    continue
                per_mtok = round(per_tok * 1_000_000, 4)
                if per_mtok <= 0:
                    continue
                sku = f"{base}-{direction}"
                offers.append({
                    "id": make_id("openrouter", sku, "global", "list"),
                    "provider": "openrouter",
                    "sku": sku,
                    "price": per_mtok,
                    "unit": "usd_per_mtok",
                    "pricing_type": "list",
                    "region": "global",
                    "attrs": {
                        "model_id": mid,
                        "model_name": model.get("name"),
                        "context_length": model.get("context_length"),
                        "direction": direction,
                        "metric": "openrouter_list",
                    },
                    "provenance": {"url": f"https://openrouter.ai/{mid}",
                                   "observed_at": observed_at},
                    "fixture": False,
                })
        return offers
