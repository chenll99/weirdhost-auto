import os
import re
import time
import random
import traceback
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

SERVER_URL = "https://hub.weirdhost.xyz/server/e66c2244"
LOGIN_URL = "https://hub.weirdhost.xyz/auth/login"

def add_server_time():
    remember_cookie = os.getenv("REMEMBER_WEB_COOKIE")
    email = os.getenv("PTERODACTYL_EMAIL")
    password = os.getenv("PTERODACTYL_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="ko-KR"
        )
        page = context.new_page()
        # 基础反检测注入
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # --- 阶段 1: 登录验证 ---
            if remember_cookie:
                context.add_cookies([{"name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d", "value": remember_cookie, "domain": "hub.weirdhost.xyz", "path": "/"}])
            
            page.goto(SERVER_URL, wait_until="networkidle")
            
            if "login" in page.url:
                page.goto(LOGIN_URL)
                page.fill('input[name="username"]', email)
                page.fill('input[name="password"]', password)
                page.click('button[type="submit"]')
                page.wait_for_url(SERVER_URL, timeout=20000)
            
            page.screenshot(path="step1_login_success.png")
            print("📸 阶段 1 完成：登录并进入控制台")

            # --- 阶段 2: 准备点击续期 ---
            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible")
            page.screenshot(path="step2_before_click_renew.png")
            
            add_button.click()
            print("🖱 阶段 2 完成：已点击续期按钮")

            # --- 阶段 3: 验证挑战出现 ---
            time.sleep(5) # 等待 5 秒让 CF 挑战框加载
            page.screenshot(path="step3_cf_challenge_loaded.png")
            
            # --- 阶段 4: 尝试点击验证框 ---
            cf_frame = page.frame_locator('iframe[src*="cloudflare"]')
            checkpoint = cf_frame.locator('div#challenge-stage, input[type="checkbox"]')
            
            if checkpoint.is_visible(timeout=5000):
                checkpoint.click(force=True)
                print("🔘 阶段 4：检测到 CF 复选框并尝试点击")
                time.sleep(3)
                page.screenshot(path="step4_after_cf_click.png")
            else:
                print("ℹ️ 阶段 4：未发现显式 CF 复选框，可能正在自动验证")

            # --- 阶段 5: 等待挑战处理结果 ---
            print("⏳ 阶段 5：正在等待 15 秒处理结果...")
            time.sleep(15)
            page.screenshot(path="step5_after_wait_cf.png")

            # --- 阶段 6: 最终状态确认 ---
            page.reload(wait_until="networkidle")
            time.sleep(5)
            page.screenshot(path="step6_final_result.png")
            
            content = page.content()
            if "once at one time period" in content:
                print("✅ 结果：检测到续期限制文字，CF 验证已通过")
            
            return True # 强制成功以保存所有截图

        except Exception as e:
            page.screenshot(path="error_crash.png")
            print(f"❌ 运行崩溃: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    exit(0 if add_server_time() else 1)
