"""
Clash/Mihomo proxy manager module.
Handles starting/stopping Clash process and proxy node selection.
"""

import subprocess
import requests
import yaml
import time
import os
import atexit
import sys
import random
import urllib.parse
from typing import Optional

from .utils import logger


class ClashManager:
    """Manages Clash/Mihomo proxy process and node selection."""
    
    # Keywords to skip when selecting nodes
    SKIP_KEYWORDS = ["自动选择", "故障转移", "DIRECT", "REJECT", "剩余", "到期", "官网"]
    
    def __init__(
        self,
        executable: str = "mihomo",
        config: str = "local.yaml",
        runtime_config: str = "config_runtime.yaml",
        port: int = 17890,
        api_port: int = 29090
    ):
        """
        Initialize Clash manager.
        
        Args:
            executable: Path to Clash/Mihomo executable
            config: Path to Clash config file
            runtime_config: Path to generated runtime config
            port: Mixed proxy port
            api_port: Clash API port
        """
        self.executable = executable
        self.config = config
        self.runtime_config = runtime_config
        self.port = port
        self.api_port = api_port
        self.api_url = f"http://127.0.0.1:{api_port}"
        self.process: Optional[subprocess.Popen] = None
        
        # Create a session that bypasses proxy for local API access
        self._api_session = requests.Session()
        self._api_session.trust_env = False  # Ignore proxy env vars
        
        self._prepare_config()
    
    def _prepare_config(self) -> None:
        """Prepare runtime config with correct ports and necessary routing rules."""
        if not os.path.exists(self.config):
            raise FileNotFoundError(f"Config not found: {self.config}")
        
        with open(self.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        
        # Override port settings
        cfg["mixed-port"] = self.port
        cfg["external-controller"] = f"127.0.0.1:{self.api_port}"
        cfg["mode"] = "rule"
        cfg["log-level"] = "info"
        
        # Auto-generate proxy-groups if not present
        if "proxy-groups" not in cfg or not cfg["proxy-groups"]:
            proxies = cfg.get("proxies", [])
            proxy_names = [p["name"] for p in proxies if "name" in p]
            
            if proxy_names:
                cfg["proxy-groups"] = [
                    {
                        "name": "🚀 节点选择",
                        "type": "select",
                        "proxies": proxy_names
                    }
                ]
                logger.info(f"[Clash] Auto-generated proxy-group with {len(proxy_names)} nodes")
        
        # Auto-generate rules if not present - route all traffic through proxy
        if "rules" not in cfg or not cfg["rules"]:
            cfg["rules"] = ["MATCH,🚀 节点选择"]
            logger.info("[Clash] Auto-generated rules: MATCH -> 🚀 节点选择")
        
        with open(self.runtime_config, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        
        logger.info(f"[Clash] Config ready: {self.runtime_config}")
    
    def start(self) -> None:
        """Start Clash process."""
        if self.process:
            return
        
        cmd = [self.executable, "-f", self.runtime_config]
        
        # Platform-specific process creation
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        self.process = subprocess.Popen(cmd, **kwargs)
        
        # Wait for Clash to start
        for _ in range(10):
            try:
                self._api_session.get(self.api_url, timeout=1)
                logger.info("[Clash] Started successfully")
                return
            except Exception:
                time.sleep(1)
        
        logger.error("[Clash] Start failed")
        self.stop()
    
    def stop(self) -> None:
        """Stop Clash process."""
        if self.process:
            self.process.terminate()
            self.process = None
            logger.info("[Clash] Stopped")
    
    def get_proxies(self) -> dict:
        """Get all proxies from Clash API."""
        try:
            url = f"{self.api_url}/proxies"
            res = self._api_session.get(url, timeout=5).json()
            return res.get("proxies", {})
        except Exception as e:
            logger.error(f"[Clash] Failed to get proxies: {e}")
            return {}
    
    def test_latency(self, proxy_name: str, timeout: int = 5000) -> int:
        """
        Test proxy node latency.
        
        Args:
            proxy_name: Name of the proxy node
            timeout: Timeout in milliseconds
            
        Returns:
            Latency in ms, or -1 if failed
        """
        try:
            encoded_name = urllib.parse.quote(proxy_name)
            url = f"{self.api_url}/proxies/{encoded_name}/delay"
            params = {
                "timeout": timeout,
                "url": "http://www.gstatic.com/generate_204"
            }
            res = self._api_session.get(url, params=params, timeout=6)
            if res.status_code == 200:
                return res.json().get("delay", 0)
            return -1
        except Exception:
            return -1
    
    def select_proxy(self, group_name: str, proxy_name: str) -> bool:
        """
        Select a proxy node in a group.
        
        Args:
            group_name: Name of the proxy group
            proxy_name: Name of the proxy to select
            
        Returns:
            True if successful
        """
        try:
            encoded_group = urllib.parse.quote(group_name)
            url = f"{self.api_url}/proxies/{encoded_group}"
            self._api_session.put(url, json={"name": proxy_name}, timeout=5)
            logger.info(f"[Clash] Switched to: {proxy_name}")
            return True
        except Exception as e:
            logger.error(f"[Clash] Failed to switch proxy: {e}")
            return False
    
    def switch_node(self, proxy_name: str) -> bool:
        """
        Switch to a specific proxy node by name.
        Auto-detects the proxy group containing the node.
        
        Args:
            proxy_name: Name of the proxy node to switch to
            
        Returns:
            True if successful
        """
        try:
            proxies = self.get_proxies()
            
            # Find group containing this proxy
            for group_name, group_info in proxies.items():
                if group_info.get("type") == "Selector":
                    all_nodes = group_info.get("all", [])
                    if proxy_name in all_nodes:
                        return self.select_proxy(group_name, proxy_name)
            
            logger.error(f"[Clash] Proxy node not found: {proxy_name}")
            return False
        except Exception as e:
            logger.error(f"[Clash] Failed to switch node: {e}")
            return False
    
    def _test_google_access(self, proxy_name: str) -> bool:
        """
        Test if the proxy can access Google services.
        
        Returns:
            True if accessible
        """
        try:
            time.sleep(1)
            
            # Create a session that ignores env proxy and uses Clash proxy only
            test_session = requests.Session()
            test_session.trust_env = False  # Ignore env proxy vars
            test_session.proxies = {
                "http": f"http://127.0.0.1:{self.port}",
                "https": f"http://127.0.0.1:{self.port}"
            }
            
            logger.info(f"   Testing [{proxy_name}]...", )
            # Use gstatic 204 endpoint for faster testing (same as reference project)
            resp = test_session.get(
                "http://www.gstatic.com/generate_204",
                timeout=5
            )
            
            if resp.status_code in [200, 204]:
                logger.info(f" ✅ PASS (status={resp.status_code})")
                return True
            else:
                logger.warning(f" ❌ Blocked (status={resp.status_code})")
                return False
        except Exception as e:
            logger.warning(f" ❌ Timeout ({type(e).__name__}: {e})")
            return False
    
    def find_healthy_node(self, group_name: Optional[str] = None) -> Optional[str]:
        """
        Find a healthy proxy node that can access Google.
        
        Args:
            group_name: Optional proxy group name, auto-detect if not provided
            
        Returns:
            Name of healthy node, or None if not found
        """
        logger.info("[Clash] Finding healthy node...")
        proxies = self.get_proxies()
        
        # Auto-detect group if not specified
        if not group_name or group_name not in proxies:
            for key, val in proxies.items():
                if val.get("type") == "Selector" and len(val.get("all", [])) > 0:
                    group_name = key
                    break
        
        if not group_name or group_name not in proxies:
            logger.error("[Clash] No proxy group found")
            return None
        
        # Get all nodes and shuffle for randomness
        all_nodes = proxies[group_name].get("all", [])
        random.shuffle(all_nodes)
        
        for node in all_nodes:
            # Skip system/utility nodes
            if any(kw in node for kw in self.SKIP_KEYWORDS):
                continue
            
            # Test latency
            delay = self.test_latency(node)
            if delay <= 0:
                continue
            
            # Select this node
            self.select_proxy(group_name, node)
            
            # Test Google access
            if self._test_google_access(node):
                return node
        
        logger.error("[Clash] No healthy node found")
        return None
    
    def get_proxy_url(self) -> str:
        """Get the proxy URL for browser/requests."""
        return f"http://127.0.0.1:{self.port}"


# Global manager instance
_manager_instance: Optional[ClashManager] = None


def get_manager(
    executable: str = "mihomo",
    config: str = "local.yaml",
    port: int = 17890,
    api_port: int = 29090
) -> ClashManager:
    """Get or create global ClashManager instance."""
    global _manager_instance
    if not _manager_instance:
        _manager_instance = ClashManager(
            executable=executable,
            config=config,
            port=port,
            api_port=api_port
        )
    return _manager_instance


@atexit.register
def cleanup():
    """Cleanup Clash process on exit."""
    if _manager_instance:
        _manager_instance.stop()
