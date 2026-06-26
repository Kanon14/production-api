"""
Security Layer
--------------
Input sanitization, PII detection/masking, and output validation.

Typical usage in a RAG pipeline:

1. User input enters the app
2. SecurityPipeline.check_input(user_input)
3. If allowed, send cleaned input to retriever / LLM
4. LLM response returns
5. SecurityPipeline.check_output(llm_response)
6. Return cleaned response to client
"""

import re
from typing import Optional

from langsmith import traceable


class InputSanitizer:
    """
    Sanitizes user input before it reaches the LLM.

    Responsibilities:
    - Detect basic prompt injection attempts
    - Clean potentially dangerous delimiters
    - Return whether the input is safe to process

    Input:
        text: Raw user input string

    Output:
        check() -> tuple[bool, Optional[str]]
            bool: True if input is safe, False if blocked
            Optional[str]: Rejection reason if blocked, otherwise None

        clean() -> str
            Cleaned version of the input text
    """

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions\s*:",
        r"system\s*prompt",
        r"---\s*end\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(if\s+)?you",
        r"bypass\s+(all\s+)?restrictions",
        r"reveal\s+(your|the)\s+(system|instructions|prompt)",
        r"you\s+are\s+now\s+(DAN|jailbroken)",
    ]

    def __init__(self) -> None:
        # Compile regex patterns once for better performance.
        self.patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.INJECTION_PATTERNS
        ]

    def check(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Check whether the input contains prompt injection patterns.

        Args:
            text: Raw user input.

        Returns:
            tuple:
                - is_safe: True if safe, False if blocked.
                - rejection_reason: Reason string if blocked, otherwise None.
        """
        for pattern in self.patterns:
            if pattern.search(text):
                return False, "Blocked: potential prompt injection detected"

        return True, None

    def clean(self, text: str) -> str:
        """
        Clean potentially risky formatting from user input.

        This does not replace proper security checks. It only removes or softens
        common delimiter patterns that may be used to separate fake instructions.

        Args:
            text: Raw user input.

        Returns:
            Cleaned user input.
        """
        # Remove long markdown-style or prompt-boundary delimiters.
        text = re.sub(r"[-]{3,}", "", text)
        text = re.sub(r"[=]{3,}", "", text)

        # Break template-style braces to reduce accidental prompt/template injection.
        text = text.replace("{{", "{ {").replace("}}", "} }")

        return text.strip()


class PIIDetector:
    """
    Detects and masks personally identifiable information.

    This can be used:
    - Before sending input to the LLM
    - Before returning LLM output to the client

    Input:
        text: Any text string

    Output:
        detect() -> dict[str, list[str]]
            Dictionary of detected PII types and matched values.

        mask() -> str
            Text with detected PII replaced by redaction markers.
    """

    PATTERNS = {
        "email": re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),
        "phone": re.compile(
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        ),
        "ssn": re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b"
        ),
        "credit_card": re.compile(
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
        ),
    }

    MASK_MAP = {
        "email": "[EMAIL REDACTED]",
        "phone": "[PHONE REDACTED]",
        "ssn": "[SSN REDACTED]",
        "credit_card": "[CARD REDACTED]",
    }

    def detect(self, text: str) -> dict[str, list[str]]:
        """
        Detect PII values in text.

        Args:
            text: Input text to scan.

        Returns:
            Dictionary where:
                key = PII type
                value = list of matched strings

        Example:
            {
                "email": ["john@example.com"],
                "phone": ["123-456-7890"]
            }
        """
        found: dict[str, list[str]] = {}

        for pii_type, pattern in self.PATTERNS.items():
            matches = pattern.findall(text)

            if matches:
                found[pii_type] = matches

        return found

    def mask(self, text: str) -> str:
        """
        Replace detected PII values with redaction markers.

        Args:
            text: Input text.

        Returns:
            Masked text.
        """
        masked = text

        for pii_type, pattern in self.PATTERNS.items():
            replacement = self.MASK_MAP[pii_type]
            masked = pattern.sub(replacement, masked)

        return masked


class OutputValidator:
    """
    Validates LLM output before returning it to the client.

    Responsibilities:
    - Mask leaked PII
    - Block simple harmful output patterns

    Input:
        output: Raw LLM response

    Output:
        tuple[str, list[str]]
            - cleaned_output: Safe response to return
            - warnings: Security notes generated during validation
    """

    HARMFUL_PATTERNS = [
        re.compile(r"here('s| is) (how|the way) to (hack|steal|attack)", re.I),
        re.compile(r"password\s+is\s+", re.I),
        re.compile(r"api[_\s]?key\s*[:=]", re.I),
    ]

    BLOCKED_RESPONSE = "[Response blocked: potentially harmful content]"

    def __init__(self) -> None:
        self.pii_detector = PIIDetector()

    def validate(self, output: str) -> tuple[str, list[str]]:
        """
        Validate and clean model output.

        Args:
            output: Raw LLM-generated response.

        Returns:
            tuple:
                - cleaned_output: Masked or blocked response.
                - warnings: List of validation warnings.
        """
        warnings: list[str] = []

        # Step 1: Detect and mask PII leakage.
        pii_found = self.pii_detector.detect(output)

        if pii_found:
            output = self.pii_detector.mask(output)
            warnings.append(f"PII masked in output: {list(pii_found.keys())}")

        # Step 2: Block harmful output patterns.
        for pattern in self.HARMFUL_PATTERNS:
            if pattern.search(output):
                output = self.BLOCKED_RESPONSE
                warnings.append("Harmful content blocked")
                break

        return output, warnings


class SecurityPipeline:
    """
    Full security pipeline for user input and LLM output.

    This class combines:
    - InputSanitizer
    - PIIDetector
    - OutputValidator

    Input flow:
        raw_user_input
            -> check injection
            -> clean delimiters
            -> mask PII
            -> send cleaned text to LLM

    Output flow:
        raw_llm_output
            -> mask leaked PII
            -> block harmful content
            -> return cleaned output to client
    """

    def __init__(self) -> None:
        self.sanitizer = InputSanitizer()
        self.pii_detector = PIIDetector()
        self.output_validator = OutputValidator()

    @traceable(name="security_check_input")
    def check_input(self, text: str) -> tuple[bool, str, list[str]]:
        """
        Process user input through security checks.

        Args:
            text: Raw user input.

        Returns:
            tuple:
                - is_allowed:
                    True if the input can be sent to the LLM.
                    False if blocked.
                - cleaned_text:
                    Cleaned and PII-masked text.
                    Empty string if blocked.
                - security_notes:
                    List of notes such as blocked reason or PII masking info.
        """
        notes: list[str] = []

        # Step 1: Block prompt injection attempts.
        is_safe, reason = self.sanitizer.check(text)

        if not is_safe:
            return False, "", [reason or "Blocked: unsafe input"]

        # Step 2: Clean suspicious delimiters or template markers.
        cleaned = self.sanitizer.clean(text)

        # Step 3: Mask PII before text reaches the LLM.
        pii_found = self.pii_detector.detect(cleaned)

        if pii_found:
            cleaned = self.pii_detector.mask(cleaned)
            notes.append(f"Input PII masked: {list(pii_found.keys())}")

        return True, cleaned, notes

    @traceable(name="security_check_output")
    def check_output(self, text: str) -> tuple[str, list[str]]:
        """
        Validate LLM output before returning it to the user/client.

        Args:
            text: Raw LLM output.

        Returns:
            tuple:
                - cleaned_output: Final safe response.
                - warnings: Output validation warnings.
        """
        return self.output_validator.validate(text)