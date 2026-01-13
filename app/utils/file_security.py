"""
File Security Utilities

Provides functions to validate file uploads and prevent path traversal attacks.
"""

import os
import re
import magic
from pathlib import Path
from typing import Optional, Tuple


# Allowed file extensions and their corresponding MIME types
ALLOWED_FILE_TYPES = {
    ".pdf": ["application/pdf"],
    ".docx": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ],
    ".doc": ["application/msword"],
    ".txt": ["text/plain"],
    ".md": ["text/markdown", "text/plain"],
    ".csv": ["text/csv", "text/plain"],
    ".json": ["application/json", "text/plain"],
    ".xlsx": [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ],
    ".xls": ["application/vnd.ms-excel"],
}

# Maximum file size in bytes (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent path traversal and other attacks.

    Args:
        filename: The filename to sanitize
        max_length: Maximum allowed filename length

    Returns:
        Sanitized filename safe for filesystem operations

    Raises:
        ValueError: If filename is invalid or contains dangerous patterns
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Filename must be a non-empty string")

    # Get basename to remove any directory components
    filename = os.path.basename(filename)

    # Check for path traversal attempts
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise ValueError("Filename contains path traversal patterns")

    # Check for null bytes
    if "\x00" in filename:
        raise ValueError("Filename contains null bytes")

    # Remove or replace dangerous characters
    # Allow: alphanumeric, underscore, dash, dot, space
    filename = re.sub(r'[^\w\s\-\.]', '_', filename)

    # Collapse multiple dots (could be used for extension confusion)
    filename = re.sub(r'\.{2,}', '.', filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')

    # Enforce length limit
    if len(filename) > max_length:
        # Keep extension if present
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext

    # Ensure filename is not empty after sanitization
    if not filename:
        raise ValueError("Filename is empty after sanitization")

    # Prevent reserved filenames on Windows
    reserved_names = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3",
                      "COM4", "LPT1", "LPT2", "LPT3"}
    name_without_ext = os.path.splitext(filename)[0].upper()
    if name_without_ext in reserved_names:
        raise ValueError(f"Filename '{filename}' is a reserved system name")

    return filename


def validate_file_path(base_dir: str, filename: str) -> str:
    """
    Validate that a file path stays within the base directory.

    Args:
        base_dir: The base directory that files must be within
        filename: The filename to validate

    Returns:
        Absolute path to the file

    Raises:
        ValueError: If path escapes base directory
    """
    # Sanitize filename first
    safe_filename = sanitize_filename(filename)

    # Resolve absolute paths
    base_path = Path(base_dir).resolve()
    file_path = (base_path / safe_filename).resolve()

    # Ensure file_path is within base_path
    try:
        file_path.relative_to(base_path)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: file would be outside {base_dir}"
        )

    return str(file_path)


def validate_file_type(
    file_path: str,
    filename: str,
    allowed_extensions: Optional[list] = None
) -> Tuple[str, str]:
    """
    Validate file type using both extension and magic bytes (MIME type).

    Args:
        file_path: Path to the file to validate
        filename: Original filename
        allowed_extensions: List of allowed extensions (defaults to ALLOWED_FILE_TYPES)

    Returns:
        Tuple of (extension, mime_type)

    Raises:
        ValueError: If file type is not allowed or extension/MIME mismatch
    """
    if allowed_extensions is None:
        allowed_extensions = list(ALLOWED_FILE_TYPES.keys())

    # Check file size
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {file_size} bytes "
            f"(max: {MAX_FILE_SIZE} bytes)"
        )

    if file_size == 0:
        raise ValueError("File is empty")

    # Check extension
    extension = os.path.splitext(filename)[1].lower()
    if extension not in allowed_extensions:
        raise ValueError(
            f"File type '{extension}' not allowed. "
            f"Allowed types: {', '.join(allowed_extensions)}"
        )

    # Validate MIME type using python-magic (libmagic)
    try:
        mime = magic.Magic(mime=True)
        detected_mime = mime.from_file(file_path)
    except Exception as e:
        raise ValueError(f"Failed to detect file MIME type: {e}")

    # Check if detected MIME matches expected MIME for extension
    expected_mimes = ALLOWED_FILE_TYPES.get(extension, [])
    if expected_mimes and detected_mime not in expected_mimes:
        # Some tolerance for text files
        if extension in [".txt", ".md", ".csv", ".json"]:
            if not detected_mime.startswith("text/"):
                raise ValueError(
                    f"MIME type mismatch: file has extension {extension} "
                    f"but MIME type is {detected_mime}"
                )
        else:
            raise ValueError(
                f"MIME type mismatch: file has extension {extension} "
                f"(expected {expected_mimes}) but MIME type is {detected_mime}"
            )

    return extension, detected_mime


def is_safe_path(base_dir: str, filepath: str) -> bool:
    """
    Check if a filepath is safe (within base directory).

    Args:
        base_dir: Base directory path
        filepath: File path to check

    Returns:
        True if path is safe, False otherwise
    """
    try:
        base_path = Path(base_dir).resolve()
        file_path = Path(filepath).resolve()
        file_path.relative_to(base_path)
        return True
    except (ValueError, OSError):
        return False
