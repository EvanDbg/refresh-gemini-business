"""
Data pusher module for sending extracted cookies to remote server.
"""

import requests
from typing import Optional

from .utils import logger, read_json_file


class DataPusher:
    """Pushes account cookie data to remote server."""
    
    def __init__(
        self,
        target_url: str,
        timeout: int = 30,
        retry_count: int = 3
    ):
        """
        Initialize data pusher.
        
        Args:
            target_url: URL to POST data to
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
        """
        self.target_url = target_url
        self.timeout = timeout
        self.retry_count = retry_count
    
    def push(self, data: list[dict]) -> bool:
        """
        Push data to target URL.
        
        Args:
            data: List of account records to push
            
        Returns:
            True if successful
        """
        if not self.target_url:
            logger.warning("[Pusher] No target URL configured, skipping push")
            return False
        
        for attempt in range(self.retry_count):
            try:
                logger.info(f"[Pusher] Sending {len(data)} records to {self.target_url}")
                
                response = requests.post(
                    self.target_url,
                    json=data,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )
                
                if response.status_code in (200, 201, 204):
                    logger.info(f"[Pusher] Push successful: {response.status_code}")
                    return True
                else:
                    logger.warning(
                        f"[Pusher] Push failed with status {response.status_code}: {response.text[:200]}"
                    )
                    
            except requests.exceptions.Timeout:
                logger.warning(f"[Pusher] Timeout on attempt {attempt + 1}/{self.retry_count}")
            except requests.exceptions.RequestException as e:
                logger.error(f"[Pusher] Request error: {e}")
            
            if attempt < self.retry_count - 1:
                logger.info(f"[Pusher] Retrying ({attempt + 2}/{self.retry_count})...")
        
        logger.error("[Pusher] All push attempts failed")
        return False
    
    def push_from_file(self, json_path: str) -> bool:
        """
        Read data from JSON file and push to target.
        
        Args:
            json_path: Path to accounts.json file
            
        Returns:
            True if successful
        """
        data = read_json_file(json_path)
        if not data:
            logger.warning(f"[Pusher] No data to push from {json_path}")
            return False
        
        return self.push(data)


def create_pusher(
    target_url: Optional[str] = None,
    timeout: int = 30,
    retry_count: int = 3
) -> Optional[DataPusher]:
    """
    Create a DataPusher instance if target URL is configured.
    
    Returns:
        DataPusher instance, or None if no target URL
    """
    if not target_url:
        return None
    
    return DataPusher(
        target_url=target_url,
        timeout=timeout,
        retry_count=retry_count
    )
