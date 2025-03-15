# -*- coding: utf-8 -*-
"""Agglomerative compile-unit estimators.

This module implements :class:`AGGLNSE` and :class:`AGGLPSE`, the agglomerative
compile-unit estimators.
"""

from recover.cu_map import CUInfo, CUMap
from recover.estimator import Estimator
from recover.exporter import Data

from networkx import Graph

from recover import util

import networkx


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["AGGLNSE", "AGGLPSE"]


class _Base(Estimator):
    """Base class inherited by both AGGLNSE and AGGLPSE.

    The agglomerative compile-unit estimation algorithm is common for both
    AGGLNSE and AGGLNSE; what changes is the number of edges in the AFCG. This
    class implements the aforementioned common interface.

    Args:
        data: The exported program data.
        segment: Selector of executable segment whose functions to partition in
            compile-unit (e.g. .text).
    """

    def __init__(self, data: Data, segment: int) -> None:
        super(_Base, self).__init__(data, segment)
        self._afcg = util.segment_view(data.afcg, segment)

    def _build_cu_graph(self, cu_map: CUMap) -> Graph:
        """Build compile-unit graph given a compile-unit map.

        Nodes in this graph correspond to compile-units, while edges represent
        function calls between functions belonging to different compile-units.
        For each edge, an attribute, named *count*, holds the number of function
        calls between the connected compile-units. Self-loops from a compile-unit
        to itself are not taken into account.

        Args:
            cu_map: The program's compile-unit map.

        Returns:
            A directed graph representing the compile-unit graph.
        """
        cu_graph = Graph()
        cu = cu_map.get_first_cu()
        while cu:
            cu_graph.add_node(cu.cu_id)
            for func_ea in cu.get_func_eas():
                for succ_ea in self._afcg.successors(func_ea):
                    succ_cu = cu_map.get_cu_by_func_ea(succ_ea)
                    if not succ_cu:
                        raise ValueError(
                            f"Could not find CU for function at {succ_ea:#x}"
                        )
                    if cu.cu_id != succ_cu.cu_id:
                        edge = (cu.cu_id, succ_cu.cu_id)
                        if cu_graph.has_edge(*edge):
                            cu_graph.edges[edge]["count"] += 1
                        else:
                            cu_graph.add_edge(*edge, count=1)
            cu = cu_map.get_next_cu(cu)
        return cu_graph

    def _count_non_tree_edges(self, cu_graph: Graph, source: int) -> int:
        """Count the number of non-tree edges in the compile-unit graph. This is
        used as a metric to measure how much the compile-unit graph differs from
        an ideal compile-unit tree.

        Args:
            cu_graph: The compile-unit graph.
            source: The compile-unit to start the DFS from.

        Returns:
            Number of non-tree edges (i.e. back-edges and cross-links).
        """
        num_edges = 0
        for tail, head, label in networkx.dfs_labeled_edges(cu_graph, source=source):
            if tail != head and label == "nontree":
                num_edges += cu_graph.edges[(tail, head)]["count"]
        return num_edges

    def _remove_from_cu(
        self, cu_map: CUMap, cu_graph: Graph, func_ea: int, func_cu: CUInfo
    ) -> None:
        """Remove function from compile-unit and update compile-unit graph edges
        accordingly.

        Args:
            cu_map: The program's compile-unit map.
            cu_graph: The compile-unit graph.
            func_ea: Address of function to be removed from compile-unit.
            func_cu: Compile-unit where the function will be removed from.
        """
        for ea in self._afcg.predecessors(func_ea):
            cu = cu_map.get_cu_by_func_ea(ea)
            if not cu:
                raise ValueError(f"Could not find CU for function at {ea:#x}")
            edge = (cu.cu_id, func_cu.cu_id)
            if cu_graph.has_edge(*edge):
                count = cu_graph.edges[edge]["count"] - 1
                if count == 0:
                    cu_graph.remove_edge(*edge)
                else:
                    cu_graph.edges[edge]["count"] = count

        for ea in self._afcg.successors(func_ea):
            cu = cu_map.get_cu_by_func_ea(ea)
            if not cu:
                raise ValueError(f"Could not find CU for function at {ea:#x}")
            edge = (func_cu.cu_id, cu.cu_id)
            if cu_graph.has_edge(*edge):
                count = cu_graph.edges[edge]["count"] - 1
                if count == 0:
                    cu_graph.remove_edge(*edge)
                else:
                    cu_graph.edges[edge]["count"] = count

    def _move_to_cu(
        self, cu_map: CUMap, cu_graph: Graph, func_ea: int, func_cu: CUInfo
    ) -> None:
        """Move function in compile-unit and update compile-unit graph edges
        accordingly.

        Args:
            cu_map: The program's compile-unit map.
            cu_graph: The compile-unit graph.
            func_ea: Address of function to be added in compile-unit.
            func_cu: Compile-unit where the function will be moved to.
        """
        for ea in self._afcg.predecessors(func_ea):
            cu = cu_map.get_cu_by_func_ea(ea)
            if not cu:
                raise ValueError(f"Could not find CU for function at {ea:#x}")
            if cu.cu_id != func_cu.cu_id:
                edge = (cu.cu_id, func_cu.cu_id)
                if cu_graph.has_edge(*edge):
                    cu_graph.edges[edge]["count"] += 1
                else:
                    cu_graph.add_edge(*edge, count=1)

        for ea in self._afcg.successors(func_ea):
            cu = cu_map.get_cu_by_func_ea(ea)
            if not cu:
                raise ValueError(f"Could not find CU for function at {ea:#x}")
            if cu.cu_id != func_cu.cu_id:
                edge = (func_cu.cu_id, cu.cu_id)
                if cu_graph.has_edge(*edge):
                    cu_graph.edges[edge]["count"] += 1
                else:
                    cu_graph.add_edge(*edge, count=1)

    def _estimate(self) -> CUMap:
        """Common agglomerative compile-unit estimation algorithm.

        The algorithm splits functions in physically contiguous groups that
        minimize the number of non-tree edges in the compile-unit graph, starting
        from the first (i.e. lowest-address) function.

        The algorithm starts by constructing a graph of singleton compile-units
        (i.e. compile-units consisting of a single function). In this graph
        edges basically correspond to AFCG edges.

        Next, it picks the first function and keeps moving its physical neighbors
        in its compile-unit for as long as the resulting compile-unit graph,
        corresponding to the updated grouping, has fewer non-tree edges (i.e.
        looks more like a tree). If the new grouping results in more non-tree
        edges, the most recently considered function is restored in its original
        compile-unit and the process restarts from that function.

        Returns:
            Compile-unit map holding the estimation results.
        """
        afcg = self._afcg

        func_eas = sorted(afcg)

        cu_map = CUMap(func_eas)
        for i in range(len(func_eas)):
            cu_map.set_cu_by_func_idx(i, i + 1)
        # cu_map.show()

        num_rounds = num_changes = 0

        cu_graph = self._build_cu_graph(cu_map)
        cache = {}

        while True:
            func_idx = 0

            cu = cu_map.get_cu_by_func_idx(func_idx)
            if not cu:
                raise ValueError(
                    f"Could not find CU for function at {func_eas[func_idx]:#x}"
                )
            next_func_idx = func_idx + len(cu)

            if cu.cu_id not in cache:
                cache[cu.cu_id] = self._count_non_tree_edges(cu_graph, cu.cu_id)

            tmp_num_changes = 0
            while next_func_idx < len(func_eas):
                next_func_ea = func_eas[next_func_idx]
                next_cu = cu_map.get_cu_by_func_idx(next_func_idx)
                if not next_cu:
                    raise ValueError(
                        f"Could not find CU for function at {next_func_ea:#x}"
                    )

                self._remove_from_cu(cu_map, cu_graph, next_func_ea, next_cu)
                cu_map.set_cu_by_func_idx(next_func_idx, cu.cu_id)
                self._move_to_cu(cu_map, cu_graph, next_func_ea, cu)

                num_edges = self._count_non_tree_edges(cu_graph, cu.cu_id)
                min_num_edges = cache[cu.cu_id]
                # self._logger.debug(
                #     "Function %d/%d, CUs %d", next_func_idx, len(func_eas), len(cu_map)
                # )

                if num_edges <= min_num_edges:
                    cache[cu.cu_id] = num_edges
                    tmp_num_changes += 1
                elif num_edges > min_num_edges:
                    self._remove_from_cu(cu_map, cu_graph, next_func_ea, cu)
                    cu_map.set_cu_by_func_idx(next_func_idx, next_cu.cu_id)
                    self._move_to_cu(cu_map, cu_graph, next_func_ea, next_cu)
                    func_idx = next_func_idx
                    if next_cu.cu_id not in cache:
                        cache[next_cu.cu_id] = self._count_non_tree_edges(
                            cu_graph, next_cu.cu_id
                        )

                cu = cu_map.get_cu_by_func_idx(func_idx)
                if not cu:
                    raise ValueError(
                        f"Could not find CU for function at {func_eas[func_idx]:#x}"
                    )

                next_func_idx = func_idx + len(cu)

            num_rounds += 1
            num_changes += tmp_num_changes
            self._logger.debug(
                "Round #%d (%d/%d), non-tree edges %d, CUs %d",
                num_rounds,
                tmp_num_changes,
                num_changes,
                min_num_edges,
                len(cu_map),
            )

            if tmp_num_changes == 0:
                break

        cu_map.renumber()
        # cu_map.show()

        return cu_map


class AGGLNSE(_Base):
    """*Agglomeration - No Sequence Edges* (AGGLNSE) compile-unit estimator.

    Args:
        data: The exported program data.
        segment: Selector of executable segment whose functions to partition in
            compile-unit (e.g. .text).
    """

    def __init__(self, data: Data, segment: int) -> None:
        super(AGGLNSE, self).__init__(data, segment)
        self._afcg = util.removed_sequence_edges_view(self._afcg)

    def estimate(self) -> CUMap:
        return self._estimate()


class AGGLPSE(_Base):
    """*Agglomeration - Partial Sequence Edges* (AGGLPSE) compile-unit estimator.

    Args:
        data: The exported program data.
        segment: Selector of executable segment whose functions to partition in
            compile-unit (e.g. .text).
    """

    def __init__(self, data: Data, segment: int) -> None:
        super(AGGLPSE, self).__init__(data, segment)
        self._afcg = util.removed_sequence_edges_view_partial(self._afcg)

    def estimate(self) -> CUMap:
        return self._estimate()
