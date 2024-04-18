import itertools
import random

import pytest

from delinker.optimization import state


_FUNC_LIST = list(range(8))

_STATES = [
    0b10000000,
    0b10000001,
    0b10000010,
    0b10000100,
    0b10001000,
    0b10010000,
    0b10100000,
    0b11000000
]

_TEST_CASES = [
    (0b10000000, [[0, 1, 2, 3, 4, 5, 6, 7]]),
    (0b10000001, [[0, 1, 2, 3, 4, 5, 6], [7]]),
    (0b10000010, [[0, 1, 2, 3, 4, 5], [6, 7]]),
    (0b10000100, [[0, 1, 2, 3, 4], [5, 6, 7]]),
    (0b10001000, [[0, 1, 2, 3], [4, 5, 6, 7]]),
    (0b10010000, [[0, 1, 2], [3, 4, 5, 6, 7]]),
    (0b10100000, [[0, 1], [2, 3, 4, 5, 6, 7]]),
    (0b11000000, [[0], [1, 2, 3, 4, 5, 6, 7]]),
]


def test_enum_states():
    assert list(state.enum_states(8, 1)) + list(state.enum_states(8, 2)) == _STATES


def test_state_to_cu_list():
    for number, cu_list in _TEST_CASES:
        assert state.state_to_cu_list(number, _FUNC_LIST) == cu_list


def test_cu_list_to_state():
    for number, cu_list in _TEST_CASES:
        assert state.cu_list_to_state(cu_list) == number


@pytest.mark.parametrize('_', range(1000))
def test_combined(_):
    func_list = list(range(100))
    split_points = sorted(random.sample(range(1, 100 - 1), 18))

    cu_list = [func_list[:split_points[0]]]
    for i, j in itertools.pairwise(split_points):
        cu_list.append(func_list[i:j])
    cu_list.append(func_list[j:])

    number = state.cu_list_to_state(cu_list)
    ret_cu_list = state.state_to_cu_list(number, func_list)

    assert ret_cu_list == cu_list
