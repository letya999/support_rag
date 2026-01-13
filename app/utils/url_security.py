"""
URL Security Utilities

Provides functions to validate URLs for webhooks and prevent SSRF attacks.
Designed for internal network deployments - allows private IPs but blocks
localhost and cloud metadata endpoints.
"""

import ipaddress
import re
from typing import Optional
from urllib.parse import urlparse
import socket


# Blocked IP ranges (localhost, link-local, cloud metadata)
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Localhost
    ipaddress.ip_network("::1/128"),           # IPv6 localhost
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / AWS metadata
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

# Allowed protocols
ALLOWED_PROTOCOLS = ["http", "https"]


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


def validate_webhook_url(url: str, allow_private: bool = True) -> tuple[bool, Optional[str]]:
    """
    Validate a webhook URL to prevent SSRF attacks.

    For internal network deployments:
    - Blocks localhost (127.0.0.1, ::1)
    - Blocks cloud metadata endpoints (169.254.x.x)
    - Allows private IPs (10.x.x.x, 192.168.x.x) since it's internal network
    - Blocks file://, ftp://, and other non-HTTP protocols

    Args:
        url: URL to validate
        allow_private: Whether to allow private IP ranges (default: True for internal networks)

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, "reason for rejection")
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

    # Check protocol
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        return False, f"Protocol '{parsed.scheme}' not allowed. Use http or https"

    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a hostname"

    # Block obvious localhost references
    localhost_patterns = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "0:0:0:0:0:0:0:1",
    ]

    if hostname.lower() in localhost_patterns:
        return False, "Localhost URLs are not allowed for security reasons"

    # Resolve hostname to IP and check
    try:
        # Get all IPs for the hostname
        addr_info = socket.getaddrinfo(hostname, None)
        ips = set(info[4][0] for info in addr_info)

        for ip_str in ips:
            # Check if IP is in blocked ranges
            if is_ip_blocked(ip_str):
                return False, f"URL resolves to blocked IP address: {ip_str}"

            # For internal networks, we allow private IPs
            # But you can disable this with allow_private=False
            if not allow_private:
                try:
                    ip = ipaddress.ip_address(ip_str)
                    if ip.is_private:
                        return False, f"Private IP addresses not allowed: {ip_str}"
                except ValueError:
                    pass

    except socket.gaierror as e:
        return False, f"Failed to resolve hostname: {str(e)}"
    except Exception as e:
        return False, f"Error validating URL: {str(e)}"

    # Additional check: Prevent DNS rebinding attacks with numeric IPs in hostname
    # If hostname is an IP, validate it directly
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
        if is_ip_blocked(hostname):
            return False, f"IP address is blocked: {hostname}"

    # Check for suspicious patterns
    suspicious_patterns = [
        r'@',  # User info in URL (http://evil.com@internal.com)
        r'\.\.',  # Directory traversal
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, url):
            return False, f"URL contains suspicious pattern: {pattern}"

    return True, None


def sanitize_webhook_url(url: str) -> str:
    """
    Sanitize and normalize a webhook URL.

    Args:
        url: URL to sanitize

    Returns:
        Normalized URL

    Raises:
        ValueError: If URL is invalid
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
