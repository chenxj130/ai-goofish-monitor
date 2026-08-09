# ai-goofish-monitor 完整聊天记录存档

> 记录自项目部署以来的全部对话上下文，按时间线还原。
> 最后更新：2026-08-09（v7 登录修复 + 文档同步 GitHub）

---

## 一、项目背景

`ai-goofish-monitor`（fork 自 `Usagi-org/ai-goofish-monitor`）是一套闲鱼商品监控工具：
- 定时爬取闲鱼搜索结果（Playwright 无头浏览器）
- AI 分析商品是否符合筛选条件（大功率商用炒菜机 / Mac mini 等）
- 通过 ntfy 推送符合条件的新商品
- 提供 Web UI + FastAPI 后端 + Docker 部署

本地运行环境：Mac（Docker Desktop），代码在 `~/Documents/GitHub/ai-goofish-monitor`。

---

## 二、阶段时间线

### 阶段一~二：初始部署与端到端打通
- 部署 Docker 容器，打通 Playwright 爬取 → AI 分析 → ntfy 推送链路。
- 关键认知：容器内访问宿主机代理必须用 `host.docker.internal:3067`（不能用 `127.0.0.1`）。

### 阶段三：Git / PR 工作流
- 建立 `fork`（chenxj130）与 `origin`（Usagi-org）双 remote 工作流。
- 提交信息规范、PR 描述模板。

### 阶段四~五：全量教程与 0 结果故障
- 首次产出保姆级教程与聊天存档（旧版，仅覆盖部署阶段）。
- **0 结果根因**：关键词把功率字面量塞进搜索词（如 `商用智能炒菜机 8 kw/15kw 炒菜机`）→ 闲鱼 API `resultList` 空。
- **修复**：宽口径搜索（`智能炒菜机 炒菜机` / `Mac mini M2`）+ AI 按 `prompts/*_criteria.txt` 过滤功率。
- **改关键词坑**：`TaskUpdate` 模型无 `keyword` 字段，PATCH 改不了；需直改 DB `UPDATE tasks SET keyword=...` + PATCH 任意字段触发调度器重载。

### 阶段六：AI 模型连环故障
- `.env` 被误改 `MiMo` → `lkeap` → `DeepSeek-V4-Flash`，逐个排查。
- **DeepSeek 无视觉 400**：多模态分析需要支持图片输入的模型，最终锁定 `agnes-2.5-flash`。
- **AIClient 缓存坑**：`AIClient.__init__` 调用 `refresh()` 只加载一次配置；改 `.env` 后**必须重建容器**，已运行 spider 不感知。
- **.env 不重载**：`docker restart` 不重载 `.env`，需 `docker compose up -d --force-recreate`。

### 阶段七：公网部署（Cloudflare）
- 规划用 Cloudflare Tunnel 暴露 `localhost:8000`，待注册域名。

### 阶段八：本地恢复 + XianyuHunter PRO
- 本地环境恢复、引入 XianyuHunter PRO 相关调整。

### 阶段九：FailureGuard 熔断
- 连续失败触发 `logs/task-failure-guard.json` 熔断（阈值 3 次），手动删文件重置。

### 阶段十：Xvfb 中途死亡 + DeepSeek 无视觉
- **"启动任务失败"反复**：Xvfb 一次性启动后崩溃，无人重启 → Playwright `TargetClosedError`。
- **根治**：`start_xvfb_guard.sh` 保活脚本（每 10s 检测 socket，崩了自动重启）+ `docker-compose.yaml` 改 `command` 引用脚本。
- 同时修复 `.env` 被改 DeepSeek（无视觉）→ 改回 agnes-2.5-flash + 重建容器 + 清熔断，验证 11 商品 + ntfy 成功。

---

## 三、2026-08-09 本次会话（登录态修复 + 文档同步）

### 3.1 复现"启动任务失败"（09:56 用户截图）
- 根因叠加：Xvfb 中途死亡 + `.env` 误改 DeepSeek-V4-Flash（无视觉）+ FailureGuard 熔断。
- 修复：agnes-2.5-flash + 重建容器 + 清熔断，验证 11 商品 + ntfy 成功。

### 3.2 全量教程 + 聊天存档（首版产出）
- 产出 `闲鱼监控保姆级实操教程_全量修正版.md` 与 `ai-goofish-monitor_完整聊天记录存档.md`（WorkBuddy 会话目录，旧版）。

### 3.3 Xvfb 保活根治（第二版修复）
- 用户再报"启动任务失败" → 根因：Xvfb 一次性启动崩了无人重启。
- 创建 `start_xvfb_guard.sh` 保活脚本 + 改 `docker-compose.yaml` 引用（YAML 多行 command 解析乱码 → 改独立脚本）。
- 暴露新问题：**登录态过期**（7/15 旧 cookie）。

### 3.4 Mac mini 0 结果（登录态过期 + 关键词过窄）
- 根因：登录态过期（7/15）+ 关键词 `Mac mini M2芯片 16G/32G+256` 过窄。
- 改关键词为 `Mac mini M2`（宽口径）。

