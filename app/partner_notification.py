"""Future notification seam for partner submissions.

The public form stores a durable submission first. A future email or CRM
adapter can be connected here without changing the API contract or making
submission success depend on an external provider.
"""
from typing import Any


def notify_partner_submission(submission: dict[str, Any]) -> None:
    """Intentionally no-op until an approved notification provider exists."""
    _ = submission
