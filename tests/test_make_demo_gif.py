import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.make_demo_gif import select_indices


class TestSelectIndices:
    def test_target_greater_than_total_returns_all(self):
        assert select_indices(5, 10) == [0, 1, 2, 3, 4]

    def test_target_equal_total_returns_all(self):
        assert select_indices(5, 5) == [0, 1, 2, 3, 4]

    def test_picks_evenly_spaced_indices_count_matches_target(self):
        result = select_indices(72, 20)
        assert len(result) == 20

    def test_picks_evenly_spaced_indices_is_sorted_no_duplicates(self):
        result = select_indices(100, 20)
        assert result == sorted(result)
        assert len(set(result)) == len(result)

    def test_first_index_is_zero(self):
        assert select_indices(72, 20)[0] == 0

    def test_last_index_is_near_end(self):
        result = select_indices(72, 20)
        assert 60 <= result[-1] <= 71
