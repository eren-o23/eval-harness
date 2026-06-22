"""Provider dispatch for the llm_judge evaluator.

`get_completion` takes a provider-qualified model string ("provider/model-name")
and returns the model's raw text response. The provider prefix selects the
client: "anthropic" uses the Anthropic SDK; everything else is treated as an
OpenAI-compatible endpoint (Ollama, LM Studio, Groq, Together AI, ...), which
all speak the same chat-completions interface.

SDKs are imported lazily so that code paths not using a given provider — and the
mocked tests — don't require it installed. API keys come from the environment
(ANTHROPIC_API_KEY, OPENAI_API_KEY, or <PROVIDER>_API_KEY); nothing is hardcoded.
"""

from __future__ import annotations

import os


def get_completion(model: str, system: str, user: str, max_tokens: int = 1024) -> str:
    """Send (system, user) to `model` and return the raw text response.

    `model` must be "provider/model-name", e.g. "anthropic/claude-sonnet-4-6",
    "openai/gpt-4o", "ollama/llama3".
    """
    if "/" not in model:
        raise ValueError(
            f"model must be 'provider/model-name' (e.g. 'anthropic/claude-sonnet-4-6'), "
            f"got {model!r}"
        )
    provider, model_name = model.split("/", 1)
    if provider == "anthropic":
        return _anthropic_complete(model_name, system, user, max_tokens)
    return _openai_compatible_complete(provider, model_name, system, user, max_tokens)


def _anthropic_complete(model_name: str, system: str, user: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=model_name,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _openai_compatible_complete(
    provider: str, model_name: str, system: str, user: str, max_tokens: int
) -> str:
    import openai

    if provider == "openai":
        base_url = None  # SDK default
        api_key = os.environ.get("OPENAI_API_KEY")
    else:
        base_url = os.environ.get(f"{provider.upper()}_BASE_URL")
        if not base_url:
            raise ValueError(
                f"provider {provider!r} is OpenAI-compatible; set {provider.upper()}_BASE_URL "
                f"(and {provider.upper()}_API_KEY if the endpoint needs one)"
            )
        # Local endpoints (Ollama, LM Studio) often need no real key.
        api_key = os.environ.get(f"{provider.upper()}_API_KEY") or "not-needed"

    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model_name,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""
