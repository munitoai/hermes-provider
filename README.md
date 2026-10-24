# Munito AI for Hermes Agent

This plugin makes [Munito AI](https://munito.ai) a model provider of [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Munito AI serves open models for Europe, private by default, on an OpenAI-compatible API.

## Install

```bash
hermes plugins install munitoai/hermes-provider
```

Create an API key at [console.munito.ai/keys](https://console.munito.ai/keys), and put it in `~/.hermes/.env`:

```bash
MUNITO_API_KEY=munitoai_...
```

Then run `hermes model` and pick **Munito AI**, or run `hermes --provider munito`.

## Providers

| Provider | Host | Use it when |
|---|---|---|
| `munito` (Munito AI) | `https://api.munito.ai/inference/v1` | Any region can process the request. |
| `munito-eu` (Munito AI (EU)) | `https://api.eu.munito.ai/inference/v1` | Each request must stay in the EU. |

Both use the same key.

## Models

| Model | Context | Input |
|---|---|---|
| `zai-org/glm-5.3-flash` | 1,048,576 | Text, images |
| `deepseek-ai/deepseek-v4-flash` | 1,048,576 | Text |
| `deepseek-ai/deepseek-v4.1-flash-1017` (preview, `munito` only) | 1,048,576 | Text, images |
| `qwen/qwen3.8-27b` | 262,144 | Text, images |
| `aleph-alpha/kolibri-1` | 1,048,576 | Text |

The prices are at [docs.munito.ai/models](https://docs.munito.ai/models).

## Reasoning

The plugin sends the effort of Hermes as `reasoning_effort`. Munito AI moves each level to the nearest level that the model has.
When you turn reasoning off, the plugin sends `none`: the model stops its reasoning, and a model that always reasons, such as GLM-5.3-Flash, runs its lowest level.
See [Reasoning models](https://docs.munito.ai/reasoning).

## What the plugin does

The plugin registers two model providers at import, and nothing else.
Hermes sends the chat requests and the model list request to the host of the provider, with `MUNITO_API_KEY`, through its own client.
Hermes also sends a `prompt_cache_key`, which keeps a conversation on its prompt cache.
Hermes shows the cost of each response at the posted prices of `models.json`. A price rule of your organization can lower the price that you pay.

## License

MIT
