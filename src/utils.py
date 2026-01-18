"""
Utility functions for file operations and logging.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Setup and return logger instance."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def read_csv_accounts(csv_path: str) -> list[dict]:
    """
    Read accounts from CSV file.
    
    Expected format: ID,Account,Password,Date
    Returns list of dicts with keys: id, email, password, date
    """
    accounts = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            accounts.append({
                "id": row.get("ID", ""),
                "email": row.get("Account", ""),
                "password": row.get("Password", ""),
                "date": row.get("Date", "")
            })
    
    logger.info(f"Loaded {len(accounts)} accounts from {csv_path}")
    return accounts


def append_to_csv(csv_path: str, email: str, password: str) -> bool:
    """
    Append a new account to the CSV file.
    
    Args:
        csv_path: Path to result.csv
        email: Account email
        password: Account password
        
    Returns:
        True if successful
    """
    try:
        # Read existing to get next ID
        path = Path(csv_path)
        next_id = 1
        
        if path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    # Get max ID + 1, handle empty or invalid IDs
                    valid_ids = [int(row.get("ID", 0)) for row in rows if row.get("ID", "").isdigit()]
                    max_id = max(valid_ids) if valid_ids else 0
                    next_id = max_id + 1
        else:
            # Create new file with header
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Account", "Password", "Date"])
        
        # Append new account
        today = datetime.now().strftime("%Y-%m-%d")
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([next_id, email, password, today])
        
        logger.info(f"Appended account to CSV: {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to append to CSV: {e}")
        return False


def read_json_file(json_path: str) -> list[dict]:
    """Read JSON file, return empty list if not exists."""
    path = Path(json_path)
    if not path.exists():
        return []
    
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(json_path: str, data: list[dict]) -> None:
    """Write data to JSON file."""
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(data)} records to {json_path}")


def update_accounts_json(
    json_path: str,
    email: str,
    cookie_data: dict
) -> None:
    """
    Update or add account cookie data in JSON file.
    
    Args:
        json_path: Path to accounts.json
        email: Account email
        cookie_data: Dict containing secure_c_ses, csesidx, config_id, host_c_oses
    """
    accounts = read_json_file(json_path)
    
    # Find existing account by email
    existing_idx = None
    for idx, account in enumerate(accounts):
        if account.get("email") == email:
            existing_idx = idx
            break
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Default expiry is 7 days from now
    expires = datetime.now().replace(day=datetime.now().day + 7).strftime("%Y-%m-%d %H:%M:%S")
    
    record = {
        "id": f"account_{len(accounts) + 1}" if existing_idx is None else accounts[existing_idx].get("id"),
        "email": email,
        "secure_c_ses": cookie_data.get("secure_c_ses", ""),
        "csesidx": cookie_data.get("csesidx", ""),
        "config_id": cookie_data.get("config_id", ""),
        "host_c_oses": cookie_data.get("host_c_oses", ""),
        "expires_at": expires,
        "created_at": now if existing_idx is None else accounts[existing_idx].get("created_at", now),
        "updated_at": now
    }
    
    if existing_idx is not None:
        accounts[existing_idx] = record
        logger.info(f"Updated account: {email}")
    else:
        accounts.append(record)
        logger.info(f"Added new account: {email}")
    
    write_json_file(json_path, accounts)
