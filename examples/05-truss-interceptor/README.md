# Truss Interceptor Integration Example

Demonstrates the `InterceptorProtocol` seam the WebMCP bridge spec calls
out for dropping in a production security layer like Truss (a separate,
external project - not an mcpflow dependency) without coupling mcpflow to it:

```python
bridge = WebMCPBridge(interceptor=TrussInterceptor(manifest="scope.yaml"))
```

Since Truss itself isn't a dependency here, `truss_style_interceptor.py`
implements the same protocol with a small, self-contained scope-manifest
model - real production code would just implement `InterceptorProtocol`'s
four methods (`before_tool_call`, `after_tool_call`, `cross_origin_check`,
`log_event`) against whatever policy engine it uses.

## Run it

```bash
pip install mcpflow[webmcp]
playwright install chromium
python demo.py
```

## What it shows

- A tool matching the scope manifest (`search*`) is allowed through.
- A tool outside the manifest (`deleteAccount`) is blocked by
  `before_tool_call` before it ever reaches the browser - the interceptor
  decides, not `WebMCPBridge`'s default security manager.
- Every decision is recorded via `log_event`, independent of mcpflow's own
  audit log.

## Swapping in a real interceptor

Any object implementing `InterceptorProtocol` works - `WebMCPBridge` never
imports or knows about the concrete implementation:

```python
from mcpflow.webmcp.bridge import WebMCPBridge

bridge = WebMCPBridge(
    origins_allowlist=["https://shop.example.com"],
    interceptor=YourProductionInterceptor(...),
)
```
