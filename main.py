import os
import time
from playwright.sync_api import sync_playwright, Cookie, TimeoutError as PlaywrightTimeoutError

import requests
def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️ 未配置 Telegram，跳过通知")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Telegram 通知失败: {e}")

def get_remaining_time_text(page):
    """
    读取服务器剩余时间文本
    成功返回字符串，失败返回 None
    """
    selectors = [
        'text=/剩余时间|Remaining|Expires|만료/',
        '.text-muted',
        '.server-status'
    ]

    for sel in selectors:
        locator = page.locator(sel)
        if locator.count() > 0:
            try:
                text = locator.first.inner_text().strip()
                if text:
                    return text
            except:
                pass

    return None


def add_server_time(server_url="https://hub.weirdhost.xyz/server/e66c2244"):
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    pterodactyl_email = os.environ.get('PTERODACTYL_EMAIL')
    pterodactyl_password = os.environ.get('PTERODACTYL_PASSWORD')

    if not (remember_web_cookie or (pterodactyl_email and pterodactyl_password)):
        print("❌ 缺少登录凭据")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(90000)

        try:
            # ========== Cookie 登录 ==========
            if remember_web_cookie:
                page.context.add_cookies([{
                    'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    'value': remember_web_cookie,
                    'domain': 'hub.weirdhost.xyz',
                    'path': '/',
                    'expires': int(time.time()) + 3600 * 24 * 365,
                    'httpOnly': True,
                    'secure': True,
                    'sameSite': 'Lax'
                }])

                page.goto(server_url, wait_until="domcontentloaded")

                if "login" in page.url or "auth" in page.url:
                    page.context.clear_cookies()
                    remember_web_cookie = None

            # ========== 邮箱密码登录 ==========
            if not remember_web_cookie:
                page.goto("https://hub.weirdhost.xyz/auth/login", wait_until="domcontentloaded")

                page.fill('input[name="username"]', pterodactyl_email)
                page.fill('input[name="password"]', pterodactyl_password)

                with page.expect_navigation():
                    page.click('button[type="submit"]')

                if "login" in page.url or "auth" in page.url:
                    raise RuntimeError("登录失败")

            # ========== 确保在服务器页面 ==========
            if page.url != server_url:
                page.goto(server_url, wait_until="domcontentloaded")

            # ========== 查找并点击按钮 ==========
            add_button = page.locator('button:has-text("시간추가")')
            add_button.wait_for(state="visible", timeout=30000)

            before_time = get_remaining_time_text(page)
            print("点击前时间:", before_time)

            add_button.click()
            time.sleep(6)

            after_time = get_remaining_time_text(page)
            print("点击后时间:", after_time)

            if before_time and after_time and before_time != after_time:
                send_telegram(
                    "✅ <b>服务器续期成功</b>\n\n"
                    f"🕒 之前：{before_time}\n"
                    f"🕓 现在：{after_time}\n\n"
                    f"🔗 {server_url}"
                )
                browser.close()
                return True
            else:
                page.screenshot(path="renew_failed.png")
                send_telegram(
                    "⚠️ <b>服务器续期异常</b>\n\n"
                    f"🕒 之前：{before_time}\n"
                    f"🕓 现在：{after_time}\n\n"
                    f"🔗 {server_url}"
                )
                browser.close()
                return False

        except Exception as e:
            page.screenshot(path="error.png")
            send_telegram(
                "❌ <b>脚本执行异常</b>\n\n"
                f"{e}\n\n"
                f"🔗 {server_url}"
            )
            browser.close()
            return False


            except PlaywrightTimeoutError:
                print(f"错误: 在30秒内未找到或 '시간추가' 按钮不可见/不可点击。")
                page.screenshot(path="add_6h_button_not_found.png")
                browser.close()
                return False

        except Exception as e:
            error_msg = (
                "❌ <b>服务器续期脚本异常</b>\n\n"
                f"{e}\n\n"
                f"🔗 {server_url}"
            )

            print(error_msg)
            page.screenshot(path="general_error.png")
            send_telegram(error_msg)
            browser.close()
            return False


if __name__ == "__main__":
    print("开始执行添加服务器时间任务...")
    success = add_server_time()
    if success:
        print("任务执行成功。")
        exit(0)
    else:
        print("任务执行失败。")
        exit(1)
