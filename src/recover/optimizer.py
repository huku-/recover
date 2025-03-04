# -*- coding: utf-8 -*-
"""Compile-unit map optimizer base definitions.

This module exports class class:`Optimizer`, subclassed by compile-unit map
optimizer implementations; currently the *local brute force* optimizer and the
*genetic optimizer*.

The purpose of compile-unit map optimizers is to reduce the problem of recovering
compile-units to a global or local optimization problem and then find a solution.
They are named after the fact that they process compile-unit maps (see module
:mod:`cu_map`), in order to optimize, according a global or local criterion, the
number and boundaries of compile-units. That is, optimizers are initially given
a compile-unit map, holding an estimation of how the compile-units are laid out,
and they attempt to optimize that layout.
"""

from recover.cu_map import CUInfo, CUMap
from recover.exporter import Data
from recover.fitness_function import FitnessFunction
from recover.state import State

import abc
import logging

from recover import util


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["Optimizer"]


class Optimizer(abc.ABC):
    """Base class for implementing compile-unit map optimizers.

    Args:
        data: The exported program data.
        cu_map: The compile-unit map to optimize.
        fitness_function: Fitness function to be used.
    """

    def __init__(
        self, data: Data, cu_map: CUMap, fitness_function: type[FitnessFunction]
    ) -> None:
        super(Optimizer, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._data = self._update_data(data)
        self._cu_map = cu_map
        self._fitness_function = fitness_function

    def _update_data(self, data: Data) -> Data:
        """Update program data so that sequence edges are removed from the PDG
        and, consequently, from the AFCG. We do that because sequence edges mess
        up score computations.

        Args:
            data: The exported program data.

        Returns:
            Program data with sequence edges removed from PDG and AFCG.
        """
        pdg = util.removed_sequence_edges_view(data.pdg)
        return Data(
            pdg=pdg, dfg=data.dfg, afcg=pdg.get_afcg(), sels=data.sels, segs=data.segs
        )

    def _update_cu_map(
        self, cu: CUInfo, next_cu: CUInfo, state: State, validate: bool = False
    ) -> tuple[int, int]:
        """Update compile-unit map, with respect to a new state, after an
        optimization step.

        Each optimization step processes compile-units in physically contiguous
        pairs and may modify their number and boundaries. These modifications
        are specified in the form of a new state ``state``. The task of this
        method is to update the compile-unit map with respect to this new state.

        Args:
            cu: First compile-unit that was optimized.
            next_cu: Second compile-unit that was optimized.
            state: New state returned by optimizer.
            validate: Validate compile-unit map (perform sanity checks on the
                new state).

        Returns:
            A tuple of two integers. The first holds the number of functions
            that moved from one compile-unit to another. If a new compile-unit
            was added during optimization, the second integer will hold its
            identifier, otherwise will be -1.
        """
        cu_map = self._cu_map

        num_changes = 0
        new_cu_id = -1

        num_bits_set = state.bit_count()

        assert (
            1 <= num_bits_set <= 3
        ), f"Invalid state {state:b} ({num_bits_set} set bits, not in [1,3])"

        cus = state.to_cu_list()

        assert (
            len(cus) == num_bits_set
        ), f"Invalid CUs for state {state:b} (expected {num_bits_set}, got {len(cus)})"

        if num_bits_set == 1:
            for ea in cus[0]:
                cu_map.set_cu_by_func_ea(ea, cu.cu_id)
                num_changes += 1
            self._logger.debug("Merged CU #%d (CUs %d)", next_cu.cu_id, len(cu_map))
        elif num_bits_set == 2:
            for ea in cus[0]:
                cu_map.set_cu_by_func_ea(ea, cu.cu_id)
                num_changes += 1
            for ea in cus[1]:
                cu_map.set_cu_by_func_ea(ea, next_cu.cu_id)
                num_changes += 1
        elif num_bits_set == 3:
            new_cu_id = cu_map.get_next_cu_id()
            for ea in cus[0]:
                cu_map.set_cu_by_func_ea(ea, cu.cu_id)
                num_changes += 1
            for ea in cus[1]:
                cu_map.set_cu_by_func_ea(ea, new_cu_id)
                num_changes += 1
            for ea in cus[2]:
                cu_map.set_cu_by_func_ea(ea, next_cu.cu_id)
                num_changes += 1
            self._logger.debug("Added CU #%d (CUs %d)", new_cu_id, len(cu_map))

        if validate:
            invalid_cus = cu_map.get_invalid_cus()
            if invalid_cus:
                cu_map.show()
                raise RuntimeError(f"Found invalid CUs: {invalid_cus}")

        return num_changes, new_cu_id

    @abc.abstractmethod
    def _optimize(self, cu: CUInfo, next_cu: CUInfo) -> tuple[int, int]:
        """Run an optimization round.

        This is an abstract method that descendants of this class must implement.
        The default implementation does nothing.

        Args:
            cu: Compile-unit to be examined in this optimization round.
            next_cu: Compile-unit physically bordering `cu`.

        Returns:
            A tuple of two integers. The first holds the number of functions
            that moved from one compile-unit to another. If a new compile-unit
            was added during optimization, the second integer will hold its
            identifier, otherwise will be -1.
        """
        return 0, -1

    def optimize(self) -> int:
        """Execute optimization rounds until equilibrium is reached.

        The optimizer's :meth:`_optimize()` method is executed as long as the
        number or boundaries of compile-units change.

        Returns:
            An integer indicating the total number of changes made to the
            compile-unit map.
        """
        cu_map = self._cu_map
        cu_map_ids = [cu_map.get_id()]

        num_rounds = prev_num_changes = num_changes = 0

        modified_cus = {cu.cu_id for cu in cu_map.get_cus()}

        while modified_cus:
            num_rounds += 1

            if self._logger.isEnabledFor(logging.INFO):
                num_modified_cus = len(modified_cus)
                num_cus = len(cu_map)
                self._logger.info(
                    "Round #%d (%d/%d), CUs %d",
                    num_rounds,
                    num_modified_cus,
                    num_changes,
                    num_cus,
                )

            for cu_id in set(modified_cus):
                cu = cu_map.get_cu_by_cu_id(cu_id)
                if cu:
                    next_cu = cu_map.get_next_cu(cu)
                    if next_cu:
                        num_cu_changes, new_cu_id = self._optimize(cu, next_cu)
                        if num_cu_changes > 0:
                            prev_cu = cu_map.get_prev_cu(cu)
                            if prev_cu:
                                modified_cus.add(prev_cu.cu_id)
                        if num_cu_changes == 0:
                            modified_cus.discard(cu_id)
                        if new_cu_id >= 0:
                            modified_cus.add(new_cu_id)
                        num_changes += num_cu_changes
                    else:
                        modified_cus.discard(cu_id)
                else:
                    modified_cus.discard(cu_id)

            cu_map_id = cu_map.get_id()
            if num_changes > prev_num_changes and cu_map_id in cu_map_ids:
                self._logger.warning("Optimization completed with recursion")
                modified_cus.clear()
            cu_map_ids.append(cu_map_id)

            prev_num_changes = num_changes

        return num_changes
