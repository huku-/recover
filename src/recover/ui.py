# -*- coding: utf-8 -*-
"""Entry point of REcover executed after virtual environment creation."""

import importlib
import logging.config
import os
import pathlib

import recover

import ida_auto
import idc

from recover.exporters import ida_pro


__author__ = "Chariton Karamitas <huku@census-labs.com>"


def main() -> int:

    path = importlib.resources.files("recover.data") / "logging.ini"
    logging.config.fileConfig(path)

    path = pathlib.Path(idc.get_idb_path())
    logging.info("IDB at %s", path)

    logging.info("Waiting for auto-analysis to finish")
    ida_auto.auto_wait()

    exporter = ida_pro.IdaPro()
    recover.export(exporter, path.parent)

    return os.EX_OK


if __name__ == "__main__":
    main()
