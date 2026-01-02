# Katabump Server Auto Renew | Katabump 自动续期脚本

这是一个运行在 GitHub Actions 上的自动化脚本，用于自动续期 Katabump 面板上的服务器。

它基于 **DrissionPage** 开发，能够有效绕过 **Cloudflare 5秒盾** 和 **Turnstile 人机验证**。采用“**Cookie 优先 + 密码兜底**”的混合登录策略，最大程度确保续期成功率。

## ✨ 功能特性

* **🛡️ 强力过盾**：使用 DrissionPage 模拟真实浏览器行为，自动处理 Cloudflare 等待页和 iframe 验证码。
* **🍪 混合登录**：
    * **优先**使用 Discord Cookie 注入，实现免密、免验证码登录。
    * **兜底**使用账号密码自动登录（当 Cookie 失效时自动触发）。
* **🤖 全自动流程**：登录 -> 进入服务器 -> 点击续期 -> 处理弹窗验证 -> 确认续期。
* **📸 故障截图**：如果运行失败，会自动上传截图到 GitHub Actions Artifacts，方便排查问题。
* **⏰ 定时运行**：默认每 3 天自动执行一次续期任务。

## 📂 文件结构

* `main.py`: 核心自动化脚本。
* `.github/workflows/renew.yml`: GitHub Action 配置文件（定时任务）。
* `requirements.txt`: Python 依赖列表。

## 🚀 部署指南

### 第一步：准备代码
将本项目的所有文件上传至您的 GitHub 仓库。

> **⚠️ 注意**：请务必修改 `main.py` 中的服务器 ID！
> 打开 `main.py`，找到以下代码行：
> ```python
> target_url = "[https://dashboard.katabump.com/servers/edit?id=197288](https://dashboard.katabump.com/servers/edit?id=197288)"
> ```
> 将 `197288` 替换为您自己服务器的 ID（可以在浏览器地址栏看到）。

### 第二步：获取 Discord Cookie
为了跳过复杂的异地登录验证，我们需要提取 Discord 的 Cookie。
1. 在浏览器（Chrome/Edge）中登录 `discord.com`。
2. 按 `F12` 打开开发者工具，切换到 **Network (网络)** 选项卡。
3. 刷新页面，点击任意一个请求（如 `library` 或 `science`）。
4. 在右侧 **Headers (标头)** -> **Request Headers (请求标头)** 中找到 `Cookie`。
5. 复制整个 Cookie 字符串（包含 `__dcfduid`, `cf_clearance` 等）。

### 第三步：配置 GitHub Secrets
进入您的 GitHub 仓库，依次点击：
`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`。

添加以下 3 个变量：

| Secret Name | Value (值) | 说明 |
| :--- | :--- | :--- |
| **DISCORD_COOKIE_STRING** | `__dcfduid=...; cf_clearance=...` | 刚才复制的长串 Cookie |
| **DISCORD_EMAIL** | `example@email.com` | 您的 Discord 登录邮箱 (兜底用) |
| **DISCORD_PASSWORD** | `your_password` | 您的 Discord 登录密码 (兜底用) |

### 第四步：启用与测试
1. 这里的配置是每 3 天自动运行一次。
2. **首次测试**：
    * 点击仓库上方的 **Actions** 标签。
    * 点击左侧的 **Katabump Auto Renew**。
    * 点击右侧的 **Run workflow** 按钮手动触发一次。
3. 等待运行完成，查看日志。如果成功，会显示 `✅✅✅ 续期成功！任务完成。`。

## ❓ 常见问题

**Q: 脚本报错，怎么看截图？**
A: 在 Actions 运行记录页面，拉到最底部，Artifacts 区域会有一个名为 `debug-screenshots` 的压缩包，下载解压即可看到报错时的屏幕截图。

**Q: 为什么日志显示 "Cookie 失效"？**
A: Discord 的 Cookie 有时效性。如果脚本提示失效并转为账号密码登录，说明 Cookie 过期了。您可以重新提取并更新 `DISCORD_COOKIE_STRING`，或者依赖脚本的自动密码登录功能。

## ⚠️ 免责声明
本项目仅供学习交流使用。请勿用于恶意滥用或违反 Katabump 服务条款的用途。开发者不对因使用本脚本导致的账号封禁或数据丢失负责。
