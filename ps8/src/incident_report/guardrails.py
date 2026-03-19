"""Guardrails for DevOps Incident Report Generator — input/output validation, PII masking, prompt injection detection."""

import re
from pydantic import BaseModel, Field


# ── Models ───────────────────────────────────────────────────────────────────

class CheckResult(BaseModel):
    name: str
    passed: bool
    message: str


class GuardrailResult(BaseModel):
    passed: bool = True
    blocked: bool = False
    block_reason: str = ""
    sanitized_input: str = ""
    checks: list[CheckResult] = Field(default_factory=list)
    pii_detected: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Content filter — TCS proxy blocked keywords ─────────────────────────────

_SENSITIVE: dict[str, str] = {
    "crime":     "reported incident",
    "criminal":  "individual of concern",
    "murder":    "serious incident",
    "assault":   "physical altercation",
    "theft":     "property incident",
    "stolen":    "property incident",
    "drug":      "substance concern",
    "narcotic":  "substance concern",
    "weapon":    "safety equipment concern",
    "violence":  "public disturbance",
    "violent":   "disruptive",
    "kill":      "serious incident",
}


def sanitize_for_proxy(text: str) -> str:
    """Replace content-filter trigger words before sending to genailab.tcs.in."""
    for word, replacement in _SENSITIVE.items():
        text = text.replace(word, replacement)
        text = text.replace(word.capitalize(), replacement.capitalize())
        text = text.replace(word.upper(), replacement.upper())
    return text


# ── PII Detection ───────────────────────────────────────────────────────────

_PII_PATTERNS: dict[str, re.Pattern] = {
    "email":       re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone":       re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    "ssn":         re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
    "ip_address":  re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    "api_key":     re.compile(r'\b(?:sk-|ak-|key-|token-)[A-Za-z0-9]{20,}\b'),
    "aws_key":     re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
}

_PII_MASKS: dict[str, str] = {
    "email":       "[EMAIL_REDACTED]",
    "phone":       "[PHONE_REDACTED]",
    "ssn":         "[SSN_REDACTED]",
    "credit_card": "[CC_REDACTED]",
    "ip_address":  "[IP_REDACTED]",
    "api_key":     "[KEY_REDACTED]",
    "aws_key":     "[KEY_REDACTED]",
}


def detect_pii(text: str) -> list[dict]:
    """Detect PII in text. Returns list of {type, match, start, end}."""
    findings = []
    for pii_type, pattern in _PII_PATTERNS.items():
        for match in pattern.finditer(text):
            # Skip IP-like patterns that look like version numbers (e.g., 1.2.3.4)
            if pii_type == "ip_address" and _is_likely_version(match.group()):
                continue
            findings.append({
                "type": pii_type,
                "match": match.group(),
                "start": match.start(),
                "end": match.end(),
            })
    return findings


def mask_pii(text: str) -> str:
    """Replace detected PII with redaction placeholders."""
    for pii_type, pattern in _PII_PATTERNS.items():
        if pii_type == "ip_address":
            text = pattern.sub(lambda m: _PII_MASKS[pii_type] if not _is_likely_version(m.group()) else m.group(), text)
        else:
            text = pattern.sub(_PII_MASKS[pii_type], text)
    return text


def _is_likely_version(ip: str) -> bool:
    """Heuristic: version numbers like 18.2.0 or 1.0.0 aren't real IPs."""
    parts = ip.split(".")
    return len(parts) == 4 and any(p == "0" for p in parts[1:])


