import os
import time
import traceback
import requests
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


# ===================== 剩余时间读取 =====================
def get_remaining_time_text(page):
    """
    ⚠️ 注意：
    这里的 selector 可能需要你根据真实页面微调
    先保证「找不到就返回 None，不抛异常」
    """
    selectors = [
        "text=/Remaining/i",
        "text=/시간/i",
        "text=/남은/i",
    ]

    for sel in selectors:
        loc = page.locator(sel)
        if loc.count() > 0:
            try:
                return loc.first.inner_text().strip()
            except Exception:
                pass
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

                with page.expect_navigation():
                    page.click('button[type="submit"]')

                if "login" in page.url:
                    raise RuntimeError("邮箱密码登录失败")

            # ---------- 进入服务器页 ----------
            if page.url != SERVER_URL:
                page.goto(SERVER_URL, wait_until="domcontentloaded")

            # ---------- 读取点击前时间 ----------
            before_time = get_remaining_time_text(page)
            print(f"点击前剩余时间: {before_time}")

            if not before_time:
                raise RuntimeError("无法读取点击前剩余时间")

            # ---------- 查找并点击按钮（关键修复点） ----------
            print("🔍 查找 시간추가 按钮")
            add_button = page.locator('button:has-text("시간추가")')

            try:
                add_button.wait_for(state="visible", timeout=15000)
            except PlaywrightTimeoutError:
                raise RuntimeError("未找到 시간추가 按钮")

            add_button.click()
            print("🖱 已点击 시간추가")

            page.wait_for_timeout(5000)

            # ---------- 读取点击后时间 ----------
            after_time = get_remaining_time_text(page)
            print(f"点击后剩余时间: {after_time}")

            if not after_time:
                raise RuntimeError("无法读取点击后剩余时间")

            # ---------- 成功校验 ----------
            if after_time == before_time:
                raise RuntimeError("时间未发生变化，续期失败")

            # ---------- 成功 ----------
            msg = (
                "✅ <b>服务器时间增加成功</b>\n\n"
                f"🔹 点击前: {before_time}\n"
                f"🔹 点击后: {after_time}\n\n"
                f"🔗 {SERVER_URL}"
            )
            send_telegram(msg)
            print("🎉 成功完成")
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
