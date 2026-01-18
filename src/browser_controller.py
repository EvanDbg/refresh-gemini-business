"""
Browser automation controller using Playwright.
Handles Chromium browser with proxy and Chrome extension.

Optimized based on V1.1.Gemini.Business/auto_register_browser.py
"""

import asyncio
import os
import urllib.parse
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

from .utils import logger
from .config import config


class BrowserController:
    """Controls Chromium browser for Gemini Business login automation."""
    
    GEMINI_LOGIN_URL = "https://business.gemini.google/"
    GEMINI_HOME_URL = "https://business.gemini.google/home"
    
    # Multiple selectors for email input (fallback strategy)
    EMAIL_SELECTORS = [
        '#email-input',
        'input[name="loginHint"]',
        'input[type="email"]',
        'input[type="text"]',
        'input[placeholder*="email" i]'
    ]
    
    # Multiple selectors for verification code input
    CODE_SELECTORS = [
        'input[type="tel"]',
        'input[name="pinInput"]',
        'input[autocomplete="one-time-code"]',
        'input[inputmode="numeric"]',
        'input[maxlength="6"]',
        'input[pattern*="[0-9]"]'
    ]
    
    # Continue/Login button selectors
    CONTINUE_SELECTORS = [
        '#log-in-button',
        'button[type="submit"]',
        'button:has-text("继续")',
        'button:has-text("Continue")'
    ]
    
    def __init__(
        self,
        proxy_url: Optional[str] = None,
        headless: bool = True,
        extension_path: Optional[str] = None
    ):
        """
        Initialize browser controller.
        
        Args:
            proxy_url: HTTP proxy URL (e.g., http://127.0.0.1:17890)
            headless: Run browser in headless mode
            extension_path: Path to Chrome extension directory
        """
        self.proxy_url = proxy_url
        self.headless = headless
        self.extension_path = extension_path or self._get_default_extension_path()
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
    
    def _get_default_extension_path(self) -> str:
        """Get default extension path relative to project root."""
        current_dir = Path(__file__).parent.parent
        extension_dir = current_dir / "extensions" / "cookie_extractor"
        return str(extension_dir.absolute())
    
    async def start(self) -> None:
        """Start browser with Playwright."""
        self._playwright = await async_playwright().start()
        
        # Build launch args with strong anti-detection
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--window-size=1920,1080",
            # Anti-headless detection
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--disable-web-security",
            "--allow-running-insecure-content",
            # Fingerprint masking
            "--disable-features=UserAgentClientHint",
            "--disable-reading-from-canvas",
        ]
        
        # Add extension if available and not headless
        if os.path.exists(self.extension_path) and not self.headless:
            launch_args.extend([
                f"--disable-extensions-except={self.extension_path}",
                f"--load-extension={self.extension_path}",
            ])
            logger.info(f"[Browser] Loading extension from: {self.extension_path}")
        
        # Configure proxy
        proxy_config = None
        if self.proxy_url:
            proxy_config = {"server": self.proxy_url}
            logger.info(f"[Browser] Using proxy: {self.proxy_url}")
        
        # Launch browser
        if os.path.exists(self.extension_path) and not self.headless:
            # Use launch_persistent_context for extension support
            # Clean up old profile to ensure fresh session for each account
            user_data_dir = "/tmp/gemini-browser-profile"
            import shutil
            if os.path.exists(user_data_dir):
                try:
                    shutil.rmtree(user_data_dir)
                    logger.info("[Browser] Cleaned up old browser profile")
                except Exception as e:
                    logger.warning(f"[Browser] Failed to clean profile: {e}")
            
            # Check if custom chromium path is specified (for Docker containers)
            chromium_path = os.environ.get("CHROMIUM_PATH")
            
            launch_kwargs = {
                "headless": False,
                "args": launch_args,
                "proxy": proxy_config,
                "viewport": {"width": 1920, "height": 1080}
            }
            
            if chromium_path and os.path.exists(chromium_path):
                launch_kwargs["executable_path"] = chromium_path
                logger.info(f"[Browser] Using system chromium: {chromium_path}")
            
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir,
                **launch_kwargs
            )
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        else:
            # Standard launch without extension
            # Add more anti-detection flags
            headless_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ] if self.headless else []
            
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=launch_args + headless_args,
                ignore_default_args=["--enable-automation"]
            )
            self._context = await self._browser.new_context(
                proxy=proxy_config,
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )
            self._page = await self._context.new_page()
        
        # Apply playwright-stealth to bypass bot detection
        stealth = Stealth(
            navigator_webdriver=True,  # Hide webdriver flag
            navigator_plugins=True,    # Fake plugins
            navigator_languages=True,  # Fake languages
            webgl_vendor=True,         # Mask WebGL fingerprint
            chrome_runtime=True,       # Add chrome.runtime
        )
        await stealth.apply_stealth_async(self._page)
        
        logger.info("[Browser] Started successfully (with stealth)")
    
    async def stop(self) -> None:
        """Stop browser and cleanup."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        
        logger.info("[Browser] Stopped")
    
    async def _find_element_by_selectors(self, selectors: list, timeout: int = 5000) -> Optional[any]:
        """
        Find element using multiple selector fallbacks.
        
        Args:
            selectors: List of CSS selectors to try
            timeout: Timeout per selector in ms
            
        Returns:
            Element handle or None if not found
        """
        for selector in selectors:
            try:
                element = await self._page.wait_for_selector(selector, timeout=timeout)
                if element:
                    logger.info(f"[Browser] Found element with: {selector}")
                    return element
            except:
                continue
        return None
    
    async def _input_via_js(self, value: str, selectors: list) -> bool:
        """
        Input value using JavaScript (more reliable than native input).
        Similar to reference project's JS injection approach.
        
        Args:
            value: Value to input
            selectors: List of selectors to try
            
        Returns:
            True if successful
        """
        try:
            # Use Playwright's argument passing for safety
            result = await self._page.evaluate('''
                ([selectors, value]) => {
                    for (const selector of selectors) {
                        try {
                            let el = document.querySelector(selector);
                            if (el) {
                                el.focus();
                                el.value = value;
                                el.dispatchEvent(new Event("input", {bubbles: true}));
                                el.dispatchEvent(new Event("change", {bubbles: true}));
                                return el.value === value;
                            }
                        } catch (e) {}
                    }
                    return false;
                }
            ''', [selectors, value])
            return result
        except Exception as e:
            logger.warning(f"[Browser] JS input failed: {e}")
            return False
    
    async def _click_via_js(self, selectors: list) -> bool:
        """
        Click element using JavaScript.
        
        Args:
            selectors: List of selectors to try
            
        Returns:
            True if successful
        """
        try:
            result = await self._page.evaluate('''
                (selectors) => {
                    for (const selector of selectors) {
                        try {
                            let el = document.querySelector(selector);
                            if (el) {
                                el.click();
                                return true;
                            }
                        } catch (e) {}
                    }
                    return false;
                }
            ''', selectors)
            return result
        except:
            return False
    
    async def login(self, email: str, password: str) -> bool:
        """
        Perform Gemini Business login with email.
        Optimized based on reference project's run_browser_cycle.
        
        Args:
            email: Account email
            password: Account password (may not be needed for Google)
            
        Returns:
            True if email was submitted successfully
        """
        try:
            # Navigate to login page with retry mechanism
            logger.info(f"[Browser] Navigating to {self.GEMINI_LOGIN_URL}")
            
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    await self._page.goto(
                        self.GEMINI_LOGIN_URL, 
                        wait_until="domcontentloaded",
                        timeout=60000
                    )
                    # Success, break the retry loop
                    break
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    if "net::ERR_CONNECTION_CLOSED" in error_msg or "net::ERR_CONNECTION_RESET" in error_msg:
                        logger.warning(f"[Browser] Connection error (attempt {attempt + 1}/{max_retries}): {error_msg[:50]}...")
                        if attempt < max_retries - 1:
                            logger.info(f"[Browser] Retrying in 3 seconds...")
                            await asyncio.sleep(3)
                            continue
                    # For other errors or max retries reached, raise
                    raise
            else:
                # All retries failed
                if last_error:
                    raise last_error
            
            # Wait for page to stabilize
            await asyncio.sleep(3)
            
            # Find email input using multiple selectors
            email_input = await self._find_element_by_selectors(
                self.EMAIL_SELECTORS, 
                timeout=10000
            )
            
            if not email_input:
                logger.error("[Browser] Email input not found")
                return False
            
            # Wait for element to be stable (check with JS)
            for _ in range(10):
                try:
                    stable = await self._page.evaluate('''
                        (function() {
                            let el = document.getElementById("email-input") ||
                                     document.querySelector('input[name="loginHint"]') ||
                                     document.querySelector('input[type="email"]') ||
                                     document.querySelector('input[type="text"]');
                            if (!el) return false;
                            let style = window.getComputedStyle(el);
                            return !el.disabled && !el.readOnly && style.visibility !== 'hidden';
                        })()
                    ''')
                    if stable:
                        break
                except:
                    pass
                await asyncio.sleep(0.3)
            
            # Try JS input first (more reliable)
            js_success = await self._input_via_js(email, self.EMAIL_SELECTORS)
            
            if not js_success:
                # Fallback to native input
                logger.info("[Browser] Using fallback native input")
                await email_input.click()
                await asyncio.sleep(0.2)
                await email_input.fill("")  # Clear
                await asyncio.sleep(0.2)
                await email_input.type(email, delay=20)  # Type character by character
            
            logger.info(f"[Browser] Entered email: {email}")
            
            # Click continue button
            await asyncio.sleep(0.5)
            
            # Remember current URL for change detection
            current_url = self._page.url
            
            # Try multiple methods to click continue
            clicked = await self._click_via_js(self.CONTINUE_SELECTORS)
            
            if not clicked:
                # Try native click
                continue_btn = await self._find_element_by_selectors(
                    self.CONTINUE_SELECTORS, 
                    timeout=5000
                )
                if continue_btn:
                    await continue_btn.click()
                    clicked = True
            
            if not clicked:
                # Fallback: press Enter
                logger.info("[Browser] Pressing Enter as fallback")
                await email_input.press("Enter")
            
            logger.info("[Browser] Clicked continue button")
            
            # Wait for page change (URL change or pin input appears)
            # This is critical for headless mode
            page_changed = False
            for attempt in range(15):  # Wait up to 15 seconds
                await asyncio.sleep(1)
                new_url = self._page.url
                
                # Check if URL changed (navigation happened)
                if new_url != current_url:
                    logger.info(f"[Browser] Page URL changed: {new_url}")
                    logger.info(f"[Browser] Page navigated to verification step")
                    page_changed = True
                    break
                
                # Check if pin input appeared (same page navigation)
                pin_input = await self._find_element_by_selectors(
                    self.CODE_SELECTORS,
                    timeout=500
                )
                if pin_input:
                    logger.info(f"[Browser] Verification code input found")
                    page_changed = True
                    break
                
                # Check if still on email input (button click may have failed)
                if attempt == 5:
                    # Try clicking again after 5 seconds
                    logger.warning("[Browser] Page not changed, retrying click...")
                    await self._click_via_js(self.CONTINUE_SELECTORS)
                    await email_input.press("Enter")
            
            # Only check if email was cleared if page did NOT change
            # (to handle the case where submit clears the field without navigating)
            if not page_changed:
                try:
                    current_value = await self._page.evaluate('''
                        (function() {
                            let el = document.getElementById("email-input") ||
                                     document.querySelector('input[name="loginHint"]') ||
                                     document.querySelector('input[type="email"]') ||
                                     document.querySelector('input[type="text"]');
                            return el ? el.value : "";
                        })()
                    ''')
                    
                    if not current_value:
                        logger.warning("[Browser] Email cleared after submit, re-inputting")
                        await self._input_via_js(email, self.EMAIL_SELECTORS)
                        await asyncio.sleep(0.3)
                        await self._click_via_js(self.CONTINUE_SELECTORS)
                except Exception:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"[Browser] Login failed: {e}")
            return False
    
    async def enter_verification_code(self, code: str) -> bool:
        """
        Enter verification code received by email.
        
        Args:
            code: 6-digit verification code
            
        Returns:
            True if code was submitted successfully
        """
        try:
            # Wait for code input using multiple selectors
            code_input = None
            for _ in range(10):
                code_input = await self._find_element_by_selectors(
                    self.CODE_SELECTORS,
                    timeout=3000
                )
                if code_input:
                    break
                await asyncio.sleep(0.5)
            
            if not code_input:
                logger.error("[Browser] Code input not found")
                return False
            
            # Input code
            await code_input.click()
            await asyncio.sleep(0.2)
            await code_input.fill(code)
            
            # Dispatch events
            await self._page.evaluate('''
                (function() {
                    let el = document.querySelector("input[name=pinInput]") || 
                             document.querySelector("input[type=tel]");
                    if(el) {
                        el.dispatchEvent(new Event("input", {bubbles: true}));
                        el.dispatchEvent(new Event("change", {bubbles: true}));
                    }
                })()
            ''')
            
            logger.info("[Browser] Entered verification code")
            
            # Find and click verify button (avoid resend buttons)
            await asyncio.sleep(0.5)
            
            # Get all buttons and find the verify button (not resend)
            clicked = await self._page.evaluate('''
                (function() {
                    let buttons = document.querySelectorAll("button");
                    for (let btn of buttons) {
                        let text = btn.textContent || "";
                        // Skip resend buttons
                        if (text.includes("重新") || text.includes("发送") || 
                            text.toLowerCase().includes("resend")) {
                            continue;
                        }
                        if (text.trim()) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                })()
            ''')
            
            if not clicked:
                await code_input.press("Enter")
                logger.info("[Browser] Pressed Enter as fallback")
            else:
                logger.info("[Browser] Clicked verify button")
            
            # Wait for navigation to complete
            for _ in range(10):
                await asyncio.sleep(3)
                curr_url = self._page.url
                if any(kw in curr_url for kw in ["home", "admin", "setup", "create", "dashboard"]):
                    logger.info("[Browser] Login successful, navigated to home")
                    return True
            
            # Check for failure indicators
            curr_url = self._page.url
            fail_keywords = ["verify", "oob", "error"]
            if any(kw in curr_url for kw in fail_keywords):
                logger.error("[Browser] Verification failed - still on verify page")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"[Browser] Verification failed: {e}")
            return False
    
    async def extract_cookies(self) -> dict:
        """
        Extract required cookies from the browser.
        Based on reference project's extract_account_config function.
        
        Returns:
            Dict containing secure_c_ses, csesidx, config_id, host_c_oses, expires_at
        """
        result = {
            "secure_c_ses": "",
            "csesidx": "",
            "config_id": "",
            "host_c_oses": "",
            "expires_at": ""
        }
        
        try:
            logger.info("[Browser] Extracting account configuration...")
            
            # Wait for page to have correct URL
            for i in range(15):
                current_url = self._page.url
                if '/cid/' in current_url or 'csesidx=' in current_url:
                    logger.info(f"[Browser] Found target URL: {current_url[:80]}...")
                    break
                await asyncio.sleep(2)
            
            # Parse URL for config_id and csesidx
            current_url = self._page.url
            parsed_url = urllib.parse.urlparse(current_url)
            path_parts = parsed_url.path.split('/')
            
            # Extract config_id from path (e.g., /home/cid/XXXXX)
            if 'cid' in path_parts:
                cid_index = path_parts.index('cid')
                if len(path_parts) > cid_index + 1:
                    result["config_id"] = path_parts[cid_index + 1]
                    logger.info(f"[Browser] config_id: {result['config_id']}")
            
            # Extract csesidx from query params
            query_params = urllib.parse.parse_qs(parsed_url.query)
            csesidx = query_params.get('csesidx', [None])[0]
            if csesidx:
                result["csesidx"] = csesidx
                logger.info(f"[Browser] csesidx: {csesidx}")
            
            # Get cookies from browser context
            cookies = await self._context.cookies()
            
            for cookie in cookies:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                
                if name == "__Secure-C_SES":
                    result["secure_c_ses"] = value
                    logger.info(f"[Browser] __Secure-C_SES: {value[:50]}...")
                    
                    # Get expiry time
                    expiry = cookie.get("expires")
                    if expiry:
                        # Cookie expiry - 12 hours = recommended update time
                        adjusted_time = datetime.fromtimestamp(expiry - 43200)
                        result["expires_at"] = adjusted_time.strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"[Browser] expires_at: {result['expires_at']}")
                        
                elif name == "__Host-C_OSES":
                    result["host_c_oses"] = value
                    logger.info(f"[Browser] __Host-C_OSES: {value[:50]}...")
            
            # Default expiry if not found
            if not result["expires_at"]:
                result["expires_at"] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"[Browser] Using default expires_at: {result['expires_at']}")
            
            if result["secure_c_ses"]:
                logger.info("[Browser] Extraction completed")
            else:
                logger.error("[Browser] Missing required cookie: __Secure-C_SES")
            
            return result
            
        except Exception as e:
            logger.error(f"[Browser] Cookie extraction failed: {e}")
            return result
    
    async def wait_for_login_complete(self, timeout: int = 60) -> bool:
        """
        Wait for login to complete by checking URL.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if login completed
        """
        try:
            for _ in range(timeout // 3):
                curr_url = self._page.url
                if any(kw in curr_url for kw in ["home", "admin", "setup", "create", "dashboard", "cid"]):
                    return True
                await asyncio.sleep(3)
            return False
        except Exception:
            return False


async def create_browser_controller(
    proxy_url: Optional[str] = None,
    headless: Optional[bool] = None
) -> BrowserController:
    """
    Create and start a browser controller.
    
    Args:
        proxy_url: Optional proxy URL, uses config default if not specified
        headless: Optional headless mode, uses config default if not specified
    """
    controller = BrowserController(
        proxy_url=proxy_url,
        headless=headless if headless is not None else config.browser_headless
    )
    await controller.start()
    return controller
