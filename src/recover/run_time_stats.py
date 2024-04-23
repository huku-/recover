# -*- coding: utf-8 -*-
"""Module to keep track of optimization pass run times.

This module exports class :class:`RunTimeStats`, used for caching and predicting
the run time of optimization passes with respect to input size. In our case,
input size is measured in bits.

Example:
    Every time an optimization pass is ran, ``RunTimeStats`` can be updated with
    the actual time it took the optimization pass to complete.

    >>> rts = RunTimeStats()
    >>> start_time = time.time()
    >>> run_optimization_pass()
    >>> end_time = time.time()
    >>> rts.set_run_time(num_bits, end_time - start_time)

    This can be repeated multiple times for various values of ``num_bits``.

    To look up the time it took for an optimization pass to complete:

    >>> rts.get_run_time(num_bits)

    If a previous measurement for ``num_bits`` does not exist in the cache,
    linear interpolation, based on already cached measurements, is used to
    predict the run time.
"""

import collections

import numpy


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["RunTimeStats"]


class RunTimeStats(object):
    """A class for caching and predicting the run time of optimization passes.

    Optimization algorithms, implemented in this library, process bit-vectors
    representing split-points between compile units (see `capeletti2017`_ for
    more information). This class is used for caching the time it takes for an
    optimization pass to complete, with respect to the size, measured in bits,
    of the input bit-vector.

    .. _capeletti2017:
       https://www.politesi.polimi.it/bitstream/10589/135107/3/2017_07_Capelletti.PDF
    """

    def __init__(self) -> None:
        super(RunTimeStats, self).__init__()
        self._stats: dict[int, float] = collections.defaultdict(float)

    def get_run_time(self, num_bits: int) -> float:
        """Return or predict the run time of an optimization pass whose input
        is ``num_bits`` bits.

        Run times of previous optimization passes are stored in a cache. When
        the run time for ``num_bits`` is requested, it is first looked up in the
        cache. If not in cache, linear interpolation is used to predict the run
        time based on previous samples found in the cache.

        Args:
            num_bits: Number of bits in input.

        Returns:
            The actual or predicted run time for the given input size.
        """
        if num_bits in self._stats:
            run_time = self._stats[num_bits]
        else:
            run_time = float(
                numpy.interp(
                    num_bits, list(self._stats.keys()), list(self._stats.values())
                )
            )
        return run_time

    def set_run_time(self, num_bits: int, run_time: float) -> None:
        """Store a measurement in the cache. Cached measurements are used for
        looking up or predicting run times of optimization passes. The more
        measurements, the better the prediction accuracy.

        In case a measurement for ``num_bits`` already exists, the maximum value
        is kept in the cache.

        Args:
            num_bits: Number of bits in input.
            run_time: Time it took the optimization pass to complete, measured
                in seconds.
        """
        cur_run_time = self._stats[num_bits]
        self._stats[num_bits] = max(cur_run_time, run_time)
