"""
DeepSeek2API：通过 DeepSeek 官网聊天提供逆向 API。
启动 playwright 的时候可能会让你过一个验证码，然后就可以随便用。
"""

import json
import asyncio
import time
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from playwright.async_api import async_playwright

if os.name == 'nt':
    os.system('color')

# ================= 凭证硬编码区 =================
CREDENTIALS = {
    "cookie": "填入你的 ds_cookie_preference",
    "userToken": "填入你 localStorage 中的 userToken"
}
# ===============================================

# 全局状态管理
global_browser_context = {
    "playwright": None,
    "browser": None,
    "page": None
}

intercepted_data = {
    "headers": {},
    "payload": None
}

intercept_event = asyncio.Event()
chat_lock = asyncio.Lock()

async def handle_route(route):
    """Playwright 路由拦截器"""
    request = route.request
    if request.method == "POST":
        raw_headers = await request.all_headers()
        clean_headers = {k: v for k, v in raw_headers.items() if not k.startswith(':')}
        intercepted_data["headers"] = clean_headers
        intercepted_data["payload"] = request.post_data
        intercept_event.set()
        await route.abort()
    else:
        await route.continue_()

async def setup_browser(p):
    """初始化无头浏览器"""
    browser = await p.chromium.launch(headless=False)
    context = await browser.new_context()
    
    cookies = []
    for item in CREDENTIALS["cookie"].split(';'):
        if '=' in item:
            name, value = item.split('=', 1)
            cookies.append({'name': name.strip(), 'value': value.strip(), 'domain': '.deepseek.com', 'path': '/'})
    await context.add_cookies(cookies)
    
    page = await context.new_page()
    await page.route("**/api/v0/chat/completion", handle_route)
    await page.goto("https://chat.deepseek.com")
    
    auth_script = f"window.localStorage.setItem('userToken', JSON.stringify({{value: '{CREDENTIALS['userToken']}', __version: '0'}}));"
    await page.evaluate(auth_script)
    await page.reload()
    
    try:
        await page.wait_for_selector('textarea[placeholder*="给 DeepSeek 发送消息"]', timeout=15000)
        return browser, page
    except Exception:
        print("❌ 登录失败，请检查 Token。")
        sys.exit(1)

async def apply_settings(page, model_choice: str, use_think: bool, use_search: bool):
    """设置对话模型及参数"""
    # 1. 每次都点击“开启新对话”，重置前端 UI 状态
    new_chat_btn = page.locator('span:text-is("开启新对话")')
    if await new_chat_btn.count() > 0 and await new_chat_btn.first.is_visible():
        await new_chat_btn.first.click()
        await asyncio.sleep(0.5)

    # 2. 切换模型
    model_type = "expert" if model_choice == '2' else "default"
    model_btn = page.locator(f'div[data-model-type="{model_type}"]')
    if await model_btn.count() > 0 and await model_btn.first.is_visible():
        await model_btn.first.click()
    
    # 3. 切换深度思考和智能搜索
    for label, want_on in [("深度思考", use_think), ("智能搜索", use_search)]:
        btn = page.locator(f'div[role="button"]:has-text("{label}")')
        if await btn.count() > 0 and await btn.first.is_visible():
            class_attr = await btn.first.get_attribute('class') or ''
            is_on = 'ds-toggle-button--selected' in class_attr
            if want_on != is_on: 
                await btn.first.click()
    await asyncio.sleep(0.5)

def parse_model_id(model_id: str):
    """解析请求的模型 ID 映射为自动化操作指令"""
    model_id = model_id.lower()
    is_expert = "expert" in model_id
    use_think = "thinking" in model_id
    use_search = "search" in model_id
    model_choice = "2" if is_expert else "1"
    return model_choice, use_think, use_search

