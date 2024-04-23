# -*- coding: utf-8 -*-
"""Graph definitions."""

from __future__ import annotations

from pathlib import Path

import enum
import pickle
import sys
import warnings

import networkx

try:
    import pygraphviz
except ImportError:
    warnings.warn("Graph visualization disabled because pygraphviz is not installed")


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["NodeType", "EdgeType", "EdgeClass", "AFCG", "DFG", "PDG"]


NODE_TYPE = "node_type"
EDGE_TYPE = "edge_type"
EDGE_CLASS = "edge_class"
SEGMENT = "segment"


@enum.unique
class NodeType(enum.IntEnum):
    """Node attribute representing its type (code vs. data)."""

    INVALID = 0
    CODE = 1
    DATA = 2


@enum.unique
class EdgeType(enum.IntEnum):
    """Edge attribute representing its type (tail and head node types)."""

    INVALID = 0
    CODE2CODE = 1
    CODE2DATA = 2
    DATA2DATA = 3
    DATA2CODE = 4


@enum.unique
class EdgeClass(enum.IntEnum):
    """Edge attribute representing the relationship of its incident nodes."""

    INVALID = 0
    CONTROL_RELATION = 1
    DATA_RELATION = 2
    SEQUENCE = 3


@enum.unique
class NodeShape(enum.Enum):
    """Graphviz node shape when visualizing."""

    INVALID = "circle"
    CODE = "rectangle"
    DATA = "diamond"

    @staticmethod
    def from_node_type(node_type: NodeType) -> str:
        return NodeShape[node_type.name].value


@enum.unique
class NodeColor(enum.Enum):
    """Graphviz node color when visualizing."""

    INVALID = "red"
    CODE = "white"
    DATA = "yellow"

    @staticmethod
    def from_node_type(node_type: NodeType) -> str:
        return NodeColor[node_type.name].value


@enum.unique
class EdgeColor(enum.Enum):
    """Graphviz edge color when visualizing."""

    INVALID = "black"
    CODE2CODE = "red"
    CODE2DATA = "blue"
    DATA2CODE = "orange"
    DATA2DATA = "cyan"

    @staticmethod
    def from_edge_type(edge_type: EdgeType) -> str:
        return EdgeColor[edge_type.name].value


@enum.unique
class EdgeStyle(enum.Enum):
    """Graphviz edge style when visualizing."""

    INVALID = "bold"
    CONTROL_RELATION = "solid"
    DATA_RELATION = "dashed"
    SEQUENCE = "dotted"

    @staticmethod
    def from_edge_class(edge_class: EdgeClass) -> str:
        return EdgeStyle[edge_class.name].value


class _BaseGraph(networkx.MultiDiGraph):
    """Base graph type inherited by AFCG, DFG and PDG."""

    def add_program_node(
        self,
        node: int,
        node_type: NodeType = NodeType.INVALID,
        segment: int = 0,
        name: str | None = None,
    ) -> None:
        """Add node in graph. If node already exists, only its attributes are
        updated.

        Args:
            node: Address of symbol, in program memory, that this node represents.
            node_type: Type of node.
            segment: Selector of segment the symbol, that this node represents,
                belongs to in program memory.
            name: Name of program symbol this node represents.
        """
        self.add_node(node, node_type=node_type, segment=segment, name=name)

    def add_program_edge(
        self,
        tail: int,
        head: int,
        edge_type: EdgeType = EdgeType.INVALID,
        edge_class: EdgeClass = EdgeClass.INVALID,
        size: int = 0,
    ) -> None:
        """Add edge in graph. Edge is added only if a similar edge of the same
        edge class does not already exist.

        Args:
            tail: Edge tail node.
            head: Edge head node.
            edge_type: Type of edge.
            edge_class: Class of edge.
            size: Number of bytes accessed by this edge.
        """
        if all(
            data["edge_class"] != edge_class
            for data in self.get_edge_data(tail, head, default={}).values()
        ):
            self.add_edge(
                tail, head, edge_type=edge_type, edge_class=edge_class, size=size
            )

    def draw(self, path: Path) -> None:
        """Export graph to Graphviz dot format.

        Args:
            path: Path to file to export graph to.
        """
        if "pygraphviz" in sys.modules:

            agraph = pygraphviz.AGraph(directed=True, splines="ortho")

            for node, data in self.nodes(data=True):
                agraph.add_node(
                    node,
                    shape=NodeShape.from_node_type(data["node_type"]),
                    fillcolor=NodeColor.from_node_type(data["node_type"]),
                    style="filled",
                    label=data["name"],
                )

            for tail, head, data in self.edges(data=True):
                agraph.add_edge(
                    tail,
                    head,
                    color=EdgeColor.from_edge_type(data["edge_type"]),
                    style=EdgeStyle.from_edge_class(data["edge_class"]),
                )

            agraph.write(path)

    def store(self, path: Path | str) -> None:
        """Store graph to file.

        Args:
            path: Path to file to store graph to.
        """
        with open(path, "wb") as fp:
            pickle.dump(self, fp)

    @classmethod
    def load(cls, path: Path) -> _BaseGraph:
        """Load graph from file.

        Args:
            path: Path to file to load graph from.

        Returns:
            A descendant of this class representing the loaded graph.
        """
        with open(path, "rb") as fp:
            self = pickle.load(fp)
            assert isinstance(self, cls), f"Invalid graph type {type(self)}"
            return self


class AFCG(_BaseGraph):
    """*Augmented Function Call Graph* (AFCG)."""


class DFG(_BaseGraph):
    """*Data Flow Graph* (DFG)."""


class PDG(_BaseGraph):
    """*Program and Data Graph* (PDG)."""

    def get_afcg(self) -> AFCG:

        def _filter_node(node: int) -> bool:
            return self.nodes[node]["node_type"] == NodeType.CODE

        def _filter_edge(tail: int, head: int, key: int) -> bool:
            return self.edges[tail, head, key]["edge_type"] == EdgeType.CODE2CODE

        return AFCG(
            networkx.classes.graphviews.subgraph_view(
                self, filter_node=_filter_node, filter_edge=_filter_edge
            )
        )

    def get_dfg(self) -> DFG:

        def _filter_edge(tail: int, head: int, key: int) -> bool:
            return self.edges[tail, head, key]["edge_type"] != EdgeType.CODE2CODE

        return DFG(
            networkx.classes.graphviews.subgraph_view(self, filter_edge=_filter_edge)
        )
