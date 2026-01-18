"""
Gemini Business Refresh Service API

Provides HTTP API for account registration and cookie refresh.
Designed to be called by the panel service.
"""

import asyncio
import uuid
import os
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import config
from .utils import logger, update_accounts_json, append_to_csv
from .clash_manager import ClashManager
from .mail_client import MailClient
from .browser_controller import BrowserController


# ============ Models ============

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    progress: Optional[Dict] = None


class RegisterRequest(BaseModel):
    count: int = 1


class RefreshRequest(BaseModel):
    email: str
    password: str


# ============ App ============

app = FastAPI(
    title="Gemini Business Refresh Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Task storage (in-memory)
tasks: Dict[str, TaskInfo] = {}

# Clash manager (singleton)
clash_manager: Optional[ClashManager] = None


# ============ Startup ============

@app.on_event("startup")
async def startup():
    global clash_manager
    
    # Initialize Clash manager
    clash_config_path = os.environ.get("CLASH_CONFIG", "local.yaml")
    clash_executable = os.environ.get("CLASH_EXECUTABLE", "mihomo")
    
    # Support CLASH_PROXIES environment variable
    clash_proxies = os.environ.get("CLASH_PROXIES")
    if clash_proxies:
        # Write proxies to config file
        with open(clash_config_path, "w") as f:
            f.write(clash_proxies)
        logger.info(f"[API] Written CLASH_PROXIES to {clash_config_path}")
    
    clash_manager = ClashManager(executable=clash_executable, config=clash_config_path)
    if not clash_manager.start():
        logger.error("[API] Failed to start Clash manager")
    else:
        logger.info("[API] Clash manager started")


@app.on_event("shutdown")
async def shutdown():
    global clash_manager
    if clash_manager:
        clash_manager.stop()
        logger.info("[API] Clash manager stopped")


# ============ Endpoints ============

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "clash_running": clash_manager is not None and clash_manager.process is not None
    }


