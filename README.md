# DeepSeek2API

简体中文 | [English](README-en.md)

通过 DeepSeek 官网聊天页（Playwright 自动化）提供一个兼容 OpenAI Chat Completions 的本地 API 服务。

## 功能

- 提供 `POST /v1/chat/completions` 接口
- 兼容 OpenAI 风格请求体（`model`、`messages`、`stream`）
- 支持流式与非流式输出
- 自动切换网页端模型、深度思考与智能搜索开关

## 环境要求

- Python 3.10+
- 可用的 DeepSeek 账号登录凭证

## 安装

```bash
pip install fastapi uvicorn httpx playwright
playwright install chromium
```

## 配置凭证

编辑 `server.py` 中的 `CREDENTIALS`：

```python
CREDENTIALS = {
    "cookie": "填入你的 ds_cookie_preference",
    "userToken": "填入你 localStorage 中的 userToken"
}
```

> 注意：当前版本使用硬编码方式管理凭证，请勿提交包含真实凭证的代码。

## 启动服务

```bash
python server.py
```

默认监听：`http://0.0.0.0:8000`

首次启动 Playwright 可能需要在浏览器页面完成验证码。

## 接口说明

### 请求

`POST /v1/chat/completions`

示例：

```json
{
  "model": "deepseek-fast-thinking-search",
  "messages": [
    {"role": "user", "content": "你好，介绍一下你自己"}
  ],
  "stream": true
}
```

### `model` 解析规则

- 包含 `expert`：切换到专家模式
- 包含 `thinking`：开启“深度思考”
- 包含 `search`：开启“智能搜索”

例如：

- `deepseek-fast`：普通模式
- `deepseek-expert`：专家模式
- `deepseek-expert-thinking-search`：专家 + 深度思考 + 智能搜索

## 已知限制

- 使用单浏览器页串行处理请求（有请求锁）
- 页面结构变化可能导致自动化失效
- 依赖 DeepSeek 官方网页接口与登录状态

## 许可证

如仓库未单独声明，请按仓库所有者约定使用。