### 3.5 登录态重获 —— 漫长历程（capture_login.py v1~v7）

**v1（桌面 UA + input）**：用桌面 UA 启动 Playwright + 自动填表 → 捕获的 cookie 在 spider 移动 UA 下无效（被风控拒）。

**v2（自动检测）**：改进检测，仍未解决 UA 不一致。

**v3（移动 UA + Enter 校验）**：改用移动 UA（与 spider 一致）→ **滑动验证码报错 `error:dnPfb9`**，点"获取验证码"无反应。

**v3→v4（短信码）**：尝试短信验证码 → 报错 `error:WVFAp9`，仍卡反爬。

**方案 A（密码登录）**：失败。

**方案 B（Chrome 导出 Cookie）**：发现 Chrome **Default profile 无 goofish cookie**，实际在 **Profile 5**。
- 尝试 `export_chrome_cookies.py` 从 Chrome Cookie SQLite 解密 → **Keychain 加密，Python 解密失败**（已弃用）。

**v5（Chrome Profile 直连）**：用 `launch_persistent_context(user_data_dir=Chrome用户数据, channel="chrome", --profile-directory=Profile 5)` 继承解密 cookie。
- 用户运行报错 `TargetClosedError` → 日志 `正在现有的浏览器会话中打开`。
- **根因**：用户正开着 Chrome，Profile 5 真实目录被 SingletonLock 占用，Playwright 拒绝新开实例。

**v6（Profile 副本隔离）**：复制 Profile 5 到 `/tmp/goofish_profile_copy`（排除缓存/锁），启动独立副本浏览器继承 cookie。
- 仍卡**滑动验证码 `error:8KH+e9`** + 获取验证码无反应 → 因为仍用**移动端 UA**，反爬严。

**v7（桌面 UA 登录 → CDP 切移动 UA）【最终成功】**：
- 阶段 A：用**桌面端 UA** 启动副本浏览器（反爬宽松）→ 用户短信登录成功。
- 阶段 B：同一 context 内用 CDP `Network.setUserAgentOverride` 切回**移动端 UA** 再访问闲鱼 → 用已有 cookie 建立 mobile session。
- 保存 `context.storage_state()`（仅 cookie）。
- **关键发现**：闲鱼 cookie **未做严格 UA 绑定**，桌面登录的 cookie 在 spider 移动 UA 下完全有效。

### 3.6 部署验证（10:37~10:48）
1. 用户跑 v7 登录成功 → `state/aicaic-1.json` 10:37 生成（259KB / 26 cookie，含 `cookie2/_m_h5_tk/_tb_token_/XSRF-TOKEN/t/unb`）。
2. `docker-compose` 已 bind mount `./state:/app/state` → 容器内自动同步。
3. 删 `logs/task-failure-guard.json` 清熔断。
4. `docker restart ai-goofish-monitor-app`（注意 compose service 名≠容器名，需用容器名 restart）。
5. 手动跑两任务验证：
   - **Mac mini**：无 `Login required` 重定向 → 解析 30 商品 → 发现新商品 → 采集卖家信息 → **ntfy 通知发送成功** ✅
   - **炒菜机（AI 模式）**：无重定向 → 解析 30 商品 → 正常翻页 AI 分析 ✅

### 3.7 文档同步 GitHub（本次任务）
- 更新 `闲鱼监控保姆级实操教程_全量修正版.md`（含 v7 登录修复 + 故障矩阵 + 速查表）。
- 更新 `ai-goofish-monitor_完整聊天记录存档.md`（本文件）。
- 同步代码：`docker-compose.yaml` / `start_xvfb_guard.sh` / `capture_login.py` + 文档 → push 到 `fork`(chenxj130) master。
- 安全：`.gitignore` 已排除 `state/ .env logs/ data/ config.json prompts/` 等，cookie/密钥不入库。

---

## 四、经验沉淀（可复用）

1. **Xvfb 保活**：无头浏览器项目必须把虚拟显示器做成守护（崩了自动重启），否则子进程必崩。
2. **Docker .env 不重载**：改 `.env` 必须 `--force-recreate` 或重建容器。
3. **AIClient 配置缓存**：改模型/代理配置需重建容器，不能只改文件。
4. **宽口径搜索 + AI 过滤**：不要把筛选条件硬塞进搜索词，否则 0 结果。
5. **改关键词直改 DB + PATCH 重载**：模型无 keyword 字段时的绕过。
6. **闲鱼反爬分 UA**：移动端 UA 反爬极严（验证码必败），桌面端宽松。登录用桌面 UA，运行时用移动 UA，cookie 不绑定 UA。
7. **Chrome Profile 占用**：Playwright 不能直连正在运行的 Chrome Profile（SingletonLock），须复制副本或关掉 Chrome。
8. **cookie 解密**：macOS Chrome cookie 用 Keychain 加密，Python 直接读需解密且易失败；让**真实 Chrome 浏览器**自己加载是最稳的。

---

## 五、待办

- [ ] Cloudflare 公网部署（待注册域名）
- [ ] 登录态约 7~30 天过期，届时重跑 `python3 capture_login.py`（v7）
