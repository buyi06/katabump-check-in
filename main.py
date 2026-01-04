import os
import time
import requests
import zipfile
import io
import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 1. 基础工具 ====================
def log(message):
    """实时日志，带强制刷新"""
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

def download_silk():
    """下载过盾插件"""
    extract_dir = "silk_ext"
    if os.path.exists(extract_dir): return os.path.abspath(extract_dir)
    log(">>> [系统] 下载插件...")
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

# ==================== 2. 核心过盾逻辑 ====================

def pass_full_page_shield(page):
    """处理全屏 Cloudflare (门神)"""
    log("--- [门神] 检查全屏验证...")
    for _ in range(5):
        title = page.title.lower()
        if "just a moment" in title or "attention" in title:
            log("--- [门神] 正在通过全屏盾...")
            # 尝试点击可能存在的 iframe
            iframe = page.ele('css:iframe[src*="cloudflare"]', timeout=2)
            if iframe: iframe.ele('tag:body').click(by_js=True)
            time.sleep(5)
        else:
            return True # 通过
    return False

def pass_modal_shield(modal):
    """处理弹窗内的 Cloudflare (内鬼)"""
    log(">>> [弹窗] 检查内部验证码...")
    
    # 在弹窗里找 iframe，必须死等出来，因为有时候它加载慢
    iframe = modal.wait.ele_displayed('css:iframe[src*="cloudflare"]', timeout=5)
    
    if not iframe:
        # 备选方案
        iframe = modal.wait.ele_displayed('css:iframe[title*="Widget"]', timeout=2)

    if iframe:
        log(">>> [弹窗] 👁️ 发现验证码，点击...")
        try:
            iframe.ele('tag:body').click(by_js=True)
            log(">>> [弹窗] 👆 已点击，强制等待 6 秒 (等待变绿)...")
            time.sleep(6) # 这里必须久一点，这是关键
            return True
        except: 
            log("⚠️ 点击验证码失败，可能已经通过")
            pass
    else:
        log(">>> [弹窗] 未发现验证码 (可能无需验证)")
    return False

# ==================== 3. 结果判定 ====================

def check_final_status(page):
    """只认死理，必须看到字才算赢"""
    html = page.html.lower()
    
    # 成功情况 1: 红条提示未到期
    if "can't renew" in html or "too early" in html:
        log("✅ [结果] 检测到红条: 还没到时间 (任务成功)")
        return True
        
    # 成功情况 2: 绿条提示成功
    if "success" in html or "extended" in html:
        log("✅ [结果] 检测到绿条: 续期成功！")
        return True
        
    return False

# ==================== 4. 主程序 ====================

def job():
    ext_path = download_silk()
    co = ChromiumOptions()
    co.set_argument('--headless=new') # 无头模式
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--window-size=1920,1080')
    co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    if ext_path: co.add_extension(ext_path)
    co.auto_port()

    # ⚠️ 关键：不使用极速模式，确保页面元素完整加载
    page = ChromiumPage(co)
    page.set.timeouts(15)

    try:
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        if not all([email, password, target_url]): 
            log("❌ 配置缺失")
            exit(1)

        # ---------------- 步骤 1: 登录 ----------------
        log(">>> [1/3] 前往登录页...")
        page.get('https://dashboard.katabump.com/auth/login')
        pass_full_page_shield(page)

        if page.ele('css:input[name="email"]'):
            log(">>> 输入账号密码...")
            page.ele('css:input[name="email"]').input(email)
            page.ele('css:input[name="password"]').input(password)
            page.ele('css:button[type="submit"]').click()
            # 等待 URL 变动，确保跳走
            page.wait.url_change('login', exclude=True, timeout=15)
        
        # ---------------- 步骤 2: 进页面找按钮 ----------------
        log(">>> [2/3] 进入服务器页面...")
        page.get(target_url)
        pass_full_page_shield(page) # 再次检查全屏盾
        
        log(">>> 正在扫描 Renew 按钮...")
        renew_btn = None
        
        # 轮询 10 秒找按钮
        for _ in range(10):
            renew_btn = page.ele('css:button:contains("Renew")')
            if renew_btn and renew_btn.states.is_displayed:
                break
            time.sleep(1)

        if not renew_btn:
            log("⚠️ 未找到 Renew 按钮，直接检查是否未到期...")
            if check_final_status(page):
                log("🎉 脚本提前结束 (无需操作)")
                return # 结束
            else:
                log("❌ 既没按钮也没提示，页面可能未加载完全，或被拦截。")
                log(f"   当前标题: {page.title}")
                exit(1) # 报错退出

        # ---------------- 步骤 3: 续期操作 (关键流程) ----------------
        log(">>> [3/3] 发现按钮，开始续期流程...")
        
        # 1. 点主按钮
        renew_btn.click(by_js=True)
        
        # 2. 等弹窗
        log(">>> 等待弹窗弹出...")
        modal = page.wait.ele_displayed('css:.modal-content', timeout=10)
        
        if modal:
            # 3. 【关键】先处理弹窗里的盾！
            pass_modal_shield(modal)
            
            # 4. 再找确认按钮
            confirm_btn = modal.ele('css:button.btn-primary')
            if confirm_btn:
                log(">>> [动作] 点击最终确认 (Confirm)...")
                confirm_btn.click(by_js=True)
                
                # 5. 等待结果
                log(">>> 等待结果回显...")
                time.sleep(5)
                if check_final_status(page):
                    log("🎉🎉🎉 完美！流程结束。")
                else:
                    log("❌ 操作完成但未检测到成功文字，请检查截图。")
                    exit(1)
            else:
                log("❌ 弹窗里找不到确认按钮 (可能被盾挡住了)")
                exit(1)
        else:
            log("❌ 弹窗未出现")
            exit(1)

    except Exception as e:
        log(f"❌ 发生异常: {e}")
        exit(1)
    finally:
        page.quit()

if __name__ == "__main__":
    job()