@app.post("/api/register")
async def register_accounts(req: RegisterRequest, background_tasks: BackgroundTasks):
    """
    Register new Gemini Business accounts.
    Returns a task_id for status tracking.
    """
    task_id = str(uuid.uuid4())[:8]
    
    task = TaskInfo(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        progress={"total": req.count, "completed": 0, "success": 0, "failed": 0}
    )
    tasks[task_id] = task
    
    # Run registration in background
    background_tasks.add_task(run_register_task, task_id, req.count)
    
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/refresh")
async def refresh_account(req: RefreshRequest, background_tasks: BackgroundTasks):
    """
    Refresh cookies for an existing account.
    Returns a task_id for status tracking.
    """
    task_id = str(uuid.uuid4())[:8]
    
    task = TaskInfo(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    tasks[task_id] = task
    
    # Run refresh in background
    background_tasks.add_task(run_refresh_task, task_id, req.email, req.password)
    
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return tasks[task_id]


@app.get("/api/tasks")
async def list_tasks(limit: int = 20):
    """List recent tasks"""
    sorted_tasks = sorted(
        tasks.values(),
        key=lambda t: t.created_at,
        reverse=True
    )
    return sorted_tasks[:limit]


# ============ Background Tasks ============

async def run_register_task(task_id: str, count: int):
    """Background task to register accounts"""
    global clash_manager
    
    task = tasks[task_id]
    task.status = TaskStatus.RUNNING
    
    results = []
    success_count = 0
    fail_count = 0
    
    try:
        for i in range(count):
            task.progress = {
                "total": count,
                "completed": i,
                "success": success_count,
                "failed": fail_count,
                "current": f"Registering account {i+1}/{count}"
            }
            
            result = await register_single_account(clash_manager)
            
            if result:
                results.append(result)
                success_count += 1
                
                # Save to accounts.json
                update_accounts_json(config.output_json_path, result["email"], result)
                
                # Save to result.csv
                append_to_csv(config.input_csv_path, result["email"], result.get("password", ""))
            else:
                fail_count += 1
            
            # Cooldown between accounts
            if i < count - 1:
                await asyncio.sleep(3)
        
        task.status = TaskStatus.SUCCESS
        task.result = {
            "accounts": results,
            "success": success_count,
            "failed": fail_count
        }
        task.progress = {
            "total": count,
            "completed": count,
            "success": success_count,
            "failed": fail_count
        }
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        logger.error(f"[API] Register task failed: {e}")
    
    task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def run_refresh_task(task_id: str, email: str, password: str):
    """Background task to refresh account cookies"""
    global clash_manager
    
    task = tasks[task_id]
    task.status = TaskStatus.RUNNING
    
    try:
        result = await refresh_single_account(clash_manager, email, password)
        
        if result:
            task.status = TaskStatus.SUCCESS
            task.result = result
            
            # Update accounts.json
            update_accounts_json(config.output_json_path, email, result)
        else:
            task.status = TaskStatus.FAILED
            task.error = "Failed to refresh cookies"
            
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        logger.error(f"[API] Refresh task failed: {e}")
    
    task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============ Core Functions ============

async def register_single_account(clash_manager: ClashManager) -> Optional[dict]:
    """Register a single new account"""
    
    # Find healthy proxy node
    node = clash_manager.find_healthy_node()
    if not node:
        logger.error("[API] No healthy proxy node")
        return None
    
    logger.info(f"[API] Using proxy node: {node}")
    
    max_retries = 3
    
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"[API] Retry {attempt + 1}/{max_retries}")
        
        # Create new mail client
        mail_client = MailClient(proxy_url=clash_manager.get_proxy_url())
        
        if not mail_client.register():
            logger.error("[API] Failed to register email")
            continue
        
        email = mail_client.email
        password = mail_client.password
        logger.info(f"[API] Using email: {email}")
        
        # Create browser
        browser = BrowserController(
            proxy_url=clash_manager.get_proxy_url(),
            headless=False  # Must be non-headless
        )
        
        try:
            await browser.start()
            
            if not await browser.login(email, password):
                logger.error("[API] Failed to login")
                await browser.stop()
                continue
            
            code = mail_client.wait_for_code(timeout=30)
            
            if not code:
                logger.warning("[API] Verification code timeout")
                await browser.stop()
                continue
            
            logger.info(f"[API] Got code: {code}")
            
            if not await browser.enter_verification_code(code):
                await browser.stop()
                continue
            
            if not await browser.wait_for_login_complete(timeout=60):
                await browser.stop()
                continue
            
            cookie_data = await browser.extract_cookies()
            
            if not cookie_data.get("secure_c_ses"):
                await browser.stop()
                continue
            
            cookie_data["email"] = email
            cookie_data["password"] = password
            
            logger.info(f"[API] ✅ Registered: {email}")
            await browser.stop()
            return cookie_data
            
        except Exception as e:
            logger.error(f"[API] Error: {e}")
            await browser.stop()
            continue
    
    return None


async def refresh_single_account(clash_manager: ClashManager, email: str, password: str) -> Optional[dict]:
    """Refresh cookies for a single account"""
    
    node = clash_manager.find_healthy_node()
    if not node:
        logger.error("[API] No healthy proxy node")
        return None
    
    logger.info(f"[API] Refreshing {email} with node: {node}")
    
    mail_client = MailClient(proxy_url=clash_manager.get_proxy_url())
    
    # Login to existing email
    if not mail_client.login_existing(email, password):
        logger.error(f"[API] Failed to login to email: {email}")
        return None
    
    browser = BrowserController(
        proxy_url=clash_manager.get_proxy_url(),
        headless=False
    )
    
    try:
        await browser.start()
        
        if not await browser.login(email, password):
            logger.error("[API] Failed to login")
            return None
        
        code = mail_client.wait_for_code(timeout=30)
        
        if not code:
            logger.error("[API] Verification code timeout")
            return None
        
        logger.info(f"[API] Got code: {code}")
        
        if not await browser.enter_verification_code(code):
            return None
        
        if not await browser.wait_for_login_complete(timeout=60):
            return None
        
        cookie_data = await browser.extract_cookies()
        
        if not cookie_data.get("secure_c_ses"):
            return None
        
        cookie_data["email"] = email
        cookie_data["password"] = password
        
        logger.info(f"[API] ✅ Refreshed: {email}")
        return cookie_data
        
    except Exception as e:
        logger.error(f"[API] Error: {e}")
        return None
        
    finally:
        await browser.stop()


# ============ Run Server ============

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
