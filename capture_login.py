#!/usr/bin/env python3
"""
闲鱼登录态导出工具 v7（桌面登录 + 自动切 Mobile UA）

解决的核心问题：
  v6（以及 v3~v5）全部卡在同一个死结：
    Playwright + 移动端 UA → 闲鱼反爬检测严格 → 滑动验证码报错(error:xxx) /
    获取验证码按钮无反应 → 无法登录。

  根因：闲鱼对「移动端请求」的风控远严于桌面端。
        Playwright 的 CDP 自动化指纹在移动端 UA 下几乎必被拦。

v7 的突破思路（两阶段）：
  阶段 A — 用【桌面端 UA】启动副本浏览器：
    · 闲鱼对桌面端反爬宽松 → 短信验证码正常可用
    · 用户在弹窗中完成登录（输手机号 → 点获取验证码 → 输码 → 点登录）
    · 登录成功后 cookie 已写入当前 browser context

  阶段 B — 同一 context 内【自动切换为移动端 UA】：
    · 不关浏览器、不丢 cookie（context 内共享）
    · 改 user_agent + is_mobile + viewport 为移动端配置
    · 新开一个 page 导航到闲鱼搜索页
    · 服务端收到「已有 cookie + 移动端 UA」→ 建立 mobile session
    · 保存此时的 storage_state → 就是 spider 可用的移动端登录态

用法:
  cd /Users/zhaoshuixian/Documents/GitHub/ai-goofish-monitor
  python3 capture_login.py
"""
import json
import os
import shutil
import sys
from playwright.sync_api import sync_playwright

# === 配置 ===
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
STATE_FILE = os.path.join(STATE_DIR, "aicaic-1.json")

CHROME_USER_DATA = os.path.expanduser("~/Library/Application Support/Google/Chrome")
CHROME_PROFILE = "Profile 5"
SRC_PROFILE_DIR = os.path.join(CHROME_USER_DATA, CHROME_PROFILE)
TMP_USER_DATA = "/tmp/goofish_profile_copy"

# 桌面端 UA（用于登录阶段，反爬宽松）
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# 移动端 UA（与 spider 完全一致，用于第二阶段建 session）
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)

EXCLUDE_DIRS = {
    "Cache", "GPUCache", "Code Cache", "Service Worker", "Session Storage",
    "blob_storage", "Crashpad", "Crashpad Reports", "Crashpad reports",
    "optimization_guide", "subresource_filter", "VideoDecodeStats",
    "Site Characteristics Database", "webrtc_event_logs", "QuotaManager",
    "Download Service", "feature_engagement", "fonts", "GrShaderCache",
    "Meipai", "assistant", "AutofillStrikeDatabase",
}


def _copytree_ignore(src, names):
    ignored = set()
    for n in names:
        full = os.path.join(src, n)
        if os.path.isdir(full):
            if n in EXCLUDE_DIRS or "Cache" in n:
                ignored.add(n)
        if n in {"SingletonLock", "SingletonSocket", "SingletonCookie"}:
            ignored.add(n)
    return ignored


def copy_profile():
    """复制 Profile 5 到临时目录。"""
    if not os.path.isdir(SRC_PROFILE_DIR):
        print(f"  ❌ 找不到源 Profile 目录: {SRC_PROFILE_DIR}")
        return False

    if os.path.isdir(TMP_USER_DATA):
        shutil.rmtree(TMP_USER_DATA, ignore_errors=True)
    os.makedirs(TMP_USER_DATA, exist_ok=True)

    print(f"  · 复制 Profile 5 → {TMP_USER_DATA} （排除缓存）...")
    try:
        shutil.copytree(
            SRC_PROFILE_DIR,
            os.path.join(TMP_USER_DATA, CHROME_PROFILE),
            ignore=_copytree_ignore,
            copy_function=shutil.copy2,
        )
    except Exception as e:
        print(f"  ⚠️  复制非致命错误: {e}")

    local_state = os.path.join(CHROME_USER_DATA, "Local State")
    if os.path.exists(local_state):
        try:
            shutil.copy2(local_state, os.path.join(TMP_USER_DATA, "Local State"))
        except Exception:
            pass

    for lock in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        lp = os.path.join(TMP_USER_DATA, lock)
        if os.path.exists(lp):
            try:
                os.remove(lp)
            except Exception:
                pass

    return True


