import os
import re
import time
import traceback
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SERVER_URL = "https://hub.weirdhost.xyz/server/e66c2244"
LOGIN_URL = "https://hub.weirdhost.xyz/auth/login"


# ===================== Telegram 通知 =====================
def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️ 未配置 Telegram，跳过通知")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
    except Exception as e:
        print(f"Telegram 发送失败: {e}")


# ===================== 到期时间解析（最终定版） =====================
def get_expire_datetime(page):
    """
    从页面文本中解析：
    유통기한 2026-01-10 13:25:54
    返回 datetime 对象，失败返回 None
    """
    try:
        text = page.locator("text=/유통기한/i").first.inner_text()
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
        if not m:
            return None
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


# ===================== 主逻辑 =====================
def add_server_time():
    remember_cookie = os.getenv("REMEMBER_WEB_COOKIE")
    email = os.getenv("PTERODACTYL_EMAIL")
    password = os.getenv("PTERODACTYL_PASSWORD")

    if not (remember_cookie or (email and password)):
        raise RuntimeError("缺少登录凭据（Cookie 或 邮箱密码）")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            # ---------- Cookie 登录 ----------
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

                page.goto(SERVER_URL, wait_until="domcontentloaded")

                if "login" in page.url:
                    print("⚠️ Cookie 失效，回退账号密码")
                    context.clear_cookies()
                else:
                    print("✅ Cookie 登录成功")

            # ---------- 邮箱密码登录 ----------
            if "login" in page.url:
                print("🔐 使用邮箱密码登录")
                page.goto(LOGIN_URL, wait_until="domcontentloaded")

                page.fill('input[name="username"]', email)
                page.fill('input[name="password"]', password)

                with page.expect_navigation(wait_until="domcontentloaded"):
                    page.click('button[type="submit"]')

                if "login" in page.url:
                    raise RuntimeError("邮箱密码登录失败")

            # ---------- 进入服务器页 ----------
            if page.url != SERVER_URL:
                page.goto(SERVER_URL, wait_until="domcontentloaded")

            # ---------- 点击前到期时间 ----------
            before_time = get_expire_datetime(page)
            print(f"点击前到期时间: {before_time}")

            if not before_time:
                raise RuntimeError("无法解析点击前到期时间")

            # ---------- 查找并点击「시간추가」 ----------
            print("🔍 查找 시간추가 按钮")
            add_button = page.locator('button:has-text("시간추가")')

            try:
                add_button.wait_for(state="visible", timeout=15000)
            except PlaywrightTimeoutError:
                raise RuntimeError("未找到 시간추가 按钮")

            add_button.click()
            print("🖱 已点击 시간추가")

            page.wait_for_timeout(5000)

            # ---------- 点击后到期时间 ----------
            after_time = get_expire_datetime(page)
            print(f"点击后到期时间: {after_time}")

            if not after_time:
                raise RuntimeError("无法解析点击后到期时间")

            # ---------- 真实成功校验 ----------
            if after_time <= before_time:
                raise RuntimeError("到期时间未增加，续期失败")

            # ---------- 成功通知 ----------
            msg = (
                "✅ <b>服务器时间增加成功</b>\n\n"
                f"🕒 原到期时间: {before_time}\n"
                f"🕒 新到期时间: {after_time}\n\n"
                f"🔗 {SERVER_URL}"
            )
            send_telegram(msg)
            print("🎉 任务成功完成")

            browser.close()
            return True

        except Exception as e:
            page.screenshot(path="error.png")
            err_msg = (
                "❌ <b>服务器续期脚本异常</b>\n\n"
                f"<code>{e}</code>\n\n"
                f"🔗 {SERVER_URL}"
            )
            send_telegram(err_msg)
            print(err_msg)
            print(traceback.format_exc())
            browser.close()
            return False


# ===================== 入口 =====================
if __name__ == "__main__":
    print("🚀 开始执行添加服务器时间任务...")
    success = add_server_time()
    exit(0 if success else 1)
