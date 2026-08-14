"""Source contract. A source fetches raw offers from one place and returns
canonical offer dicts (see schema/offer.schema.json). Real sources live here
one file per provider; each declares the provenance URL it observed."""


import re


def slug(text):
    """Lowercase, non-alphanumerics collapsed to single dashes."""
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9.-]+", "-", str(text).lower())).strip("-")


def make_id(provider, sku, region, pricing_type):
    parts = [provider, sku, region or "global", pricing_type]
    return ":".join(slug(p) for p in parts)


class Source:
    """Interface: subclasses implement fetch(observed_at) -> list[dict]."""

    name = "unnamed"

    def fetch(self, observed_at):
        raise NotImplementedError