def main():
    os.makedirs(STATE_DIR, exist_ok=True)

    print("=" * 60)
    print("  闲鱼登录态捕获 v7")
    print("  (桌面 UA 登录 → 自动切 Mobile UA 建 session)")
    print("=" * 60)
    print(f"  输出文件: {STATE_FILE}")
    print()

    # ── 准备 Profile 副本 ──
    if not copy_profile():
        sys.exit(1)

    with sync_playwright() as p:
        # ════════════════════════════════════════
        #  阶段 A：桌面端 UA — 登录
        # ════════════════════════════════════════
        print()
        print("━━ 阶段 A：桌面端浏览器（用于登录） ━━")
        print("  正在启动浏览器（桌面端 UA，反爬宽松）...")
        print()

        context = p.chromium.launch_persistent_context(
            user_data_dir=TMP_USER_DATA,
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--profile-directory={CHROME_PROFILE}",
                "--disable-extensions",
            ],
            viewport={"width": 1280, "height": 800},
            user_agent=DESKTOP_UA,
            is_mobile=False,
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get() { return undefined } });"
        )

        print("  ✅ 浏览器已启动")
        print("  → 打开闲鱼登录页...")
        page.goto(
            "https://www.goofish.com/search?q=test",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        final_url = page.url
        is_login_page = ("passport" in final_url) or ("mini_login" in final_url)

        if not is_login_page:
            print(f"  ✅ 已登录！（URL: {final_url}）")
            print("     直接进入阶段 B...")
        else:
            print()
            print("  ⚡ 重要提示 ⚡")
            print("  这次用的是【桌面端 UA】，反爬比移动端宽松很多！")
            print("  请在弹出的浏览器窗口中：")
            print("    1. 输入手机号")
            print("    2. 点击「获取验证码」（这次应该能正常发送！）")
            print("    3. 输入收到的短信验证码")
            print("    4. 点击「登录」")
            print()
            input("  💡 登录成功后，按 Enter 进入阶段 B（自动切换移动端 UA）...")

        # ════════════════════════════════════════
        #  阶段 B：同一 context 内切 Mobile UA
        # ════════════════════════════════════════
        print()
        print("━━ 阶段 B：切换为移动端 UA ━━")
        print("  正在切换 UA + 视口...")

        # 设置移动端参数（cookie 不丢，因为是同一个 context）
        mobile_page = context.new_page()
        mobile_page.set_viewport_size({"width": 390, "height": 844})

        # 通过 init_script 覆盖 UA（context 级别的 user_agent 参数无法动态更改，
        # 所以用 JS 注入方式配合 CDP 来实现）
        mobile_page.add_init_script(f"""
            Object.defineProperty(navigator, 'userAgent', {{ get: () => '{MOBILE_UA}' }});
            Object.defineProperty(navigator, 'platform', {{ get: () => 'Linux armv8l' }});
            Object.defineProperty(navigator, 'vendor', {{ get: () => 'Google Inc.' }});
        """)

        # 用 CDP 设置真正的 User-Agent（这才是服务端看到的）
        cdp = mobile_page.context.new_cdp_session(mobile_page)
        cdp.send("Network.setUserAgentOverride", {
            "userAgent": MOBILE_UA,
            "acceptLanguage": "zh-CN,zh;q=0.9,en;q=0.8",
            "platform": "Linux armv8l",
        })

        print("  → 用移动端 UA 导航到闲鱼搜索页...")
        mobile_page.goto(
            "https://www.goofish.com/search?q=Mac%20mini%20M2",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        mobile_final_url = mobile_page.url
        is_still_login = ("passport" in mobile_final_url) or ("mini_login" in mobile_final_url)

        print(f"  → 最终 URL: {mobile_final_url}")

        if is_still_login:
            print()
            print("  ❌ 切换到移动端 UA 后仍被重定向到登录页。")
            print("     这说明闲鱼的登录态确实绑定了设备信息。")
            print()
            print("     备选方案：请在弹出的窗口中（桌面端 UA）手动登录，")
            print("     然后我们尝试直接用桌面端 cookie 运行 spider。")
            input("  按 Enter 保存当前状态（桌面端 cookie）...")
        else:
            print("  ✅ 移动端 UA 下未跳转登录页！session 建立成功！")
            try:
                mobile_page.wait_for_selector("text=新发布", timeout=15000)
                print("  ✅ 页面出现 '新发布' → 搜索结果正常加载")
            except Exception:
                print("  ℹ️  未检测到 '新发布'，但仍继续保存")

        print()
        input("  💡 按 Enter 保存登录态...")

        # ════════════════════════════════════════
        #  保存
        # ════════════════════════════════════════
        state = context.storage_state()
        all_cookies = state.get("cookies", [])
        relevant_cookies = [
            c for c in all_cookies
            if any(d in c.get("domain", "") for d in [
                "goofish.com", "taobao.com", "aliapp.org",
                "mmstat.com", "alibaba.com",
            ])
        ]
        if len(relevant_cookies) < 5:
            relevant_cookies = all_cookies

        output_state = {
            "cookies": relevant_cookies,
            "origins": state.get("origins", []),
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(output_state, f, ensure_ascii=False, indent=2)

        cookie_count = len(relevant_cookies)
        file_size = os.path.getsize(STATE_FILE)
        print()
        print(f"  ✅ 登录态已保存!")
        print(f"     文件: {STATE_FILE}")
        print(f"     大小: {file_size:,} bytes")
        print(f"     Cookies: {cookie_count} 个")
        key_names = [c["name"] for c in relevant_cookies if c["name"] in
                     ["cookie2", "_m_h5_tk", "_tb_token_", "XSRF-TOKEN", "t", "unb"]]
        if key_names:
            print(f"     关键标识: {key_names}")

        context.close()

    shutil.rmtree(TMP_USER_DATA, ignore_errors=True)

    print()
    print("-" * 60)
    print("  下一步: 告诉我「登录好了」，我会自动部署到容器并验证")


if __name__ == "__main__":
    main()
