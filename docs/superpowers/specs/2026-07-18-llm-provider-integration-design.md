# LLM Provider Integration — Design Spec

**Goal:** Make `ChatManager` actually call a real LLM (it currently doesn't — `_generate_response()` is a hardcoded stub returning `f"Response from {model} model"`), while staying fully provider-agnostic: mcpflow must never hardcode a fixed list of supported providers.

**Why this scope, not more:** The WebMCP bridge itself needs zero LLM integration — when consumed via Claude Desktop/Cursor/Claude Code, mcpflow is the MCP *server* and the LLM lives entirely in the client. This work only matters for `ChatManager`, the separate code path where mcpflow acts as its own agent loop (the "bridge + mcpflow ChatManager end-to-end agent" example, spec §4.8b). `ChatManager` should stay a thin orchestration loop, not grow into a competitor of LangChain/LiteLLM.

## Architecture

```
ChatManager.send()
    │
    ▼
build LLMMessage[] from history + system prompt
    │
    ▼
provider.generate(messages, tools, model)  ◄── LLMProvider Protocol
    │
    ▼
LLMResponse (content, tool_calls)
    │
    ├── tool_calls present ──► MCPRegistry.call_tool() per call ──► append tool-result messages ──► loop (bounded by max_tool_calls)
    │
    └── no tool_calls ──► return content
```

## 1. Protocol & types — `mcpflow/providers/base.py`

```python
@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_call_id: Optional[str] = None       # set on role="tool" messages
    tool_calls: List[LLMToolCall] = field(default_factory=list)  # set on role="assistant" when the model requests calls

@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: List[LLMToolCall]
    raw: Any = None  # provider's raw response, for debugging

class LLMProvider(Protocol):
    async def generate(
        self, messages: List[LLMMessage], tools: List[dict], model: str
    ) -> LLMResponse: ...
```

Tools are passed to `generate()` in OpenAI function-calling JSON shape (`{"type": "function", "function": {"name", "description", "parameters"}}`) — the one format essentially every provider and router (including OpenRouter's Anthropic proxying) accepts. `MCPRegistry.get_tools()` already returns JSON-Schema `input_schema`, so this is a direct field mapping, not a translation layer.

Anyone can implement `LLMProvider` for anything (a provider we never heard of, a test double, a local model server) — this is what makes mcpflow provider-agnostic by construction, not by a maintained list.

## 2. Built-in providers — `mcpflow/providers/`

**`OpenAICompatibleProvider(base_url: str, api_key: Optional[str] = None)`**
- Ships in core. Zero extra dependency — uses `httpx`, already a core mcpflow dependency.
- POSTs to `{base_url}/chat/completions` with the standard OpenAI request shape; parses `choices[0].message`, including `tool_calls`.
- Covers OpenRouter, Ollama, Groq, Together, vLLM's OpenAI-compatible server, LM Studio — anything speaking this wire format — via `base_url` alone. Reaches Anthropic models too, through OpenRouter's catalog, with no Anthropic-specific parsing anywhere in mcpflow.
- Deliberately does **not** special-case Anthropic's native `/v1/messages` shape. That's out of scope for this adapter — `LiteLLMProvider` is the escape hatch when a user wants provider-native features.

**`LiteLLMProvider(**kwargs)`**
- Optional dependency (`pip install mcpflow[llm]`), lazy-imports `litellm` inside `generate()` so importing `mcpflow.providers` never requires it.
- Wraps `litellm.acompletion(model=..., messages=..., tools=..., **kwargs)`.
- This is the recommended default when installed — broader/deeper provider coverage (native Anthropic, Bedrock, Vertex, etc.) than the OpenAI-compatible adapter can express.

**`build_provider_from_config(model_config: ModelConfig) -> LLMProvider`**
- `model_config.provider == "litellm"` → `LiteLLMProvider`
- anything else (default) → `OpenAICompatibleProvider(base_url=model_config.base_url, api_key=model_config.api_key)`
- No changes needed to `ModelConfig`/`TeamConfig` — `provider`/`name`/`api_key`/`base_url` fields already fit this exactly; this factory is purely new code, not a schema migration.

## 3. ChatManager integration

- New constructor param: `provider: Optional[LLMProvider] = None`.
- Default resolution (only when `.send()` actually needs it, not at construction time): if `provider` is `None`, try `LiteLLMProvider()` — if `litellm` isn't importable, raise `RuntimeError` with an actionable message ("No provider configured and litellm isn't installed. Pass provider=... or run: pip install mcpflow[llm]"). **Never silently fall back to a fake response** — that's the exact mistake already fixed once in this codebase (the WebMCP bridge's simulated tool execution).
- `_generate_response()` is replaced by a real loop:
  1. Build `LLMMessage[]` from `self.system_prompt` + `self.history`.
  2. If `self.registry` is set, convert `registry.get_tools()` to OpenAI tool schema via a small `_tools_to_llm_schema()` helper. `MCPRegistry.get_tools()` returns tools without an MCP-name prefix, but the LLM only sees one flat namespace of tool names — so this helper must namespace each tool as `{mcp_name}__{tool_name}` when building the schema (iterating `registry.get_registered_mcps()` and `registry.get_tools(mcp_name)` per MCP, mirroring the `{origin}__{tool}` convention `SchemaTranslator` already uses for WebMCP tools). If no registry is set, pass `tools=[]`.
  3. Call `provider.generate(messages, tools, model)`.
  4. If `response.tool_calls` is non-empty: for each call, split the LLM-facing tool name on the first `__` into `(mcp_name, tool_name)` and call `registry.call_tool(mcp_name, tool_name, arguments)`. On success or failure, append a `role="tool"` message carrying the result or error back into the loop (matches the `ToolCall.error` field that already exists on the dataclass). Loop back to step 3, bounded by `max_tool_calls`.
  5. If no tool calls, return `response.content` as the final answer.
- Tool execution errors are fed back to the model as tool-result content, not raised — mirrors real agent-loop behavior and lets the model react (retry with different args, apologize, etc.).

## 4. Testing

- Rewrite `test_chat.py`'s `test_send_message_with_model` / `_with_model_override` / `_with_context` / `_chat_history_accumulation` against a `FakeProvider` test double instead of asserting on the literal stub string (`"test-model" in response`), since that was testing fake behavior, not a real contract.
- New `tests/test_providers.py`:
  - `OpenAICompatibleProvider`: tested against a mocked `httpx` transport (`httpx.MockTransport`, no real network calls) — one case for a plain-text response, one for a tool-call response.
  - `LiteLLMProvider`: `pytest.importorskip("litellm")`-gated, same pattern already used for the Playwright e2e tests.
- One integration-style test: `ChatManager` + `MCPRegistry` + `FakeProvider` where the fake returns a tool call on turn 1 and plain text on turn 2 — asserts the registry tool was actually invoked with the right arguments and the loop terminated correctly, without needing a real API key.

## Explicitly out of scope

- No Anthropic-native adapter, no per-provider adapter files beyond the two above.
- No retries, fallback chains, streaming, or multi-agent orchestration in `ChatManager` — that's LiteLLM/LangChain territory.
- No changes to the WebMCP bridge; this work is entirely in core `mcpflow` (`chat.py`, new `providers/` package, `config.py` factory function).
