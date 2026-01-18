#!/usr/bin/env python3
"""
Gemini Business Cookie Refresh Tool - Main Entry Point

This tool automates the process of logging into Gemini Business accounts
and extracting required cookies for API access.

Supports two modes:
1. Refresh existing accounts (from CSV)
2. Register new accounts (using DuckMail temporary email)
"""

import asyncio
import argparse
import sys
from typing import Optional

from .config import config
from .utils import logger, read_csv_accounts, update_accounts_json, read_json_file, append_to_csv
from .clash_manager import ClashManager, get_manager
from .mail_client import MailClient, get_mail_client
from .browser_controller import BrowserController
from .data_pusher import create_pusher


async def register_new_account(
    clash_manager: ClashManager,
    headless: bool = True
) -> Optional[dict]:
    """
    Register a new Gemini Business account using DuckMail.
    
    Args:
        clash_manager: ClashManager instance
        headless: Run browser in headless mode
        
    Returns:
        Account data dict if successful, None otherwise
    """
    logger.info("="*50)
    logger.info("Registering new Gemini Business account")
    logger.info("="*50)
    
    # Find healthy proxy node
    node = clash_manager.find_healthy_node()
    if not node:
        logger.error("No healthy proxy node available")
        return None
    
    logger.info(f"Using proxy node: {node}")
    
    max_retries = 3
    
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"[Retry] Attempt {attempt + 1}/{max_retries} - Registering new email...")
        
        # Create new mail client for each attempt
        mail_client = MailClient(proxy_url=clash_manager.get_proxy_url())
        
        # Register new email
        if not mail_client.register():
            logger.error("Failed to register temporary email")
            continue
        
        email = mail_client.email
        password = mail_client.password
        logger.info(f"Using email: {email}")
        
        # Create browser controller
        browser = BrowserController(
            proxy_url=clash_manager.get_proxy_url(),
            headless=headless
        )
        
        try:
            # Start browser
            await browser.start()
            
            # Perform login (enter email)
            if not await browser.login(email, password):
                logger.error("Failed to submit email to Gemini Business")
                await browser.stop()
                continue
            
            # Wait for verification code from DuckMail
            code = mail_client.wait_for_code(timeout=30)
            
            if not code:
                logger.warning(f"[Mail] Verification code timeout (attempt {attempt + 1}/{max_retries})")
                await browser.stop()
                continue
            
            logger.info(f"Got verification code: {code}")
            
            # Enter verification code
            if not await browser.enter_verification_code(code):
                logger.error("Failed to verify code")
                await browser.stop()
                continue
            
            # Wait for login to complete
            if not await browser.wait_for_login_complete(timeout=60):
                logger.error("Login did not complete")
                await browser.stop()
                continue
            
            # Extract cookies
            cookie_data = await browser.extract_cookies()
            
            if not cookie_data.get("secure_c_ses"):
                logger.error("Failed to extract cookies")
                await browser.stop()
                continue
            
            # Add account info
            cookie_data["email"] = email
            cookie_data["password"] = password
            
            logger.info(f"✅ Successfully registered: {email}")
            await browser.stop()
            return cookie_data
            
        except Exception as e:
            logger.error(f"Error during registration: {e}")
            await browser.stop()
            continue
    
    logger.error("Failed to register account after all retries")
    return None


async def process_existing_account(
    account: dict,
    clash_manager: ClashManager,
    headless: bool = True,
    proxy_node: str = None
) -> bool:
    """
    Process an existing DuckMail account: login to Gemini Business and extract cookies.
    Uses DuckMail API to get verification code.
    
    Args:
        account: Account dict with email, password
        clash_manager: ClashManager instance
        headless: Run browser in headless mode
        proxy_node: Specific proxy node name to use (if None, find healthy node)
        
    Returns:
        True if successful
    """
    email = account.get("email", "")
    password = account.get("password", "")
    
    if not email:
        logger.error("Account missing email")
        return False
    
    logger.info("="*50)
    logger.info(f"Processing account: {email}")
    logger.info("="*50)
    
    # Use specified node or find healthy one
    if proxy_node:
        # Switch to specified node
        if clash_manager.switch_node(proxy_node):
            node = proxy_node
            logger.info(f"Using specified proxy node: {node}")
        else:
            logger.error(f"Failed to switch to specified node: {proxy_node}")
            return False
    else:
        # Find healthy proxy node
        node = clash_manager.find_healthy_node()
        if not node:
            logger.error(f"No healthy proxy node available for {email}")
            return False
        logger.info(f"Using proxy node: {node}")
    
    # Create mail client with proxy - set credentials for this account
    mail_client = MailClient(proxy_url=clash_manager.get_proxy_url())
    mail_client.email = email
    mail_client.password = password
    
    # Create browser controller
    browser = BrowserController(
        proxy_url=clash_manager.get_proxy_url(),
        headless=headless
    )
    
    try:
        # Start browser
        await browser.start()
        
        # Clear old messages before login to avoid old verification codes
        mail_client.clear_inbox()
        
        # Perform login (enter email on Gemini Business)
        if not await browser.login(email, password):
            logger.error(f"Failed to start login for {email}")
            return False
        
        # Get verification code from DuckMail API
        code = mail_client.wait_for_code(timeout=30)
        if not code:
            logger.error(f"Failed to get verification code for {email}")
            return False
        
        logger.info(f"Got verification code: {code}")
        
        # Enter verification code in browser
        if not await browser.enter_verification_code(code):
            logger.error(f"Failed to verify code for {email}")
            return False
        
        # Wait for login to complete
        if not await browser.wait_for_login_complete(timeout=60):
            logger.error(f"Login did not complete for {email}")
            return False
        
        # Extract cookies
        cookie_data = await browser.extract_cookies()
        
        if not cookie_data.get("secure_c_ses"):
            logger.error(f"Failed to extract cookies for {email}")
            return False
        
        # Add account info
        cookie_data["email"] = email
        
        # Save to accounts.json
        update_accounts_json(config.output_json_path, email, cookie_data)
        
        logger.info(f"✅ Successfully processed: {email}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing {email}: {e}")
        return False
        
    finally:
        await browser.stop()


