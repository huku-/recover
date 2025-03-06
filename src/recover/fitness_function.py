# -*- coding: utf-8 -*-
"""Fitness function interface.

Fitness functions use heuristics to compute a *fitness score* for a given
compile-unit segmentation given in the form of an optimizer state (i.e. a
bit-vector). They are used by optimization algorithms repeatedly to compute
fitness scores during state exploration.

The current design of the fitness function interface is flexible enough to allow
for future use for global optimization purposes.
"""

from recover.cu_map import CUMap
from recover.exporter import Data
from recover.state import State

import abc
import logging

from recover import util


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["FitnessFunction", "DataFitnessFunction"]


class FitnessFunction(abc.ABC):
    """Represents a fitness function. Arguments to this constructor allow for
    arbitrary computations in :meth:`score()` based on the current state of the
    optimization process.

    Args:
        data: Exported program data.
        cu_map: The program's compile-unit map.
        init_state: Initial state before any further optimization is performed
            (useful in cases where preprocessing might be required).
    """

    def __init__(self, data: Data, cu_map: CUMap, init_state: State) -> None:
        super(FitnessFunction, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._data = data
        self._cu_map = cu_map
        self._init_state = init_state

    @abc.abstractmethod
    def score(self, state: State) -> float:
        """Compute the fitness score of a specific optimization state.

        Args:
            state: The state whose fitness score to compute.

        Returns:
            The computed fitness score.
        """
        raise NotImplementedError


class DataFitnessFunction(FitnessFunction):
    """Base class for implementing fitness functions that take into account data
    references.

    Args:
        data: Exported program data.
        cu_map: The program's compile-unit map.
        init_state: Initial state before any further optimization is performed
            (useful in cases where preprocessing might be required).
    """

    def __init__(self, data: Data, cu_map: CUMap, init_state: State) -> None:
        super(DataFitnessFunction, self).__init__(data, cu_map, init_state)
        funcs = init_state.funcs
        nodes = set(funcs)
        data_refs = {}
        for func in funcs:
            func_data_refs = (
                set(util.get_func_data_refs(data.dfg, func, flatten=True)) - nodes
            )
            nodes |= func_data_refs
            data_refs[func] = func_data_refs
        self._nodes = nodes
        self._data_refs = data_refs