async def fetch_deepseek_stream(headers: dict, payload: str):
    """建立与 DeepSeek 官方接口的流式连接，返回处理后的字符串生成器"""
    url = "https://chat.deepseek.com/api/v0/chat/completion"
    is_thinking = False
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("POST", url, headers=headers, content=payload) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                    
                json_str = line[6:]
                if json_str == "[DONE]":
                    break
                    
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    continue

                v = data.get("v")
                content_chunk = ""

                # 极简增量
                if "p" not in data and isinstance(v, str):
                    content_chunk = v

                # 状态切换
                elif data.get("p") == "response/fragments" and data.get("o") == "APPEND":
                    frags = v if isinstance(v, list) else []
                    for frag in frags:
                        if frag.get("type") == "RESPONSE":
                            if is_thinking:
                                content_chunk += "\n</think>\n\n"
                                is_thinking = False
                            content_chunk += frag.get("content", "")

                # 初始数据包
                elif isinstance(v, dict) and "response" in v:
                    frags = v["response"].get("fragments", [])
                    for frag in frags:
                        if frag.get("type") == "THINK":
                            is_thinking = True
                            content_chunk += "<think>\n" + frag.get("content", "")
                        elif frag.get("type") == "RESPONSE":
                            content_chunk += frag.get("content", "")

                # 指定路径追加
                elif data.get("p") == "response/fragments/-1/content" and isinstance(v, str):
                    content_chunk += v
                
                if content_chunk:
                    yield content_chunk

@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理 FastAPI 的生命周期，绑定 Playwright"""
    print("⏳ 初始化无头浏览器环境中...")
    global_browser_context["playwright"] = await async_playwright().start()
    browser, page = await setup_browser(global_browser_context["playwright"])
    global_browser_context["browser"] = browser
    global_browser_context["page"] = page
    print("✅ 浏览器就绪，API 服务启动成功。")
    
    yield
    
    print("关闭浏览器环境...")
    if global_browser_context["browser"]:
        await global_browser_context["browser"].close()
    if global_browser_context["playwright"]:
        await global_browser_context["playwright"].stop()

app = FastAPI(lifespan=lifespan)

# 允许跨域，方便客户端或 Web UI 接入
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """兼容 OpenAI 格式的对话接口"""
    body = await request.json()
    model = body.get("model", "deepseek-fast")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    
    if not messages:
        raise HTTPException(status_code=400, detail="The 'messages' array is required.")

    # 将历史消息合并为单次查询输入（针对新对话模式）
    query_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages])
    
    # 解析模型指令
    m_choice, use_think, use_search = parse_model_id(model)
    req_id = int(time.time())

    # 获取队列锁，防止多请求同时操控浏览器
    await chat_lock.acquire()
    
    try:
        page = global_browser_context["page"]
        intercept_event.clear()
        
        await apply_settings(page, m_choice, use_think, use_search)
        
        text_area = page.locator('textarea[placeholder*="给 DeepSeek 发送消息"]')
        await text_area.fill(query_text)
        await text_area.press("Enter")
        
        try:
            await asyncio.wait_for(intercept_event.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Timeout waiting for browser interception.")
            
        request_headers = intercepted_data["headers"]
        request_payload = intercepted_data["payload"]
        
    except Exception as e:
        chat_lock.release()
        raise HTTPException(status_code=500, detail=str(e))

    # 生成流式响应
    if stream:
        async def event_generator():
            try:
                async for text_chunk in fetch_deepseek_stream(request_headers, request_payload):
                    chunk_data = {
                        "id": f"chatcmpl-{req_id}",
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": text_chunk}}]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                chat_lock.release()

        return StreamingResponse(event_generator(), media_type="text/event-stream")
        
    # 生成阻塞响应（非流式）
    else:
        full_content = ""
        try:
            async for text_chunk in fetch_deepseek_stream(request_headers, request_payload):
                full_content += text_chunk
        finally:
            chat_lock.release()
            
        return JSONResponse(content={
            "id": f"chatcmpl-{req_id}",
            "object": "chat.completion",
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": full_content}}]
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
