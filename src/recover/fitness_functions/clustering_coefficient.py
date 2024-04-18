# -*- coding: utf-8 -*-
"""Fitness function that computes a score based on the *clustering coefficient*
`clustering_coefficient`_.

.. _clustering_coefficient:
   https://en.wikipedia.org/wiki/Clustering_coefficient
"""

from recover.cu_map import CUMap
from recover.fitness_function import FitnessFunction
from recover.state import State
from recover.util import Data

import math

from recover import util

import networkx



__author__ = 'Chariton Karamitas <huku@census-labs.com>'

__all__ = ['ClusteringCoefficient']



class ClusteringCoefficient(FitnessFunction):
    """Clustering coefficient fitness function.

    The state number and the corresponding function list are converted to a
    series of communities of the program's PDG. An overall score is computed as
    the product of the communities' clustering coefficients.

    Args:
        data: Exported program data.
        cu_map: The program's compile-unit map.
    """
    def __init__(self, data: Data, cu_map: CUMap) -> None:
        super(ClusteringCoefficient, self).__init__(data, cu_map)
        self._graph = networkx.DiGraph(self._data.pdg)

    def score(self, state: State) -> float:
        cus = state.to_cu_list()
        total_coeff = 1.0
        for community in util.to_pdg_partition(self._data, cus):
            for coeff in networkx.clustering(self._graph, nodes=community).values():
                total_coeff *= 1.0 + coeff
        return math.tanh(total_coeff / len(state))
