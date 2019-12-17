from collections import defaultdict
from zmon_slr.generate_slr import get_worst_sli


def test_zero_slis():
    count, breaches = get_worst_sli(defaultdict(int), defaultdict(int))
    assert count == 0
    assert breaches == 0


def test_single_sli():
    counts = defaultdict(int, {1: 100})
    breaches = defaultdict(int, {1: 50})
    count, breaches = get_worst_sli(counts, breaches)
    assert count == 100
    assert breaches == 50


def test_multiple_slis():
    counts = defaultdict(int, {1: 100, 2: 1000, 3: 300})
    breaches = defaultdict(int, {1: 50, 2: 900, 3: 300})
    count, breaches = get_worst_sli(counts, breaches)
    assert count == 300
    assert breaches == 300


