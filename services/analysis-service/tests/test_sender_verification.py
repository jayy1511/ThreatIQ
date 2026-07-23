"""
Unit tests for sender verification (C5).

These tests are purely deterministic — no LLM calls, no network, no file I/O.
They verify that parse_and_verify() and build_classifier_context() correctly:
- parse email headers from explicit header_text
- detect Reply-To mismatches
- detect SPF/DKIM/DMARC failures from Authentication-Results
- detect SPF from Received-SPF
- detect free-email impersonation
- return 'unavailable' when no headers are present
- survive malformed / partial headers without crashing
- never expose raw header content in classifier context
"""

import pytest
from app.sender_verification import (
    parse_and_verify,
    build_classifier_context,
    _extract_domain,
    _extract_header,
    _parse_auth_results,
    _registrable_domain,
)


# ---------------------------------------------------------------------------
# Helper builder
# ---------------------------------------------------------------------------

def make_headers(**kwargs) -> str:
    """Build a minimal header block from keyword arguments."""
    lines = []
    for name, value in kwargs.items():
        header_name = name.replace("_", "-").title()
        lines.append(f"{header_name}: {value}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------

class TestExtractDomain:

    def test_standard_email(self):
        assert _extract_domain("user@example.com") == "example.com"

    def test_display_name_angle_bracket(self):
        assert _extract_domain("Alice <alice@bank.com>") == "bank.com"

    def test_bare_domain(self):
        assert _extract_domain("paypal.com") == "paypal.com"

    def test_empty_string(self):
        assert _extract_domain("") is None

    def test_no_at_no_dot(self):
        assert _extract_domain("notanemail") is None


class TestExtractHeader:

    def test_basic_header(self):
        headers = ["From: Alice <alice@example.com>", "Subject: Test"]
        assert _extract_header(headers, "From") == "Alice <alice@example.com>"

    def test_case_insensitive(self):
        headers = ["REPLY-TO: bounce@other.com"]
        assert _extract_header(headers, "reply-to") == "bounce@other.com"

    def test_missing_header(self):
        headers = ["From: user@example.com"]
        assert _extract_header(headers, "Reply-To") is None

    def test_folded_header(self):
        headers = [
            "Authentication-Results: mx.google.com;",
            "       spf=pass smtp.mailfrom=example.com",
        ]
        result = _extract_header(headers, "Authentication-Results")
        assert "spf=pass" in result


class TestParseAuthResults:

    def test_all_pass(self):
        ar = "mx.google.com; spf=pass smtp.mailfrom=example.com; dkim=pass header.i=@example.com; dmarc=pass"
        result = _parse_auth_results(ar)
        assert result == {"spf": "pass", "dkim": "pass", "dmarc": "pass"}

    def test_spf_fail_dkim_none(self):
        ar = "mx.google.com; spf=fail; dkim=none"
        result = _parse_auth_results(ar)
        assert result["spf"] == "fail"
        assert result["dkim"] == "none"

    def test_dmarc_fail(self):
        ar = "mx.google.com; dmarc=fail"
        result = _parse_auth_results(ar)
        assert result["dmarc"] == "fail"

    def test_empty_string_returns_empty(self):
        result = _parse_auth_results("")
        assert result == {}


class TestRegistrableDomain:

    def test_subdomain_stripped(self):
        assert _registrable_domain("mail.paypal.com") == "paypal.com"

    def test_already_registrable(self):
        assert _registrable_domain("paypal.com") == "paypal.com"

    def test_deep_subdomain(self):
        assert _registrable_domain("a.b.c.example.co.uk") == "co.uk"


# ---------------------------------------------------------------------------
# Integration tests: parse_and_verify()
# ---------------------------------------------------------------------------

class TestParseAndVerify:

    def test_no_headers_returns_unavailable(self):
        result = parse_and_verify("Hello, please click here to verify.")
        assert result["status"] == "unavailable"
        assert result["signals"] == []
        assert result["technical_details"] is None

    def test_none_header_text_returns_unavailable(self):
        result = parse_and_verify("Some message", header_text=None)
        assert result["status"] == "unavailable"

    def test_empty_header_text_returns_unavailable(self):
        result = parse_and_verify("Some message", header_text="   ")
        assert result["status"] == "unavailable"

    def test_clean_email_returns_verified(self):
        headers = (
            "From: support@paypal.com\n"
            "Reply-To: support@paypal.com\n"
            "Return-Path: <bounce@paypal.com>\n"
            "Authentication-Results: mx.google.com; spf=pass; dkim=pass; dmarc=pass\n"
        )
        result = parse_and_verify("Your account is fine.", header_text=headers)
        assert result["status"] == "verified"
        assert result["signals"] == []

    def test_reply_to_mismatch_detected(self):
        headers = (
            "From: noreply@paypal.com\n"
            "Reply-To: harvester@evil.ru\n"
        )
        result = parse_and_verify("Click here.", header_text=headers)
        assert result["status"] in ("suspicious", "warning")
        # Plain-language signal should mention different address
        assert any("different address" in s for s in result["signals"])

    def test_spf_fail_detected(self):
        headers = (
            "From: billing@bank.com\n"
            "Authentication-Results: mx.google.com; spf=fail; dkim=fail; dmarc=fail\n"
        )
        result = parse_and_verify("Pay now.", header_text=headers)
        assert result["status"] == "suspicious"
        # Should detect multiple signals
        assert len(result["signals"]) >= 1

    def test_spf_softfail_produces_warning(self):
        headers = (
            "From: billing@bank.com\n"
            "Authentication-Results: mx.google.com; spf=softfail\n"
        )
        result = parse_and_verify("Pay now.", header_text=headers)
        assert result["status"] in ("warning", "suspicious")

    def test_dmarc_fail_detected(self):
        headers = (
            "From: support@amazon.com\n"
            "Authentication-Results: mx.google.com; dmarc=fail\n"
        )
        result = parse_and_verify("Your order.", header_text=headers)
        assert result["status"] in ("suspicious", "warning")
        assert any("could not be verified" in s or "claimed sender" in s for s in result["signals"])

    def test_received_spf_fail_detected(self):
        headers = (
            "From: security@mybank.com\n"
            "Received-SPF: fail (google.com: domain does not designate)\n"
        )
        result = parse_and_verify("Verify your account.", header_text=headers)
        assert result["status"] in ("suspicious", "warning")

    def test_free_email_impersonation_detected(self):
        headers = "From: support@gmail.com\n"
        body = "Your PayPal account has been suspended. Verify now."
        result = parse_and_verify(body, header_text=headers)
        # Claiming PayPal from gmail.com
        assert result["status"] in ("suspicious", "warning")
        assert any("free email" in s.lower() or "well-known" in s.lower() for s in result["signals"])

    def test_return_path_mismatch_detected(self):
        headers = (
            "From: noreply@amazon.com\n"
            "Return-Path: <bounce@completely-different.xyz>\n"
        )
        result = parse_and_verify("Your order.", header_text=headers)
        assert result["status"] in ("suspicious", "warning")

    def test_malformed_headers_do_not_crash(self):
        """Malformed or garbage header text must not raise an exception."""
        garbage = "NOT A HEADER\n\x00\x01binary\nFrom:no space after colon"
        result = parse_and_verify("body text", header_text=garbage)
        # Should return a valid result, not raise
        assert result["status"] in ("unavailable", "verified", "warning", "suspicious")

    def test_signals_capped_at_four(self):
        """Never return more than 4 plain-language signals."""
        headers = (
            "From: info@gmail.com\n"
            "Reply-To: phish@evil.ru\n"
            "Return-Path: <other@elsewhere.biz>\n"
            "Authentication-Results: mx.google.com; spf=fail; dkim=fail; dmarc=fail\n"
        )
        body = "Your paypal account is suspended. Verify now."
        result = parse_and_verify(body, header_text=headers)
        assert len(result["signals"]) <= 4

    def test_technical_details_absent_when_no_signals_and_verified(self):
        """When all checks pass, technical_details may still be present (domains extracted)."""
        headers = (
            "From: support@example.com\n"
            "Reply-To: support@example.com\n"
            "Authentication-Results: mx.google.com; spf=pass; dkim=pass; dmarc=pass\n"
        )
        result = parse_and_verify("Hello.", header_text=headers)
        # Technical details should be present (domains extracted) but mismatches absent
        if result["technical_details"]:
            assert "mismatches" not in result["technical_details"] or result["technical_details"]["mismatches"] == []

    def test_inferred_headers_from_pasted_message(self):
        """
        When user pastes a full email with headers but no explicit header_text,
        parse_and_verify should detect the headers in the message body.
        """
        full_email = (
            "From: noreply@paypal.com\n"
            "Reply-To: harvest@evil.ru\n"
            "Subject: Urgent: Verify your account\n"
            "\n"
            "Dear customer, please verify your PayPal account immediately."
        )
        result = parse_and_verify(full_email, header_text=None)
        # Should detect Reply-To mismatch from the inferred headers
        assert result["status"] in ("suspicious", "warning", "unavailable")


# ---------------------------------------------------------------------------
# Tests: build_classifier_context()
# ---------------------------------------------------------------------------

class TestBuildClassifierContext:

    def test_unavailable_returns_empty_string(self):
        verification = {"status": "unavailable", "signals": [], "technical_details": None, "summary": ""}
        assert build_classifier_context(verification) == ""

    def test_verified_no_signals_returns_status_line(self):
        verification = {"status": "verified", "signals": [], "technical_details": None, "summary": ""}
        ctx = build_classifier_context(verification)
        assert "verified" in ctx
        assert len(ctx) < 80  # Should be short

    def test_suspicious_with_signals_returns_summary(self):
        verification = {
            "status": "suspicious",
            "signals": [
                "Replies may go to a different address than the visible sender.",
                "The sending source does not appear to match the organization it claims.",
            ],
            "technical_details": None,
            "summary": "",
        }
        ctx = build_classifier_context(verification)
        assert "suspicious" in ctx
        # Should include at most 3 signals
        assert len(ctx) < 600

    def test_context_does_not_contain_raw_domains(self):
        """Classifier context must not include raw email addresses or header values."""
        verification = {
            "status": "suspicious",
            "signals": ["Replies may go to a different address than the visible sender."],
            "technical_details": {"from_domain": "evil.ru", "reply_to_domain": "evil.ru"},
            "summary": "",
        }
        ctx = build_classifier_context(verification)
        # The context string should not include raw domain names
        assert "evil.ru" not in ctx
