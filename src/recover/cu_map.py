# -*- coding: utf-8 -*-
"""Compile-unit related definitions.

This module holds classes used to represent the ordering and boundaries of
compile-units in programs. More specifically, a program is treated as a list of
functions and each function is owned by a single compile-unit. Compile-units are
laid out consecutively and never overlap. More formally, compile-units are a
`partition`_ of functions in a program.

Each compile-unit is assigned a unique identifier, which is not related to the
order of the compile-unit in the program (i.e. compile-unit 10 might come before
compile-unit 1). A compile-unit's identifier, its boundaries (indices of first
and last function) and the corresponding addresses, are kept in instances of
class :class:`CUInfo`. Most APIs, defined below, return instances of this class.
Normally, you wouldn't instantiate it manually.

Class :class:`CUMap` is responsible for keeping track of which functions belong
to each compile-unit. It exposes a simple API for accessing and iterating
:class:`CUInfo` instances.

.. _partition:
   https://en.wikipedia.org/wiki/Partition_of_a_set
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import bisect
import dataclasses
import hashlib
import json
import pickle
import pprint


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["CUInfo", "CUMap"]


@dataclasses.dataclass
class CUInfo(object):
    """Represents a compile-unit in the program. It holds the addresses and
    indices of functions belonging to the compile-unit.
    """

    cu_id: int
    bounds: tuple[int, int]
    funcs: list[int]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CUInfo):
            raise NotImplementedError
        return self.cu_id == other.cu_id

    def __len__(self) -> int:
        return len(self.funcs)

    def get_func_idxs(self) -> list[int]:
        """Return the list of function indices in this compile-unit.

        Returns:
            List of function indices.
        """
        return list(range(*self.bounds))

    def get_func_eas(self) -> list[int]:
        """Return the list of function addresses in this compile-unit.

        Returns:
            List of function addresses.
        """
        return list(self.funcs)


class CUMap(object):
    """Represents a, so called, *compile-unit map*, which maps functions to
    compile-units they belong to.

    Args:
        funcs: List of function addresses to be assigned to compile-units.
    """

    def __init__(self, funcs: list[int]) -> None:
        super(CUMap, self).__init__()
        self._funcs = funcs
        self._func_to_cu = [-1] * len(funcs)

    def __len__(self) -> int:
        return len(set(self._func_to_cu))

    def __copy__(self) -> CUMap:
        cu_map = CUMap(self._funcs)
        cu_map._func_to_cu = self._func_to_cu
        return cu_map

    def __deepcopy__(self, _: dict) -> CUMap:
        cu_map = CUMap(self._funcs)
        cu_map._func_to_cu = list(self._func_to_cu)
        return cu_map

    @property
    def funcs(self) -> list[int]:
        """Return the list of functions in this compile-unit map.

        Returns:
            A copy of the list of functions to make sure callers do not
            accidentally modify the list used internally.
        """
        return list(self._funcs)

    def get_id(self) -> str:
        """Generate a unique string identifier for the current compile-unit map.

        Returns:
            Unique string identifier.
        """
        data = ""
        cu = self.get_first_cu()
        while cu:
            data += f"{len(cu)}|"
            cu = self.get_next_cu(cu)
        return hashlib.sha256(data.encode()).hexdigest()

    def get_invalid_cus(self) -> dict[int, int]:
        """Get list of invalid compile-units.

        Invalid compile-units are those whose boundaries overlap with other
        compile-units. Even though this should not happen under normal
        circumstances, checking the compile-unit map for invalid entries might
        help detect errors early during development.

        Returns:
            Dictionary mapping invalid compile-unit identifiers to their first
            function index.
        """
        invalid = {}
        i = 0
        k = len(self._func_to_cu)
        while i < k:
            cu_id = self._func_to_cu[i]
            if self._func_to_cu.index(cu_id) != i:
                invalid[cu_id] = i
            while i < k and self._func_to_cu[i] == cu_id:
                i += 1
        return invalid

    def get_next_cu_id(self) -> int:
        """Get next available compile-unit identifier. Used for creating a new
        compile-unit.

        Returns:
            The next available compile-unit identifier (should equal the number
            of compile-units, currently in the program, plus 1).
        """
        return max(self._func_to_cu) + 1

    def _get_cu_index(self, cu_id: int, start: int = 0) -> int:
        try:
            i = self._func_to_cu.index(cu_id, start)
        except ValueError:
            i = -1
        return i

    def _get_cu_bounds(self, cu_id: int, start: int = 0) -> tuple[int, int] | None:
        i = j = self._get_cu_index(cu_id, start=start)
        if i >= 0:
            while j < len(self._func_to_cu) and self._func_to_cu[j] == cu_id:
                j += 1
            return (i, j)

    def _get_cu_funcs(self, bounds: tuple[int, int]) -> list[int]:
        return [self._funcs[i] for i in range(*bounds)]

    def _get_cu_info(self, cu_id: int, start: int = 0) -> CUInfo | None:
        bounds = self._get_cu_bounds(cu_id, start=start)
        if bounds:
            funcs = self._get_cu_funcs(bounds)
            return CUInfo(cu_id, bounds, funcs)

    def get_first_cu(self) -> CUInfo | None:
        """Get first compile-unit.

        Returns:
            First compile-unit, or ``None`` if no compile-units are defined.
        """
        if len(self._func_to_cu) > 0:
            cu_id = self._func_to_cu[0]
            return self._get_cu_info(cu_id)

    def get_last_cu(self) -> CUInfo | None:
        """Get last compile-unit.

        Returns:
            Last compile-unit, or ``None`` if no compile-units are defined.
        """
        if len(self._func_to_cu) > 0:
            cu_id = self._func_to_cu[-1]
            return self._get_cu_info(cu_id)

    def get_next_cu(self, cu_info: CUInfo) -> CUInfo | None:
        """Get next compile-unit.

        Returns:
            The compile-unit that comes after ``cu_info``, or ``None`` if no
            such compile-unit exists.
        """
        cu_id = cu_info.cu_id
        i = self._get_cu_index(cu_id)
        if i >= 0:
            size = len(self._func_to_cu)
            while i < size and self._func_to_cu[i] == cu_id:
                i += 1
            if i < size:
                cu_id = self._func_to_cu[i]
                return self._get_cu_info(cu_id, start=i)

    def get_n_next_cus(self, cu_info: CUInfo, n: int) -> Iterator[CUInfo]:
        """Like :meth:`get_next_cu`, but yields the next ``n`` compile-units.

        Yields:
            ``n`` compile-units following ``cu_info``. Iteration might stop
            earlier if there are less than ``n`` compile-units defined after
            ``cu_info``.
        """
        for _ in range(n):
            next_cu_info = self.get_next_cu(cu_info)
            if not next_cu_info:
                break
            yield next_cu_info
            cu_info = next_cu_info

    def get_prev_cu(self, cu_info: CUInfo) -> CUInfo | None:
        """Get previous compile-unit.

        Returns:
            The compile-unit that comes before ``cu_info``, or ``None`` if no
            such compile-unit exists.
        """
        cu_id = cu_info.cu_id
        i = self._get_cu_index(cu_id)
        if i >= 1:
            cu_id = self._func_to_cu[i - 1]
            return self._get_cu_info(cu_id)

    def get_n_prev_cus(self, cu_info: CUInfo, n: int) -> Iterator[CUInfo]:
        """Like :meth:`get_prev_cu`, but yields the previous ``n`` compile-units.

        Yields:
            ``n`` compile-units preceding ``cu_info``. Iteration might stop
            earlier if there are less than ``n`` compile-units defined before
            ``cu_info``.
        """
        for _ in range(n):
            prev_cu_info = self.get_prev_cu(cu_info)
            if not prev_cu_info:
                break
            yield prev_cu_info
            cu_info = prev_cu_info

    def get_cus(self, reverse: bool = False) -> Iterator[CUInfo]:
        """Iterate through all compile-units in the compile-unit map.

        Compile-units are returned in the order they appear in the compile-unit
        map, or in reverse if ``reverse`` is ``True``.

        Yields:
            All compile-units currently defined.
        """
        if reverse:
            cu_info = self.get_last_cu()
            while cu_info:
                yield cu_info
                cu_info = self.get_prev_cu(cu_info)
        else:
            cu_info = self.get_first_cu()
            while cu_info:
                yield cu_info
                cu_info = self.get_next_cu(cu_info)

    def get_cu_by_cu_id(self, cu_id: int) -> CUInfo | None:
        """Get compile-unit given its compile-unit identifier.

        Args:
            cu_id: Identifier of target compile-unit.

        Returns:
            The requested compile-unit, or ``None`` if no such compile-unit
            exists.
        """
        return self._get_cu_info(cu_id)

    def get_cu_by_func_idx(self, i: int) -> CUInfo | None:
        """Get compile-unit given function specified by index.

        Args:
            i: Index of function whose compile-unit is requested.

        Returns:
            Compile-unit for function, or ``None`` if ``i`` is out of bounds.
        """
        if 0 <= i < len(self._func_to_cu):
            return self._get_cu_info(self._func_to_cu[i])

    def set_cu_by_func_idx(self, i: int, cu_id: int) -> None:
        """Move function, specified by its index, in compile-unit.

        Args:
            i: Index of function to move.
            cu_id: Compile-unit identifier of the target compile-unit.
        """
        self._func_to_cu[i] = cu_id

    def get_cu_by_func_ea(self, ea: int) -> CUInfo | None:
        """Get compile-unit given function specified by address.

        Args:
            ea: Address of function whose compile-unit is requested.

        Returns:
            Compile-unit for function, or ``None`` if address is not found.
        """
        i = bisect.bisect_left(self._funcs, ea)
        if i != len(self._funcs) and self._funcs[i] == ea:
            return self.get_cu_by_func_idx(i)

    def set_cu_by_func_ea(self, ea: int, cu_id: int) -> None:
        """Move function, specified by address, in compile-unit.

        Args:
            ea: Address of function to move.
            cu_id: Compile-unit identifier of the target compile-unit.
        """
        i = bisect.bisect_left(self._funcs, ea)
        if i != len(self._funcs) and self._funcs[i] == ea:
            self.set_cu_by_func_idx(i, cu_id)

    def renumber(self) -> None:
        """Renumber all compile-unit identifiers, in this compile-unit map, so
        that they are sequential integers starting at 0.
        """
        i = j = 0
        k = len(self._func_to_cu)
        while i < k:
            cu_id = self._func_to_cu[i]
            while i < k and self._func_to_cu[i] == cu_id:
                self._func_to_cu[i] = j
                i += 1
            j += 1

    def show(self) -> None:
        """Pretty-print compile-unit map."""
        pprint.pprint(self._func_to_cu, width=80, compact=True)

    def save_pickle(self, path: str | Path) -> None:
        """Save compile-unit map in a file in Pickle format.

        Args:
            path: Path of file to save compile-unit map to.
        """
        with open(path, "wb") as fp:
            pickle.dump(self, fp)

    def save_json(self, path: str | Path) -> None:
        """Save compile-unit map in a file in JSON format.

        Args:
            path: Path of file to save compile-unit map to.
        """
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(
                {"funcs": self._funcs, "func_to_cu": self._func_to_cu},
                fp=fp,
                sort_keys=True,
                indent=4,
            )

    @classmethod
    def load(cls, path: str | Path) -> CUMap:
        """Load a compile-unit map from a file. Automatically determines the file
        format based on its extension (".pcl" vs. ".json").

        Args:
            path: Path of file to load the compile-unit map from.

        Returns:
            The loaded compile-unit map.

        Raises:
            ValueError: If the file extension of ``path`` is neither ".pcl" nor
                ".json".
            TypeError: If the loaded data does not look like a previously saved
                compile-unit map.
        """
        if not isinstance(path, Path):
            path = Path(path)

        if path.suffix == ".pcl":
            with open(path, "rb") as fp:
                self = pickle.load(fp)
                if not isinstance(self, cls):
                    raise TypeError(f"Loaded invalid class {type(self)}")
                return self

        elif path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as fp:
                js = json.load(fp)
                if "funcs" not in js or "func_to_cu" not in js:
                    raise TypeError("Loaded invalid class")
                self = CUMap(js["funcs"])
                self._func_to_cu = js["funcs_to_cu"]
                return self

        raise ValueError(f"Unrecognized file format {path}")
