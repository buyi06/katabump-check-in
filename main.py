import os
import time
import json
from DrissionPage import ChromiumPage, ChromiumOptions

def handle_cloudflare(page, retries=5):
    """
    增强版 Cloudflare 处理逻辑
    """
    print(f"--- [安全检查] 正在扫描 Cloudflare 盾 ({retries}次尝试)... ---")
    for i in range(retries):
        try:
            # 1. 检查标题和页面内容
            title = page.title.lower()
            html = page.html.lower()
            
            # 如果看起来像正常页面，直接放行
            if "dashboard" in page.url and "just a moment" not in title:
                return True
            
            # 2. 寻找 Cloudflare 的特征 iframe
            iframe = page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe:
                print(f"--- [防御] 发现验证框 (第 {i+1} 次)，尝试突破... ---")
                time.sleep(2) # 等待 iframe 加载完全
                iframe.ele('tag:body').click()
                time.sleep(5) # 点击后多等一会
                page.refresh() # 刷新页面看是否过盾
                time.sleep(3)
            else:
                # 没有 iframe，可能是正在加载或者已经过了
                if "just a moment" not in title and "verify" not in html:
                    return True
                time.sleep(2)
        except Exception as e:
            print(f"--- [警告] 过盾检测轻微异常: {e} ---")
            time.sleep(1)
    return False

def find_element_robust(page, selectors, timeout=15):
    """
    多重保障查找元素
    """
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
    # --- 1. 浏览器初始化 (针对 GitHub Actions 的核心修复) ---
    co = ChromiumOptions()
    
    # 【修复重点 1】使用新版无头模式 (报错提示要求的)
    co.set_argument('--headless=new')
    
    # 【修复重点 2】解决 Linux 容器内存不足导致崩溃的问题 (至关重要)
    co.set_argument('--disable-dev-shm-usage') 
    
    # 常规 Linux 必备参数
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--ignore-certificate-errors')
    
    # 模拟真实用户
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # 尝试自动寻找系统安装的 Chrome (GitHub Actions 环境通常在标准路径)
    co.auto_port() 

    page = ChromiumPage(co)
    # 设置全局超时
    page.set.timeout(20)
    
    try:
        # ==================== 步骤 1: 强力注入 Token ====================
        print(">>> [1/7] 初始化环境与 Token 注入...")
        token = os.environ.get("DISCORD_TOKEN")
        if not token:
            raise Exception("❌ 致命错误：Github Secrets 中未找到 DISCORD_TOKEN")

        # 访问 Discord 之前先清空 Cookie
        page.get('https://discord.com/login', retry=3, timeout=15)
        page.clear_cookies()
        
        handle_cloudflare(page)

        # 注入 Token
        token_value = f'"{token}"'
        js_code = f"window.localStorage.setItem('token', '{token_value}');"
        page.run_js(js_code)
        time.sleep(1)
        
        print(">>> Token 注入完毕，正在验证有效性...")
        page.refresh()
        page.wait.load_start()
        time.sleep(5)
        
        if page.ele('css:input[name="email"]'):
            print("⚠️ 警告：Discord Token 可能已失效。尝试继续...")
        else:
            print(">>> ✅ Discord Token 有效，已跳过密码输入。")

        # ==================== 步骤 2: 智能登录判断 ====================
        print(">>> [2/7] 前往 Katabump 面板...")
        page.get('https://dashboard.katabump.com/', retry=3)
        page.wait.load_start()
        handle_cloudflare(page)
        
        if "auth/login" in page.url:
            print(">>> 检测到未登录状态，开始寻找登录按钮...")
            
            selectors = [
                ('text', 'Login with Discord'),
                ('text', 'Discord'),
                ('css', 'a[href*="discord"]'),
                ('css', '.btn-primary')
            ]
            
            btn = find_element_robust(page, selectors, timeout=15)
            
            if btn:
                print(f">>> ✅ 成功定位登录按钮 (文本: {btn.text})，点击中...")
                btn.click()
            else:
                print(f"DEBUG: 页面源码预览: {page.html[:200]}")
                page.get_screenshot(path='login_btn_missing_debug.jpg')
                raise Exception("❌ 无法找到登录按钮")

            print(">>> 跳转授权页...")
            time.sleep(5)

            # ==================== 步骤 3: Discord 授权 ====================
            if "discord.com" in page.url:
                print(">>> [3/7] 处理授权...")
                handle_cloudflare(page)
                
                auth_selectors = [
                    ('text', 'Authorize'),
                    ('text', '授权'),
                    ('css', 'button div:contains("Authorize")')
                ]
                auth_btn = find_element_robust(page, auth_selectors, timeout=8)
                
                if auth_btn:
                    auth_btn.click()
                    print(">>> 点击了授权按钮")
                else:
                    print(">>> 未发现授权按钮（可能已自动授权），跳过...")

        else:
            print(">>> ✅ 检测到已直接进入 Dashboard，跳过登录步骤！")

        # ==================== 步骤 4: 确认进入后台 ====================
        print(">>> [4/7] 等待面板加载...")
        is_logged_in = False
        for i in range(20):
            if "katabump.com" in page.url and "login" not in page.url:
                is_logged_in = True
                break
            time.sleep(1)
        
        if not is_logged_in:
             page.get_screenshot(path='login_failed_final.jpg')
             raise Exception("❌ 登录流程结束，但 URL 仍停留在登录页")

        # ==================== 步骤 5: 直达服务器 ====================
        target_url = "https://dashboard.katabump.com/servers/edit?id=197288"
        print(f">>> [5/7] 进入服务器管理: {target_url}")
        page.get(target_url, retry=3)
        page.wait.load_start()
        time.sleep(5)
        handle_cloudflare(page)

        # ==================== 步骤 6: 寻找续期入口 ====================
        print(">>> [6/7] 寻找 Renew 按钮...")
        renew_selectors = [
            ('text', 'Renew'),
            ('text', '续期'),
            ('text', 'Extend'),
            ('css', 'button:contains("Renew")')
        ]
        
        main_renew = find_element_robust(page, renew_selectors, timeout=10)
        
        if main_renew:
            main_renew.click()
            print(">>> ✅ 点击主 Renew 按钮，等待弹窗...")
            time.sleep(3)
            
            # ==================== 步骤 7: 弹窗终极验证 ====================
            print(">>> [7/7] 处理弹窗验证...")
            handle_cloudflare(page)
            
            try:
                modal = page.ele('css:.modal-content')
                if modal:
                    confirm_btn = find_element_robust(modal, [('text', 'Renew'), ('css', 'button.btn-primary')], timeout=5)
                    if confirm_btn:
                        confirm_btn.click()
                        print("🎉🎉🎉 续期成功！任务完美结束！")
                    else:
                        print("❌ 弹窗已弹出，但找不到确认按钮")
                else:
                    print("❌ 找不到弹窗元素 (.modal-content)")
            except Exception as e:
                print(f"❌ 弹窗处理异常: {e}")
        else:
            print("⚠️ 未找到 Renew 按钮 (可能已续期或布局变更)。")
            page.get_screenshot(path='no_renew_btn.jpg')

    except Exception as e:
        print(f"❌ 脚本崩溃: {e}")
        try:
            page.get_screenshot(path='crash_report.jpg', full_page=True)
        except:
            pass
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
