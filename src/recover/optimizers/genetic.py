# -*- coding: utf-8 -*-
"""Genetic compile-unit map optimizer implementation."""

from collections.abc import Callable

from recover.cu_map import CUInfo, CUMap
from recover.exporter import Data
from recover.fitness_function import FitnessFunction
from recover.optimizer import Optimizer
from recover.state import State

import functools
import random

import numpy
import pygad


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["Genetic"]


_MULTIPLIER = 64


class Genetic(Optimizer):
    """Genetic compile-unit map optimizer implementation.

    Args:
        data: The exported program data.
        cu_map: The compile-unit map to optimize.
        fitness_function: Fitness function to use.
    """

    def __init__(
        self, data: Data, cu_map: CUMap, fitness_function: type[FitnessFunction]
    ) -> None:
        super(Genetic, self).__init__(data, cu_map, fitness_function)
        self._cu_scores: dict[int, float] = {}

    def _get_crossover_function(self, num_bits: int, max_bits_set: int) -> Callable:

        def _crossover_func(parents, sizes, _):

            set_bits = []
            for parent in map(int, parents):
                for i in range(num_bits):
                    if parent & (1 << i):
                        set_bits.append(i)

            children = []
            for _ in range(sizes[0]):
                num_samples = random.randrange(min(len(set_bits), max_bits_set))

                child = 1 << (num_bits - 1)
                for i in random.sample(set_bits, num_samples):
                    child |= 1 << i

                assert (
                    1 <= child.bit_count() <= 3
                ), f"Invalid crossover state {child:b} ({num_samples + 1} set bits, not in [1,3])"

                children.append([child])

            return numpy.asarray(children)

        return _crossover_func

    #
    # https://stackoverflow.com/questions/69544556/passing-arguments-to-pygad-fitness-function
    #
    def _get_mutation_function(self, num_bits: int, max_bits_set: int) -> Callable:

        def _mutate(state: int, num_bits: int) -> int:

            new_state = -1
            mutation_str = ""

            set_bits = []
            for i in range(num_bits):
                if state & (1 << i):
                    set_bits.append(i)

            num_bits_set = len(set_bits)

            if num_bits_set == 1:
                new_state = 1 << (num_bits - 1)
                num_samples = random.randrange(max_bits_set)
                for i in random.sample(range(num_bits - 1), num_samples):
                    new_state |= 1 << i
                self._logger.debug("RES %s -> %s", bin(state), bin(new_state))

            elif num_bits_set == 2:
                while new_state == -1:
                    mutation = random.randrange(4)
                    if mutation == 0 and num_bits >= 3:
                        i = random.randrange(num_bits)
                        while i in set_bits:
                            i = random.randrange(num_bits)
                        new_state = state | (1 << i)
                        mutation_str = "NEW"
                    elif mutation == 1:
                        new_state = state ^ (1 << set_bits[0])
                        mutation_str = "REM_LOW"
                    elif mutation == 2 and set_bits[0] + 1 < num_bits - 1:
                        i = set_bits[0]
                        new_state = (state ^ (1 << i)) | (1 << (i + 1))
                        mutation_str = "MOV_LOW_L"
                    elif mutation == 3 and set_bits[0] > 0:
                        i = set_bits[0]
                        new_state = (state ^ (1 << i)) | (1 << (i - 1))
                        mutation_str = "MOV_LOW_R"

            elif num_bits_set == 3:
                while new_state == -1:
                    mutation = random.randrange(6)
                    if mutation == 0:
                        new_state = state ^ (1 << set_bits[0])
                        mutation_str = "REM_LOW"
                    elif mutation == 1:
                        new_state = state ^ (1 << set_bits[1])
                        mutation_str = "REM_MID"
                    elif mutation == 2 and set_bits[1] + 1 < num_bits - 1:
                        i = set_bits[1]
                        new_state = (state ^ (1 << i)) | (1 << (i + 1))
                        mutation_str = "MOV_MID_L"
                    elif mutation == 3 and set_bits[1] > 0:
                        i = set_bits[1]
                        new_state = (state ^ (1 << i)) | (1 << (i - 1))
                        mutation_str = "MOV_MID_R"
                    elif mutation == 2 and set_bits[0] + 1 < num_bits - 1:
                        i = set_bits[0]
                        new_state = (state ^ (1 << i)) | (1 << (i + 1))
                        mutation_str = "MOV_LOW_L"
                    elif mutation == 3 and set_bits[0] > 0:
                        i = set_bits[0]
                        new_state = (state ^ (1 << i)) | (1 << (i - 1))
                        mutation_str = "MOV_LOW_R"

            elif num_bits_set > 3:
                new_state = 1 << (num_bits - 1)
                num_samples = random.randrange(max_bits_set)
                for i in random.sample(set_bits, num_samples):
                    new_state |= 1 << i
                mutation_str = "RES"

            self._logger.debug("%s %s -> %s", mutation_str, bin(state), bin(new_state))

            assert (
                new_state != -1 and new_state.bit_count() <= 3
            ), f"Mutation algorithm generated invalid state {new_state:b}"

            return new_state

        def _mutation_function(parents, _):
            return numpy.asarray(
                [
                    [_mutate(int(parents[0][0]), num_bits)],
                    [_mutate(int(parents[1][0]), num_bits)],
                ]
            )

        return _mutation_function

    def _get_fitness_function(
        self, fitness_function: FitnessFunction, funcs: list[int]
    ) -> Callable:
        """Return a callable to be used as a fitness function during the genetic
        algorithm's state exploration. We have to resort to this trick because
        the fitness function prototype used internally by PyGAD is different
        from ours.

        Args:
            fitness_function: Fitness function to use.
            funcs: List of functions corresponding to the currently explored
                state space.

        Returns:
            Fitness function callable in a prototype used by PyGAD.
        """

        @functools.wraps(fitness_function.score)
        def _fitness_function(ga: pygad.GA, state: numpy.ndarray, i: int) -> float:

            state = int(state[0])

            assert (
                1 <= state.bit_count() <= 3
            ), f"Invalid state {state:b} ({state.bit_count()} set bits, not in [1,3])"

            return fitness_function.score(State(state, funcs))

        return _fitness_function

    def _optimize(self, cu: CUInfo, next_cu: CUInfo) -> tuple[int, int]:

        cu_scores = self._cu_scores

        num_changes = 0
        new_cu_id = -1

        state = State.from_cu_list([cu.get_func_eas(), next_cu.get_func_eas()])

        fitness_function = self._fitness_function(self._data, self._cu_map)

        if cu.cu_id not in cu_scores:
            score = cu_scores.setdefault(cu.cu_id, fitness_function.score(state))
        else:
            score = cu_scores[cu.cu_id]

        num_bits = len(cu) + len(next_cu)
        max_bits_set = min(num_bits, 3)
        min_state = 1 << (num_bits - 1)
        max_state = sum(1 << (num_bits - i - 1) for i in range(max_bits_set))

        self._logger.info(
            "Examining CUs %d and %d (%d bits), state %s (%f)",
            cu.cu_id,
            next_cu.cu_id,
            num_bits,
            bin(state),
            score,
        )

        self._logger.info("State space %s - %s", bin(min_state), bin(max_state))

        ga = pygad.GA(
            suppress_warnings=True,
            num_generations=num_bits * _MULTIPLIER,
            num_parents_mating=2,
            fitness_func=self._get_fitness_function(fitness_function, state.funcs),
            sol_per_pop=2 + 1,
            num_genes=1,
            init_range_low=min_state,
            init_range_high=max_state,
            gene_type=object,
            gene_space=[min_state, max_state],
            mutation_type=self._get_mutation_function(num_bits, max_bits_set),
            mutation_num_genes=1,
            crossover_type=self._get_crossover_function(num_bits, max_bits_set),
        )
        ga.run()

        max_state, max_score, _ = ga.best_solution()
        max_state = State(int(max_state[0]), state.funcs)

        if max_score > score and state != max_state:
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
