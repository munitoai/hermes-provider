"""Compare models.json with the model feed of the Munito AI API, and exit 1 on each difference.

usage: python3 .github/check_models.py

Each host of models.json serves a public feed at ``<baseUrl>/models/openrouter``. The feed gives the name, the
limits, the input types, the reasoning levels and the standard prices of each model that the host sells. A model
belongs in models.json when it calls tools and its context window is not below the minimum of Hermes Agent. A
model marked ``gated`` is absent from the public feed, so the check cannot compare its values.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

# Hermes Agent refuses a model with a smaller context window (MINIMUM_CONTEXT_LENGTH in agent/model_metadata.py).
MIN_CONTEXT = 64_000
# The input types that Hermes uses. The feed also names video and audio.
INPUTS = ("text", "image")
PRICES = {"input": "prompt", "cachedInput": "cached_prompt", "output": "completion"}
AGENT = "munito-hermes-provider-check"


def fetch(url: str) -> list[dict[str, Any]]:
    """The documents of one feed. Three attempts, because one failed request must not fail a scheduled run."""
    error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"accept": "application/json", "user-agent": AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)["data"]
        except Exception as exc:  # noqa: BLE001 - each failure of the request has the same result
            error = exc
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"No answer from {url}: {error}")


def part(document: dict[str, Any], side: str) -> dict[str, Any]:
    return next(item for item in document[side] if item["type"] == "text")


def offer(document: dict[str, Any]) -> dict[str, Any]:
    """One feed document in the fields of models.json. A price is for a million tokens."""
    text_in, text_out = part(document, "input_modalities"), part(document, "output_modalities")
    cost = {row["type"]: Decimal(row["cost_usd"]) * 1_000_000 for row in text_in["pricing"] + text_out["pricing"]}
    parameters = text_out.get("supported_parameters") or {}
    return {
        "name": document["name"],
        "context": text_in["supported_inputs"]["max_context_length"]["value"],
        "maxOutput": text_out["max_length"]["value"],
        "input": [item["type"] for item in document["input_modalities"] if item["type"] in INPUTS],
        "efforts": (parameters.get("reasoning_effort") or {}).get("values") or [],
        "tools": "tools" in parameters,
        # A model with no cached price bills cached input at the input price.
        "price": {field: cost.get(kind, cost["prompt"]) for field, kind in PRICES.items()},
    }


def offers(base_url: str) -> dict[str, dict[str, Any]]:
    """The standard offer of each model on one host. An id with ``@`` pins a region, and a tier has its own document."""
    documents = fetch(f"{base_url}/models/openrouter")
    return {doc["id"]: offer(doc) for doc in documents if "@" not in doc["id"] and not doc.get("service_tier")}


def differences(data: dict[str, Any], feeds: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    """Each difference between models.json and the feeds, as one sentence."""
    found: list[str] = []
    listed = {model["id"]: model for model in data["models"]}
    for provider, feed in feeds.items():
        for model_id, sold in feed.items():
            if sold["tools"] and sold["context"] >= MIN_CONTEXT and model_id not in listed:
                found.append(f"{model_id}: {provider} sells it, and models.json does not have it")
    for model_id, model in listed.items():
        sellers = [provider for provider, feed in feeds.items() if model_id in feed]
        if model.get("gated"):
            if sellers:
                found.append(f"{model_id}: it is public on {', '.join(sellers)}, so remove its gated mark")
            continue
        if not sellers:
            found.append(f"{model_id}: no host sells it, so remove it from models.json")
            continue
        for provider, feed in feeds.items():
            sold, price = feed.get(model_id), model["price"].get(provider)
            if sold is None and price is None:
                continue
            if sold is None:
                found.append(f"{model_id}: models.json has a price for {provider}, and that host does not sell it")
                continue
            if price is None:
                found.append(f"{model_id}: {provider} sells it, and models.json has no price for {provider}")
                continue
            for field in ("name", "context", "maxOutput", "input", "efforts"):
                if model[field] != sold[field]:
                    found.append(f"{model_id}: {field} is {model[field]!r}, and {provider} gives {sold[field]!r}")
            for field, amount in sold["price"].items():
                if Decimal(str(price[field])) != amount:
                    found.append(
                        f"{model_id}: the {field} price for {provider} is {price[field]}, and the host gives {amount.normalize():f}"
                    )
    return found


def main() -> int:
    data = json.loads((Path(__file__).resolve().parent.parent / "models.json").read_text(encoding="utf-8"))
    feeds = {name: offers(host["baseUrl"]) for name, host in data["providers"].items()}
    found = differences(data, feeds)
    for line in found:
        print(line)
    if found:
        print(f"models.json differs from the API in {len(found)} places.")
        return 1
    print(f"models.json agrees with the API: {len(data['models'])} models on {len(feeds)} hosts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
