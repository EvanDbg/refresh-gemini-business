# Gemini Business 面板集成需求文档

## 项目概述

将 `refresh-gemini-business` 的账号注册和 Cookie 刷新功能集成到 `gemini-business2api-clash` 面板项目中，提供 Web UI 操作界面。

## 需求背景

原有的 `refresh-gemini-business` 工具是命令行工具，用户需要通过命令行来注册新账号和刷新 Cookie。现在需要将这些功能集成到面板项目中，让用户可以通过 Web 界面来操作。

## 功能需求

### 1. 批量注册账号

- 用户可以在管理面板中点击"批量注册"按钮
- 弹出对话框，输入要注册的账号数量（1-10个）
- 点击"开始注册"后，后台开始注册流程
- 显示注册进度和结果

### 2. 刷新 Cookie

- 用户可以选中一个或多个账号
- 点击"刷新Cookie"按钮，刷新选中账号的 Cookie
- 后台异步执行刷新任务

### 3. 定时自动刷新

- 后台定时检查账号过期时间
- 当账号 Cookie 剩余时间小于阈值时，自动刷新
- 可通过环境变量配置刷新间隔和阈值

## 技术方案

### 架构

采用微服务架构：面板调用独立的刷新服务 API

```
面板 (7860端口) ←→ 刷新服务 (8000端口)
                        ↓
              linuxserver/chromium 桌面环境
```

### 接口设计

#### 刷新服务 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 批量注册账号 |
| `/api/refresh` | POST | 刷新指定账号Cookie |
| `/api/status/{task_id}` | GET | 查询任务状态 |
| `/api/health` | GET | 健康检查 |

#### 面板管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin/accounts/register` | POST | 批量注册账号 |
| `/admin/accounts/{id}/refresh` | POST | 刷新指定账号Cookie |
| `/admin/refresh/task/{task_id}` | GET | 获取任务状态 |
| `/admin/refresh/tasks` | GET | 获取任务列表 |

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ADMIN_KEY` | 管理面板登录密钥 | - |
| `CLASH_PROXIES` | Clash 代理配置 (YAML 格式) | - |
| `AUTO_REFRESH_ENABLED` | 自动刷新开关 | true |
| `AUTO_REFRESH_INTERVAL_HOURS` | 刷新间隔(小时) | 6 |
| `AUTO_REFRESH_THRESHOLD_HOURS` | 刷新阈值(小时) | 3 |

## 实现状态

- [x] Phase 1: 刷新服务 API 化
- [x] Phase 2: Dockerfile 合并
- [x] Phase 3: 面板后端集成
- [x] Phase 4: 前端 UI 集成
