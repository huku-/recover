# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,unused-import
"""REcover console entry point."""

from recover.cu_map import CUMap
from recover.exporter import Data, Segment, SegmentClass
from recover.fitness_function import FitnessFunction
from recover.graphs import AFCG, DFG, PDG, EdgeType, EdgeClass, NodeType
from recover.optimizer import Optimizer

import argparse
import logging.config
import os
import pathlib
import pkg_resources
import sys
import time

import recover.cu_map
import recover.estimators
import recover.exporter
import recover.fitness_functions
import recover.optimizers
import recover.util


__author__ = "Chariton Karamitas <huku@census-labs.com>"


def _show_cus(data: Data, cu_map: CUMap) -> None:
    for cu in cu_map.get_cus():
        print(f"CU #{cu.cu_id}")
        for ea in cu.get_func_eas():
            name = data.afcg.nodes[ea].get("name")
            print(f"\t{name:48s} [{ea:#x}]")
    cu_map.show()


def _get_segment_selector(data: Data, name: str) -> int | None:
    for seg in data.segs:
        if name in seg.name:
            return seg.selector


def main(argv: list[str] | None = None) -> int:

    argv = argv or sys.argv

    parser = argparse.ArgumentParser(
        prog="REcover", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--estimator",
        "-e",
        choices=["agglnse", "agglpse", "apsnse", "apspse"],
        type=str,
        default="apspse",
        help="algorithm to use for initial compile-unit number estimation",
    )
    parser.add_argument(
        "--load-estimation",
        "-l",
        metavar="FILE",
        type=pathlib.Path,
        help="load initial compile-unit estimation from this file",
    )
    parser.add_argument(
        "--fitness-function",
        "-f",
        choices=["none", "modularity", "cc"],
        type=str,
        default="none",
        help="fitness function to use for compile-unit layout optimization",
    )
    parser.add_argument(
        "--optimizer",
        "-o",
        choices=["brute", "genetic", "mixed"],
        type=str,
        default="brute",
        help="algorithm to use for compile-unit layout optimization",
    )
    parser.add_argument(
        "--filter-method",
        "-t",
        choices=["none", "rank"],
        type=str,
        default="none",
        help="graph filtering method to use before estimation and optimization",
    )
    parser.add_argument(
        "--segment",
        "-s",
        metavar="NAME",
        type=str,
        default=".text",
        help="segment name whose functions to split in compile-units",
    )
    parser.add_argument(
        "--debug", "-d", action="store_true", help="enable debugging output"
    )
    parser.add_argument(
        "path",
        metavar="PATH",
        type=pathlib.Path,
        help="path to IDA Pro exported files for target executable",
    )
    parser.add_argument(
        "output_file",
        metavar="FILE",
        type=pathlib.Path,
        help="path to output file to store compile-units",
    )
    args = parser.parse_args(argv[1:])

    if args.debug:
        path = pkg_resources.resource_filename("recover", "data/logging-debug.ini")
    else:
        path = pkg_resources.resource_filename("recover", "data/logging.ini")

    logging.config.fileConfig(path)

    data = recover.exporter.load_data(args.path)

    sel = _get_segment_selector(data, args.segment)
    if not sel:
        raise ValueError(f"Could not locate segment {args.segment}")

    start_time = int(time.time())

    if args.filter_method != "none":
        raise NotImplementedError("Graph filtering is WIP")

    if args.load_estimation:
        logging.info("Loading initial estimation from %s", args.load_estimation)
        cu_map = recover.cu_map.CUMap.load(args.load_estimation)
    elif args.estimator == "apsnse":
        logging.info("Using articulation-points (apsnse) for initial CU estimation")
        cu_map = recover.estimators.APSNSE(data, sel).estimate()
    elif args.estimator == "apspse":
        logging.info("Using articulation-points (apspse) for initial CU estimation")
        cu_map = recover.estimators.APSPSE(data, sel).estimate()
    elif args.estimator == "agglnse":
        logging.info("Using agglomeration (agglnse) for initial CU estimation")
        cu_map = recover.estimators.AGGLNSE(data, sel).estimate()
    elif args.estimator == "agglpse":
        logging.info("Using agglomeration (agglpse) for initial CU estimation")
        cu_map = recover.estimators.AGGLPSE(data, sel).estimate()

    if args.fitness_function != "none":
        fitness_function: type[FitnessFunction]
        if args.fitness_function == "modularity":
            logging.info("Using modularity fitness function")
            fitness_function = recover.fitness_functions.Modularity
        elif args.fitness_function == "cc":
            logging.info("Using clustering-coefficient fitness function")
            fitness_function = recover.fitness_functions.ClusteringCoefficient

        optimizer: Optimizer
        if args.optimizer == "brute":
            logging.info("Using brute-force optimizer")
            optimizer = recover.optimizers.BruteForce(data, cu_map, fitness_function)
        elif args.optimizer == "genetic":
            logging.info("Using genetic optimizer")
            optimizer = recover.optimizers.Genetic(data, cu_map, fitness_function)
        optimizer.optimize()

    end_time = int(time.time())

    cu_map.renumber()
    _show_cus(data, cu_map)
    cu_map.save(args.output_file)

    with open(f"{args.output_file}.time", "w", encoding="utf-8") as fp:
        fp.write(str(round(end_time - start_time + 0.5)))

    print(f"Recovered {len(cu_map)} compile-units")

    return os.EX_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
