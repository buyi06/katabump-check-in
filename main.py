import os
import time
import requests
import zipfile
import io
import datetime
import re
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 基础工具 ====================
def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

def download_silk():
    extract_dir = "silk_ext"
    if os.path.exists(extract_dir): return os.path.abspath(extract_dir)
    try:
        url = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3Dajhmfdgkijocedmfjonnpjfojldioehi%26uc"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, stream=True)
        if resp.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                zf.extractall(extract_dir)
            return os.path.abspath(extract_dir)
    except: pass
    return None

# ==================== 核心逻辑 ====================

def pass_full_page_shield(page):
    """处理全屏 Cloudflare"""
    for _ in range(3):
        if "just a moment" in page.title.lower():
            log("--- [门神] 正在通过全屏盾...")
            iframe = page.ele('css:iframe[src*="cloudflare"]', timeout=2)
            if iframe: 
                iframe.ele('tag:body').click(by_js=True)
                time.sleep(3)
        else:
            return True
    return False

def pass_modal_captcha(modal):
    """处理弹窗内的盾"""
    log(">>> [弹窗] 扫描验证码...")
    iframe = modal.ele('css:iframe[src*="cloudflare"]', timeout=8)
    if not iframe:
        iframe = modal.ele('css:iframe[title*="Widget"]', timeout=2)

    if iframe:
        log(">>> [弹窗] 发现验证码，点击...")
        try:
            iframe.ele('tag:body').click(by_js=True)
            log(">>> [弹窗] 已点击，等待 5 秒...")
            time.sleep(5) 
        except: pass
    else:
        log(">>> [弹窗] 未发现验证码 (可能无需验证)")

def analyze_page_alert(page):
    """
    【精准定位版】专门解析 .alert 提示框
    """
    log(">>> [系统] 正在读取页面提示框 (.alert)...")
    
    # 1. 查找红色警告框 (alert-danger)
    danger_alert = page.ele('css:.alert.alert-danger')
    if danger_alert and danger_alert.states.is_displayed:
        text = danger_alert.text
        log(f"⬇️ 捕获到红色提示: {text}")
        
        if "can't renew" in text.lower():
            # 尝试提取天数
            days = "未知"
            match = re.search(r'\(in (\d+) day', text)
            if match:
                days = match.group(1)
            
            log(f"✅ [结果] 还没到时间 (还需等待 {days} 天)")
            return "SUCCESS_TOO_EARLY"
        else:
            log("⚠️ [结果] 出现其他错误提示")
            return "FAIL"

    # 2. 查找绿色成功框 (alert-success)
    success_alert = page.ele('css:.alert.alert-success')
    if success_alert and success_alert.states.is_displayed:
        text = success_alert.text
        log(f"⬇️ 捕获到绿色提示: {text}")
        log("🎉 [结果] 续期成功！")
        return "SUCCESS"

    return "UNKNOWN"

# ==================== 主程序 ====================
def job():
    ext_path = download_silk()
    
    co = ChromiumOptions()
    co.set_argument('--headless=new')
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    if ext_path: co.add_extension(ext_path)
    co.auto_port()

    page = ChromiumPage(co)
    page.set.timeouts(15)

    try:
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        
        if not all([email, password, target_url]): 
            log("❌ 配置缺失")
            exit(1)

        # Step 1: 登录
        log(">>> [1/3] 登录...")
        page.get('https://dashboard.katabump.com/auth/login')
        pass_full_page_shield(page)

        if page.ele('css:input[name="email"]'):
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            page.ele('css:button#submit').click()
            page.wait.url_change('login', exclude=True, timeout=20)
        
        # Step 2: 进页面
        log(">>> [2/3] 进入服务器页面...")
        page.get(target_url)
        pass_full_page_shield(page)
        
        # Step 3: 操作
        log(">>> [3/3] 寻找按钮...")
        renew_btn = None
        for _ in range(10):
            renew_btn = page.ele('css:button[data-bs-target="#renew-modal"]')
            if renew_btn and renew_btn.states.is_displayed: break
            time.sleep(1)

        if renew_btn:
            log(">>> 点击 Renew 按钮...")
            renew_btn.click(by_js=True)
            
            modal = page.ele('css:.modal-content', timeout=10)
            if modal:
                pass_modal_captcha(modal)
                confirm_btn = modal.ele('css:button[type="submit"].btn-primary')
                
                if confirm_btn:
                    log(">>> 点击 Confirm 确认...")
                    confirm_btn.click(by_js=True)
                    log(">>> 等待服务器响应 (5s)...")
                    time.sleep(5)
                    
                    # 🎯 【精准判定】
                    # 这里会去抓所有的 alert-danger 和 alert-success
                    result = analyze_page_alert(page)
                    
                    if result == "UNKNOWN":
                        log("⚠️ 未捕获到明确提示框，尝试读取原文...")
                        # 兜底：如果 alert 没抓到，打印所有 alert 类的文本
                        alerts = page.eles('css:.alert')
                        for a in alerts:
                            if a.states.is_displayed: print(f"👉 页面提示: {a.text}")
                else:
                    log("❌ 找不到确认按钮")
            else:
                log("❌ 弹窗未出")
        else:
            log("⚠️ 未找到 Renew 按钮，检查是否已有提示...")
            analyze_page_alert(page)

    except Exception as e:
        log(f"❌ 异常: {e}")
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
