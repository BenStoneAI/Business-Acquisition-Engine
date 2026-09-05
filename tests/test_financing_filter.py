from src.models import Listing
from src.financing_filter import (
    FULL,
    POSSIBLE,
    PARTIAL_CAPPED,
    NONE,
    financing_status,
    qualifies,
    filter_full_seller_financing,
)


def make(**kw) -> Listing:
    base = dict(business_name="Biz", industry="hvac", location="UT")
    base.update(kw)
    return Listing(**base)


def test_explicit_100_percent_is_full():
    l = make(notes="Owner will offer 100% seller financing to a qualified buyer.")
    assert financing_status(l) == FULL
    assert qualifies(l) is True


def test_flag_without_stated_cap_is_possible():
    l = make(seller_financing=True, notes="Great recurring revenue. No website.")
    assert financing_status(l) == POSSIBLE
    assert qualifies(l) is True


def test_financing_mentioned_in_text_without_flag_is_possible():
    l = make(seller_financing=False, notes="Seller financing available for the right buyer.")
    assert financing_status(l) == POSSIBLE
    assert qualifies(l) is True


def test_partial_percentage_cap_is_excluded():
    # Real sample data: Bee Safe "Owner willing to finance 25 percent".
    l = make(seller_financing=True, notes="Owner willing to finance 25 percent and stay 6 months.")
    assert financing_status(l) == PARTIAL_CAPPED
    assert qualifies(l) is False


def test_explicit_no_financing_is_excluded():
    l = make(seller_financing=False, notes="No seller financing. Cash or SBA only.")
    assert financing_status(l) == NONE
    assert qualifies(l) is False


def test_third_party_only_is_excluded():
    l = make(seller_financing=False, notes="Third-party financing only; owner exploring options.")
    assert qualifies(l) is False


def test_full_carry_language_beats_a_down_payment_percentage():
    # A small down payment must not be read as a sub-100% cap.
    l = make(seller_financing=True,
             seller_financing_terms="Full seller carry with 10% down payment.")
    assert financing_status(l) == FULL
    assert qualifies(l) is True


def test_no_signal_at_all_is_excluded():
    l = make(seller_financing=False, notes="Established business, good books.")
    assert qualifies(l) is False


def test_filter_splits_kept_and_dropped():
    keep = make(business_name="Keep", seller_financing=True)
    drop = make(business_name="Drop", seller_financing=False, notes="No seller financing")
    kept, dropped = filter_full_seller_financing([keep, drop])
    assert [l.business_name for l in kept] == ["Keep"]
    assert [l.business_name for l in dropped] == ["Drop"]


def test_down_payment_percentage_is_not_a_cap():
    # Bug A2: "seller will finance with 10% down" is a 90% carry, not a 10% cap.
    l = make(seller_financing=True, notes="Seller will finance with 10% down.")
    assert financing_status(l) == POSSIBLE
    assert qualifies(l) is True
    l2 = make(seller_financing=True,
              notes="10% down payment and the owner will carry the balance.")
    assert qualifies(l2) is True


def test_sba_100_percent_is_not_seller_carry():
    # Bug A6a: "SBA 100% financing" must not read as full seller carry.
    l = make(seller_financing=False, notes="SBA 100% financing available.")
    assert financing_status(l) != FULL
    l2 = make(seller_financing=True, notes="SBA 100% financing available.")
    assert financing_status(l2) == POSSIBLE


def test_majority_carry_at_or_above_50_qualifies():
    # 2026-07-19 strategy change: screen on quality, negotiate structure.
    from src.financing_filter import MAJORITY
    l = make(seller_financing=True, notes="Seller will carry 60% for a qualified buyer.")
    assert financing_status(l) == MAJORITY
    assert qualifies(l) is True
    boundary = make(seller_financing=True, notes="Owner willing to finance 50 percent.")
    assert financing_status(boundary) == MAJORITY
    assert qualifies(boundary) is True
    below = make(seller_financing=True, notes="Owner willing to finance 45 percent.")
    assert financing_status(below) == PARTIAL_CAPPED
    assert qualifies(below) is False
