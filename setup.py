#!/usr/bin/env python

import setuptools

packages = {
    "recover",
    "recover.data",
    "recover.estimators",
    "recover.exporters",
    "recover.fitness_functions",
    "recover.graphs",
    "recover.optimizers",
    "recover.ui",
}

package_data = {
    "recover": ["py.typed"],
    "recover.data": ["logging.ini", "logging-debug.ini"],
}

requirements = open("requirements.txt").read().splitlines()

setuptools.setup(
    name="REcover",
    version="1.0",
    description="Recover compile-units from stripped binary executables",
    author="Chariton Karamitas",
    author_email="huku@census-labs.com",
    packages=packages,
    package_dir={"": "src"},
    include_package_data=True,
    package_data=package_data,
    install_requires=requirements,
    zip_safe=False,
)
