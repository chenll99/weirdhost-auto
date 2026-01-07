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
    """
    尝试登录 hub.weirdhost.xyz 并点击 "시간 추가" 按钮。
    优先使用 REMEMBER_WEB_COOKIE 进行会话登录，如果不存在则回退到邮箱密码登录。
    此函数设计为每次GitHub Actions运行时执行一次。
    """
    # 从环境变量获取登录凭据
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    pterodactyl_email = os.environ.get('PTERODACTYL_EMAIL')
    pterodactyl_password = os.environ.get('PTERODACTYL_PASSWORD')

    # 检查是否提供了任何登录凭据
    if not (remember_web_cookie or (pterodactyl_email and pterodactyl_password)):
        print("错误: 缺少登录凭据。请设置 REMEMBER_WEB_COOKIE 或 PTERODACTYL_EMAIL 和 PTERODACTYL_PASSWORD 环境变量。")
        return False

    with sync_playwright() as p:
        # 在 GitHub Actions 中，使用 headless 无头模式运行
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # 增加默认超时时间到90秒，以应对网络波动和慢加载
        page.set_default_timeout(90000)

        try:
            # --- 方案一：优先尝试使用 Cookie 会话登录 ---
            if remember_web_cookie:
                print("检测到 REMEMBER_WEB_COOKIE，尝试使用 Cookie 登录...")
                session_cookie = {
                    'name': 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    'value': remember_web_cookie,
                    'domain': 'hub.weirdhost.xyz',  # 已更新为新的域名
                    'path': '/',
                    'expires': int(time.time()) + 3600 * 24 * 365, # 设置一个较长的过期时间
                    'httpOnly': True,
                    'secure': True,
                    'sameSite': 'Lax'
                }
                page.context.add_cookies([session_cookie])
                print(f"已设置 Cookie。正在访问目标服务器页面: {server_url}")
                
                try:
                    # 使用 'domcontentloaded' 以加快页面加载判断，然后依赖选择器等待确保元素加载
                    page.goto(server_url, wait_until="domcontentloaded", timeout=90000)
                except PlaywrightTimeoutError:
                    print(f"页面加载超时（90秒）。")
                    page.screenshot(path="goto_timeout_error.png")
                
                # 检查是否因 Cookie 无效被重定向到登录页
                if "login" in page.url or "auth" in page.url:
                    print("Cookie 登录失败或会话已过期，将回退到邮箱密码登录。")
                    page.context.clear_cookies()
                    remember_web_cookie = None # 标记 Cookie 登录失败，以便执行下一步
                else:
                    print("Cookie 登录成功，已进入服务器页面。")

            # --- 方案二：如果 Cookie 方案失败或未提供，则使用邮箱密码登录 ---
            if not remember_web_cookie:
                if not (pterodactyl_email and pterodactyl_password):
                    print("错误: Cookie 无效，且未提供 PTERODACTYL_EMAIL 或 PTERODACTYL_PASSWORD。无法登录。")
                    browser.close()
                    return False

                login_url = "https://hub.weirdhost.xyz/auth/login" # 已更新为新的登录URL
                print(f"正在访问登录页面: {login_url}")
                page.goto(login_url, wait_until="domcontentloaded", timeout=90000)

                # 定义选择器 (Pterodactyl 面板通用，无需修改)
                email_selector = 'input[name="username"]' 
                password_selector = 'input[name="password"]'
                login_button_selector = 'button[type="submit"]'

                print("等待登录表单元素加载...")
                page.wait_for_selector(email_selector)
                page.wait_for_selector(password_selector)
                page.wait_for_selector(login_button_selector)

                print("正在填写邮箱和密码...")
                page.fill(email_selector, pterodactyl_email)
                page.fill(password_selector, pterodactyl_password)

                print("正在点击登录按钮...")
                with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
                    page.click(login_button_selector)

                # 检查登录后是否成功
                if "login" in page.url or "auth" in page.url:
                    error_text = page.locator('.alert.alert-danger').inner_text().strip() if page.locator('.alert.alert-danger').count() > 0 else "未知错误，URL仍在登录页。"
                    print(f"邮箱密码登录失败: {error_text}")
                    page.screenshot(path="login_fail_error.png")
                    browser.close()
                    return False
                else:
                    print("邮箱密码登录成功。")

            # --- 确保当前位于正确的服务器页面 ---
            if page.url != server_url:
                print(f"当前不在目标服务器页面，正在导航至: {server_url}")
                page.goto(server_url, wait_until="domcontentloaded", timeout=90000)
                if "login" in page.url:
                    print("导航失败，会话可能已失效，需要重新登录。")
                    page.screenshot(path="server_page_nav_fail.png")
                    browser.close()
                    return False

            # --- 核心操作：查找并点击 "시간추가" 按钮 ---
            add_button_selector = 'button:has-text("시간추가")' # 已更新为新的按钮文本
            print(f"正在查找并等待 '{add_button_selector}' 按钮...")

            try:
                # 等待按钮变为可见且可点击
            # —— 点击前读取剩余时间 ——
            before_time = get_remaining_time_text(page)
            print(f"点击前剩余时间: {before_time}")

            add_button.click()
            print("已点击 '시간추가' 按钮，等待服务器更新...")
            time.sleep(6)

            # —— 点击后再次读取 ——
            after_time = get_remaining_time_text(page)
            print(f"点击后剩余时间: {after_time}")

            # —— 判断是否真的增加 ——
            if before_time and after_time and before_time != after_time:
                print("✅ 剩余时间已变化，确认续期成功")

                send_telegram(
                    "✅ <b>服务器续期成功</b>\n\n"
                    f"🕒 之前：{before_time}\n"
                    f"🕓 现在：{after_time}\n\n"
                    f"🔗 {server_url}"
               )

               browser.close()
               return True
            else:
                print("⚠️ 点击完成，但未检测到剩余时间变化")

                page.screenshot(path="renew_time_not_changed.png")

                send_telegram(
                    "⚠️ <b>服务器续期异常</b>\n\n"
                    f"🕒 之前：{before_time}\n"
                    f"🕓 现在：{after_time}\n\n"
                    "按钮已点击，但时间未确认增加\n"
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
