# -*- coding: utf-8 -*-
"""Compile-unit estimator interface.

Compile-unit estimators implement algorithms that return an initial, approximate
estimation of the number and boundaries of compile-units in a program. The output
of an estimator can be passed to an optimizer to improve the estimated results,
based on a user-specified fitness function.
"""
from recover.cu_map import CUMap
from recover.exporter import Data

import abc
import logging


__author__ = 'Chariton Karamitas <huku@census-labs.com>'

__all__ = ['Estimator']


class Estimator(abc.ABC):
    """Base class inherited by all compile-unit estimators.

    Args:
        data: The exported program data.
        segment: Selector of executable segment whose functions to partition in
            compile-unit (e.g. .text).
    """
    def __init__(self, data: Data, segment: int) -> None:
        super(Estimator, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._data = data
        self._segment = segment

    @abc.abstractmethod
    def estimate(self) -> CUMap:
        """Perform compile-unit estimation.

        Returns:
            Compile-unit map holding the estimation results.
        """
        raise NotImplementedError
