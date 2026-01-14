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
        browser = p.chromium.launch(headless=True)
        # 增加更多的浏览器指纹伪装
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
        )
        page = context.new_page()

        # 【核心修正】手动注入伪装脚本，替代 playwright-stealth 插件
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

        page.set_default_timeout(60000)

        try:
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
                print("🔐 Cookie失效，尝试账号密码登录")
                page.goto(LOGIN_URL, wait_until="networkidle")
                page.fill('input[name="username"]', email)
                page.fill('input[name="password"]', password)
                page.click('button[type="submit"]')
                page.wait_for_url(SERVER_URL, timeout=20000)

            before_time = get_expire_datetime(page)
            print(f"点击前时间: {before_time}")

            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible")
            time.sleep(random.uniform(3, 6)) # 稍微多停一会，更像真人
            add_button.click()
            print("🖱 已点击续期按钮")

            # 处理点击后的验证码
            try:
                # 给验证码框架一点加载时间
                time.sleep(3)
                captcha_frame = page.frame_locator('iframe[src*="cloudflare"]')
                checkpoint = captcha_frame.locator('#challenge-stage')
                if checkpoint.is_visible(timeout=5000):
                    print("🔘 发现挑战，尝试点击...")
                    checkpoint.click()
                    time.sleep(10) # 验证码通过需要时间
            except:
                print("ℹ️ 未发现或已通过验证码")

            time.sleep(5)
            after_time = get_expire_datetime(page)
            print(f"点击后时间: {after_time}")

            if after_time and (not before_time or after_time > before_time):
                send_telegram(f"✅ 续期成功！\n新到期: {after_time}")
                return True
            else:
                raise RuntimeError("续期后时间未增加")

        except Exception as e:
            page.screenshot(path="error.png")
            print(traceback.format_exc())
            send_telegram(f"❌ 运行异常: {str(e)}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    exit(0 if add_server_time() else 1)
