# -*- coding: utf-8 -*-
"""Fitness function that computes a score based on the *Newman modularity*
`modularity`_.

.. _modularity:
   https://en.wikipedia.org/wiki/Modularity_(networks)
"""

from typing import Set

from recover.cu_map import CUMap
from recover.fitness_function import FitnessFunction
from recover.state import State
from recover.util import Data

from recover import util



__author__ = 'Chariton Karamitas <huku@census-labs.com>'

__all__ = ['Modularity']



class Modularity(FitnessFunction):
    """Newman modularity fitness function.

    The state number and the corresponding function list are converted to a
    series of communities of the program's PDG. The modularity score of the
    resulting partitioning is computed and returned.

    Args:
        data: Exported program data.
        cu_map: The program's compile-unit map.
    """
    def __init__(self, data: Data, cu_map: CUMap) -> None:
        super(Modularity, self).__init__(data, cu_map)
        self._in_degrees = dict(data.pdg.in_degree())
        self._out_degrees = dict(data.pdg.out_degree())
        self._m = sum(self._out_degrees.values())

    def _compute_modularity(self, community: Set[int]) -> float:
        link_sum = sum(1 for _, u in self._data.pdg.edges(community) if u in community)
        out_degree_sum = sum(self._out_degrees[u] for u in community)
        in_degree_sum = sum(self._in_degrees[u] for u in community)
        return link_sum / self._m - out_degree_sum * in_degree_sum * (1 / self._m ** 2)

    def score(self, state: State) -> float:
        cus = state.to_cu_list()
        modularity = 0.0
        for community in util.to_pdg_partition(self._data, cus):
            modularity += self._compute_modularity(community)
        return modularity
