"""Future browser integration boundary. There is deliberately no submit() operation."""

from typing import Protocol

from .providers import ProviderError


class ClaimFormAdapter(Protocol):
    """Populate only reviewed, non-identity fields, then leave the browser with the user.

    Implementations must use observed official controls, never invented selectors; must
    not read or fill CPR/banking/credentials; and must never click Submit. Revalidate
    official URL and form version. Consent/terms and authentication remain user-owned.
    """

    def fill_for_user_review(self, prepared_fields: dict) -> dict: ...


class UnavailableDsbFormAdapter:
    def fill_for_user_review(self, prepared_fields: dict) -> dict:
        raise ProviderError(
            "Live DSB form filling is not implemented. Use the handoff details manually. "
            "Future form automation must stop for the user's final review and submission."
        )
