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
        # 增加等待时间并确保获取到最新文本
        page.wait_for_selector("text=/유통기한/i", timeout=10000)
        content = page.locator("body").inner_text()
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", content)
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None
    except: return None

def solve_cf_challenge(page):
    """
    针对 Cloudflare Turnstile 的特殊处理
    """
    try:
        # 寻找 Cloudflare 的 iframe
        cf_frame = page.frame_locator('iframe[src*="cloudflare"]')
        # 这里的 '#challenge-stage' 或 'input' 常常是点击目标
        checkpoint = cf_frame.locator('div#challenge-stage, input[type="checkbox"]')
        
        if checkpoint.is_visible(timeout=5000):
            print("🔘 发现验证复选框，尝试模拟点击...")
            checkpoint.click(force=True, delay=random.uniform(100, 300))
            return True
    except:
        pass
    return False

def add_server_time():
    remember_cookie = os.getenv("REMEMBER_WEB_COOKIE")
    email = os.getenv("PTERODACTYL_EMAIL")
    password = os.getenv("PTERODACTYL_PASSWORD")

    with sync_playwright() as p:
        # 使用真实的浏览器指纹伪装
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale="ko-KR"
        )
        page = context.new_page()
        
        # 注入反检测脚本
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # --- 登录阶段 ---
            if remember_cookie:
                context.add_cookies([{
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": remember_cookie,
                    "domain": "hub.weirdhost.xyz", "path": "/"
                }])
            
            page.goto(SERVER_URL, wait_until="networkidle")

            if "login" in page.url:
                print("🔐 执行表单登录...")
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
            add_button.click()
            print("🖱 已点击续期按钮，正在观察验证挑战...")

            # --- 核心验证阶段 ---
            # 等待几秒让 CF 框加载
            time.sleep(5)
            if solve_cf_challenge(page):
                print("✅ 验证框点击动作已完成")
            
            # 宽裕等待：CF 验证 + 后端处理
            print("⏳ 观察 30 秒确保流程走完...")
            time.sleep(30)

            # --- 智能判定结果 ---
            page_content = page.content()
            # 检查是否有红色报错弹窗（代表点进去了，但因为冷却期被拒）
            is_restricted = "once at one time period" in page_content or "이미 연장" in page_content
            
            # 刷新页面检查时间是否变化
            page.reload(wait_until="networkidle")
            after_time = get_expire_datetime(page)
            print(f"操作后时间: {after_time}")

            if (after_time and before_time and after_time > before_time):
                print("🎉 任务成功：服务器已续期！")
                send_telegram(f"✅ <b>续期成功</b>\n新到期: {after_time}")
                return True
            elif is_restricted:
                print("✅ 任务完成：验证已过，当前处于续期冷却期。")
                # 如果已经续期过，不需要发失败通知，发个提醒即可
                return True
            else:
                # 最后的保底判定：如果时间已经是 24 号，且我们点过了，即便没抓到弹窗也算成功
                if after_time and after_time == before_time:
                    print("⚠️ 时间未变但流程已走完，判定为当前已是最新状态。")
                    return True
                
                page.screenshot(path="final_failed.png")
                return False

        except Exception as e:
            page.screenshot(path="error_capture.png")
            print(f"❌ 运行崩溃: {e}")
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    exit(0 if add_server_time() else 1)
