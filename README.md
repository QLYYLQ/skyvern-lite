# skyvern-lite

Minimal Python SDK for [Skyvern](https://www.skyvern.com/) cloud browser sessions. Only does one thing: **create a cloud browser, return a CDP URL, clean up when done**.

## Install

```bash
pip install skyvern-lite
```

## Quick Start

```python
from skyvern_lite import SkyvernCloud

client = SkyvernCloud(api_key="your-api-key")  # or set SKYVERN_API_KEY env var

# Create a cloud browser session
session = client.sessions.create()
print(session.cdp_url)      # wss://sessions.skyvern.com/...
print(session.session_id)   # pbs_...

# Connect with Playwright
# NOTE: Skyvern's CDP WebSocket requires x-api-key header for auth
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(
        session.cdp_url,
        headers={"x-api-key": "your-api-key"},
    )
    page = browser.contexts[0].new_page()
    page.goto("https://example.com")
    print(page.title())

# Clean up
client.sessions.delete(session.session_id)
```

### Context Manager (auto-cleanup)

```python
with client.sessions.create() as session:
    # use session.cdp_url ...
    pass
# session automatically deleted on exit
```

### Async

```python
from skyvern_lite import AsyncSkyvernCloud

async with AsyncSkyvernCloud(api_key="your-api-key") as client:
    session = await client.sessions.create()
    print(session.cdp_url)
    await client.sessions.delete(session.session_id)
```

## API

### Client

```python
SkyvernCloud(api_key=None, *, base_url=None, timeout=60.0, max_retries=2)
AsyncSkyvernCloud(api_key=None, *, base_url=None, timeout=60.0, max_retries=2)
```

- `api_key` — defaults to `SKYVERN_API_KEY` env var
- `base_url` — defaults to `https://api.skyvern.com`

### Sessions (`client.sessions`)

| Method | Description |
|--------|-------------|
| `create(**kwargs) -> SessionInfo` | Create cloud browser, returns CDP URL |
| `get(session_id) -> SessionInfo` | Get session status |
| `list(**filters) -> list[SessionInfo]` | List sessions |
| `delete(session_id) -> None` | Close session (idempotent) |

### `create()` Parameters

```python
session = client.sessions.create(
    # Proxy — managed residential IP
    proxy=ManagedProxyConfig(country="US"),

    # Extensions
    extensions=["ad-blocker", "captcha-solver"],

    # Browser type
    browser_type="chrome",   # or "msedge"

    # Timeout (in MINUTES, range 5–1440, default 60)
    timeout=120,
)
```

### SessionInfo Fields

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `str` | Unique identifier |
| `cdp_url` | `str \| None` | CDP WebSocket URL (`wss://...`) |
| `status` | `str` | `"active"`, `"closed"`, or `"error"` |
| `created_at` | `datetime \| None` | Creation timestamp |
| `inspect_url` | `str \| None` | Skyvern dashboard debug URL |
| `metadata` | `dict` | Vendor-specific data |
| `metadata["recordings"]` | `list` | Auto-generated session recording URLs (.webm) |

### CDP WebSocket Authentication

Skyvern's CDP WebSocket endpoint (`wss://sessions.skyvern.com/...`) is **not a standard open WebSocket**. It requires authentication via the `x-api-key` HTTP header during the WebSocket handshake. Without this header, the connection will fail with `401 Unauthorized`.

```python
# Playwright
browser = pw.chromium.connect_over_cdp(
    session.cdp_url,
    headers={"x-api-key": api_key},  # REQUIRED
)

# Raw websockets library
import websockets
ws = await websockets.connect(
    session.cdp_url,
    additional_headers={"x-api-key": api_key},  # REQUIRED
)

# Selenium (does NOT support custom WebSocket headers — cannot connect directly)
```

> **If your CDP client does not support custom headers on WebSocket upgrade, you cannot connect to Skyvern cloud browsers directly.** Playwright and raw websockets libraries work. Selenium's CDP support does not.

### Feature Support

| Feature | Status | Usage |
|---------|--------|-------|
| Residential proxy (20 countries) | Supported | `proxy=ManagedProxyConfig(country="US")` |
| ISP proxy | Supported | `proxy=ManagedProxyConfig(country="ISP")` |
| Ad blocker | Supported | `extensions=["ad-blocker"]` |
| Captcha solver | Supported | `extensions=["captcha-solver"]` |
| Browser type | Supported | `browser_type="chrome"` or `"msedge"` |
| Custom timeout | Supported | `timeout=120` (minutes, 5–1440) |
| Session recording | Auto | Recordings in `metadata["recordings"]` |
| Custom proxy server | Not supported | `ProxyConfig()` raises `NotImplementedError` |
| Browser fingerprint | Not supported | Skyvern API does not accept fingerprint params |
| Browser profile | Not supported | Requires Skyvern Task/Workflow, not usable via CDP |

Supported proxy countries: US, AR, AU, BR, CA, DE, ES, FR, GB, IE, IN, IT, JP, KR, MX, NL, NZ, PH, TR, ZA.

### Exceptions

```
CloudBrowserError
├── AuthenticationError     # 401/403
├── QuotaExceededError      # 429 (has .retry_after)
├── SessionNotFoundError    # 404
├── ProviderError           # 5xx (has .status_code, .request_id)
├── TimeoutError            # Operation timeout
└── NetworkError            # Connection failure
```

### Backward Compatibility

```python
from skyvern_lite import Skyvern       # alias for SkyvernCloud
from skyvern_lite import AsyncSkyvern  # alias for AsyncSkyvernCloud
```

## License

MIT
