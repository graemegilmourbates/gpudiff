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
    """Interface: subclasses implement fetch(observed_at) -> list[dict].

    cadence: "hourly" fetches every run; "daily" fetches on the 06:xx UTC run
    (or when the provider is missing from the carry pool) and is carried
    forward unchanged in between — for bulky sources whose prices move slowly."""

    name = "unnamed"
    cadence = "hourly"

    @property
    def emits(self):
        """Provider names this source produces offers under (for cadence
        carry-forward). Defaults to the source's own name."""
        return {self.name}

    def fetch(self, observed_at):
        raise NotImplementedError
