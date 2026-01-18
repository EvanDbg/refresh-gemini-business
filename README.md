# Gemini Business Cookie Refresh Tool

自动化登录 Gemini Business 账号并提取所需 Cookie 的工具。

## 功能特性

- 🔐 **自动登录**: 使用 Playwright 控制 Chromium 浏览器自动登录
- 📧 **邮箱验证**: 通过 DuckMail API 自动获取验证码
- 🌐 **代理管理**: 集成 Clash/Mihomo，自动选择健康节点
- 🍪 **Cookie 提取**: 使用 Chrome 扩展提取 httpOnly Cookie
- 📤 **数据推送**: 支持将结果 POST 到目标服务器
- 🐳 **容器化**: 支持 Docker 部署，多架构支持 (amd64/arm64)

## GitHub Actions 使用指南

其他用户可以 Fork 本仓库，通过 GitHub Actions 直接运行工具。

### 1. Fork 仓库

点击右上角 **Fork** 按钮复制本仓库到你的账户。

### 2. 配置 Secrets

在仓库 **Settings → Secrets and variables → Actions** 中添加：

| Secret 名称 | 描述 | 必需 |
|------------|------|------|
| `CLASH_CONFIG` | Clash/Mihomo YAML 配置（包含代理节点） | ✅ |
| `ACCOUNTS_CSV` | result.csv 内容（刷新模式需要） | 刷新模式需要 |
| `POST_TARGET_URL` | Cookie 推送目标地址 | ❌ 可选 |

**CLASH_CONFIG 示例：**
```yaml
proxies:
  - name: '🇺🇸 US Node'
    type: ss
    server: your.server.com
    port: 443
    cipher: 2022-blake3-aes-256-gcm
    password: your-password
  - name: '🇺🇸 US Node'
    type: ss
    server: your.server.com
    port: 443
    cipher: 2022-blake3-aes-256-gcm
    password: your-password
```

**ACCOUNTS_CSV 示例：**
```csv
ID,Account,Password,Date
1,example@domain.com,Password123,2026-01-16
```

### 3. 触发运行

**手动触发：**
1. 进入 **Actions** 页面
2. 选择 **Run Gemini Business Tool** 工作流
3. 点击 **Run workflow**
4. 选择模式 (refresh/register) 和账号数量

**自动触发：**
- 每 6 小时自动运行刷新模式

### 4. 获取结果

运行完成后，在 **Actions → 对应运行记录 → Artifacts** 下载 `gemini-results-xxx`，包含：
- `accounts.json` - 提取的 Cookie 数据
- `result.csv` - 账号列表（注册模式会更新）


## 快速开始

### 环境要求

- Python 3.10+
- Chromium 浏览器
- Mihomo (Clash Meta) v1.19+

### 本地运行

1. **克隆仓库**
   ```bash
   git clone https://github.com/YOUR_USERNAME/refresh-gemini-business.git
   cd refresh-gemini-business
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **配置 Clash**
   - 准备 `local.yaml` 配置文件（包含代理节点）
   - 下载 [Mihomo](https://github.com/MetaCubeX/mihomo/releases) 并放到 PATH 中

4. **准备账号**
   - 编辑 `result.csv` 添加账号信息

5. **运行**
   ```bash
   python -m src.main
   ```

### Docker 运行

1. **构建镜像**
   ```bash
   docker build -t gemini-refresh .
   ```

2. **运行容器**
   ```bash
   docker run -v ./local.yaml:/data/local.yaml:ro \
              -v ./result.csv:/data/result.csv:ro \
              -v ./data:/data \
              gemini-refresh --headless
   ```

或使用 Docker Compose:
```bash
docker compose up
```

## 配置说明

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `CLASH_EXECUTABLE` | Mihomo 可执行文件路径 | `mihomo` |
| `CLASH_CONFIG` | Clash 配置文件路径 | `./local.yaml` |
| `CLASH_PORT` | Clash 代理端口 | `17890` |
| `CLASH_API_PORT` | Clash API 端口 | `29090` |
| `EMAIL_API_URL` | DuckMail API 地址 | `https://api.duckmail.sbs` |
| `POST_TARGET_URL` | Cookie 推送目标地址 | - |
| `INPUT_CSV_PATH` | 输入 CSV 路径 | `./result.csv` |
| `OUTPUT_JSON_PATH` | 输出 JSON 路径 | `./accounts.json` |
| `BROWSER_HEADLESS` | 无头模式 | `true` |

### 输入文件格式

**result.csv**
```csv
ID,Account,Password,Date
1,example@domain.com,Password123,2026-01-16
```

### 输出文件格式

**accounts.json**
```json
[
  {
    "id": "account_1",
    "email": "example@domain.com",
    "secure_c_ses": "CSE.Ad_...",
    "csesidx": "12345678",
    "config_id": "your-config-id",
    "host_c_oses": "COS.Af_...",
    "expires_at": "2026-01-23 17:00:00",
    "created_at": "2026-01-16 17:00:00"
  }
]
```

## 项目结构

```
refresh-gemini-business/
├── .github/workflows/       # GitHub Actions
├── extensions/              # Chrome 扩展
│   └── cookie_extractor/
├── src/                     # Python 源码
│   ├── main.py              # 主入口
│   ├── browser_controller.py
│   ├── clash_manager.py
│   ├── mail_client.py
│   ├── data_pusher.py
│   ├── config.py
│   └── utils.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── local.yaml               # Clash 配置
```



### Docker 镜像

推送到 `main` 分支或创建 tag 时会自动构建并推送 Docker 镜像：

```bash
docker pull ghcr.io/YOUR_USERNAME/refresh-gemini-business:latest
```


## 参考项目

- [Zooo-1/Gemini-Business](https://github.com/Zooo-1/Gemini-Business) - 自动注册工具
- [Mouseww/GeminiBusiness_CookieExtractor](https://github.com/Mouseww/GeminiBusiness_CookieExtractor) - Cookie 提取插件

## 免责声明

本工具仅供学习和合规用途使用。请遵守相关服务条款和法律法规。

## License

MIT
