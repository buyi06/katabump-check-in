import os
import time
from DrissionPage import ChromiumPage, ChromiumOptions

def parse_cookie_string(cookie_str):
    """解析 Cookie 字符串"""
    cookies = []
    if not cookie_str:
        return cookies
    try:
        for item in cookie_str.split(';'):
            if '=' in item:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': '.discord.com',
                    'path': '/'
                })
    except Exception as e:
        print(f"Cookie 解析警告: {e}")
    return cookies

def handle_cloudflare(page):
    """专门处理 Cloudflare 5秒盾"""
    print("--- [检测] 正在检查 Cloudflare 拦截 ---")
    
    # 最多尝试 20 秒
    for _ in range(10):
        title = page.title.lower()
        if "just a moment" not in title and "cloudflare" not in title:
            print("--- Cloudflare 已消失或未触发 ---")
            return True
        
        print("--- 发现 Cloudflare 盾，尝试寻找验证码 iframe... ---")
        try:
            iframe = page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe:
                print("--- 点击 Cloudflare 验证框... ---")
                iframe.ele('tag:body').click()
                time.sleep(3)
            else:
                print("--- 等待自动跳转... ---")
                time.sleep(2)
        except:
            time.sleep(2)
            
    return False

def job():
    # --- 1. 浏览器初始化 ---
    co = ChromiumOptions()
    co.headless(True)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--lang=zh-CN')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    page = ChromiumPage(co)
    
    try:
        # ==================== 阶段一：注入凭证与登录 ====================
        print(">>> [1/7] 正在尝试注入 Discord Cookie...")
        raw_cookie = os.environ.get("DISCORD_COOKIE_STRING")
        if raw_cookie:
            try:
                page.get('https://discord.com', retry=1, timeout=10)
                page.set.cookies(parse_cookie_string(raw_cookie))
                time.sleep(1)
                print(">>> Cookie 注入完成。")
            except Exception as e:
                print(f"注入 Cookie 时访问 Discord 失败 (网络问题?): {e}")

        print(">>> [2/7] 前往 Katabump 点击登录...")
        # 增加重试机制
        page.get('https://dashboard.katabump.com/auth/login', retry=2, timeout=15)
        
        # 【关键修改】调用过盾逻辑
        handle_cloudflare(page)
        
        # 截图当前状态，万一失败了方便看是不是盾还没过
        # page.get_screenshot(path='before_click_login.jpg')

        print(">>> 正在寻找 Discord 登录按钮...")
        # 【关键修改】使用更宽泛的查找策略
        # 1. 找文本包含 Discord 的
        # 2. 找链接包含 discord 的 (这是最稳的，因为图标按钮通常是一个链接)
        discord_btn = page.ele('text:Login with Discord') or \
                      page.ele('css:a[href*="discord"]') or \
                      page.ele('text:Discord')

        if discord_btn:
            print(">>> 找到按钮，点击...")
            discord_btn.click()
        else:
            # 打印一下当前页面标题和 URL，方便调试
            print(f"当前页面标题: {page.title}")
            print(f"当前页面URL: {page.url}")
            # 保存页面源码的一部分看看到底加载了啥
            print(f"页面源码前200字符: {page.html[:200]}")
            raise Exception("未找到 Discord 登录按钮，可能是 Cloudflare 没过或者页面白屏")
            
        print(">>> 正在跳转至 Discord 授权页...")
        time.sleep(5)
        
        # ==================== 阶段二：Discord 登录/授权处理 ====================
        if "discord.com" in page.url:
            print(">>> [3/7] 已到达 Discord，判断登录状态...")
            
            # 优先处理 Cloudflare (Discord 也有盾)
            handle_cloudflare(page)

            # 【情况 A：Cookie 失效，需要输入密码】
            if page.ele('css:input[name="email"]'):
                print(">>> Cookie 失效，执行账号密码补救登录...")
                email = os.environ.get("DISCORD_EMAIL")
                password = os.environ.get("DISCORD_PASSWORD")
                
                if not email:
                    raise Exception("需要登录但未配置 DISCORD_EMAIL")

                page.ele('css:input[name="email"]').input(email)
                page.ele('css:input[name="password"]').input(password)
                
                print(">>> 点击登录...")
                page.ele('css:button[type="submit"]').click()
                time.sleep(5)
            
            # 【情况 B：点击授权】
            print(">>> [4/7] 寻找授权按钮...")
            time.sleep(3)
            # 很多时候 Discord 登录后会再次弹 Cloudflare
            handle_cloudflare(page)
            
            auth_btn = page.ele('text:Authorize') or page.ele('text:授权') or page.ele('css:button div:contains("Authorize")')
            
            if auth_btn:
                print(">>> 点击授权...")
                auth_btn.click()
            else:
                print(">>> 未找到授权按钮（可能已自动跳转），继续等待...")

        # ==================== 阶段三：验证登录结果 ====================
        print(">>> [5/7] 等待跳转回 Katabump 面板...")
        for i in range(30):
            if "katabump.com" in page.url and "login" not in page.url:
                print(">>> 登录成功！已进入面板。")
                break
            time.sleep(1)
            
        if "login" in page.url:
             page.get_screenshot(path='login_failed.jpg')
             raise Exception("登录失败：流程结束后仍然停留在登录页")

        # ==================== 阶段四：执行服务器续期 ====================
        target_url = "https://dashboard.katabump.com/servers/edit?id=197288"
        print(f">>> [6/7] 进入目标服务器: {target_url}")
        page.get(target_url)
        time.sleep(5)
        
        # 进入页面后可能还有一次盾
        handle_cloudflare(page)

        # 1. 点击主界面的 Renew 按钮
        main_renew = None
        # 使用更灵活的查找
        renew_texts = ['Renew', '续期', 'Extend']
        for text in renew_texts:
            btn = page.ele(f'text:{text}')
            if btn:
                # 确保它是按钮或在主界面
                if btn.tag == 'button' or 'btn' in btn.attr('class', ''): 
                    main_renew = btn
                    break
        
        if main_renew:
            main_renew.click()
            print(">>> 已点击主 Renew 按钮，等待弹窗...")
            time.sleep(3)
            
            # 2. 处理弹窗内的 Cloudflare 验证
            print(">>> [7/7] 处理弹窗验证与确认...")
            handle_cloudflare(page) # 复用过盾逻辑
            
            # 3. 点击弹窗内的最终确认按钮
            modal = page.ele('css:.modal-content')
            if modal:
                final_btn = modal.ele('text:Renew') or modal.ele('css:button.btn-primary')
                if final_btn:
                    final_btn.click()
                    print("✅✅✅ 续期成功！任务完成。")
                else:
                    print("❌ 错误：在弹窗里没找到 Renew 确认按钮")
            else:
                print("❌ 错误：弹窗未正常显示")
        else:
            # 打印页面内容帮助调试
            print("页面预览:", page.ele('tag:body').text[:100])
            print("❌ 错误：主界面未找到 Renew 按钮")

    except Exception as e:
        print(f"❌ 运行出错: {e}")
        page.get_screenshot(path='error_screenshot.jpg', full_page=True)
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
