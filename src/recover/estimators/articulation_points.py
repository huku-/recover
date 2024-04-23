# -*- coding: utf-8 -*-
"""Articulation-point-based compile-unit estimators.

This module implements :class:`APSNSE` and :class:`APSPSE`, the articulation-point-
based compile-unit estimators.
"""

from recover.cu_map import CUMap
from recover.estimator import Estimator
from recover.exporter import Data

from recover import util

import networkx


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["APSNSE", "APSPSE"]


class _Base(Estimator):
    """Base class inherited by both APSNSE and APSPSE.

    The articulation-point-based compile-unit estimation algorithm is common for
    both APSNSE and APSPSE; what changes is the number of edges in the AFCG. This
    class implements the aforementioned common interface.

    Args:
        data: The exported program data.
        segment: Selector of executable segment whose functions to partition in
            compile-unit (e.g. .text).
    """

    def __init__(self, data: Data, segment: int) -> None:
        super(_Base, self).__init__(data, segment)
        self._afcg = util.segment_view(data.afcg, segment)

    def _estimate(self) -> CUMap:
        """Common articulation-point-based compile-unit estimation algorithm.

        Finds the articulation-points in the program's AFCG and partitions
        functions in compile-units with articulation-points being the boundaries.

        Returns:
            Compile-unit map holding the estimation results.
        """
        afcg = self._afcg.to_undirected()

        func_eas = list(sorted(afcg))

        cu_map = CUMap(func_eas)

        i = prev_j = j = 0
        for i, ap in enumerate(sorted(networkx.articulation_points(afcg))):
            j = func_eas.index(ap, prev_j)
            for k in range(prev_j, j):
                cu_map.set_cu_by_func_idx(k, i + 1)
            prev_j = j

        for k in range(prev_j, len(func_eas)):
            cu_map.set_cu_by_func_idx(k, i + 1)

        cu_map.renumber()
        # cu_map.show()

        return cu_map


class APSNSE(_Base):
    """*Articulation Points - No Sequence Edges* (APSNSE) compile-unit estimator.

    Args:
        data: The exported program data.
        segment: Selector of executable segment whose functions to partition in
            compile-unit (e.g. .text).
    """

    def __init__(self, data: Data, segment: int) -> None:
        super(APSNSE, self).__init__(data, segment)
        self._afcg = util.removed_sequence_edges_view(self._afcg)

    def estimate(self) -> CUMap:
        return self._estimate()


class APSPSE(_Base):
    """*Articulation Points - Partial Sequence Edges* (APSPSE) compile-unit
    estimator.

    Args:
        data: The exported program data.
        segment: Selector of executable segment whose functions to partition in
            compile-unit (e.g. .text).
    """

    def __init__(self, data: Data, segment: int) -> None:
        super(APSPSE, self).__init__(data, segment)
        self._afcg = util.removed_sequence_edges_view_partial(self._afcg)

    def estimate(self) -> CUMap:
        return self._estimate()
