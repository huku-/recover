# -*- coding: utf-8 -*-
"""Local brute-force compile-unit map optimizer."""

from recover.cu_map import CUInfo, CUMap
from recover.exporter import Data
from recover.fitness_function import FitnessFunction
from recover.optimizer import Optimizer
from recover.state import State


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["BruteForce"]


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
        self._cu_scores: dict[int, float] = {}

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
            "Examining CUs %d and %d (%d bits), state %s (%f)",
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
                    self._logger.info("New state %s (%f)", bin(new_state), new_score)

        if max_score > score and max_state != state:
            self._logger.info(
                "Accept %s (%f) -> %s (%f)",
                bin(state),
                score,
                bin(max_state),
                max_score,
            )
            cu_scores[cu.cu_id] = max_score
            num_changes, new_cu_id = self._update_cu_map(cu, next_cu, max_state)

        return num_changes, new_cu_id
