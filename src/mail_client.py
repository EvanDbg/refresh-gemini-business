"""
DuckMail API client for temporary email and verification codes.
Based on V1.1.Gemini.Business/mail_client.py implementation.
"""

import re
import time
import random
import string
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional

from .utils import logger


class MailClient:
    """Client for DuckMail temporary email API."""
    
    BASE_URL = "https://api.duckmail.sbs"
    
    def __init__(self, proxy_url: Optional[str] = None):
        """
        Initialize mail client with session, retry strategy, and proxy.
        
        Args:
            proxy_url: Proxy URL for requests (e.g., http://127.0.0.1:17890)
        """
        self.proxy_url = proxy_url
        self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        
        # Create session with retry strategy
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "DELETE", "PATCH"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Set proxy for session
        if self.proxies:
            self.session.proxies.update(self.proxies)
            logger.info(f"[Mail] Using proxy: {proxy_url}")
        
        # Account credentials
        self.email: Optional[str] = None
        self.password: Optional[str] = None
        self.account_id: Optional[str] = None
        self.token: Optional[str] = None
    
    def register(self, domain: Optional[str] = None) -> bool:
        """
        Register a new temporary email account.
        
        Args:
            domain: Optional domain to use
            
        Returns:
            True if successful
        """
        # Get available domain if not specified
        if not domain:
            domain = "virgilian.com"  # Default domain
            try:
                resp = self.session.get(
                    f"{self.BASE_URL}/domains",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if 'hydra:member' in data and len(data['hydra:member']) > 0:
                        domain = data['hydra:member'][0]['domain']
            except Exception as e:
                logger.warning(f"[Mail] Failed to get domains, using default: {e}")
        
        # Generate random email and password
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        timestamp = str(int(time.time()))[-4:]
        self.email = f"t{timestamp}{rand_str}@{domain}"
        self.password = f"Pwd{rand_str}{timestamp}"
        
        logger.info(f"[Mail] Registering: {self.email}")
        
        try:
            resp = self.session.post(
                f"{self.BASE_URL}/accounts",
                json={"address": self.email, "password": self.password},
                timeout=15
            )
            if resp.status_code in [200, 201]:
                self.account_id = resp.json().get('id')
                logger.info(f"[Mail] Registered successfully")
                return True
            else:
                logger.error(f"[Mail] Register failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"[Mail] Register error: {e}")
            return False
    
    def login(self) -> bool:
        """
        Login to get access token.
        
        Returns:
            True if successful
        """
        if not self.email:
            logger.error("[Mail] No email to login with")
            return False
        
        try:
            resp = self.session.post(
                f"{self.BASE_URL}/token",
                json={"address": self.email, "password": self.password},
                timeout=15
            )
            if resp.status_code == 200:
                self.token = resp.json().get('token')
                logger.info("[Mail] Login successful")
                return True
            else:
                logger.error(f"[Mail] Login failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"[Mail] Login error: {e}")
            return False
    
    def login_existing(self, email: str, password: str) -> bool:
        """
        Login to an existing email account.
        
        Args:
            email: Email address
            password: Password
            
        Returns:
            True if successful
        """
        self.email = email
        self.password = password
        return self.login()
    
    def clear_inbox(self) -> int:
        """
        Clear all messages in the inbox to avoid old verification codes.
        
        Returns:
            Number of messages deleted
        """
        if not self.token:
            if not self.login():
                return 0
        
        headers = {"Authorization": f"Bearer {self.token}"}
        deleted_count = 0
        
        try:
            # Get all messages
            resp = self.session.get(
                f"{self.BASE_URL}/messages",
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                msgs = resp.json().get('hydra:member', [])
                for msg in msgs:
                    msg_id = msg.get('id')
                    if msg_id:
                        try:
                            # Delete message
                            self.session.delete(
                                f"{self.BASE_URL}/messages/{msg_id}",
                                headers=headers,
                                timeout=10
                            )
                            deleted_count += 1
                        except:
                            pass
                
                if deleted_count > 0:
                    logger.info(f"[Mail] Cleared {deleted_count} old messages")
        except Exception as e:
            logger.warning(f"[Mail] Error clearing inbox: {e}")
        
        return deleted_count
    
    def wait_for_code(self, timeout: int = 300) -> Optional[str]:
        """
        Wait for and extract verification code from incoming emails.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            Verification code, or None if timeout
        """
        if not self.token:
            if not self.login():
                return None
        
        logger.info(f"[Mail] Waiting for code ({timeout}s)...")
        headers = {"Authorization": f"Bearer {self.token}"}
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                resp = self.session.get(
                    f"{self.BASE_URL}/messages",
                    headers=headers,
                    timeout=10
                )
                if resp.status_code == 200:
                    msgs = resp.json().get('hydra:member', [])
                    if msgs:
                        msg_id = msgs[0]['id']
                        # Get message detail
                        detail = self.session.get(
                            f"{self.BASE_URL}/messages/{msg_id}",
                            headers=headers,
                            timeout=10
                        )
                        data = detail.json()
                        content = data.get('text') or data.get('html') or ""
                        
                        code = self._extract_code(content)
                        if code:
                            logger.info(f"[Mail] Got verification code: {code}")
                            return code
            except Exception as e:
                logger.warning(f"[Mail] Error checking messages: {e}")
            
            time.sleep(3)
        
        logger.error("[Mail] Timeout waiting for verification code")
        return None
    
    def _extract_code(self, text: str) -> Optional[str]:
        """
        Extract verification code from email content.
        
        Args:
            text: Email content
            
        Returns:
            Extracted code or None
        """
        # Pattern for code with context (e.g., "验证码: 123456")
        pattern_context = r'(?:验证码|code|verification|passcode|pin).*?[:：]\s*([A-Za-z0-9]{4,8})\b'
        match = re.search(pattern_context, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
        
        # Fallback: find 6-digit number
        digits = re.findall(r'\b\d{6}\b', text)
        if digits:
            return digits[0]
        
        return None
    
    def delete(self) -> None:
        """Delete the temporary email account."""
        if not self.account_id or not self.token:
            return
        
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            self.session.delete(
                f"{self.BASE_URL}/accounts/{self.account_id}",
                headers=headers,
                timeout=10
            )
            logger.info("[Mail] Account deleted")
        except Exception as e:
            logger.warning(f"[Mail] Failed to delete account: {e}")


# Convenience function
def get_mail_client(proxy_url: Optional[str] = None) -> MailClient:
    """Create and return a MailClient instance."""
    return MailClient(proxy_url=proxy_url)
