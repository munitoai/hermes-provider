"""Munito AI as a Hermes model provider: pick Munito AI in ``hermes model``, or pass ``--provider munito``.

Munito AI serves open models for Europe, private by default, on an OpenAI-compatible API. The plugin adds two
providers that share the key ``MUNITO_API_KEY``: ``munito`` on the global host, and ``munito-eu``, which processes
each request in the EU. ``models.json`` gives the context window, tool support and image input of each model, so
Hermes guesses none of them. The effort goes out as the top-level ``reasoning_effort``, and ``none`` turns
reasoning off. Hermes sends a ``prompt_cache_key``, which keeps a conversation on its prompt cache.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

API_KEY_ENV = "MUNITO_API_KEY"
DATA = json.loads(Path(__file__).with_name("models.json").read_text(encoding="utf-8"))

PRICES = {(name, model["id"]): price for model in DATA["models"] for name, price in model["price"].items()}

# Munito accepts each of these levels on every model, and moves it to the nearest level that the model has.
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def reasoning_effort_for(reasoning_config: Any) -> str | None:
    """The ``reasoning_effort`` to send, or None to leave the field out and keep the default of the model."""
    if not isinstance(reasoning_config, dict):
        return None
    requested = str(reasoning_config.get("effort") or "").strip().lower()
    if reasoning_config.get("enabled") is False or requested == "none":
        return "none"
    if requested == "ultra":
        return "max"
    return requested if requested in EFFORTS else None


class MunitoProfile(ProviderProfile):
    """One Munito host: a top-level reasoning_effort, and the models of models.json that the host lists."""

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, **context: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        effort = reasoning_effort_for(reasoning_config)
        return {}, ({"reasoning_effort": effort} if effort else {})

    def get_usage_cost(self, model: str, usage: Any) -> Any | None:
        """The cost of a response at the posted prices of models.json. A cache write costs the input price."""
        price = PRICES.get((self.name, model))
        if price is None:
            return None
        try:
            from agent.usage_pricing import CostResult, format_cost_label
        except ImportError:
            return None
        parts = (
            (usage.input_tokens + usage.cache_write_tokens, price["input"]),
            (usage.cache_read_tokens, price["cachedInput"]),
            (usage.output_tokens, price["output"]),
        )
        amount = sum((Decimal(tokens) * Decimal(str(rate)) for tokens, rate in parts), Decimal(0)) / Decimal(1_000_000)
        return CostResult(
            amount_usd=amount,
            status="estimated",
            source="official_docs_snapshot",
            label=format_cost_label(amount),
            pricing_version=DATA["checked"],
            notes=("The posted price of Munito AI. A price rule of your organization can lower it.",),
        )

    def fetch_models(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 8.0
    ) -> list[str] | None:
        models = super().fetch_models(api_key=api_key, base_url=base_url, timeout=timeout)
        if models is None:
            return None
        # The host also lists OCR and decision models, which do not call tools.
        available = set(models)
        return [model for model in self.fallback_models if model in available]


def munito_profile(provider: str) -> MunitoProfile:
    host = DATA["providers"][provider]
    models = [model for model in DATA["models"] if provider in model["price"]]
    return MunitoProfile(
        name=provider,
        display_name=host["name"],
        description=f"{host['name']}: open models for Europe, private by default",
        signup_url="https://console.munito.ai/keys",
        env_vars=(API_KEY_ENV,),
        base_url=host["baseUrl"],
        auth_type="api_key",
        default_aux_model="qwen/qwen3.8-27b",
        fallback_models=tuple(model["id"] for model in models),
        supports_prompt_cache_key=True,
        supports_vision_tool_messages=False,
        model_capabilities={
            model["id"]: {
                "context_window": model["context"],
                "supports_tools": True,
                "supports_reasoning": True,
                "supports_vision": "image" in model["input"],
            }
            for model in models
        },
    )


for name in DATA["providers"]:
    register_provider(munito_profile(name))
