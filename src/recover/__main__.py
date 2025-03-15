# -*- coding: utf-8 -*-
"""REcover console entry point."""

import argparse
import importlib.resources
import logging.config
import os
import pathlib
import sys

import recover


__author__ = "Chariton Karamitas <huku@census-labs.com>"


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
        "--optimizer",
        "-o",
        choices=["none", "brute_fast", "brute", "genetic"],
        type=str,
        default="brute_fast",
        help="algorithm to use for compile-unit layout optimization",
    )
    parser.add_argument(
        "--fitness-function",
        "-f",
        choices=["modularity"],
        type=str,
        default="modularity",
        help="fitness function to use for compile-unit layout optimization",
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
        "-k",
        "--pickle",
        dest="pickle_path",
        metavar="FILE",
        type=pathlib.Path,
        help="path to file to store output compile-unit map in Pickle format",
    )
    parser.add_argument(
        "-j",
        "--json",
        dest="json_path",
        metavar="FILE",
        type=pathlib.Path,
        help="path to file to store output compile-unit map in JSON format",
    )
    parser.add_argument(
        "-m",
        "--time",
        dest="write_time",
        action="store_true",
        help="write timing information",
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
    args = parser.parse_args(argv[1:])

    if args.debug:
        path = importlib.resources.files("recover.data") / "logging-debug.ini"
    else:
        path = importlib.resources.files("recover.data") / "logging.ini"

    logging.config.fileConfig(str(path))

    if args.filter_method != "none":
        raise NotImplementedError("Graph filtering is WIP")

    recover.analyze(
        args.path,
        estimator=args.estimator,
        load_estimation=args.load_estimation,
        fitness_function=args.fitness_function,
        optimizer=args.optimizer,
        segment=args.segment,
        pickle_path=args.pickle_path,
        json_path=args.json_path,
        write_time=args.write_time,
        debug=args.debug,
    )

    return os.EX_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
