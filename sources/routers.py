"""LLM router catalogs: Requesty, Glama, Novita, DeepInfra.

Each publishes an unauthenticated model list with per-token prices, so the
same model can be priced across several routers — the token-market equivalent
of comparing one GPU across clouds. Prices are normalized to USD per million
tokens, input and output tracked as separate series.

A router often lists the same model several times (different upstream hosts or
regions). We keep the cheapest route per (router, model, direction) — that's
the honest "what this router charges for this model" number — and record how
many routes were collapsed."""

import json
import re
import urllib.request

from .base import Source, make_id, slug

UA = "FoundryBot/0.1 (pricing aggregator; gpudiff.com)"


def canon_model(model_id):
    """Canonical model name shared across routers: last path segment, region
    suffix stripped, lowercased. vertex/claude-sonnet-5@eu -> claude-sonnet-5"""
    s = str(model_id).split("@")[0].strip().lower().split("/")[-1]
    return re.sub(r"[^a-z0-9.+-]+", "-", s).strip("-")


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def requesty_models():
    """input_price / output_price are USD per token."""
    for m in _fetch("https://router.requesty.ai/v1/models").get("data", []):
        mid = m.get("id")
        if not mid:
            continue
        yield mid, _num(m.get("input_price")), _num(m.get("output_price")), m.get("context_window")


def glama_models():
    """pricePerToken.input / .output are USD per token, as strings."""
    d = _fetch("https://glama.ai/api/gateway/v1/models")
    for m in (d.get("data") if isinstance(d, dict) else d) or []:
        mid, p = m.get("id"), m.get("pricePerToken") or {}
        if not mid:
            continue
        yield mid, _num(p.get("input")), _num(p.get("output")), m.get("maxTokensInput")


def novita_models():
    """*_token_price_per_m are USD per million tokens scaled by 10,000."""
    d = _fetch("https://api.novita.ai/v3/openai/models")
    for m in (d.get("data") if isinstance(d, dict) else d) or []:
        mid = m.get("id")
        if not mid:
            continue
        i, o = _num(m.get("input_token_price_per_m")), _num(m.get("output_token_price_per_m"))
        yield (mid, i / 10000.0 / 1e6 if i else None, o / 10000.0 / 1e6 if o else None,
               m.get("context_size"))


def deepinfra_models():
    """pricing.cents_per_*_token are US cents per token."""
    for m in _fetch("https://api.deepinfra.com/models/list"):
        pricing = m.get("pricing") or {}
        mid = m.get("model_name")
        if not mid or pricing.get("type") != "tokens" or m.get("deprecated"):
            continue
        i, o = _num(pricing.get("cents_per_input_token")), _num(pricing.get("cents_per_output_token"))
        yield (mid, i / 100.0 if i else None, o / 100.0 if o else None, m.get("max_tokens"))


ROUTERS = {
    "requesty": requesty_models,
    "glama": glama_models,
    "novita": novita_models,
    "deepinfra": deepinfra_models,
}


class RoutersSource(Source):
    """One source, four routers — a failure in one never costs us the others."""

    name = "routers"
    cadence = "hourly"

    @property
    def emits(self):
        return set(ROUTERS)

    def fetch(self, observed_at):
        offers, failures = [], []
        for router, lister in ROUTERS.items():
            try:
                rows = list(lister())
            except Exception as exc:  # noqa: BLE001 — one router down is not an outage
                failures.append(f"{router}: {type(exc).__name__}")
                continue

            # Cheapest route per (canonical model, direction) for this router.
            best = {}
            for mid, price_in, price_out, ctx in rows:
                canonical = canon_model(mid)
                if not canonical:
                    continue
                for direction, per_token in (("input", price_in), ("output", price_out)):
                    if not per_token:
                        continue
                    per_mtok = round(per_token * 1_000_000, 4)
                    if per_mtok <= 0:
                        continue
                    key = (canonical, direction)
                    cur = best.get(key)
                    if cur is None or per_mtok < cur["price"]:
                        best[key] = {"price": per_mtok, "model_id": mid, "context": ctx, "routes": 1}
                    else:
                        cur["routes"] += 1

            for (canonical, direction), info in sorted(best.items()):
                sku = f"{slug(canonical)}-{direction}"
                offers.append({
                    "id": make_id(router, sku, "global", "list"),
                    "provider": router,
                    "sku": sku,
                    "price": info["price"],
                    "unit": "usd_per_mtok",
                    "pricing_type": "list",
                    "region": "global",
                    "attrs": {
                        "model_id": info["model_id"],
                        "canonical": canonical,
                        "direction": direction,
                        "context_length": info["context"],
                        "routes_collapsed": info["routes"],
                        "metric": "router_list",
                    },
                    "provenance": {"url": PROVENANCE[router], "observed_at": observed_at},
                    "fixture": False,
                })

        if failures and len(failures) == len(ROUTERS):
            raise RuntimeError("all routers failed: " + "; ".join(failures))
        return offers


PROVENANCE = {
    "requesty": "https://requesty.ai/models",
    "glama": "https://glama.ai/gateway/models",
    "novita": "https://novita.ai/models",
    "deepinfra": "https://deepinfra.com/models",
}
