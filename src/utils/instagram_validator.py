"""Utilities for Instagram session validation"""
import json
import logging
import requests
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)

def load_cookies_from_file(cookie_file: str) -> Optional[Dict[str, str]]:
    """Load and parse cookies from Netscape/Mozilla format file"""
    cookies = {}
    try:
        with open(cookie_file, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                    
                fields = line.strip().split('\t')
                if len(fields) >= 7:
                    cookies[fields[5]] = fields[6]
                    
        return cookies if cookies else None
    except Exception as e:
        logger.error(f"Error loading cookies: {str(e)}")
        return None

def validate_instagram_session(cookie_file: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Instagram session by making a lightweight request.
    Uses the /web/__mid/ endpoint which is a lightweight endpoint
    that doesn't trigger security checks but requires authentication.
    """
    cookies = load_cookies_from_file(cookie_file)
    if not cookies:
        return False, "Failed to load cookies from file"
        
    # Required cookies for basic authentication
    required_cookies = ['sessionid', 'ds_user_id']
    missing_cookies = [c for c in required_cookies if c not in cookies]
    if missing_cookies:
        return False, f"Missing required cookies: {', '.join(missing_cookies)}"
        
    try:
        # Make a lightweight request to check session validity
        response = requests.get(
            'https://www.instagram.com/web/__mid/',
            cookies=cookies,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest'
            },
            timeout=10
        )
        
        # Check if we got a valid response
        if response.status_code == 200:
            try:
                # The endpoint returns a machine ID if authenticated
                machine_id = response.text.strip('"')
                if machine_id and len(machine_id) > 10:  # Basic validation of machine ID
                    return True, None
            except:
                pass
                
        if response.status_code == 403:
            return False, "Session invalid or expired"
            
        return False, f"Session validation failed with status code: {response.status_code}"
            
    except requests.RequestException as e:
        logger.error(f"Error validating session: {str(e)}")
        return False, "Network error during session validation"