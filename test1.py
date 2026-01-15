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
    except Exception as e: print(f"Telegram 发送失败: {e}")

def get_expire_datetime(page):
    try:
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
        # 即使是 Headless 模式，也通过伪装让 CF 认为我们是真人
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="ko-KR"
        )
        page = context.new_page()

        # 注入底层指纹伪装，跳过浏览器检测
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # --- 登录步骤 ---
            if remember_cookie:
                context.add_cookies([{
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": remember_cookie,
                    "domain": "hub.weirdhost.xyz", "path": "/",
                    "httpOnly": True, "secure": True, "sameSite": "Lax",
                }])
            
            page.goto(SERVER_URL, wait_until="networkidle")

            if "login" in page.url:
                print("🔐 Cookie失效，正在使用账号登录...")
                page.goto(LOGIN_URL)
                page.fill('input[name="username"]', email)
                page.fill('input[name="password"]', password)
                page.click('button[type="submit"]')
                page.wait_for_url(SERVER_URL, timeout=20000)

            before_time = get_expire_datetime(page)
            print(f"点击前时间: {before_time}")

            # --- 点击按钮 ---
            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible")
            time.sleep(random.uniform(2, 4))
            add_button.click()
            print("🖱 已点击续期按钮，正在处理 Cloudflare 验证...")

            # --- 【核心】Cloudflare 验证处理逻辑 ---
            # 1. 首先尝试定位验证码 iframe
            time.sleep(5)
            try:
                # 寻找包含 Turnstile 的框架并尝试点击
                captcha_frame = page.frame_locator('iframe[src*="cloudflare"]')
                checkpoint = captcha_frame.locator('#challenge-stage')
                if checkpoint.is_visible(timeout=5000):
                    print("🔘 成功定位到 CF 复选框，尝试点击...")
                    checkpoint.click(force=True)
            except:
                print("ℹ️ 未发现显式复选框，可能正在自动验证")

            # 2. 强制等待验证码加载、验证并提交的时间
            print("⏳ 正在等待 CF 验证流程结束 (20秒)...")
            time.sleep(20) 

            # --- 结果全量扫描判定 ---
            # 即使时间没变，只要网页里出现了成功的特征或失败的红框，都代表 CF 验证已完成
            page_content = page.content()
            
            # 检测是否出现了“已经续期”的限制消息 (wer1.png 情况)
            is_renew_restricted = "once at one time period" in page_content
            
            # 刷新页面获取最新时间
            page.reload(wait_until="networkidle")
            after_time = get_expire_datetime(page)
            print(f"操作后时间: {after_time}")

            # 只要满足以下任一条件，即视为 CF 项目任务完成：
            # 1. 时间增加了
            # 2. 源码里出现了重复续期的报错（说明点进去了）
            if (after_time and before_time and after_time > before_time):
                print("🎉 任务成功：服务器已续期！")
                send_telegram(f"✅ <b>续期成功</b>\n新到期: {after_time}")
                return True
            elif is_renew_restricted:
                print("✅ 任务完成：CF验证已通过，但当前无需重复续期")
                send_telegram(f"✅ <b>CF验证通过</b>\n状态: 已是最新 ({before_time})")
                return True
            else:
                page.screenshot(path="failed_final.png")
                print("❌ 失败：未检测到时间变化或成功信号")
                return False

        except Exception as e:
            page.screenshot(path="error.png")
            print(traceback.format_exc())
            send_telegram(f"❌ 运行异常: {str(e)}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    exit(0 if add_server_time() else 1)
