import random
from datetime import datetime, timedelta, timezone

from hypothesis import given, strategies as st

from page888.models import Alert, Severity
from page888.order import order_alerts
from page888.parse import NOT_STATED

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
tzs = st.sampled_from([timezone.utc, timezone(timedelta(hours=-8)), timezone(timedelta(hours=5, minutes=30))])
expiries = st.none() | st.builds(
    lambda mins, tz: (NOW + timedelta(minutes=mins)).astimezone(tz),
    st.integers(min_value=-600, max_value=600),
    tzs,
)
ids = st.sampled_from(["a", "b", "c", "d", NOT_STATED])


def make(id_="x", sev=Severity.MINOR, expires=None, event="E") -> Alert:
    return Alert(id=id_, event=event, severity=sev, urgency="Unknown", certainty="Unknown",
                 area_desc="A", headline="H", description="D", instruction="", onset=None,
                 expires=expires, sender_name="S", source_url="")


alerts = st.builds(
    make, ids, st.sampled_from(list(Severity)), expiries, st.sampled_from(["E1", "E2"])
)


def key(a: Alert):
    inf = datetime.max.replace(tzinfo=timezone.utc)
    return (a.severity, a.expires.astimezone(timezone.utc) if a.expires else inf, a.id)


@given(st.lists(alerts, max_size=15))
def test_prop_order_sorted_permutation(items):
    out = order_alerts(items, NOW)
    keys = [key(a) for a in out]
    assert keys == sorted(keys)
    live = [a for a in items if a.expires is None or a.expires > NOW]
    # real ids are deduped; placeholders and unique ids all survive
    real = {a.id for a in live if a.id != NOT_STATED}
    assert {a.id for a in out if a.id != NOT_STATED} == real
    assert len(out) == len(real) + sum(a.id == NOT_STATED for a in live)
    assert all(a in live for a in out)


@given(st.lists(alerts, max_size=15), st.randoms())
def test_prop_order_input_invariant(items, rnd):
    shuffled = list(items)
    rnd.shuffle(shuffled)
    assert order_alerts(items, NOW) == order_alerts(shuffled, NOW)


@given(st.lists(alerts, max_size=15))
def test_prop_dedupe_unique_real_ids(items):
    out = order_alerts(items, NOW)
    real = [a.id for a in out if a.id != NOT_STATED]
    assert len(real) == len(set(real))
    assert {a.id for a in out} <= {a.id for a in items}


def test_placeholder_ids_never_collapsed():
    a = make(NOT_STATED, event="ONE")
    b = make(NOT_STATED, event="TWO")
    c = make(NOT_STATED, event="ONE")  # identical to a: still kept
    assert len(order_alerts([a, b, c], NOW)) == 3


def test_real_id_deduped():
    assert len(order_alerts([make("a"), make("a"), make("b")], NOW)) == 2


def test_expired_excluded():
    past = make("p", expires=NOW - timedelta(seconds=1))
    at = make("q", expires=NOW)
    ok = make("r", expires=NOW + timedelta(seconds=1))
    assert order_alerts([past, at, ok], NOW) == [ok]


def test_missing_expiry_last_in_severity_group():
    none = make("n", Severity.SEVERE, None)
    soon = make("s", Severity.SEVERE, NOW + timedelta(hours=9))
    extreme = make("e", Severity.EXTREME, None)
    assert order_alerts([none, soon, extreme], NOW) == [extreme, soon, none]


def test_utc_comparison_across_offsets():
    # 13:00-08:00 is 21:00 UTC; 20:00+00:00 is earlier despite the larger local clock number
    late = make("late", expires=datetime(2026, 11, 13, 13, 0, tzinfo=timezone(timedelta(hours=-8))))
    early = make("early", expires=datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc))
    assert order_alerts([late, early], NOW) == [early, late]


def test_shuffle_fixed_example():
    items = [make(str(i), Severity(i % 5), NOW + timedelta(hours=i + 1)) for i in range(20)]
    expected = order_alerts(items, NOW)
    random.Random(1).shuffle(items)
    assert order_alerts(items, NOW) == expected
