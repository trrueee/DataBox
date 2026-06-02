import re

class DataRedactor:
    """
    DataRedactor provides high-fidelity SQL and text scrubbing/redaction 
    for PII (emails, phone numbers, credit cards) and database credentials 
    to enforce privacy in public-facing or audit logging states.
    """

    # Regular expressions for PII detection
    EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
    PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[- ]?)?1[3-9]\d{9}\b|\b(?:\+?\d{1,3}[- ]?)?\d{3,4}[- ]\d{7,8}\b")
    CREDIT_CARD_REGEX = re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")
    
    # Matches assignment of credential values in SQL (e.g. password = 'value' or SET PASSWORD = 'value')
    # It dynamically captures typical credential keyword names and masks the string literals.
    CREDENTIAL_ASSIGN_REGEX = re.compile(
        r"(?i)\b(password|passwd|secret|token|api_key|apikey|credential|passphrase|private_key|privatekey)\b\s*=\s*'[^']+'"
    )

    @classmethod
    def redact_sql(cls, sql_str: str) -> str:
        """
        Redacts sensitive PII and database credential assignments in the given SQL string.
        """
        if not sql_str:
            return ""

        # 1. Mask credential assignments like: password = 'abc' => password = '[REDACTED_SECURE]'
        def replace_cred_assign(match: re.Match[str]) -> str:
            keyword = match.group(1)
            return f"{keyword} = '[REDACTED_SECURE]'"

        scrubbed = cls.CREDENTIAL_ASSIGN_REGEX.sub(replace_cred_assign, sql_str)

        # 2. Redact Emails
        scrubbed = cls.EMAIL_REGEX.sub("[REDACTED_EMAIL]", scrubbed)

        # 3. Redact Phone Numbers
        scrubbed = cls.PHONE_REGEX.sub("[REDACTED_PHONE]", scrubbed)

        # 4. Redact Credit Cards
        scrubbed = cls.CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", scrubbed)

        return scrubbed
