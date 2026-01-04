import os
import time
import requests
import zipfile
import io
from DrissionPage import ChromiumPage, ChromiumOptions

def download_and_extract_silk_extension():
    """自动下载并解压 Silk 插件"""
    extension_id = "ajhmfdgkijocedmfjonnpjfojldioehi"
    crx_path = "silk.crx"
    extract_dir = "silk_ext"
    
    if os.path.exists(extract_dir) and os.listdir(extract_dir):
        print(f">>> [系统] 插件已就绪: {extract_dir}")
        return os.path.abspath(extract_dir)
        
    print(">>> [系统] 正在下载 Silk 隐私插件...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    download_url = f"https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3D{extension_id}%26uc"
    
    try:
        resp = requests.get(download_url, headers=headers, stream=True)
        if resp.status_code == 200:
            content = resp.content
            zip_start = content.find(b'PK\x03\x04')
            if zip_start == -1: return None
            with zipfile.ZipFile(io.BytesIO(content[zip_start:])) as zf:
                if not os.path.exists(extract_dir): os.makedirs(extract_dir)
                zf.extractall(extract_dir)
            return os.path.abspath(extract_dir)
        return None
    except: return None

def wait_for_cloudflare(page, timeout=20):
    """全页盾检测"""
    print(f"--- [盾] 检查全页 Cloudflare ({timeout}s)... ---")
    start = time.time()
    while time.time() - start < timeout:
        if "just a moment" not in page.title.lower():
            if not page.ele('@src^https://challenges.cloudflare.com'):
                return True
        try:
            iframe = page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe: iframe.ele('tag:body').click(by_js=True)
        except: pass
        time.sleep(1)
    return False

def solve_modal_captcha(modal):
    """
    【核心优化】死磕弹窗里的验证码
    """
    print(">>> [验证] 正在扫描弹窗内的 Captcha (最多等 15 秒)...")
    
    iframe = None
    # 循环等待 iframe 出现，防止加载慢找不到
    for i in range(15):
        iframe = modal.ele('tag:iframe')
        # 或者更精确的特征
        if not iframe:
            iframe = modal.ele('@src^https://challenges.cloudflare.com')
        
        if iframe:
            print(f">>> [验证] 第 {i+1} 秒发现了验证码 iframe！")
            break
        time.sleep(1)
    
    if iframe:
        print(">>> [验证] 尝试点击验证码...")
        try:
            time.sleep(1) # 再稳一下
            iframe.ele('tag:body').click(by_js=True)
            
            # 点击后必须死等，让它转圈变绿
            print(">>> [验证] 已点击，正在等待验证通过 (8秒)...")
            time.sleep(8) 
            return True
        except Exception as e:
            print(f"⚠️ 验证码点击异常: {e}")
    else:
        print(">>> [验证] 超时未发现 iframe (可能已被插件自动解决，或真的没有)。")
    return False

def robust_click(ele):
    """多重保障点击"""
    try:
        ele.scroll.to_see()
        time.sleep(0.5)
        print(f">>> [动作] 点击按钮: {ele.text}")
        ele.click(by_js=True)
        return True
    except:
        try:
            ele.wait.displayed(timeout=3)
            ele.click()
            return True
        except Exception as e2:
            print(f"❌ 点击失败: {e2}")
            return False

def check_result_with_retry(page):
    """检测结果，返回 True(成功/未到期) 或 False(失败/被拦截)"""
    print(">>> [检测] 正在分析页面回显...")
    start_time = time.time()
    
    while time.time() - start_time < 12: # 多看一会
        alerts = page.eles('css:div[class*="alert"]')
        messages = []
        for alert in alerts:
            if alert.states.is_displayed:
                messages.append(f"[提示框]: {alert.text}")

        # 只要发现信息就打印
        if messages:
            print("\n" + "="*50)
            print("📢 【页面真实回显】:")
            for msg in messages:
                print(f"   {msg}")
            print("="*50 + "\n")
            
            full_msg = str(messages).lower()
            
            # 1. 失败情况：验证码被拦截
            if "captcha" in full_msg or "验证码" in full_msg:
                print("❌ 结果: 验证码未通过，被拦截！准备重试...")
                return False 
            
            # 2. 成功情况：时间没到
            if "can't renew" in full_msg or "too early" in full_msg:
                print("✅ 结果: 还没到时间 (脚本操作正确)")
                return True
            
            # 3. 成功情况：续期成功
            if "success" in full_msg or "extended" in full_msg:
                print("✅ 结果: 续期成功")
                return True
                
        time.sleep(1)
    
    print("⚠️ 未捕捉到明确结果，认为本次尝试可能失败。")
    return False

def job():
    ext_path = download_and_extract_silk_extension()
    co = ChromiumOptions()
    co.set_argument('--headless=new')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    if ext_path: co.add_extension(ext_path)
    co.auto_port()
    
    page = ChromiumPage(co)
    try: page.set.timeouts(20) # 全局超时放宽
    except: pass

    try:
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        if not all([email, password, target_url]): raise Exception("缺少 Secrets 配置")

        # ==================== 1. 登录 (只做一次) ====================
        print(">>> [Step 1] 前往登录页...")
        page.get('https://dashboard.katabump.com/auth/login', retry=3)
        wait_for_cloudflare(page)
        
        if "auth/login" in page.url:
            print(">>> 输入账号密码...")
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            time.sleep(1)
            page.ele('css:button[type="submit"]').click()
            print(">>> 等待跳转 (10s)...")
            time.sleep(10) # 宽裕时间
            wait_for_cloudflare(page)
        
        if "login" in page.url: raise Exception("登录失败")
        print(">>> ✅ 登录成功！")

        # ==================== 2. 核心任务循环 (重试 5 次) ====================
        max_retries = 5
        success = False
        
        for attempt in range(1, max_retries + 1):
            print(f"\n🚀 [Step 2] 开始第 {attempt}/{max_retries} 次续期尝试...")
            try:
                # 刷新页面，重新开始流程
                print(f">>> 正在进入服务器页面: {target_url}")
                page.get(target_url, retry=3)
                page.wait.load_start()
                
                # 页面加载缓冲
                print(">>> 页面加载中 (等待 8s)...")
                wait_for_cloudflare(page)
                time.sleep(8) 

                # 寻找主 Renew 按钮
                print(">>> 寻找主界面 Renew 按钮...")
                renew_btn = page.ele('css:button:contains("Renew")') or \
                            page.ele('xpath://button[contains(text(), "Renew")]') or \
                            page.ele('text:Renew')
                
                if not renew_btn:
                    print("⚠️ 未找到主 Renew 按钮 (可能已续期)，检查页面提示...")
                    if check_result_with_retry(page):
                        success = True
                        break
                    continue # 没找到按钮也没成功提示，重试

                # 点击主按钮
                robust_click(renew_btn)
                print(">>> 已点击主按钮，等待弹窗加载 (8s)...")
                time.sleep(8) # 等弹窗完全出来
                
                # 处理弹窗
                modal = page.ele('css:.modal-content')
                if modal:
                    print(">>> 检测到弹窗，处理验证码...")
                    
                    # 【关键】寻找并点击验证码
                    solve_modal_captcha(modal)
                    
                    # 寻找确认按钮
                    confirm_btn = modal.ele('css:button.btn-primary') or \
                                  modal.ele('css:button[type="submit"]') or \
                                  modal.ele('xpath:.//button[contains(text(), "Renew")]')
                    
                    if confirm_btn and confirm_btn.states.is_enabled:
                        print(">>> 准备点击最终确认按钮...")
                        robust_click(confirm_btn)
                        print(">>> 指令已发送，等待反馈 (5s)...")
                        time.sleep(5)
                        
                        # 检查结果
                        if check_result_with_retry(page):
                            success = True
                            break # 成功了！跳出循环
                        else:
                            print(f"⚠️ 第 {attempt} 次尝试未成功，稍后重试...")
                    else:
                        print("⚠️ 确认按钮不可用，检查页面反馈...")
                        if check_result_with_retry(page):
                            success = True
                            break
                else:
                    print("❌ 未检测到弹窗，刷新页面重试...")
            
            except Exception as e:
                print(f"❌ 本次尝试发生异常: {e}")
            
            # 如果没成功，等待一段时间再重试
            if not success and attempt < max_retries:
                print("⏳ 等待 10 秒后进行下一次尝试...")
                time.sleep(10)

        # ==================== 3. 最终总结 ====================
        if success:
            print("\n🎉🎉🎉 最终结果: 任务成功完成！")
        else:
            print("\n😭😭😭 最终结果: 5 次尝试全部失败。")
            exit(1)

    except Exception as e:
        print(f"❌ 脚本崩溃: {e}")
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
