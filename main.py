import os
import re
import time
import random
import traceback
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 【核心修正点】改用这种最稳妥的导入方式
import playwright_stealth

SERVER_URL = "https://hub.weirdhost.xyz/server/e66c2244"
LOGIN_URL = "https://hub.weirdhost.xyz/auth/login"

# ... (send_telegram 和 get_expire_datetime 函数保持不变)

def add_server_time():
    remember_cookie = os.getenv("REMEMBER_WEB_COOKIE")
    email = os.getenv("PTERODACTYL_EMAIL")
    password = os.getenv("PTERODACTYL_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # 【核心修正点】使用全路径调用，避免“模块不可调用”错误
        playwright_stealth.stealth_sync(page) 
        
        page.set_default_timeout(60000)
        # ... 后面逻辑保持不变 ...

        try:
            # ---------- 登录逻辑 ----------
            if remember_cookie:
                print("🍪 使用 Cookie 登录")
                context.add_cookies([{
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": remember_cookie,
                    "domain": "hub.weirdhost.xyz",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                }])
                page.goto(SERVER_URL, wait_until="networkidle")

            if "login" in page.url:
                print("🔐 使用邮箱密码登录")
                page.goto(LOGIN_URL, wait_until="networkidle")
                page.fill('input[name="username"]', email)
                page.fill('input[name="password"]', password)
                page.click('button[type="submit"]')
                page.wait_for_url(SERVER_URL, timeout=15000)

            # ---------- 续期逻辑 ----------
            before_time = get_expire_datetime(page)
            print(f"点击前到期时间: {before_time}")

            print("🔍 查找 시간추가 按钮")
            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible", timeout=15000)
            
            # 【修改点 6】模拟真人思考，随机停顿 2-4 秒再点击
            time.sleep(random.uniform(2, 4))
            add_button.click()
            print("🖱 已点击时间追加")

            # 【修改点 7】处理点击后出现的 Cloudflare 验证码
            try:
                # 等待 5 秒看是否有验证码 iframe 弹出
                captcha_frame = page.frame_locator('iframe[src*="cloudflare"]')
                checkpoint = captcha_frame.locator('#challenge-stage')
                if checkpoint.is_visible(timeout=5000):
                    print("⚠️ 发现 Cloudflare 验证挑战！尝试自动点击...")
                    checkpoint.click()
                    time.sleep(5) # 等待验证通过
            except:
                print("✅ 未发现验证码或已自动跳过")

            # 等待页面刷新数据
            time.sleep(5)

            after_time = get_expire_datetime(page)
            print(f"点击后到期时间: {after_time}")

            if not after_time or (before_time and after_time <= before_time):
                raise RuntimeError("到期时间未增加，可能被验证码拦截")

            # ---------- 成功通知 ----------
            msg = f"✅ <b>服务器续期成功</b>\n新到期: {after_time}"
            send_telegram(msg)
            return True

        except Exception as e:
            page.screenshot(path="error.png")
            print(f"发生错误: {e}")
            send_telegram(f"❌ 续期异常: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    success = add_server_time()
    exit(0 if success else 1)