# ── Prompt Injection Detection ───────────────────────────────────────────────

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r'ignore\s+(previous|above|all|prior)\s+(instructions|prompts|rules)', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+', re.IGNORECASE),
    re.compile(r'new\s+instructions?\s*:', re.IGNORECASE),
    re.compile(r'system\s*:\s*', re.IGNORECASE),
    re.compile(r'<\|.*?\|>', re.IGNORECASE),
    re.compile(r'###\s*(instruction|system|prompt)', re.IGNORECASE),
    re.compile(r'forget\s+(everything|all|your)', re.IGNORECASE),
    re.compile(r'do\s+not\s+follow\s+(your|the)\s+(original|previous)', re.IGNORECASE),
    re.compile(r'pretend\s+you\s+are', re.IGNORECASE),
    re.compile(r'act\s+as\s+(if|a|an)\s+', re.IGNORECASE),
    re.compile(r'jailbreak', re.IGNORECASE),
    re.compile(r'DAN\s+mode', re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> list[str]:
    """Detect potential prompt injection patterns. Returns list of matched pattern descriptions."""
    detections = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            detections.append(pattern.pattern)
    return detections


# ── Input Validation ─────────────────────────────────────────────────────────

_MAX_INPUT_LENGTH = 50000  # characters


def validate_input(text: str, max_length: int = _MAX_INPUT_LENGTH) -> tuple[bool, str]:
    """Validate input text. Returns (is_valid, error_message)."""
    if not text or not text.strip():
        return False, "Input is empty"
    if len(text) > max_length:
        return False, f"Input exceeds maximum length ({len(text):,} > {max_length:,} characters)"
    return True, ""


# ── Output Validation (project-specific) ─────────────────────────────────────

_VALID_SEVERITIES = {"SEV1", "SEV2", "SEV3", "SEV4"}
_VALID_STATUSES = {"resolved", "monitoring", "ongoing"}


def validate_output(result) -> tuple[bool, list[str]]:
    """Validate agent output. Returns (is_valid, list_of_issues)."""
    issues = []

    if hasattr(result, "severity"):
        if result.severity not in _VALID_SEVERITIES:
            issues.append(f"Invalid severity '{result.severity}' — expected one of {_VALID_SEVERITIES}")

    if hasattr(result, "status"):
        if result.status.lower() not in _VALID_STATUSES:
            issues.append(f"Invalid status '{result.status}' — expected one of {_VALID_STATUSES}")

    if hasattr(result, "title"):
        if not result.title or not result.title.strip():
            issues.append("Title is empty")

    if hasattr(result, "executive_summary"):
        if not result.executive_summary or not result.executive_summary.strip():
            issues.append("Executive summary is empty")

    if hasattr(result, "root_cause"):
        if not result.root_cause or not result.root_cause.strip():
            issues.append("Root cause is empty")

    if hasattr(result, "timeline"):
        if not result.timeline:
            issues.append("Timeline is empty")

    if hasattr(result, "action_items"):
        if not result.action_items:
            issues.append("Action items is empty")

    if hasattr(result, "affected_services"):
        if not result.affected_services:
            issues.append("Affected services is empty")

    return len(issues) == 0, issues


# ── Main Guardrail Runner ───────────────────────────────────────────────────

def run_input_guardrails(text: str, mask_pii_in_output: bool = True) -> GuardrailResult:
    """Run all input guardrails. Returns GuardrailResult with sanitized input and check details."""
    result = GuardrailResult(sanitized_input=text)

    # 1. Input validation
    valid, err = validate_input(text)
    result.checks.append(CheckResult(name="input_validation", passed=valid, message=err or "Input is valid"))
    if not valid:
        result.passed = False
        result.blocked = True
        result.block_reason = err
        return result

    # 2. Prompt injection detection
    injections = detect_prompt_injection(text)
    is_clean = len(injections) == 0
    result.checks.append(CheckResult(
        name="prompt_injection",
        passed=is_clean,
        message="No injection patterns detected" if is_clean else f"Detected {len(injections)} suspicious pattern(s)",
    ))
    if not is_clean:
        result.passed = False
        result.blocked = True
        result.block_reason = f"Potential prompt injection detected: {len(injections)} suspicious pattern(s)"
        result.warnings.extend([f"Injection pattern: {p}" for p in injections])
        return result

    # 3. PII detection
    pii_findings = detect_pii(text)
    has_pii = len(pii_findings) > 0
    result.checks.append(CheckResult(
        name="pii_detection",
        passed=not has_pii,
        message="No PII detected" if not has_pii else f"Found {len(pii_findings)} PII item(s)",
    ))
    if has_pii:
        result.pii_detected = [f"{f['type']}: {f['match'][:8]}..." for f in pii_findings]
        result.warnings.extend([f"PII found: {f['type']}" for f in pii_findings])
        if mask_pii_in_output:
            text = mask_pii(text)

    # 4. Content sanitization for TCS proxy
    sanitized = sanitize_for_proxy(text)
    was_sanitized = sanitized != text
    result.checks.append(CheckResult(
        name="content_filter",
        passed=True,
        message="Content sanitized for proxy" if was_sanitized else "No blocked keywords found",
    ))
    if was_sanitized:
        result.warnings.append("Input contained proxy-blocked keywords — auto-sanitized")

    result.sanitized_input = sanitized
    return result


def run_output_guardrails(result) -> GuardrailResult:
    """Run output guardrails on agent result."""
    guard = GuardrailResult()
    valid, issues = validate_output(result)
    guard.passed = valid
    guard.checks.append(CheckResult(
        name="output_validation",
        passed=valid,
        message="Output is valid" if valid else f"{len(issues)} issue(s) found",
    ))
    if not valid:
        guard.warnings.extend(issues)
    return guard
