"""Utility functions for working with alert fingerprints."""

import re

def is_hashed_fingerprint(fingerprint: str) -> bool:
    """
    Check if a fingerprint appears to be a SHA256 hash.
    
    Args:
        fingerprint: The fingerprint to check
        
    Returns:
        bool: True if the fingerprint appears to be a SHA256 hash, False otherwise
    """
    # SHA256 hashes are 64 characters long and contain only hex digits
    SHA256_PATTERN = re.compile(r'^[a-f0-9]{64}$')
    return bool(SHA256_PATTERN.match(fingerprint)) 