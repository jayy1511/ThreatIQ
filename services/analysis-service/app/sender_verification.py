"""
Sender Verification Service (C5)

Deterministic, LLM-free analysis of email header metadata.
Produces a SenderVerification result used to:
  1. Inject a concise risk summary into the AI classifier prompt.
  2. Surface a plain-language card in the frontend UI.

Privacy rules:
  - Never logs raw header text.
  - Never includes sender email addresses in log lines.
  - technical_details is only populated for use in the API response;
    it is never written to the application log.
"""

from __future__ import annotations

import re
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Free/consumer webmail domains that cannot claim enterprise identity
_FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com",
    "hotmail.co.uk", "outlook.com", "live.com", "msn.com", "aol.com",
    "protonmail.com", "icloud.com", "me.com", "mac.com",
    "yandex.com", "yandex.ru", "mail.ru", "zoho.com",
})

# Domains from large institutions that free-webmail senders cannot validly claim
_ENTERPRISE_CLAIM_KEYWORDS = [
    "bank", "paypal", "amazon", "microsoft", "apple", "google", "facebook",
    "instagram", "irs", "gov", "hmrc", "fedex", "ups", "dhl", "netflix",
    "spotify", "ebay", "chase", "wellsfargo", "barclays", "hsbc",
]

# Regex to extract domain from RFC 5321-style address e.g. "Display Name <addr@domain.com>"
_EMAIL_ADDR_RE = re.compile(r"[\w.+%-]+@([\w.-]+\.[a-zA-Z]{2,})")

# Regex to find all http/https URLs in body text
_URL_RE = re.compile(r"https?://([a-zA-Z0-9._-]+)", re.IGNORECASE)

# Maximum header_text length the parser will process (chars, not bytes).
# Anything beyond this is silently truncated to avoid DoS via huge inputs.
MAX_HEADER_TEXT_CHARS = 4_000


# ---------------------------------------------------------------------------
# Domain extraction helpers
# ---------------------------------------------------------------------------

def _extract_domain(address: str) -> Optional[str]:
    """
    Extract the registrable domain from an email address or bare domain.
    Returns lowercase domain, or None if unparseable.
    """
    if not address:
        return None
    address = address.strip()

    # Try RFC 2822 angle-bracket format first
    match = _EMAIL_ADDR_RE.search(address)
    if match:
        return match.group(1).lower()

    # Bare domain / IP
    if "@" not in address and "." in address:
        return address.lower()

    return None


def _extract_header(header_lines: list[str], name: str) -> Optional[str]:
    """
    Case-insensitive extraction of the first matching header value.
    Handles folded headers (RFC 5322 continuation lines).
    """
    name_lower = name.lower() + ":"
    result_parts: list[str] = []
    capturing = False

    for line in header_lines:
        if capturing:
            # Folded continuation line starts with whitespace
            if line and line[0] in (" ", "\t"):
                result_parts.append(line.strip())
                continue
            else:
                # New header — stop capturing
                break
        if line.lower().startswith(name_lower):
            value = line[len(name_lower):].strip()
            result_parts.append(value)
            capturing = True

    return " ".join(result_parts) if result_parts else None


def _parse_auth_results(auth_results: str) -> dict[str, str]:
    """
    Parse an Authentication-Results header into a dict of
    {mechanism: result}.  e.g. {"spf": "pass", "dkim": "fail", "dmarc": "none"}
    """
    results: dict[str, str] = {}
    for mechanism in ("spf", "dkim", "dmarc"):
        pattern = re.compile(
            rf"\b{mechanism}=([a-zA-Z]+)", re.IGNORECASE
        )
        m = pattern.search(auth_results)
        if m:
            results[mechanism] = m.group(1).lower()
    return results


def _parse_received_spf(received_spf: str) -> Optional[str]:
    """Extract the result word from a Received-SPF header."""
    m = re.match(r"\s*(pass|fail|softfail|neutral|none|temperror|permerror)", received_spf, re.IGNORECASE)
    return m.group(1).lower() if m else None


