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

def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10)
    except Exception as e: print(f"Telegram 失败: {e}")

def get_expire_datetime(page):
    try:
        # 寻找包含日期的文本
        page.wait_for_selector("text=/유통기한/i", timeout=10000)
        text = page.locator("text=/유통기한/i").all_inner_texts()
        full_text = " ".join(text)
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", full_text)
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None
    except: return None

def add_server_time():
    remember_cookie = os.getenv("REMEMBER_WEB_COOKIE")
    email = os.getenv("PTERODACTYL_EMAIL")
    password = os.getenv("PTERODACTYL_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 模拟真实的浏览器环境
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="ko-KR"
        )
        page = context.new_page()

        # 注入基础反爬伪装
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # --- 登录部分 ---
            if remember_cookie:
                context.add_cookies([{
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": remember_cookie,
                    "domain": "hub.weirdhost.xyz", "path": "/",
                    "httpOnly": True, "secure": True, "sameSite": "Lax",
                }])
            
            page.goto(SERVER_URL, wait_until="networkidle")

            if "login" in page.url:
                print("🔐 执行账号登录...")
                page.goto(LOGIN_URL)
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
            print("🖱 已点击续期按钮，进入 CF 验证观察期...")

            # --- 处理 Cloudflare Turnstile 验证 ---
            # 自动验证通常需要 5-10 秒。我们直接等待 20 秒，让验证码和后续弹窗都跑完
            print("⏳ 正在等待 CF 自动挑战及弹窗响应 (20秒)...")
            time.sleep(20) 

            # --- 结果逻辑判定 ---
            # 情况 A: 到期日期文本发生了变化
            after_time = get_expire_datetime(page)
            print(f"操作后时间: {after_time}")
            
            # 情况 B: 页面出现了红色警告 (代表已经续期过了，见 wer1.png)
            # 我们检查源码中是否出现了 "once at one time period"
            page_content = page.content()
            is_renew_restricted = "once at one time period" in page_content

            if (after_time and before_time and after_time > before_time):
                print("🎉 续期成功：时间已增加")
                send_telegram(f"✅ <b>服务器续期成功</b>\n新到期时间: {after_time}")
                return True
            elif is_renew_restricted:
                print("ℹ️ 状态正常：检测到续期频率限制提示")
                send_telegram(f"✅ <b>续期状态正常</b>\n当前已是最新状态: {before_time}")
                return True
            else:
                # 如果都没匹配上，尝试刷新页面做最后一搏
                print("🔄 未检测到变化，尝试刷新页面...")
                page.reload(wait_until="networkidle")
                final_time = get_expire_datetime(page)
                if final_time and before_time and final_time > before_time:
                    send_telegram(f"✅ <b>续期成功 (刷新后确认)</b>\n新到期时间: {final_time}")
                    return True
                
                # 记录失败快照
                page.screenshot(path="failed_check.png")
                print("❌ 任务失败：无法确认续期结果")
                return False

        except Exception as e:
            page.screenshot(path="error.png")
            print(traceback.format_exc())
            send_telegram(f"❌ 运行异常: {str(e)}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    # 如果 add_server_time 返回 True，Action 就会变绿
    exit(0 if add_server_time() else 1)
