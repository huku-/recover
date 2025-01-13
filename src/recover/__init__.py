# -*- coding: utf-8 -*-
"""Entry points to REcover export and analysis logic.

Reverse engineers can import REcover in their own modules and use it to export
data from binary executables and perform compile-unit recovery analyses.

Example:
    One could do the following from within an IDA Python script:

    >>> from recover.exporters import ida_pro
    >>> import recover
    >>> exporter = ida_pro.IdaPro()
    >>> recover.export(exporter, "/tmp/program-data")
    >>> recover.analyze("/tmp/program-data")
"""

from pathlib import Path

from recover.exporter import Exporter, Segment, SegmentClass
from recover.fitness_function import FitnessFunction

import recover.cu_map
import recover.estimators
import recover.exporter
import recover.fitness_functions
import recover.optimizers

import logging
import time


__author__ = "Chariton Karamitas <huku@census-labs.com>"

__all__ = ["export", "analyze"]


def export(exporter: Exporter, path: str | Path) -> None:
    logging.info("Exporting in %s", path)
    exporter.export(path)
    logging.info("Done")


def analyze(
    path: str | Path,
    estimator: str = "apspse",
    load_estimation: str | Path | None = None,
    fitness_function: str = "modularity",
    optimizer: str = "brute",
    segment: str = ".text",
    pickle_path: str | Path | None = None,
    json_path: str | Path | None = None,
    write_time: bool = False,
    debug: bool = False,
) -> None:
    logging.info("Loading exported data from %s", path)
    data = recover.exporter.load_data(path)

    segs = [seg for seg in data.segs if segment in seg.name]
    if not segs:
        raise ValueError(f"Could not locate segment {segment}")
    if len(segs) > 1:
        logging.info(
            "Multiple segments matching %s (%s), will use %s",
            segment,
            ", ".join([seg.name for seg in segs]),
            segs[0].name,
        )
    sel = segs[0].selector

    start_time = int(time.time())

    if load_estimation:
        logging.info("Loading initial estimation from %s", load_estimation)
        cu_map = recover.cu_map.CUMap.load(load_estimation)
    elif estimator == "apsnse":
        logging.info("Using articulation-points (apsnse) for initial CU estimation")
        cu_map = recover.estimators.APSNSE(data, sel).estimate()
    elif estimator == "apspse":
        logging.info("Using articulation-points (apspse) for initial CU estimation")
        cu_map = recover.estimators.APSPSE(data, sel).estimate()
    elif estimator == "agglnse":
        logging.info("Using agglomeration (agglnse) for initial CU estimation")
        cu_map = recover.estimators.AGGLNSE(data, sel).estimate()
    elif estimator == "agglpse":
        logging.info("Using agglomeration (agglpse) for initial CU estimation")
        cu_map = recover.estimators.AGGLPSE(data, sel).estimate()
    else:
        raise ValueError(f"Invalid estimator {estimator}")

    if optimizer != "none":
        fft: type[FitnessFunction]
        if fitness_function == "modularity":
            logging.info("Using modularity fitness function")
            fft = recover.fitness_functions.Modularity
        elif fitness_function == "cc":
            logging.info("Using clustering-coefficient fitness function")
            fft = recover.fitness_functions.ClusteringCoefficient
        else:
            raise ValueError(f"Invalid fitness function {fitness_function}")

        if optimizer == "brute":
            logging.info("Using brute-force optimizer")
            recover.optimizers.BruteForce(data, cu_map, fft).optimize()
        elif optimizer == "genetic":
            logging.info("Using genetic optimizer")
            recover.optimizers.Genetic(data, cu_map, fft).optimize()
        else:
            raise ValueError(f"Invalid optimizer {optimizer}")

    end_time = int(time.time())

    cu_map.renumber()

    if debug:
        for cu in cu_map.get_cus():
            print(f"CU #{cu.cu_id}")
            for ea in cu.get_func_eas():
                name = data.afcg.nodes[ea].get("name")
                print(f"\t{name:48s} [{ea:#x}]")
        cu_map.show()

    if not pickle_path:
        pickle_path = (
            Path(path) / f"cu_map-{estimator}-{optimizer}-{fitness_function}.pcl"
        )
    cu_map.save_pickle(pickle_path)

    if not json_path:
        json_path = (
            Path(path) / f"cu_map-{estimator}-{optimizer}-{fitness_function}.json"
        )
    cu_map.save_json(json_path)

    if write_time:
        with open(f"{pickle_path}.time", "w", encoding="utf-8") as fp:
            fp.write(f"{end_time - start_time}\n")

    print(f"Recovered {len(cu_map)} compile-units")
