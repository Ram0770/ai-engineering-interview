"""Prompt injection defenses and input sanitization."""

import re

# Patterns commonly used in LLM jailbreaks and indirect prompt injection attacks
INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b"),
    re.compile(r"(?i)\bignore\s+(?:the\s+)?above\s+instructions\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(?:in\s+)?(?:developer|dan|jailbreak)\s+mode\b"),
    re.compile(r"(?i)\boutput\s+(?:all\s+)?(?:system|api|confidential|private)\s+keys?\b"),
    re.compile(r"(?i)\bprint\s+(?:the\s+)?system\s+prompt\b"),
    re.compile(r"(?i)<\s*system\s*>"),
    re.compile(r"(?i)\[\s*system\s*\]"),
    re.compile(r"(?i)assistant\s*:\s*"),
]


class PromptInjectionError(ValueError):
    """Raised when an incoming post or payload contains prompt injection payloads."""

    pass


def scan_for_prompt_injection(text: str) -> tuple[bool, str]:
    """Scans text for known prompt injection and jailbreak payloads.

    Returns:
        (is_safe: bool, reason: str)
    """
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, f"Potential prompt injection pattern detected: '{match.group(0)}'"

    return True, "Safe"


def sanitize_post_content(text: str) -> str:
    """Escapes control delimiters to ensure post content remains data and not prompt instructions."""
    is_safe, reason = scan_for_prompt_injection(text)
    if not is_safe:
        raise PromptInjectionError(reason)

    # Sanitize markdown formatting and system delimiters
    sanitized = text.replace("```", "'''")
    return sanitized.strip()
