"""
URL Security Utilities

Provides functions to validate URLs for webhooks and prevent SSRF attacks.
Designed for internal network deployments - allows private IPs but blocks
localhost and cloud metadata endpoints.
"""

import ipaddress
import re
import socket
import asyncio
from typing import Optional, List, Set, Tuple
from urllib.parse import urlparse

# Blocked IP ranges (localhost, link-local, cloud metadata)
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Localhost
    ipaddress.ip_network("::1/128"),           # IPv6 localhost
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / AWS metadata
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

# Allowed protocols
ALLOWED_PROTOCOLS = ["http", "https"]

# Pre-compiled suspicious patterns (Task 13 optimization)
SUSPICIOUS_PATTERNS_COMPILED = [
    re.compile(r'@'),      # User info in URL
    re.compile(r'\.\.'),   # Directory traversal
]

# Pre-compiled localhost patterns
LOCALHOST_PATTERNS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "0:0:0:0:0:0:0:1",
}


def is_ip_blocked(ip_str: str) -> bool:
    """
    Check if an IP address is in blocked ranges.

    Args:
        ip_str: IP address string

    Returns:
        True if IP is blocked, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for blocked_range in BLOCKED_IP_RANGES:
            if ip in blocked_range:
                return True
        return False
    except ValueError:
        # Invalid IP format
        return False


def validate_url_syntax(url: str, allow_localhost: bool = False) -> Tuple[bool, Optional[str], Optional[urlparse]]:
    """
    Validate URL syntax and basics (No DNS).
    Returns: (is_valid, error_msg, parsed_url)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string", None

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}", None

    # Check protocol
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        return False, f"Protocol '{parsed.scheme}' not allowed. Use http or https", None

    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a hostname", None

    # Block obvious localhost references
    if not allow_localhost:
        if hostname.lower() in LOCALHOST_PATTERNS:
            return False, "Localhost URLs are not allowed for security reasons", None

    # Check for suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS_COMPILED:
        if pattern.search(url):
            return False, f"URL contains suspicious pattern", None

    return True, None, parsed


def _validate_ips(ips: Set[str], allow_private: bool, allow_localhost: bool) -> Tuple[bool, Optional[str]]:
    """
    Validate a set of resolved IPs against security rules.
    """
    for ip_str in ips:
        # Check if IP is in blocked ranges (cloud metadata, etc.)
        # Skip localhost check if allow_localhost is True
        if not allow_localhost and is_ip_blocked(ip_str):
            return False, f"URL resolves to blocked IP address: {ip_str}"

        # For allow_localhost=True, only block metadata endpoints, not localhost
        if allow_localhost:
            try:
                ip = ipaddress.ip_address(ip_str)
                # Still block cloud metadata even in dev mode
                if ip in ipaddress.ip_network("169.254.0.0/16"):
                    return False, f"Cloud metadata endpoint blocked: {ip_str}"
            except ValueError:
                pass

        # For internal networks, we allow private IPs
        # But you can disable this with allow_private=False
        if not allow_private:
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private:
                    return False, f"Private IP addresses not allowed: {ip_str}"
            except ValueError:
                pass
    return True, None


def validate_webhook_url(url: str, allow_private: bool = True, allow_localhost: bool = False) -> tuple[bool, Optional[str]]:
    """
    Validate a webhook URL to prevent SSRF attacks (Synchronous, Blocking).
    
    WARNING: This function performs blocking DNS resolution. 
    Use validate_webhook_url_async in async contexts.

    Args:
        url: URL to validate
        allow_private: Whether to allow private IP ranges
        allow_localhost: Whether to allow localhost URLs

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error, parsed = validate_url_syntax(url, allow_localhost)
    if not is_valid:
        return False, error

    hostname = parsed.hostname

    # Resolve hostname to IP and check (BLOCKING)
    try:
        # Get all IPs for the hostname
        addr_info = socket.getaddrinfo(hostname, None)
        ips = set(info[4][0] for info in addr_info)

        is_valid_ips, ip_error = _validate_ips(ips, allow_private, allow_localhost)
        if not is_valid_ips:
            return False, ip_error

    except socket.gaierror as e:
        return False, f"Failed to resolve hostname: {str(e)}"
    except Exception as e:
        return False, f"Error validating URL: {str(e)}"

    # Additional check: Prevent DNS rebinding attacks with numeric IPs in hostname
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
        # reuse validation logic by treating hostname as IP
        is_valid_ips, ip_error = _validate_ips({hostname}, allow_private, allow_localhost)
        if not is_valid_ips:
            return False, ip_error

    return True, None


async def validate_webhook_url_async(url: str, allow_private: bool = True, allow_localhost: bool = False) -> tuple[bool, Optional[str]]:
    """
    Validate a webhook URL to prevent SSRF attacks (Asynchronous).
    
    Uses non-blocking DNS resolution.

    Args:
        url: URL to validate
        allow_private: Whether to allow private IP ranges
        allow_localhost: Whether to allow localhost URLs

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error, parsed = validate_url_syntax(url, allow_localhost)
    if not is_valid:
        return False, error

    hostname = parsed.hostname

    # Resolve hostname to IP and check (ASYNC)
    try:
        loop = asyncio.get_running_loop()
        addr_info = await loop.getaddrinfo(hostname, None)
        ips = set(info[4][0] for info in addr_info)

        is_valid_ips, ip_error = _validate_ips(ips, allow_private, allow_localhost)
        if not is_valid_ips:
            return False, ip_error

    except socket.gaierror as e:
        return False, f"Failed to resolve hostname: {str(e)}"
    except Exception as e:
        return False, f"Error validating URL: {str(e)}"

    # Additional check: Numeric IPs
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
        is_valid_ips, ip_error = _validate_ips({hostname}, allow_private, allow_localhost)
        if not is_valid_ips:
            return False, ip_error

    return True, None


def sanitize_webhook_url(url: str) -> str:
    """
    Sanitize and normalize a webhook URL.
    
    Uses synchronous validation. Use with caution in async loops.
    """
    is_valid, error = validate_webhook_url(url)
    if not is_valid:
        raise ValueError(f"Invalid webhook URL: {error}")

    # Parse and reconstruct to normalize
    parsed = urlparse(url)

    # Remove default ports
    port = parsed.port
    if (parsed.scheme == "http" and port == 80) or \
       (parsed.scheme == "https" and port == 443):
        # Remove default port from netloc
        netloc = parsed.hostname
    else:
        netloc = parsed.netloc

    # Reconstruct URL
    normalized = f"{parsed.scheme}://{netloc}{parsed.path}"

    if parsed.query:
        normalized += f"?{parsed.query}"

    if parsed.fragment:
        normalized += f"#{parsed.fragment}"

    return normalized
