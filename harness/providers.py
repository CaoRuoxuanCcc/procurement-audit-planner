"""One tool-calling interface over Anthropic, OpenAI and Gemini (via LiteLLM).

Bring-your-own-key: the key lives only in an LLMConfig object held in memory
for the length of one stage. It is never written to disk, events or logs,
and every error message is scrubbed before it leaves this module.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

CONFIG = json.loads((Path(__file__).parent / "config" / "models.json").read_text())

KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
]
_live_keys: set = set()


def redact(text) -> str:
    text = str(text)
    for k in list(_live_keys):
        if k:
            text = text.replace(k, "[redacted]")
    for p in KEY_PATTERNS:
        text = p.sub("[redacted]", text)
    return text


class RedactFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def install_log_redaction():
    f = RedactFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "LiteLLM", "litellm", "httpx"):
        lg = logging.getLogger(name)
        lg.addFilter(f)
        for h in lg.handlers:
            h.addFilter(f)


@dataclass
class LLMConfig:
    provider: str
    model: str
    key: str = field(repr=False)

    def __post_init__(self):
        if self.provider not in CONFIG["providers"] and self.provider != "mock":
            raise ValueError(f"unknown provider {self.provider!r}")
        if not self.model or not re.fullmatch(r"[A-Za-z0-9._:\-/]+", self.model):
            raise ValueError("model id is empty or has unexpected characters")
        if self.provider != "mock" and not self.key:
            raise ValueError("an API key is required")

    def __enter__(self):
        _live_keys.add(self.key)
        return self

    def __exit__(self, *exc):
        _live_keys.discard(self.key)
        self.key = ""

    @property
    def litellm_model(self) -> str:
        return CONFIG["providers"][self.provider]["litellm_prefix"] + self.model


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class Reply:
    text: str
    tool_calls: list
    finish_reason: str
    message: dict  # the assistant message to append to the history, as the provider returned it
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = None


class LLMError(Exception):
    pass


# Tests register a function here: (agent_name, messages, tools) -> Reply.
MOCK = {"fn": None}


def _with_cache_marks(messages):
    """Anthropic prompt caching: mark the system prompt and the newest message."""
    out = [dict(m) for m in messages]
    for i in (0, len(out) - 1):
        m = out[i]
        if m["role"] in ("system", "user", "tool") and isinstance(m.get("content"), str) and m["content"]:
            m["content"] = [{"type": "text", "text": m["content"], "cache_control": {"type": "ephemeral"}}]
    return out


async def complete(cfg: LLMConfig, messages: list, tools: list, agent: str = "") -> Reply:
    if cfg.provider == "mock":
        return MOCK["fn"](agent, messages, tools)
    import litellm

    litellm.drop_params = True
    litellm.suppress_debug_info = True
    send = _with_cache_marks(messages) if cfg.provider == "anthropic" else messages
    try:
        resp = await litellm.acompletion(
            model=cfg.litellm_model,
            messages=send,
            tools=tools or None,
            api_key=cfg.key,
            max_tokens=CONFIG["max_output_tokens"],
            num_retries=4,
            timeout=600,
        )
    except Exception as e:  # noqa: BLE001 - surface every provider error, scrubbed
        raise LLMError(f"{type(e).__name__}: {redact(e)}") from None
    choice = resp.choices[0]
    msg = choice.message
    calls = [
        ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
        for tc in (msg.tool_calls or [])
    ]
    message = msg.model_dump(exclude_none=True)
    message["role"] = "assistant"
    if not message.get("content") and not calls:
        message["content"] = ""
    usage = getattr(resp, "usage", None)
    try:
        cost = float(litellm.completion_cost(completion_response=resp))
    except Exception:  # noqa: BLE001 - unknown pricing for a new model id
        cost = None
    return Reply(
        text=msg.content or "",
        tool_calls=calls,
        finish_reason=choice.finish_reason or "",
        message=message,
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        cost=cost,
    )


async def list_models(provider: str, key: str) -> list:
    """The provider's model ids for this key. Free: no tokens are used."""
    async with httpx.AsyncClient(timeout=20) as c:
        if provider == "anthropic":
            r = await c.get("https://api.anthropic.com/v1/models?limit=1000",
                            headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
            ids = [m["id"] for m in r.json().get("data", [])] if r.status_code == 200 else None
        elif provider == "openai":
            r = await c.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
            ids = [m["id"] for m in r.json().get("data", [])] if r.status_code == 200 else None
        elif provider == "gemini":
            r = await c.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                            headers={"x-goog-api-key": key})
            ids = ([m["name"].removeprefix("models/") for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])]
                   if r.status_code == 200 else None)
        else:
            raise ValueError("unknown provider")
    if ids is None:
        try:
            detail = r.json().get("error", {})
            detail = detail.get("message", detail) if isinstance(detail, dict) else detail
        except Exception:  # noqa: BLE001
            detail = r.text[:200]
        raise LLMError(f"the provider rejected the key (HTTP {r.status_code}): {redact(detail)}")
    return sorted(ids)