def _registrable_domain(domain: str) -> str:
    """
    Reduce a domain to its registrable part for comparison.
    e.g. mail.paypal.com -> paypal.com
    This is a best-effort simplification; no PSL library is required.
    """
    parts = domain.strip(".").split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def _link_domains_from_body(body: str) -> list[str]:
    """Extract unique link destination domains from the message body."""
    seen: set[str] = set()
    result: list[str] = []
    for match in _URL_RE.finditer(body):
        domain = match.group(1).lower()
        if domain not in seen:
            seen.add(domain)
            result.append(domain)
    return result


# ---------------------------------------------------------------------------
# Plain-language translation helpers
# ---------------------------------------------------------------------------

_STATUS_SUMMARIES = {
    "verified":    "The sender information appears consistent.",
    "warning":     "One or more sender signals raised a concern.",
    "suspicious":  "Multiple sender signals raised concerns about this message.",
    "unavailable": "No technical sender information was available for this message.",
}


def _translate_signal(raw: str) -> str:
    """Map internal signal keys to user-friendly plain language."""
    _MAP = {
        "reply_to_mismatch":       "Replies may go to a different address than the visible sender.",
        "return_path_mismatch":    "The sending path does not match the claimed sender address.",
        "spf_fail":                "The sending source does not appear to match the organization it claims to represent.",
        "spf_softfail":            "The sending source could not be fully verified for this organization.",
        "dkim_fail":               "This email's digital signature could not be verified.",
        "dmarc_fail":              "This email could not be verified as coming from the claimed sender.",
        "free_email_impersonation":"A free email address is claiming to represent a well-known organization.",
        "link_domain_mismatch":    "Links in the message lead to domains unrelated to the claimed sender.",
    }
    return _MAP.get(raw, raw.replace("_", " ").capitalize() + ".")


# ---------------------------------------------------------------------------
# Core verification logic
# ---------------------------------------------------------------------------

def _verify_headers(
    header_text: str,
    body: str,
) -> dict:
    """
    Parse header_text and run deterministic checks.

    Args:
        header_text: Raw email header block (may be partial).
        body: The message body text (used for link domain extraction).

    Returns:
        A sender_verification dict with status, summary, signals, technical_details.
    """
    # Truncate to prevent DoS
    header_text = header_text[:MAX_HEADER_TEXT_CHARS]

    lines = header_text.splitlines()

    # Extract relevant header values
    from_val        = _extract_header(lines, "From")
    reply_to_val    = _extract_header(lines, "Reply-To")
    return_path_val = _extract_header(lines, "Return-Path")
    auth_results    = _extract_header(lines, "Authentication-Results")
    received_spf    = _extract_header(lines, "Received-SPF")

    from_domain        = _extract_domain(from_val or "") if from_val else None
    reply_to_domain    = _extract_domain(reply_to_val or "") if reply_to_val else None
    return_path_domain = _extract_domain(return_path_val or "") if return_path_val else None

    auth: dict[str, str] = {}
    if auth_results:
        auth = _parse_auth_results(auth_results)

    spf_result: Optional[str] = auth.get("spf")
    if not spf_result and received_spf:
        spf_result = _parse_received_spf(received_spf)

    dkim_result  = auth.get("dkim")
    dmarc_result = auth.get("dmarc")

    link_domains = _link_domains_from_body(body)

    # ── Run checks ────────────────────────────────────────────────────────────
    raw_signals: list[str] = []

    if from_domain and reply_to_domain:
        if _registrable_domain(from_domain) != _registrable_domain(reply_to_domain):
            raw_signals.append("reply_to_mismatch")

    if from_domain and return_path_domain:
        if _registrable_domain(from_domain) != _registrable_domain(return_path_domain):
            raw_signals.append("return_path_mismatch")

    if spf_result in ("fail", "hardfail"):
        raw_signals.append("spf_fail")
    elif spf_result == "softfail":
        raw_signals.append("spf_softfail")

    if dkim_result in ("fail", "none"):
        raw_signals.append("dkim_fail")

    if dmarc_result == "fail":
        raw_signals.append("dmarc_fail")

    # Free webmail impersonating enterprise
    if from_domain and _registrable_domain(from_domain) in _FREE_EMAIL_DOMAINS:
        body_lower = body.lower()
        if any(kw in body_lower for kw in _ENTERPRISE_CLAIM_KEYWORDS):
            raw_signals.append("free_email_impersonation")

    # Link domain mismatch
    if from_domain:
        from_reg = _registrable_domain(from_domain)
        mismatched_links = [
            d for d in link_domains
            if _registrable_domain(d) != from_reg
            and _registrable_domain(d) not in _FREE_EMAIL_DOMAINS
        ]
        if mismatched_links:
            raw_signals.append("link_domain_mismatch")

    # ── Determine status ──────────────────────────────────────────────────────
    high_risk = {"reply_to_mismatch", "spf_fail", "dkim_fail", "dmarc_fail", "free_email_impersonation"}
    medium_risk = {"return_path_mismatch", "spf_softfail", "link_domain_mismatch"}

    has_high   = any(s in high_risk for s in raw_signals)
    has_medium = any(s in medium_risk for s in raw_signals)
    signal_count = len(raw_signals)

    if signal_count == 0:
        status = "verified"
    elif signal_count >= 2 or has_high:
        status = "suspicious"
    elif has_medium:
        status = "warning"
    else:
        status = "warning"

    plain_signals = [_translate_signal(s) for s in raw_signals[:4]]

    technical_details: dict = {}
    if from_domain:
        technical_details["from_domain"] = from_domain
    if reply_to_domain:
        technical_details["reply_to_domain"] = reply_to_domain
    if return_path_domain:
        technical_details["return_path_domain"] = return_path_domain
    if spf_result:
        technical_details["spf"] = spf_result
    if dkim_result:
        technical_details["dkim"] = dkim_result
    if dmarc_result:
        technical_details["dmarc"] = dmarc_result
    if link_domains:
        technical_details["link_domains"] = link_domains[:10]
    if raw_signals:
        technical_details["mismatches"] = raw_signals

    return {
        "status":             status,
        "summary":            _STATUS_SUMMARIES[status],
        "signals":            plain_signals,
        "technical_details":  technical_details if technical_details else None,
    }


