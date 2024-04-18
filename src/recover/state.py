# -*- coding: utf-8 -*-
"""Optimizer state-space definitions.

Optimizers, as defined in this module, explore states. Each state corresponds to
a different way of splitting a series of functions into a predetermined number
of compile-units. A state is represented as a bit-vector (integer), with each
bit representing a function and each set bit indicating a split-point (see
`capeletti2017`_).

For example, let's assume one needs to explore each possible way of splitting 8
functions in 2 compile-units. Each state, in this case, is an 8-bit number::

    0b10010000

This state, for example, represents the case where the first 3 functions form a
compile-unit and the remaining 5 another.

.. _capeletti2017:
   https://www.politesi.polimi.it/bitstream/10589/135107/3/2017_07_Capelletti.PDF
"""

from __future__ import annotations

from typing import Iterator, List

import itertools



__author__ = 'Chariton Karamitas <huku@census-labs.com>'

__all__ = ['State']



class State(int):
    """Represents a state during optimization.

    A state is basically a bit-vector (integer) that represents the way a list
    of functions is split into compile-units. This class, encapsulates both the
    aforementioned bit-vector and the corresponding list of functions, since
    they are usually used alongside each other.
    """

    _funcs: List[int]


    def __new__(cls, state: int, funcs: List[int]) -> State:
        self = int.__new__(cls, state)
        self._funcs = funcs
        return self


    def __len__(self) -> int:
        """Returns the size of this state.

        Returns:
            Size of state in bits or, equivalently, number of functions being
            segmented in compile-units.
        """
        return len(self._funcs)


    @property
    def funcs(self) -> List[int]:
        """Return the list of functions in this state.

        Returns:
            A copy of the list of functions to make sure callers do not
            accidentally modify the list used internally.
        """
        return list(self._funcs)


    def to_cu_list(self) -> List[List[int]]:
        """Convert this state to a list of compile-units (i.e. list of function
        address lists).

        Returns:
            List of compile-units, each holding at least one function.
        """
        cu_list = []
        funcs = self._funcs

        i, j = 0, len(funcs) - 1
        while j >= 0:
            if self & (1 << j):
                cu = [funcs[i]]
                while j - 1 >= 0 and not (self & (1 << (j - 1))):
                    cu.append(funcs[i + 1])
                    i += 1
                    j -= 1
                cu_list.append(cu)
            i += 1
            j -= 1

        return cu_list


    def siblings(self, num_cus: int) -> Iterator[State]:
        """Generate all sibling states of this state.

        Generates all states of the same size (number of bits) with ``num_cus``
        bits set. Passing ``num_cus``, basically, allows for the corresponding
        function list to be split in an arbitrary number of compile-units. As a
        reminder, since the generated bit-vectors represent split-points between
        compile-units, the highest bit, at index ``num_cus - 1``, should always
        be set, to indicate that the first compile-unit is distinct from the
        compile-units coming before. This leaves ``num_cus - 1`` for the
        remaining combinations.

        Args:
            num_cus: Number of set bits in generated states or, equivalently,
                number of compile-units into which to split the function list.

        Yields:
            Sibling states with ``num_cus`` bits set.
        """
        funcs = self._funcs
        size = len(funcs)
        for bits in itertools.combinations(range(size - 1), num_cus - 1):
            state = (1 << (size - 1)) + sum(1 << i for i in bits)
            yield State(state, funcs)


    @classmethod
    def from_cu_list(cls, cu_list: List[List[int]]) -> State:
        """Convert list of compile-units (i.e. list of function address lists)
        to a state.

        This, basically, builds a state number that has one bit set for each
        split-point between those compile-units. The idea is the following; the
        first function of the last compile-unit is a split-point. So, starting
        from the last compile-unit, bit at ``len(cu) - 1`` is set to one. We
        repeat the same step for each compile-unit in reverse order, but we add
        the total length of all compile-units following it when computing the
        index of the bit that needs to be set.

        Args:
            cu_list: List of compile-units.

        Returns:
            State representing the given list of compile-units.
        """
        state = i = 0
        for cu in reversed(cu_list):
            state |= 1 << (i + len(cu) - 1)
            i += len(cu)
        return cls(state, list(itertools.chain(*cu_list)))
