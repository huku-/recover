# -*- coding: utf-8 -*-
"""Local brute-force compile-unit map optimizer."""

from recover.cu_map import CUInfo, CUMap
from recover.exporter import Data
from recover.fitness_function import FitnessFunction
from recover.optimizer import Optimizer
from recover.state import State


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["BruteForce", "BruteForceFast"]


class BruteForce(Optimizer):
    """Local brute-force compile-unit map optimizer implementation.

    Args:
        data: The exported program data.
        cu_map: The compile-unit map to optimize.
        fitness_function: Fitness function to use.
    """

    def __init__(
        self, data: Data, cu_map: CUMap, fitness_function: type[FitnessFunction]
    ) -> None:
        super(BruteForce, self).__init__(data, cu_map, fitness_function)
        self._cu_scores = {}

    def _optimize(self, cu: CUInfo, next_cu: CUInfo) -> tuple[int, int]:

        cu_scores = self._cu_scores

        num_changes = 0
        new_cu_id = -1

        state = max_state = State.from_cu_list(
            [cu.get_func_eas(), next_cu.get_func_eas()]
        )

        fitness_function = self._fitness_function(self._data, self._cu_map, state)

        if cu.cu_id not in cu_scores:
            score = max_score = cu_scores.setdefault(
                cu.cu_id, fitness_function.score(state)
            )
        else:
            score = max_score = cu_scores[cu.cu_id]

        num_bits = len(cu) + len(next_cu)
        max_bits_set = min(num_bits, 3)

        self._logger.info(
            "Examining CUs %d and %d (%d bits), state %s (%.18f)",
            cu.cu_id,
            next_cu.cu_id,
            num_bits,
            bin(state),
            score,
        )

        for num_ones in range(1, max_bits_set + 1):
            for new_state in state.siblings(num_ones):
                new_score = fitness_function.score(new_state)
                if new_score > max_score:
                    max_state = new_state
                    max_score = new_score
                    self._logger.debug(
                        "New state %s (%.18f) [+%.18f]",
                        bin(new_state),
                        new_score,
                        new_score - score,
                    )

        if max_score > score and max_state != state:
            self._logger.info(
                "Accept %s (%.18f) -> %s (%.18f) [+%.18f]",
                bin(state),
                score,
                bin(max_state),
                max_score,
                max_score - score,
            )
            cu_scores[cu.cu_id] = max_score
            num_changes, new_cu_id = self._update_cu_map(cu, next_cu, max_state)

        return num_changes, new_cu_id


class BruteForceFast(Optimizer):
    """Faster version of the local brute-force compile-unit map optimizer.

    Instead of exploring the whole state space, the fast brute-force optimizer
    first computes the fitness score for the 1-bit state (i.e., merged compile-
    units). Then, all 2-bit possible states are explored (i.e., all possible
    boundary locations between the examined compile-unit pair). However, only
    the 3-bit states, generated from the maximum 2-bit state by adding an
    additional bit, are examined (i.e., we assume that the best 3-segmentation
    is derived from the best 2-segmentation, after splitting one of the latter's
    segments in two).

    Args:
        data: The exported program data.
        cu_map: The compile-unit map to optimize.
        fitness_function: Fitness function to use.
    """

    def __init__(
        self, data: Data, cu_map: CUMap, fitness_function: type[FitnessFunction]
    ) -> None:
        super(BruteForceFast, self).__init__(data, cu_map, fitness_function)
        self._cu_scores = {}

    def _optimize(self, cu: CUInfo, next_cu: CUInfo) -> tuple[int, int]:

        cu_scores = self._cu_scores

        num_changes = 0
        new_cu_id = -1

        state = State.from_cu_list([cu.get_func_eas(), next_cu.get_func_eas()])
        fitness_function = self._fitness_function(self._data, self._cu_map, state)

        if cu.cu_id not in cu_scores:
            score = cu_scores.setdefault(cu.cu_id, fitness_function.score(state))
        else:
            score = cu_scores[cu.cu_id]

        num_bits = len(cu) + len(next_cu)

        self._logger.info(
            "Examining CUs %d and %d (%d bits), state %s (%.18f)",
            cu.cu_id,
            next_cu.cu_id,
            num_bits,
            bin(state),
            score,
        )

        prev_max_state = max_state = State(1 << (num_bits - 1), state.funcs)
        max_score = fitness_function.score(max_state)

        for new_state in prev_max_state.siblings_fast():
            new_score = fitness_function.score(new_state)
            if new_score > max_score:
                prev_max_state = max_state = new_state
                max_score = new_score
                self._logger.debug(
                    "New state %s (%.18f) [+%.18f]",
                    bin(new_state),
                    new_score,
                    new_score - score,
                )

        for new_state in prev_max_state.siblings_fast():
            new_score = fitness_function.score(new_state)
            if new_score > max_score:
                max_state = new_state
                max_score = new_score
                self._logger.debug(
                    "New state %s (%.18f) [+%.18f]",
                    bin(new_state),
                    new_score,
                    new_score - score,
                )

        if max_score > score and max_state != state:
            self._logger.info(
                "Accept %s (%.18f) -> %s (%.18f) [+%.18f]",
                bin(state),
                score,
                bin(max_state),
                max_score,
                max_score - score,
            )
            cu_scores[cu.cu_id] = max_score
            num_changes, new_cu_id = self._update_cu_map(cu, next_cu, max_state)

        return num_changes, new_cu_id
