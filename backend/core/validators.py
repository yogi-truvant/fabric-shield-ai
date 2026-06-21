"""
FabricShield AI — Value validators (content detection, Tier 1)

Deterministic, NAME-AGNOSTIC checks that run on actual column VALUES. A column called
``CC`` (or ``x_field_3``) full of Luhn-valid 16-digit numbers is detected as a credit
card here, regardless of its header — solving the unreliable-column-name problem.

These are pure functions over a single string value. The content scanner aggregates
their hit-rate across a sample to decide whether a column holds that entity type.

NOTHING here reads a database or stores anything; callers pass values already sampled
in memory and discarded after scanning.
"""

import ipaddress
import re
from datetime import datetime
from typing import Callable, Dict, List, Tuple

from backend.models.schemas import MaskType, PiiEntityType

_DIGITS = re.compile(r"\D")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%b-%Y")


def _digits_only(value: str) -> str:
    return _DIGITS.sub("", value)


def luhn_ok(number: str) -> bool:
    """Luhn (mod-10) checksum — credit cards, NPI."""
    digits = _digits_only(number)
    if not digits:
        return False
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = ord(ch) - 48
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def is_credit_card(value: str) -> bool:
    d = _digits_only(value)
    return 13 <= len(d) <= 19 and luhn_ok(d)


def is_ssn(value: str) -> bool:
    """US SSN with structural validity (excludes obviously invalid area/group/serial)."""
    m = re.fullmatch(r"(\d{3})-?(\d{2})-?(\d{4})", value.strip())
    if not m:
        return False
    area, group, serial = m.group(1), m.group(2), m.group(3)
    if area in ("000", "666") or area[0] == "9":
        return False
    if group == "00" or serial == "0000":
        return False
    return True


def is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


def is_phone(value: str) -> bool:
    v = value.strip()
    if not re.fullmatch(r"\+?[\d\s().\-]{7,20}", v):
        return False
    return 7 <= len(_digits_only(v)) <= 15


def _iban_mod97(iban: str) -> bool:
    s = iban[4:] + iban[:4]
    converted = "".join(str(ord(c) - 55) if c.isalpha() else c for c in s)
    try:
        return int(converted) % 97 == 1
    except ValueError:
        return False


def is_iban(value: str) -> bool:
    v = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", v):
        return False
    return _iban_mod97(v)


def is_aba_routing(value: str) -> bool:
    """US bank routing number — ABA checksum."""
    d = value.strip()
    if not re.fullmatch(r"\d{9}", d):
        return False
    n = [int(c) for c in d]
    checksum = 3 * (n[0] + n[3] + n[6]) + 7 * (n[1] + n[4] + n[7]) + (n[2] + n[5] + n[8])
    return checksum % 10 == 0


def is_npi(value: str) -> bool:
    """US National Provider Identifier — 10 digits, Luhn over prefix 80840."""
    d = value.strip()
    if not re.fullmatch(r"\d{10}", d):
        return False
    return luhn_ok("80840" + d)


def is_dea(value: str) -> bool:
    """US DEA number — 2 letters + 7 digits with its check digit."""
    v = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}\d{7}", v):
        return False
    digits = [int(c) for c in v[2:]]
    check = (digits[0] + digits[2] + digits[4]) + 2 * (digits[1] + digits[3] + digits[5])
    return check % 10 == digits[6]


def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip())
        return True
    except ValueError:
        return False


def is_us_zip(value: str) -> bool:
    return bool(re.fullmatch(r"\d{5}(-\d{4})?", value.strip()))


def is_date_of_birth(value: str) -> bool:
    """A parseable date in a plausible human-birth range (1900..today)."""
    v = value.strip()[:10]
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(v, fmt)
        except ValueError:
            continue
        return 1900 <= dt.year <= datetime.utcnow().year
    return False


# (validator, entity, recommended mask, is_checksum_strong)
# Order matters: most specific / strongest checks first so a value is claimed by the
# best-fitting entity (e.g. an SSN-shaped value is tested for SSN before generic ZIP).
VALIDATORS: List[Tuple[Callable[[str], bool], PiiEntityType, MaskType, bool]] = [
    (is_email, PiiEntityType.EMAIL, MaskType.email, True),
    (is_credit_card, PiiEntityType.CREDIT_CARD, MaskType.partial, True),
    (is_iban, PiiEntityType.IBAN, MaskType.partial, True),
    (is_dea, PiiEntityType.DEA, MaskType.partial, True),
    (is_npi, PiiEntityType.NPI, MaskType.partial, True),
    (is_aba_routing, PiiEntityType.IBAN, MaskType.partial, True),
    (is_ssn, PiiEntityType.SSN, MaskType.partial, True),
    (is_ip_address, PiiEntityType.IP_ADDRESS, MaskType.default, True),
    (is_phone, PiiEntityType.PHONE, MaskType.partial, False),
    (is_date_of_birth, PiiEntityType.DATE_OF_BIRTH, MaskType.default, False),
    (is_us_zip, PiiEntityType.LOCATION, MaskType.partial, False),
]

# Strong (checksum/format-locked) entities can be trusted at a lower hit-rate than weak
# ones (phone/zip/date), which co-occur with non-PII numbers and need a higher hit-rate.
STRONG_MIN_MATCH = 0.55
WEAK_MIN_MATCH = 0.80


def best_value_entity(
    values: List[str],
) -> Tuple[PiiEntityType, MaskType, float, bool] | None:
    """Return the best (entity, mask, match_fraction, is_strong) across the validators for a
    column's sampled values, or None if nothing clears its threshold. Pure / in-memory."""
    cleaned = [str(v).strip() for v in values if v is not None and str(v).strip() != ""]
    if not cleaned:
        return None

    best = None
    for validator, entity, mask, strong in VALIDATORS:
        hits = sum(1 for v in cleaned if validator(v))
        frac = hits / len(cleaned)
        threshold = STRONG_MIN_MATCH if strong else WEAK_MIN_MATCH
        if frac < threshold:
            continue
        # Prefer strong validators, then higher hit fraction.
        rank = (1 if strong else 0, frac)
        if best is None or rank > best[0]:
            best = (rank, entity, mask, frac, strong)

    if best is None:
        return None
    _, entity, mask, frac, strong = best
    return entity, mask, frac, strong


def confidence_from_match(frac: float, strong: bool) -> float:
    """Map a sample hit-rate to a confidence score. Checksum validators earn more trust."""
    if strong:
        return round(min(1.0, 0.80 + 0.19 * frac), 3)
    return round(min(0.90, 0.55 + 0.30 * frac), 3)


# Convenience registry for tests / introspection.
VALIDATOR_REGISTRY: Dict[str, Callable[[str], bool]] = {
    "credit_card": is_credit_card, "ssn": is_ssn, "email": is_email, "phone": is_phone,
    "iban": is_iban, "aba_routing": is_aba_routing, "npi": is_npi, "dea": is_dea,
    "ip_address": is_ip_address, "us_zip": is_us_zip, "date_of_birth": is_date_of_birth,
}
