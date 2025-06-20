# -*- coding: utf-8 -*-
"""IDA Pro exporter."""

from collections.abc import Iterator

from recover.exporter import Exporter, Segment, SegmentClass
from recover.graphs import PDG, EdgeType, EdgeClass, NodeType

from ida_funcs import func_t

import itertools
import logging

import networkx

import ida_bytes
import ida_funcs
import ida_gdl
import ida_segment
import ida_xref
import idc


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["IdaPro"]


AGGRESSIVE = False


def _is_badaddr(ea: int) -> bool:
    return ea >= 0xFF00000000000000 or ea == idc.BADADDR


def _is_named(flags: int) -> bool:
    return flags & ida_bytes.FF_NAME


def _is_labeled(flags: int) -> bool:
    # return flags & ida_bytes.FF_REF and \
    #     (flags & ida_bytes.FF_NAME or flags & ida_bytes.FF_LABL)
    return flags & (ida_bytes.FF_NAME | ida_bytes.FF_LABL)


def _is_referenced(flags: int) -> bool:
    return bool(flags & ida_bytes.FF_REF)


def _is_data(flags: int) -> bool:
    return idc.is_data(flags) or idc.is_unknown(flags)


def _is_code(flags: int) -> bool:
    return idc.is_code(flags)


def _get_ea_info(ea: int) -> tuple[int, int]:
    return (ea, ida_bytes.get_item_size(ea))


