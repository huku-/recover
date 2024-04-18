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


__author__ = 'Chariton Karamitas <huku@census-labs.com>'

__all__ = ['FitnessFunction']


class FitnessFunction(abc.ABC):
    """Represents a fitness function. Arguments to this constructor to allow for
    arbitrary computations in :meth:`score()` based on the current state of the
    optimization process.

    Args:
        data: Exported program data.
        cu_map: The program's compile-unit map.
    """
    def __init__(self, data: Data, cu_map: CUMap) -> None:
        super(FitnessFunction, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._data = data
        self._cu_map = cu_map

    @abc.abstractmethod
    def score(self, state: State) -> float:
        """Compute the fitness score of a specific optimization state.

        Args:
            state: The state whose fitness score to compute.

        Returns:
            The computed fitness score.
        """
        raise NotImplementedError
