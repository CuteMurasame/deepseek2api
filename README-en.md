# DeepSeek2API

[简体中文](README.md) | English

An OpenAI-compatible local Chat Completions API built by automating the DeepSeek web chat with Playwright.

## Features

- Exposes `POST /v1/chat/completions`
- Accepts OpenAI-style payloads (`model`, `messages`, `stream`)
- Supports both streaming and non-streaming responses
- Automatically switches web UI model and toggles thinking/search options

## Requirements

- Python 3.10+
- Valid DeepSeek login credentials

## Installation

```bash
pip install fastapi uvicorn httpx playwright
playwright install chromium
```

## Configure Credentials

Edit `CREDENTIALS` in `server.py`:

```python
CREDENTIALS = {
    "cookie": "your ds_cookie_preference value",
    "userToken": "your userToken from localStorage"
}
```

> Warning: credentials are currently hardcoded. Never commit real secrets.

## Run

```bash
python server.py
```

Default bind address: `http://0.0.0.0:8000`

On first launch, Playwright may open a browser where you need to pass a captcha.

## API

### Request

`POST /v1/chat/completions`

Example:

```json
{
  "model": "deepseek-fast-thinking-search",
  "messages": [
    {"role": "user", "content": "Hello, introduce yourself"}
  ],
  "stream": true
}
```

### `model` parsing rules

- Contains `expert`: use expert mode
- Contains `thinking`: enable deep thinking
- Contains `search`: enable smart search

Examples:

- `deepseek-fast`: default mode
- `deepseek-expert`: expert mode
- `deepseek-expert-thinking-search`: expert + thinking + search

## Known Limitations

- Requests are serialized through a single browser page (lock-based)
- UI selector changes on DeepSeek website can break automation
- Depends on DeepSeek web endpoint behavior and login session validity

## License

If no license file is provided, follow repository owner terms.
