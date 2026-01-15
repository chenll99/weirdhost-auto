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
        # 注入高级伪装，隐藏自动化特征
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # --- 1. 登录处理 ---
            if remember_cookie:
                context.add_cookies([{"name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d", "value": remember_cookie, "domain": "hub.weirdhost.xyz", "path": "/"}])
            
            page.goto(SERVER_URL, wait_until="networkidle")
            
            if "login" in page.url:
                page.goto(LOGIN_URL)
                page.fill('input[name="username"]', email)
                page.fill('input[name="password"]', password)
                page.click('button[type="submit"]')
                page.wait_for_url(SERVER_URL, timeout=20000)
            
            page.screenshot(path="step1_login_check.png")

            # --- 2. 准备点击 ---
            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible")
            add_button.click()
            print("🖱 已点击续期按钮，正在处理验证挑战...")

            # --- 3. 核心：坐标盲点突破 CF 验证 ---
            time.sleep(6) # 给验证码 6 秒加载时间
            page.screenshot(path="step2_cf_appear.png")
            
            cf_frame = page.query_selector('iframe[src*="cloudflare"]')
            if cf_frame:
                box = cf_frame.bounding_box()
                if box:
                    # 计算复选框的大致坐标：iframe 内部靠左约 40 像素，垂直居中
                    target_x = box['x'] + 45
                    target_y = box['y'] + box['height'] / 2
                    
                    print(f"🎯 识别到验证框坐标: ({target_x}, {target_y})")
                    # 模拟真人鼠标轨迹移动
                    page.mouse.move(target_x - 20, target_y - 20)
                    time.sleep(0.5)
                    # 执行物理点击
                    page.mouse.click(target_x, target_y)
                    print("🖱 已执行物理坐标点击")
                    
                    time.sleep(2)
                    page.screenshot(path="step3_after_click.png")

            # --- 4. 观察与容错等待 ---
            print("⏳ 等待验证处理 (25秒)...")
            time.sleep(25)
            page.screenshot(path="step4_after_wait.png")

            # --- 5. 最终状态刷新 ---
            page.reload(wait_until="networkidle")
            time.sleep(5)
            page.screenshot(path="step5_final_check.png")
            
            # 判定结果：包含红色报错字符或时间增加均视为完成
            content = page.content()
            if "once at one time period" in content or "이미 연장" in content:
                print("✅ 验证通过：当前已是最新状态")
            else:
                print("ℹ️ 流程结束，请查看截图确认效果")
            
            return True # 强制 True 以便在 Actions 看到所有截图

        except Exception as e:
            page.screenshot(path="error_stack.png")
            print(f"❌ 运行崩溃: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    exit(0 if add_server_time() else 1)
