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
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )
        page = context.new_page()

        # 注入底层指纹伪装
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
        """)

        page.set_default_timeout(60000)

        try:
            # --- 登录逻辑 ---
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

            # 获取初始时间
            before_time = get_expire_datetime(page)
            print(f"点击前时间: {before_time}")

            # --- 点击续期按钮 ---
            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible")
            time.sleep(random.uniform(2, 4))
            add_button.click()
            print("🖱 已点击续期按钮，等待 CF 验证处理...")

            # --- 处理 Cloudflare Turnstile 验证 ---
            # 根据反馈，验证约需 10 秒
            time.sleep(5) 
            try:
                captcha_frame = page.frame_locator('iframe[src*="cloudflare"]')
                checkpoint = captcha_frame.locator('#challenge-stage')
                if checkpoint.is_visible(timeout=5000):
                    print("🔘 发现验证复选框，尝试点击")
                    checkpoint.click(force=True)
            except:
                print("ℹ️ 未发现或无需手动点击验证框")

            # 等待验证完成及弹窗出现
            print("⏳ 等待验证完成 (15秒)...")
            time.sleep(15) 

            # --- 结果校验与容错 ---
            # 刷新页面以清除验证码遮挡并获取最新后端数据
            page.reload(wait_until="networkidle")
            after_time = get_expire_datetime(page)
            print(f"操作后时间: {after_time}")

            # 只要时间增加，或者页面显示了“已续期”的错误提示，都视为成功
            is_already_renewed = page.locator('text=/can only once at one time period/i').is_visible()

            if (after_time and before_time and after_time > before_time) or is_already_renewed:
                print("🎉 续期成功或当前已是最新状态")
                send_telegram(f"✅ <b>续期成功</b>\n新到期时间: {after_time or before_time}")
                return True
            else:
                page.screenshot(path="failed_check.png")
                print("❌ 时间未刷新且未见成功提示")
                return False

        except Exception as e:
            page.screenshot(path="error.png")
            print(traceback.format_exc())
            send_telegram(f"❌ 脚本异常: {str(e)}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    # 执行并根据结果退出，确保 Actions 状态准确
    exit(0 if add_server_time() else 1)
