# -*- coding: utf-8 -*-
"""Exporter related definitions.

This module exports class :class:`Exporter`, which is used for abstracting the
process of exporting program data from reverse engineering frameworks like IDA
Pro, Ghidra etc and loading it from disk at a later time. Each exporter (e.g.
IDA Pro) is represented by a descendant of this class and is expected to
implement methods :meth:`export_segments()` and :meth:`export_pdg()`, which are
documented below.

Example:
    To implement an exporter, for a reverse engineering framework, just subclass
    `Exporter` and override the aforementioned methods:

    >>> class MyExporter(Exporter):
    >>>     def export_segments(self):
    >>>         ...
    >>>     def export_pdg(self):
    >>>         ...

    To start the exporter, instantiate it and call :meth:`export()`, passing it
    the path to a directory where exported data will be stored to:

    >>> exporter = MyExporter()
    >>> exporter.export('/tmp/export_dir')

    To load exported data from disk at later time, use meth:`load_data()`:

    >>> data = load_data('/tmp/export_dir')
"""

from pathlib import Path

from recover.graphs import AFCG, DFG, PDG

import abc
import dataclasses
import enum
import logging
import pickle


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["SegmentClass", "Segment", "Exporter"]


@enum.unique
class SegmentClass(enum.IntEnum):
    """Represents the type of an exported segment."""

    INVALID = 0
    CODE = 1
    DATA = 2


@dataclasses.dataclass
class Segment(object):
    """Represents an exported segment."""

    name: str
    start_ea: int
    end_ea: int
    selector: int
    permissions: int
    segment_class: SegmentClass


@dataclasses.dataclass
class Data(object):
    """Represents exported data as loaded from disk."""

    pdg: PDG
    dfg: DFG
    afcg: AFCG
    sels: list[int]
    segs: list[Segment]


class Exporter(abc.ABC):
    """Base class inherited by all exporters."""

    def __init__(self) -> None:
        super(Exporter, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def export_segments(self) -> list[Segment]:
        """Export information on program segmentation.

        Returns:
            A list of program segments each represented by an instance of class
            class:`Segment`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def export_pdg(self) -> PDG:
        """Export the program's PDG.

        Returns:
            The program's PDG.
        """
        raise NotImplementedError

    def export(self, path: Path | str, prefix: str = "") -> None:
        """Start the exporter.

        Args:
            path: Path to base directory where exported data will be stored.
            prefix: Name prefix to use for files in `path`.
        """
        if isinstance(path, str):
            path = Path(path)
        assert (
            path.exists() and path.is_dir()
        ), f"{path} does not exist or not a directory"

        self._logger.info("Exporting PDG")
        pdg = self.export_pdg()
        self._logger.info("Storing PDG, AFCG and DFG")
        pdg.store(path / f"{prefix}pdg.pcl")
        pdg.get_afcg().store(path / f"{prefix}afcg.pcl")
        pdg.get_dfg().store(path / f"{prefix}dfg.pcl")

        self._logger.info("Exporting segments")
        segments = self.export_segments()
        with open(path / f"{prefix}segs.pcl", "wb") as fp:
            pickle.dump(segments, fp)


def load_data(path: Path | str, prefix: str = "") -> Data:
    """Load exported data from disk.

    Args:
        path: Path to base directory where exported data will be loaded from.
        prefix: Name prefix to use for files in `path`.

    Return:
        Program data exported by an exporter.
    """
    if isinstance(path, str):
        path = Path(path)
    assert path.exists() and path.is_dir(), f"{path} does not exist or not a directory"

    logging.info("Loading PDG, DFG and AFCG")
    pdg = PDG.load(path / f"{prefix}pdg.pcl")
    dfg = DFG.load(path / f"{prefix}dfg.pcl")
    afcg = AFCG.load(path / f"{prefix}afcg.pcl")

    logging.info("Loading segments")
    with open(path / f"{prefix}segs.pcl", "rb") as fp:
        segs = pickle.load(fp)

    sels = []
    for seg in segs:
        if "plt" not in seg.name and "got" not in seg.name:
            sels.append(seg.selector)

    return Data(pdg=pdg, dfg=dfg, afcg=afcg, sels=sels, segs=segs)
