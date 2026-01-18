# Gemini Business Cookie 自动刷新工具 - 需求文档

## 1. 项目背景

在合规场景下，需要自动化登录Gemini Business账号并提取所需的Cookie信息，以便后续API调用或其他自动化操作。本工具旨在实现自动化的账号登录和Cookie提取流程，并支持多账号批量处理。

## 2. 功能需求

### 2.1 浏览器自动化控制

| 需求ID | 需求描述 | 优先级 |
|--------|----------|--------|
| F-001 | 通过脚本程序控制Chromium浏览器 | P0 |
| F-002 | 支持自动打开指定URL并执行登录流程 | P0 |
| F-003 | 支持通过代理服务器访问网络 | P0 |
| F-004 | 浏览器操作需支持Headless模式（Docker环境） | P0 |

### 2.2 邮箱验证处理

| 需求ID | 需求描述 | 优先级 |
|--------|----------|--------|
| F-005 | 通过邮箱服务器API获取登录验证码 | P0 |
| F-006 | 支持自动识别和提取邮件中的验证码 | P0 |
| F-007 | 支持轮询等待验证码邮件 | P0 |

### 2.3 Cookie提取

| 需求ID | 需求描述 | 优先级 |
|--------|----------|--------|
| F-008 | 使用Chrome扩展/油猴脚本提取Cookie | P0 |
| F-009 | 提取 `__Secure-C_SES` Cookie | P0 |
| F-010 | 提取 `__Host-C_OSES` Cookie | P1 |
| F-011 | 提取 `csesidx` 和 `config_id` 信息 | P0 |
| F-012 | 支持httpOnly Cookie的提取 | P0 |

### 2.4 多账号管理

| 需求ID | 需求描述 | 优先级 |
|--------|----------|--------|
| F-013 | 从CSV文件读取账号登录凭据 | P0 |
| F-014 | 多账号Cookie信息保存到JSON文件 | P0 |
| F-015 | 支持增量更新已存在的账号信息 | P1 |
| F-016 | 记录Cookie过期时间 | P1 |

### 2.5 数据推送

| 需求ID | 需求描述 | 优先级 |
|--------|----------|--------|
| F-017 | 支持配置POST目标服务器地址 | P0 |
| F-018 | 将获取的accounts.json发送到目标服务器 | P0 |
| F-019 | 支持配置请求超时和重试策略 | P1 |

### 2.6 容器化部署

| 需求ID | 需求描述 | 优先级 |
|--------|----------|--------|
| F-020 | 支持Docker容器化运行 | P0 |
| F-021 | 支持arm64架构 | P0 |
| F-022 | 支持amd64架构 | P0 |
| F-023 | 通过GitHub Actions构建和推送镜像 | P0 |

## 3. 数据格式规范

### 3.1 输入账号格式 (result.csv)

```csv
ID,Account,Password,Date
1,example@domain.com,Password123,2026-01-16
2,example2@domain.com,Password456,2026-01-16
```

### 3.2 输出Cookie格式 (accounts.json)

```json
[
  {
    "id": "account_1",
    "email": "example@domain.com",
    "secure_c_ses": "CSE.Ad_YOUR_SECURE_C_SES_VALUE_HERE",
    "csesidx": "12345678",
    "config_id": "your-config-id-here",
    "host_c_oses": "COS.Af_YOUR_HOST_C_OSES_VALUE_HERE",
    "expires_at": "2026-01-23 17:00:00",
    "created_at": "2026-01-16 17:00:00"
  }
]
```

## 4. 配置项

| 配置项 | 描述 | 默认值 |
|--------|------|--------|
| `CLASH_EXECUTABLE` | Clash/Mihomo可执行文件路径 | `mihomo` |
| `CLASH_CONFIG` | Clash配置文件路径 | `./local.yaml` |
| `CLASH_PORT` | Clash代理端口 | `17890` |
| `CLASH_API_PORT` | Clash API端口 | `29090` |
| `EMAIL_API_URL` | 邮箱API服务地址 | `https://api.duckmail.sbs` |
| `POST_TARGET_URL` | Cookie数据推送目标地址 | - |
| `INPUT_CSV_PATH` | 输入账号CSV文件路径 | `./result.csv` |
| `OUTPUT_JSON_PATH` | 输出Cookie JSON文件路径 | `./accounts.json` |
| `BROWSER_HEADLESS` | 浏览器是否无头模式 | `true` |
| `REQUEST_TIMEOUT` | 请求超时时间(秒) | `30` |
| `RETRY_COUNT` | 失败重试次数 | `3` |

## 5. 非功能需求

### 5.1 性能需求
- 单账号处理时间不超过2分钟（含验证码等待）
- 支持配置并发账号处理数量

### 5.2 可靠性需求
- 单账号失败不影响其他账号处理
- 提供详细的日志记录

### 5.3 安全性需求
- 敏感配置通过环境变量传入
- 不在日志中输出完整Cookie值

## 6. 技术约束

- 编程语言：Python 3.10+
- 浏览器自动化：Playwright 或 Selenium
- 容器基础镜像：需支持Chromium运行
- Chrome扩展：需预装到浏览器中

## 7. 参考项目

1. [Zooo-1/Gemini-Business](https://github.com/Zooo-1/Gemini-Business) - 自动注册工具，参考其代理管理和邮箱API实现
2. [Mouseww/GeminiBusiness_CookieExtractor](https://github.com/Mouseww/GeminiBusiness_CookieExtractor) - Cookie提取Chrome插件
