"""Guardrails — input validation and hard blockers for the chat endpoint.

Checks user messages before they reach the LLM. If a message triggers a hard
blocker, returns a refusal response. Otherwise returns None, allowing the
message to proceed to the LLM.
"""

import re

# ── Hard blockers — these trigger an immediate refusal ───────────────────

HARD_BLOCKER_PATTERNS: list[tuple[str, str]] = [
    # Trading/execution
    (r"(?i)\b(execute|place|fill|cancel)\b.*\b(trade|order|buy|sell)\b",
     "place trades or orders"),
    (r"(?i)\bbuy\b.*\b(shares?|stock|etf|fund|bond)\b",
     "buy investments"),
    (r"(?i)\bsell\b.*\b(shares?|stock|etf|fund|bond)\b",
     "sell investments"),
    # Prohibited advice requests
    (r"(?i)\b(what should I do|tell me exactly what to do|give me financial advice)\b",
     "give financial advice"),
    (r"(?i)\btell me (what|how)\b.*\b(invest|buy|sell|put my money)\b",
     "give personalised investment advice"),
    # Security
    (r"(?i)\b(password|login|credentials|2fa|mfa|auth code)\b",
     "access account credentials"),
    # Illegal
    (r"(?i)\b(tax evasion|hide money|money laundering|illegal)\b",
     "help with illegal activities"),
]

# ── UK term corrections — injectable into system prompt ─────────────────

UK_TERMS_MAP = """
UK TERM : US EQUIVALENT
─────────────────────────────
ISA     : Roth IRA / TFSA
SIPP    : 401k / IRA
GIA     : Taxable brokerage account
LISA    : Not directly equivalent (closest: Roth IRA with home-buying)
CGT     : Capital gains tax
HMRC    : IRS
State Pension : Social Security
P60     : W-2 (but not identical)
NI      : Social Security tax
SDRT    : No US equivalent
"""

# ── Refusal template ────────────────────────────────────────────────────

REFUSAL_TEMPLATE = """I can't {request_type}, but I can help you think through the options.

Here's what I can tell you based on your portfolio:
• Your current portfolio value is £{portfolio_value:,.0f} across {num_holdings} holdings
• Your overall health grade is {health_grade}

If you're considering making changes, here are things to discuss with your financial adviser:
- Review your asset allocation against your risk tolerance
- Check for tax-efficient wrapping of your holdings
- Consider rebalancing if you've drifted from your target

I'm here to analyse and explain — not to execute decisions."""


# ── Public API ──────────────────────────────────────────────────────────

def check_input(message: str) -> str | None:
    """Check a user message against hard blockers.

    Args:
        message: The user's raw input.

    Returns:
        A refusal text string if the message triggers a blocker, or ``None``
        if the message is safe to pass to the LLM.
    """
    for pattern, request_type in HARD_BLOCKER_PATTERNS:
        if re.search(pattern, message):
            return _build_refusal(request_type)
    return None


def _build_refusal(request_type: str) -> str:
    """Build a refusal message."""
    return REFUSAL_TEMPLATE.format(
        request_type=request_type,
        portfolio_value=0,
        num_holdings=0,
        health_grade="N/A",
    )


def build_refusal_with_context(
    request_type: str,
    portfolio_value: float = 0,
    num_holdings: int = 0,
    health_grade: str = "N/A",
) -> str:
    """Build a refusal message with portfolio context numbers.

    Use this version when you have the portfolio context available and want
    to include the user's actual numbers in the refusal.
    """
    return REFUSAL_TEMPLATE.format(
        request_type=request_type,
        portfolio_value=portfolio_value,
        num_holdings=num_holdings,
        health_grade=health_grade,
    )
