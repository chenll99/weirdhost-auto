import os
import re
import time
import random
import traceback
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SERVER_URL = "https://hub.weirdhost.xyz/server/e66c2244"
LOGIN_URL = "https://hub.weirdhost.xyz/auth/login"

def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10)
    except Exception as e: print(f"Telegram 发送失败: {e}")

def get_expire_datetime(page):
    try:
        page.wait_for_selector("text=/유통기한/i", timeout=10000)
        text = page.locator("text=/유통기한/i").first.inner_text()
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None
    except: return None

def add_server_time():
    remember_cookie = os.getenv("REMEMBER_WEB_COOKIE")
    email = os.getenv("PTERODACTYL_EMAIL")
    password = os.getenv("PTERODACTYL_PASSWORD")

    with sync_playwright() as p:
        # 启动 Chromium
        browser = p.chromium.launch(headless=True)
        # 配置深度伪装的浏览器上下文
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )
        page = context.new_page()

        # 【核心修正】手动注入抗爬虫伪装脚本，替代不稳定的插件
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
        """)

        page.set_default_timeout(60000)

        try:
            # --- 登录部分 ---
            if remember_cookie:
                context.add_cookies([{
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": remember_cookie,
                    "domain": "hub.weirdhost.xyz",
                    "path": "/",
                    "httpOnly": True, "secure": True, "sameSite": "Lax",
                }])
            
            page.goto(SERVER_URL, wait_until="networkidle")

            if "login" in page.url:
                print("🔐 Cookie失效，尝试密码登录...")
                page.goto(LOGIN_URL, wait_until="networkidle")
                page.fill('input[name="username"]', email)
                page.fill('input[name="password"]', password)
                page.click('button[type="submit"]')
                page.wait_for_url(SERVER_URL, timeout=20000)

            # --- 续期操作 ---
            before_time = get_expire_datetime(page)
            print(f"操作前时间: {before_time}")

            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible")
            
            # 模拟真实人类的随机延迟点击
            time.sleep(random.uniform(2, 5))
            add_button.click()
            print("🖱 已点击续期按钮，正在观察验证挑战...")

            # --- 验证挑战处理 ---
            # 针对截图中的 Cloudflare Turnstile，等待其可能出现的 iframe
            time.sleep(5) 
            try:
                # 定位验证码 iframe
                captcha_frame = page.frame_locator('iframe[src*="cloudflare"]')
                # 尝试定位复选框所在区域并点击
                checkpoint = captcha_frame.locator('#challenge-stage')
                if checkpoint.is_visible(timeout=5000):
                    print("🔘 发现验证复选框，尝试强制点击...")
                    checkpoint.click(force=True)
                    time.sleep(10) # 给验证码通过留出时间
            except:
                print("ℹ️ 未发现验证框或点击失败，继续后续逻辑")

            # 等待数据刷新
            time.sleep(5)
            after_time = get_expire_datetime(page)
            print(f"操作后时间: {after_time}")

            if after_time and (not before_time or after_time > before_time):
                send_telegram(f"✅ <b>续期成功</b>\n新到期时间: {after_time}")
                return True
            else:
                # 如果没成功，最后截一张图辅助分析
                page.screenshot(path="final_check.png")
                raise RuntimeError("续期后时间未增加，可能卡在验证挑战")

        except Exception as e:
            page.screenshot(path="error.png")
            print(traceback.format_exc())
            send_telegram(f"❌ <b>运行异常</b>\n{str(e)}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    exit(0 if add_server_time() else 1)
