"""
Configuration management module.
Loads configuration from environment variables with defaults.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file if exists
load_dotenv()


@dataclass
class Config:
    """Application configuration."""
    
    # Clash/Mihomo settings
    clash_executable: str = os.getenv("CLASH_EXECUTABLE", "mihomo")
    clash_config: str = os.getenv("CLASH_CONFIG", "./local.yaml")
    clash_port: int = int(os.getenv("CLASH_PORT", "17890"))
    clash_api_port: int = int(os.getenv("CLASH_API_PORT", "29090"))
    
    # Email API
    email_api_url: str = os.getenv("EMAIL_API_URL", "https://api.duckmail.sbs")
    
    # Data push
    post_target_url: str = os.getenv("POST_TARGET_URL", "")
    
    # File paths
    input_csv_path: str = os.getenv("INPUT_CSV_PATH", "./result.csv")
    output_json_path: str = os.getenv("OUTPUT_JSON_PATH", "./accounts.json")
    
    # Browser settings
    browser_headless: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    
    # Request settings
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    retry_count: int = int(os.getenv("RETRY_COUNT", "3"))
    
    def validate(self) -> list[str]:
        """Validate configuration, return list of errors."""
        errors = []
        
        if not os.path.exists(self.clash_config):
            errors.append(f"Clash config not found: {self.clash_config}")
        
        if not os.path.exists(self.input_csv_path):
            errors.append(f"Input CSV not found: {self.input_csv_path}")
        
        return errors


# Global config instance
config = Config()