def _looks_like_headers(text: str) -> bool:
    """
    Heuristic: does the text appear to contain email headers?
    Looks for at least one RFC 5322-style "Header-Name: value" line.
    """
    header_line_re = re.compile(r"^[A-Za-z\-]{2,}:\s+\S", re.MULTILINE)
    return bool(header_line_re.search(text[:2_000]))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_and_verify(
    message: str,
    header_text: Optional[str] = None,
) -> dict:
    """
    Entry point for sender verification.

    Args:
        message:     The raw message text (may include pasted headers if no
                     explicit header_text is provided).
        header_text: Explicit header block, if provided separately (e.g. from
                     the frontend optional input or from Gmail API metadata).

    Returns:
        A sender_verification dict.  Always returns a safe result — never raises.
    """
    try:
        if header_text and header_text.strip():
            # Explicit header block provided (frontend input or Gmail triage)
            return _verify_headers(header_text, body=message)

        # Try to detect if the message itself contains headers at the top
        # (common when users paste full email source into the text area).
        if _looks_like_headers(message):
            # Split at the first blank line to separate headers from body
            parts = re.split(r"\n\s*\n", message, maxsplit=1)
            if len(parts) == 2:
                inferred_headers, body = parts
                result = _verify_headers(inferred_headers, body=body)
                logger.info(
                    "Sender verification: inferred headers from pasted message; status=%s",
                    result.get("status"),
                )
                return result

        # No headers available
        logger.info("Sender verification: no header information available; returning unavailable")
        return {
            "status":            "unavailable",
            "summary":           _STATUS_SUMMARIES["unavailable"],
            "signals":           [],
            "technical_details": None,
        }

    except Exception as exc:
        logger.error("Sender verification failed unexpectedly: %s", exc, exc_info=True)
        return {
            "status":            "unavailable",
            "summary":           _STATUS_SUMMARIES["unavailable"],
            "signals":           [],
            "technical_details": None,
        }


def build_classifier_context(verification: dict) -> str:
    """
    Build a concise plain-text summary to inject into the classifier prompt.
    Returns an empty string when status is 'unavailable' (nothing to add).
    """
    status = verification.get("status", "unavailable")
    if status == "unavailable":
        return ""

    signals = verification.get("signals", [])
    if not signals:
        return f"Sender verification status: {status}."

    # Keep it short — at most 3 signals to avoid token bloat
    signal_list = " ".join(signals[:3])
    return f"Sender verification signals ({status}): {signal_list}"
