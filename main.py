import os
import time
import json
import requests
from DrissionPage import ChromiumPage, ChromiumOptions

def download_silk_extension():
    """
    自动下载 Silk - Privacy Pass Client 插件
    """
    extension_id = "ajhmfdgkijocedmfjonnpjfojldioehi"
    crx_path = "silk.crx"
    
    # 如果文件已存在，跳过下载
    if os.path.exists(crx_path):
        return os.path.abspath(crx_path)
        
    print(">>> [系统] 正在下载 Silk 隐私插件...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    # Google 官方插件下载接口
    download_url = f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3D{extension_id}%26uc"
    
    try:
        resp = requests.get(download_url, headers=headers, stream=True)
        if resp.status_code == 200:
            with open(crx_path, 'wb') as f:
                f.write(resp.content)
            print(">>> [系统] 插件下载成功！")
            return os.path.abspath(crx_path)
        else:
            print(f"⚠️ 插件下载失败，状态码: {resp.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ 插件下载出错: {e}")
        return None

def wait_for_cloudflare_auto_solve(page, timeout=20):
    """
    被动式过盾：完全依赖插件自动解决
    """
    print(f"--- [插件] 等待 Silk 插件自动过盾 (超时 {timeout}s)... ---")
    start = time.time()
    while time.time() - start < timeout:
        title = page.title.lower()
        html = page.html.lower()
        
        # 成功的标志：标题不再是 Just a moment，且页面没有 CF 验证框
        if "just a moment" not in title and "cloudflare" not in title:
            print("--- [插件] 检测到 Cloudflare 已消失！ ---")
            return True
        
        # 如果插件没反应，尝试手动点一下 iframe 激活它
        try:
            iframe = page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe:
                # 稍微点一下 body 唤醒插件
                iframe.ele('tag:body').click(by_js=True)
        except:
            pass
            
        time.sleep(1)
    
    print("--- [警告] 插件自动过盾超时，尝试强制继续... ---")
    return False

def find_element_robust(page, selectors, timeout=15):
    """多重保障查找元素"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        for method, value in selectors:
            try:
                if method == 'text':
                    ele = page.ele(f'text:{value}')
                elif method == 'css':
                    ele = page.ele(f'css:{value}')
                elif method == 'raw':
                    ele = page.ele(value)
                if ele and ele.is_displayed():
                    return ele
            except:
                pass
        time.sleep(1)
    return None

def job():
    # --- 1. 下载插件 ---
    extension_path = download_silk_extension()
    
    # --- 2. 浏览器配置 ---
    co = ChromiumOptions()
    co.set_argument('--headless=new')       
    co.set_argument('--disable-dev-shm-usage') 
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--ignore-certificate-errors')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # 【核心】挂载插件
    if extension_path:
        co.add_extension(extension_path)
    
    co.auto_port() 
    page = ChromiumPage(co)
    
    # 设置超时 (修正版写法)
    try:
        page.set.timeouts(20)
    except:
        pass

    try:
        # ==================== 步骤 1: 注入 Token ====================
        print(">>> [1/7] 初始化环境与 Token 注入...")
        token = os.environ.get("DISCORD_TOKEN")
        if not token:
            raise Exception("❌ 致命错误：Github Secrets 中未找到 DISCORD_TOKEN")

        page.get('https://discord.com/login', retry=3, timeout=15)
        
        try:
            page.set.cookies.clear()
        except:
            page.clear_cookies()
        
        # 等待插件处理 Discord 的盾
        wait_for_cloudflare_auto_solve(page)

        # 注入 Token
        token_value = f'"{token}"'
        js_code = f"window.localStorage.setItem('token', '{token_value}');"
        page.run_js(js_code)
        time.sleep(1)
        
        print(">>> Token 注入完毕，刷新验证...")
        page.refresh()
        page.wait.load_start()
        time.sleep(5)
        
        if page.ele('css:input[name="email"]'):
            page.get_screenshot(path='token_fail.jpg')
            raise Exception("❌ Token 无效，Discord 仍要求登录")
        else:
            print(">>> ✅ Discord Token 有效。")

        # ==================== 步骤 2: 前往面板 ====================
        print(">>> [2/7] 前往 Katabump 面板...")
        page.get('https://dashboard.katabump.com/', retry=3)
        page.wait.load_start()
        
        # 等待插件处理 Katabump 的盾
        wait_for_cloudflare_auto_solve(page)
        
        # 检查是否需要登录
        if "auth/login" in page.url:
            print(">>> 寻找登录按钮...")
            selectors = [
                ('text', 'Login with Discord'),
                ('css', 'a[href*="discord"]'),
                ('css', '.btn-primary')
            ]
            btn = find_element_robust(page, selectors, timeout=15)
            
            if btn:
                print(">>> 点击登录...")
                btn.click()
            else:
                page.get_screenshot(path='no_login_btn.jpg')
                print(f"DEBUG HTML: {page.html[:200]}")
                raise Exception("❌ 未找到登录按钮")

            print(">>> 跳转授权页...")
            time.sleep(5)

            # ==================== 步骤 3: 授权 ====================
            if "discord.com" in page.url:
                print(">>> [3/7] 处理授权...")
                wait_for_cloudflare_auto_solve(page)
                
                auth_btn = find_element_robust(page, [('text', 'Authorize'), ('text', '授权')], timeout=8)
                if auth_btn:
                    auth_btn.click()
                    print(">>> 点击授权")
                else:
                    print(">>> 未发现授权按钮，可能已跳过")

        else:
            print(">>> ✅ 已直接进入 Dashboard")

        # ==================== 步骤 4: 确认进入后台 ====================
        print(">>> [4/7] 等待面板加载...")
        is_logged_in = False
        for i in range(20):
            if "katabump.com" in page.url and "login" not in page.url:
                is_logged_in = True
                break
            time.sleep(1)
        
        if not is_logged_in:
             page.get_screenshot(path='login_fail_final.jpg')
             raise Exception("❌ 登录失败")

        # ==================== 步骤 5: 直达服务器 ====================
        target_url = "https://dashboard.katabump.com/servers/edit?id=197288"
        print(f">>> [5/7] 进入服务器: {target_url}")
        page.get(target_url, retry=3)
        page.wait.load_start()
        time.sleep(5)
        
        wait_for_cloudflare_auto_solve(page)

        # ==================== 步骤 6: 续期 ====================
        print(">>> [6/7] 寻找 Renew 按钮...")
        renew_selectors = [('text', 'Renew'), ('text', '续期'), ('css', 'button:contains("Renew")')]
        main_renew = find_element_robust(page, renew_selectors, timeout=10)
        
        if main_renew:
            main_renew.click()
            print(">>> 点击 Renew...")
            time.sleep(3)
            
            # ==================== 步骤 7: 弹窗 ====================
            print(">>> [7/7] 处理弹窗...")
            # 这里的盾也会被插件自动秒杀，我们只需要等
            wait_for_cloudflare_auto_solve(page)
            
            modal = page.ele('css:.modal-content')
            if modal:
                confirm_btn = find_element_robust(modal, [('text', 'Renew'), ('css', 'button.btn-primary')], timeout=5)
                if confirm_btn:
                    confirm_btn.click()
                    print("🎉🎉🎉 续期成功！")
                else:
                    print("❌ 弹窗里无按钮")
            else:
                print("❌ 无弹窗")
        else:
            print("⚠️ 未找到 Renew 按钮")
            page.get_screenshot(path='no_renew.jpg')

    except Exception as e:
        print(f"❌ 错误: {e}")
        try:
            page.get_screenshot(path='crash.jpg', full_page=True)
        except:
            pass
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
