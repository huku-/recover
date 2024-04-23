# -*- coding: utf-8 -*-
"""Various utility functions."""

from collections.abc import Iterable

import bisect
import collections
import json

from networkx import Graph

import networkx

from recover.graphs import DFG, EdgeClass, EdgeType
from recover.exporter import Data


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = [
    "get_func_data_refs",
    "to_pdg_partition",
    "removed_sequence_edges_view",
    "removed_sequence_edges_view_partial",
    "segment_view",
]


DataRef = tuple[int, int, int]
DataRefs = dict[int, list[DataRef]]


def get_func_data_refs(
    dfg: DFG,
    func_ea: int | Iterable[int],
    debug: bool = False,
    merge: bool = False,
    skip_sels: list[int] | None = None,
) -> DataRefs:
    """Get data references of function(s).

    Args:
        dfg: Program's DFG.
        func_ea: Address or iterable of addresses of function(s) whose data
            references to return.
        debug: Print data references to standard output in JSON format for
            debugging purposes.
        merge: Merge overlapping data references, if any.
        skip_sels: List of selectors of segments whose data references not to
            include in the returned data references.

    Returns:
        Data references of function(s).
    """
    data_eas: list[int] = []
    data_sizes: list[int] = []
    data_freqs: list[int] = []
    data_sels: list[int] = []

    def _overlap(
        start_ea_i: int, end_ea_i: int, start_ea_j: int, end_ea_j: int
    ) -> bool:
        return not (end_ea_i < start_ea_j or end_ea_j < start_ea_i)

    def _add_data_ref(ea: int, size: int, sel: int) -> bool:
        i = bisect.bisect_left(data_eas, ea)
        if i != len(data_eas) and data_eas[i] == ea:
            data_sizes[i] = max(data_sizes[i], size)
            data_freqs[i] += 1
            exists = True
        else:
            data_eas.insert(i, ea)
            data_sizes.insert(i, size)
            data_freqs.insert(i, 1)
            data_sels.insert(i, sel)
            exists = False
        return exists

    def _get_data_refs(ea: int) -> None:
        for _, succ_ea, key, edge_type in dfg.edges(
            nbunch=ea, keys=True, data="edge_type"
        ):
            size = dfg.edges[ea, succ_ea, key]["size"]
            sel = dfg.nodes[succ_ea]["segment"]
            if (
                not _add_data_ref(succ_ea, size, sel)
                and edge_type != EdgeType.DATA2CODE
            ):
                _get_data_refs(succ_ea)

    for _, succ_ea, size in dfg.edges(nbunch=func_ea, data="size"):
        sel = dfg.nodes[succ_ea]["segment"]
        _add_data_ref(succ_ea, size, sel)
        _get_data_refs(succ_ea)

    if merge and len(data_eas) >= 2:
        for i in range(len(data_eas) - 2, -1, -1):
            j = i + 1
            start_ea_i = data_eas[i]
            end_ea_i = start_ea_i + data_sizes[i]
            start_ea_j = data_eas[j]
            end_ea_j = start_ea_j + data_sizes[j]
            while _overlap(start_ea_i, end_ea_i, start_ea_j, end_ea_j):
                start_ea = min(start_ea_i, start_ea_j)
                end_ea = max(end_ea_i, end_ea_j)
                data_eas[i] = start_ea
                data_sizes[i] = end_ea - start_ea
                data_freqs[i] += data_freqs[j]
                del data_eas[j], data_sizes[j], data_freqs[j], data_sels[j]
                if j >= len(data_eas):
                    break
                start_ea_j = data_eas[j]
                end_ea_j = start_ea_j + data_sizes[j]

    data_refs = collections.defaultdict(list)
    for sel, ea, size, freq in zip(data_sels, data_eas, data_sizes, data_freqs):
        if not skip_sels or sel not in skip_sels:
            data_refs[sel].append((ea, size, freq))

    if debug:
        if isinstance(func_ea, list):
            k = ",".join([f"{ea:#x}" for ea in func_ea])
        else:
            k = f"{func_ea:#x}"
        d = collections.defaultdict(list)
        for sel in data_refs:
            for ea, size, freq in sorted(data_refs[sel]):
                d[sel].append((f"{ea:#x}", size, freq))
        print(json.dumps({f"{k}": d}, indent=4))

    return data_refs


def to_pdg_partition(
    data: Data, partition: list[list[int]], disjoint: bool = True
) -> list[set[int]]:
    """Take a partition of program functions, provided as a list-of-lists of
    function addresses, and convert it to a PDG partition, a list-of-sets of
    function and data addresses (addresses of data elements accessed by those
    functions). Furthermore, if ``disjoint`` is true, PDG partitions will be
    disjoint, i.e. no data element will appear in more than one partition.

    .. warning::
       Notice that ``partition`` should also be non-overlapping, but for
       performance purposes, we don't explicitly check it here.

    Args:
        data: Exported program data.
        partition: Partition of program functions.
        disjoint: Make PDG partitions disjoint.

    Returns:
        PDG partition corresponding to ``partition``.
    """

    def _flatten_data_refs(data_refs: DataRefs) -> list[int]:
        flat_data_refs = []
        for sel in data_refs:
            for sel_data_refs in data_refs[sel]:
                flat_data_refs.append(sel_data_refs[0])
        return flat_data_refs

    pdg_partition: list[set[int]] = []

    for func_eas in partition:
        data_refs = _flatten_data_refs(get_func_data_refs(data.dfg, func_eas))
        if disjoint:
            pdg_partition.append(
                set(func_eas + data_refs) - set().union(*pdg_partition)
            )
        else:
            pdg_partition.append(set(func_eas + data_refs))

    return pdg_partition


def removed_sequence_edges_view(graph: Graph) -> Graph:
    """Return a subgraph view of a program graph (e.g. PDG), which removes all
    sequence edges.

    Args:
        graph: Program graph whose subgraph to return.

    Returns:
        A graph view over the given graph.
    """

    def _filter_edge(tail: int, head: int, key: int) -> bool:
        return graph.edges[tail, head, key]["edge_class"] != EdgeClass.SEQUENCE

    return type(graph)(
        networkx.classes.graphviews.subgraph_view(graph, filter_edge=_filter_edge)
    )


def removed_sequence_edges_view_partial(graph: Graph) -> Graph:
    """Return a subgraph view of a program graph (e.g. PDG), which removes most,
    but not all, sequence edges. More specifically, sequence edges that, when
    removed, result in orphan nodes are preserved.

    Args:
        graph: Program graph whose subgraph to return.

    Returns:
        A graph view over the given graph.
    """

    def _filter_edge(tail: int, head: int, key: int) -> bool:
        return (
            graph.edges[tail, head, key]["edge_class"] != EdgeClass.SEQUENCE
            or graph.out_degree(tail) == 1
            or graph.in_degree(head) == 1
        )

    return type(graph)(
        networkx.classes.graphviews.subgraph_view(graph, filter_edge=_filter_edge)
    )


def segment_view(graph: Graph, sel: int) -> Graph:
    """Return a subgraph view of a program graph (e.g. PDG), which only contains
    program elements (code & data) located at a specified segment.

    Args:
        graph: Program graph whose subgraph to return.
        sel: Segment selector of chosen segment.

    Returns:
        A graph view over the given graph.
    """

    def _filter_node(node: int) -> bool:
        return graph.nodes[node].get("segment") == sel

    return type(graph)(
        networkx.classes.graphviews.subgraph_view(graph, filter_node=_filter_node)
    )
