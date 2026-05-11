from cvcore.eval.metrics import count_mae


def test_count_mae():
    assert count_mae([1, 2], [1, 3]) == 0.5