class _PdgBuilder(object):
    """Builds PDG using IDA Pro APIs."""

    def __init__(self) -> None:
        super(_PdgBuilder, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._pdg = PDG()

    def _add_program_node(
        self, node: int, node_type: NodeType = NodeType.INVALID
    ) -> None:

        flags = ida_bytes.get_flags(node)

        if node_type == NodeType.INVALID:
            if _is_code(flags):
                node_type = NodeType.CODE
            else:
                node_type = NodeType.DATA

        segment = ida_segment.getseg(node).sel

        if _is_named(flags):
            name = idc.get_name(node)
        else:
            name = f"{node_type.name}:{node:#x}"

        self._pdg.add_program_node(
            node, node_type=node_type, segment=segment, name=name
        )
        self._logger.debug("%s/%#x (%s)", name, node, node_type.name)

    def _add_program_edge(
        self,
        tail: int,
        head: int,
        edge_type: EdgeType = EdgeType.INVALID,
        edge_class: EdgeClass = EdgeClass.INVALID,
        size: int = 0,
    ) -> None:

        if edge_type == EdgeType.INVALID:
            if _is_code(ida_bytes.get_flags(tail)):
                if _is_code(ida_bytes.get_flags(head)):
                    edge_type = EdgeType.CODE2CODE
                else:
                    edge_type = EdgeType.CODE2DATA
            else:
                if _is_code(ida_bytes.get_flags(head)):
                    edge_type = EdgeType.DATA2CODE
                else:
                    edge_type = EdgeType.DATA2DATA

        for data in self._pdg.get_edge_data(tail, head, default={}).values():
            if data["edge_class"] == edge_class:
                break
        else:
            self._pdg.add_program_edge(
                tail, head, edge_type=edge_type, edge_class=edge_class, size=size
            )

        self._logger.debug("%#x -> %#x (%s)", tail, head, edge_type.name)

    def _process_heads(self, ea: int) -> Iterator[tuple[int, int]]:

        if _is_labeled(ida_bytes.get_flags(ea)):
            yield _get_ea_info(ea)

            if AGGRESSIVE:
                ea = idc.next_head(ea, idc.BADADDR)

                while ea != idc.BADADDR:
                    flags = ida_bytes.get_flags(ea)
                    if _is_labeled(flags) or not _is_data(flags):
                        break
                    if not ida_bytes.is_align(flags):
                        yield _get_ea_info(ea)

                    ea = idc.next_head(ea, idc.BADADDR)

    def _process_drefs(
        self, ea: int, seen: set[int] | None = None
    ) -> Iterator[tuple[int, int]]:

        if not seen:
            seen = set()

        func = ida_funcs.get_func(ea)
        if func:
            src_ea = func.start_ea
        else:
            src_ea = ea

        ref_ea = ida_xref.get_first_dref_from(ea)

        while not _is_badaddr(ref_ea):
            flags = ida_bytes.get_flags(ref_ea)

            if _is_data(flags):
                for head_ea, head_size in self._process_heads(ref_ea):
                    if head_ea not in self._pdg:
                        self._add_program_node(head_ea)
                    self._add_program_edge(
                        src_ea,
                        head_ea,
                        edge_class=EdgeClass.DATA_RELATION,
                        size=head_size,
                    )
                    yield head_ea, head_size

                    if head_ea not in seen:
                        seen.add(head_ea)
                        yield from self._process_drefs(head_ea, seen=seen)

            elif _is_code(flags):
                head_ea, head_size = _get_ea_info(ref_ea)
                func = ida_funcs.get_func(head_ea)
                if func:
                    head_ea = func.start_ea
                if head_ea not in self._pdg:
                    self._add_program_node(head_ea)
                self._add_program_edge(
                    src_ea, head_ea, edge_class=EdgeClass.DATA_RELATION, size=head_size
                )
                yield head_ea, head_size

            ref_ea = ida_xref.get_next_dref_from(ea, ref_ea)

    def _process_func(self, func: func_t) -> Iterator[tuple[int, int]]:

        def _is_valid_bb(bb):
            return bb.start_ea != bb.end_ea and idc.is_code(
                ida_bytes.get_flags(bb.start_ea)
            )

        for bb in filter(_is_valid_bb, ida_gdl.FlowChart(func)):
            ea = bb.start_ea
            end_ea = bb.end_ea
            while not _is_badaddr(ea):
                self._logger.debug("Processing %#x", ea)
                yield from self._process_drefs(ea)
                ea = idc.next_head(ea, end_ea)

    def _add_data_to_code_edges_func(self, func: func_t) -> None:
        for succ_ea, succ_size in self._process_func(func):
            if _is_code(ida_bytes.get_flags(succ_ea)):
                succ_func = ida_funcs.get_func(succ_ea)
                if succ_func:
                    self._add_program_edge(
                        func.start_ea,
                        succ_func.start_ea,
                        edge_class=EdgeClass.CONTROL_RELATION,
                        edge_type=EdgeType.CODE2CODE,
                        size=succ_size,
                    )

    def _add_data_to_code_edges(self) -> None:

        num_edges = self._pdg.number_of_edges()

        for i in range(ida_funcs.get_func_qty()):
            self._add_data_to_code_edges_func(ida_funcs.getn_func(i))

        self._logger.info(
            "Added %d data-to-code reference edges",
            self._pdg.number_of_edges() - num_edges,
        )

    def _add_sequence_edges(self) -> None:

        prev_ea = None
        prev_sel = None

        for i in range(ida_funcs.get_func_qty()):
            ea = ida_funcs.getn_func(i).start_ea
            sel = ida_segment.getseg(ea).sel
            if prev_ea and prev_sel == sel:
                self._add_program_edge(
                    prev_ea,
                    ea,
                    edge_class=EdgeClass.SEQUENCE,
                    edge_type=EdgeType.CODE2CODE,
                )

            prev_ea = ea
            prev_sel = sel

    def _add_density_edges(self, depth_limit: int = 1, window: int = 1) -> None:

        def _splice(node_idx: list[int], window: int) -> Iterator[list[int]]:
            while node_idx:
                i = node_idx.pop(0)
                seq = [i]
                while node_idx and abs(node_idx[0] - i) <= window:
                    i = node_idx.pop(0)
                    seq.append(i)
                yield seq

        nodes = list(sorted(self._pdg))

        density_seqs = []
        for ea in self._pdg:
            successors = [
                nodes.index(node_ea)
                for node_ea in networkx.dfs_preorder_nodes(
                    self._pdg, source=ea, depth_limit=depth_limit, sort_neighbors=sorted
                )
                if node_ea != ea
            ]
            density_seqs += list(_splice(successors, window))

        num_edges = self._pdg.number_of_edges()

        for seq in density_seqs:
            for i, j in itertools.pairwise(seq):
                self._add_program_edge(
                    nodes[i],
                    nodes[j],
                    edge_class=EdgeClass.DENSITY,
                    edge_type=EdgeType.CODE2CODE,
                )
                self._add_program_edge(
                    nodes[j],
                    nodes[i],
                    edge_class=EdgeClass.DENSITY,
                    edge_type=EdgeType.CODE2CODE,
                )

        self._logger.info(
            "Added %d density edges", self._pdg.number_of_edges() - num_edges
        )

    def _get_func_xrefs_to(self, ea: int) -> Iterator[func_t]:

        ref = ida_xref.get_first_fcref_to(ea)

        while not _is_badaddr(ref):

            #
            # Is this function defined? If not then `ref' is probably within the
            # range of an undetected/unanalyzed function.
            #
            func = ida_funcs.get_func(ref)
            if func:
                yield func

            ref = ida_xref.get_next_fcref_to(ea, ref)

    def _add_fcg_edges(self) -> None:

        for i in range(ida_funcs.get_func_qty()):
            func = ida_funcs.getn_func(i)

            ea = func.start_ea
            if ea not in self._pdg:
                self._add_program_node(ea, node_type=NodeType.CODE)

            for func in self._get_func_xrefs_to(ea):
                pred_ea = func.start_ea
                if pred_ea not in self._pdg:
                    self._add_program_node(pred_ea, node_type=NodeType.CODE)
                self._add_program_edge(
                    pred_ea,
                    ea,
                    edge_class=EdgeClass.CONTROL_RELATION,
                    edge_type=EdgeType.CODE2CODE,
                )

    def build(self) -> PDG:
        self._logger.info("Adding FCG edges")
        self._add_fcg_edges()
        # self._add_density_edges()
        self._logger.info("Adding sequence edges")
        self._add_sequence_edges()
        self._logger.info("Adding data edges")
        self._add_data_to_code_edges()
        return self._pdg


class IdaPro(Exporter):
    """IDA Pro exporter."""

    def export_segments(self) -> list[Segment]:

        segs = []

        seg = ida_segment.get_first_seg()

        while seg:
            sclass = ida_segment.get_segm_class(seg)
            if sclass == "CODE":
                sclass = SegmentClass.CODE
            elif sclass == "BSS" or sclass == "CONST" or sclass == "DATA":
                sclass = SegmentClass.DATA
            elif seg.perm:
                if seg.perm & ida_segment.SEGPERM_EXEC == 0:
                    sclass = SegmentClass.DATA
                elif seg.perm & ida_segment.SEGPERM_WRITE != 0:
                    sclass = SegmentClass.CODE | SegmentClass.DATA
                else:
                    sclass = SegmentClass.CODE
            else:
                sclass = SegmentClass.INVALID

            segs.append(
                Segment(
                    ida_segment.get_segm_name(seg),
                    seg.start_ea,
                    seg.end_ea,
                    seg.sel,
                    seg.perm,
                    sclass,
                )
            )

            seg = ida_segment.get_next_seg(seg.start_ea)

        return segs

    def export_pdg(self) -> PDG:
        return _PdgBuilder().build()
