# -*- coding: utf-8 -*-
"""Fitness function that computes a score based on the *Newman modularity*
`modularity`_.

.. _modularity:
   https://en.wikipedia.org/wiki/Modularity_(networks)
"""

from recover.cu_map import CUMap
from recover.fitness_function import DataFitnessFunction
from recover.state import State
from recover.util import Data

import functools

from recover import util


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["Modularity"]


class Modularity(DataFitnessFunction):
    """Newman modularity fitness function.

    The state number and the corresponding function list are converted to a
    series of communities of the program's PDG. The modularity score of the
    resulting partitioning is computed and returned.

    Args:
        data: Exported program data.
        cu_map: The program's compile-unit map.
        init_state: Initial state before any further optimization is performed
            (useful in cases where preprocessing might be required).
    """

    def __init__(self, data: Data, cu_map: CUMap, init_state: State) -> None:
        super(Modularity, self).__init__(data, cu_map, init_state)
        self._in_degrees = dict(data.pdg.in_degree(self._nodes))
        self._out_degrees = dict(data.pdg.out_degree(self._nodes))
        self._m = data.pdg.size()

    def _compute_modularity(self, community: set[int]) -> float:
        link_sum = sum(1 for _, u in self._data.pdg.edges(community) if u in community)
        out_degree_sum = sum(self._out_degrees[u] for u in community)
        in_degree_sum = sum(self._in_degrees[u] for u in community)
        return link_sum / self._m - out_degree_sum * in_degree_sum * (1 / self._m**2)

    def score(self, state: State) -> float:
        cus = state.to_cu_list()
        data_refs = self._data_refs
        modularity = 0
        for cu in cus:
            community = set(cu) | functools.reduce(
                set.union, (data_refs[func] for func in cu)
            )
            modularity += self._compute_modularity(community)
        return modularity
