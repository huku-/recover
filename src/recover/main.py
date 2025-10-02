# -*- coding: utf-8 -*-
"""REcover IDA Pro entry point."""

from types import ModuleType
from pathlib import Path

import errno
import functools
import importlib.util
import os
import runpy
import site

try:
    import ida_pro
    import idc
except ImportError as exception:
    raise RuntimeError("Not running in IDA Pro") from exception


__author__ = "Chariton Karamitas <huku@census-labs.com>"


@functools.cache
def _get_script_path() -> Path:
    return Path(__file__).resolve(strict=True).parent


def _get_venv_path() -> Path:
    path = _get_script_path() / ".venv"
    if path.exists() and not path.is_dir():
        raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), str(path))
    return path


def _import_ida_venv() -> ModuleType:
    path = _get_script_path() / "ida-venv"
    if not path.is_dir():
        raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), str(path))
    site.addsitedir(str(path))
    return importlib.import_module("ida_venv")


def _bool_env(name: str) -> bool:
    value = os.getenv(name, default="false").lower()
    if value in ("f", "false", "n", "no", "0"):
        return False
    if value in ("t", "true", "y", "yes", "1"):
        return True
    raise ValueError(f"{name} is not a valid boolean")


# pylint: disable=unused-argument
def main(argv: list[str]) -> int:

    #
    # Get path to the currently executing script. It should have been executed
    # from within the source distribution of REcover (as opposed to the user
    # manually navigating in site-packages).
    #
    script_path = _get_script_path()
    assert script_path.parts[-3:] == (
        "recover",
        "src",
        "recover",
    ), "REcover not executed from within the source distribution"

    #
    # Try to locate REcover. If not there, then it means we are either outside a
    # virtual environment, or REcover is not installed in the current virtual
    # environment.
    #
    if not importlib.util.find_spec("recover"):

        #
        # Get path to REcover's source distribution.
        #
        recover_path = script_path.parent.parent
        print(f"REcover at {recover_path}")

        #
        # Get path to virtual environment.
        #
        venv_path = _get_venv_path()
        print(f"Using virtual environment at {venv_path}")

        #
        # Import ida-venv which will allow us to create a new virtual environment
        # or reuse an existing one.
        #
        ida_venv = _import_ida_venv()

        #
        # Install REcover in the newly created virtual environment. The list of
        # dependencies is set to REcover's top-level directory that contains
        # requirements.txt, which will be used by pip in the background.
        #
        ida_venv.run_script_in_env(
            script_path=script_path / "ui.py",
            venv_path=venv_path,
            dependencies=[recover_path],
        )

    #
    # REcover is already present, which means its dependencies are too. Don't
    # care how we got here, just fire up the REcover IDA Pro UI.
    #
    else:
        runpy.run_path(str(script_path / "ui.py"), run_name="__main__")

    return os.EX_OK


if __name__ == "__main__":
    if _bool_env("RECOVER_EXIT"):
        ida_pro.qexit(main(idc.ARGV))
    else:
        main(idc.ARGV)
