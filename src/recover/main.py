# -*- coding: utf-8 -*-
"""REcover IDA Pro entry point."""

from types import ModuleType
from pathlib import Path

import importlib.util
import os
import sys
import tempfile
import traceback



__author__ = 'Chariton Karamitas <huku@census-labs.com>'



def _get_script_path() -> Path:
    path = Path(__file__).resolve()
    return path.parent


def _get_venv_path() -> Path:
    return _get_script_path().parent.parent / '.venv'


def _import_ida_venv() -> ModuleType:

    path = _get_script_path()

    spec = importlib.util.spec_from_file_location('ida_venv',
        path / 'ida-venv' / 'ida_venv.py')
    assert spec and spec.loader, \
        f'Module ida-venv not found under {path}'

    module = importlib.util.module_from_spec(spec)
    sys.modules['ida_venv'] = module
    spec.loader.exec_module(module)
    return module


def _has_recover() -> bool:
    return importlib.util.find_spec('recover') is not None


def _is_ida() -> bool:
    return importlib.util.find_spec('idc') is not None


def main() -> int:

    #
    # First try to locate REcover. If not there, then it means we are either
    # outside a virtual environment, or REcover is not installed in the current
    # virtual environment.
    #
    if not _has_recover():

        #
        # Get path to the currently executing script. It should have been
        # executed from within the source distribution of REcover (as opposed to
        # the user manually navigating in site-packages).
        #
        script_path = _get_script_path()
        assert script_path.parts[-3:] == ('recover', 'src', 'recover'), \
            'REcover not executed from within the source distribution'

        #
        # Get path to REcover's source distribution.
        #
        recover_path = script_path.parent.parent
        print(f'REcover at {recover_path}')

        #
        # Get path to virtual environment.
        #
        venv_path = _get_venv_path()
        print(f'Using virtual environment at {venv_path}')

        #
        # Import ida-venv which will allow us to create a new virtual environment
        # or reuse an existing one. The list of dependencies is set to REcover's
        # top-level directory that contains requirements.txt, which will be used
        # by pip in the background.
        #
        ida_venv = _import_ida_venv()
        ida_venv.run_script_in_env(script_path=script_path / 'ui.py',
            venv_path=venv_path, dependencies=[recover_path])

    return os.EX_OK


if __name__ == '__main__':
    assert _is_ida(), 'Not running in IDA Pro'
    main()
