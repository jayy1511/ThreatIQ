"""
Data redaction utility.

Provides functions to redact sensitive PII (emails, phone numbers, tokens, etc.)
from text before it is logged, sent to external services (like LLMs for evaluation),
or exposed via administrative APIs.
"""

import re

# Regex patterns for common sensitive information
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
# Simple phone number pattern: matches international and common formats
PHONE_PATTERN = re.compile(r'\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
# Token/API Key pattern: matches common keywords followed by base64-like or hex strings
TOKEN_PATTERN = re.compile(r'(?:api_key|token|auth|password|secret|key|pwd)[\s:=]+[\'"]?([a-zA-Z0-9_\-\.]{16,})[\'"]?', re.IGNORECASE)
# Credit card pattern: matches 13-19 digit numbers, optionally separated by spaces or dashes
CC_PATTERN = re.compile(r'\b(?:\d[ -]*?){13,19}\b')

def redact_sensitive_info(text: str) -> str:
    """
    Scans the given text and replaces sensitive patterns with placeholders.
    
    Args:
        text: The raw input string
        
    Returns:
        The redacted string
    """
    if not text:
        return text

    # Redact Emails
    text = EMAIL_PATTERN.sub('[REDACTED_EMAIL]', text)
    
    # Redact Phone Numbers
    text = PHONE_PATTERN.sub('[REDACTED_PHONE]', text)
    
    # Redact Credit Cards (basic)
    text = CC_PATTERN.sub('[REDACTED_CC]', text)
    
    # Redact potential Tokens/Secrets
    # Only replace the actual token part, preserve the key name
    text = TOKEN_PATTERN.sub(r'\g<0>'.replace(r'\g<1>', '[REDACTED_TOKEN]'), text)
    # The above replace might be tricky with regex backreferences. 
    # Let's do it safer:
    text = TOKEN_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), '[REDACTED_SECRET]'), text)
    
    return text