async def main_async(args: argparse.Namespace) -> int:
    """
    Async main function.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code
    """
    # Validate config
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        return 1
    
    # Initialize Clash manager
    logger.info("Starting Clash proxy manager...")
    clash_manager = get_manager(
        executable=config.clash_executable,
        config=config.clash_config,
        port=config.clash_port,
        api_port=config.clash_api_port
    )
    clash_manager.start()
    
    success_count = 0
    fail_count = 0
    
    try:
        if args.register:
            # Register new accounts mode
            for i in range(args.count):
                logger.info(f"\n--- Account {i+1}/{args.count} ---\n")
                result = await register_new_account(
                    clash_manager,
                    headless=config.browser_headless
                )
                if result:
                    # Save to accounts.json
                    update_accounts_json(config.output_json_path, result["email"], result)
                    # Also save to result.csv for future refresh
                    append_to_csv(config.input_csv_path, result["email"], result.get("password", ""))
                    success_count += 1
                else:
                    fail_count += 1
                
                # Cooldown between accounts
                if i < args.count - 1:
                    logger.info("Cooldown 3s...")
                    await asyncio.sleep(3)
        else:
            accounts = read_csv_accounts(config.input_csv_path)
            if not accounts:
                logger.error("No accounts to process")
                return 1
            
            logger.info(f"Loaded {len(accounts)} accounts from {config.input_csv_path}")
            
            # Load existing accounts from accounts.json to skip already processed
            existing_accounts = set()
            try:
                existing_data = read_json_file(config.output_json_path)
                if isinstance(existing_data, list):
                    for acc in existing_data:
                        if acc.get("email"):
                            existing_accounts.add(acc["email"])
                elif isinstance(existing_data, dict):
                    for email in existing_data.keys():
                        existing_accounts.add(email)
                if existing_accounts:
                    logger.info(f"Found {len(existing_accounts)} already processed accounts in accounts.json")
            except:
                pass
            
            for account in accounts:
                email = account.get("email", "")
                
                # Skip already processed accounts
                if email in existing_accounts:
                    logger.info(f"Skipping already processed: {email}")
                    continue
                
                try:
                    if await process_existing_account(
                        account,
                        clash_manager,
                        headless=config.browser_headless,
                        proxy_node=args.proxy_node
                    ):
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    fail_count += 1
    
    finally:
        # Stop Clash
        clash_manager.stop()
    
    # Summary
    logger.info("="*50)
    logger.info("Processing complete!")
    logger.info(f"Success: {success_count}, Failed: {fail_count}")
    logger.info("="*50)
    
    # Push results if configured
    if config.post_target_url:
        pusher = create_pusher(
            target_url=config.post_target_url,
            timeout=config.request_timeout,
            retry_count=config.retry_count
        )
        if pusher:
            pusher.push_from_file(config.output_json_path)
    
    return 0 if fail_count == 0 else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Gemini Business Cookie Refresh Tool"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to Clash config file"
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to input CSV file"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to output JSON file"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with GUI (non-headless)"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register new accounts mode (use DuckMail)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of accounts to register (with --register)"
    )
    parser.add_argument(
        "--proxy-node",
        type=str,
        help="Specific proxy node name to use (e.g., 'EVAN1s-US_RAILWAY 3')"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run as API server mode (FastAPI)"
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="Port for API server (default: 8000)"
    )
    
    args = parser.parse_args()
    
    # API server mode
    if args.api:
        from .api_server import run_server
        print(f"Starting API server on port {args.api_port}...")
        run_server(port=args.api_port)
        return 0
    
    # Override config with command line args
    if args.config:
        config.clash_config = args.config
    if args.input:
        config.input_csv_path = args.input
    if args.output:
        config.output_json_path = args.output
    if args.no_headless:
        config.browser_headless = False
    elif args.headless:
        config.browser_headless = True
    
    # Run async main
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())

