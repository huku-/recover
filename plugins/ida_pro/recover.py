# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,unused-argument
"""REcover IDA Pro plug-in."""

__author__ = "Chariton Karamitas <huku@census-labs.com>"


from pathlib import Path

import collections
import contextlib
import errno
import functools
import importlib
import importlib.resources
import json
import logging.config
import os

try:
    import ida_venv
except ImportError as exception:
    raise RuntimeError("Module ida-venv not found") from exception

try:
    from ida_idaapi import plugin_t
    from ida_kernwin import Form

    import ida_auto
    import ida_funcs
    import ida_idaapi
    import ida_kernwin
    import idc
except ImportError as exception:
    raise RuntimeError("Not running in IDA Pro") from exception


ESTIMATORS = ["agglnse", "agglpse", "apsnse", "apspse", "file"]
OPTIMIZERS = ["none", "brute_fast", "brute", "genetic"]
FITNESS_FUNCTIONS = ["modularity"]

WIDTH = 48
HEIGHT = 32


def check_dir(path: Path) -> None:
    """Make sure path exists and is a directory.

    Args:
        path: Path to check.

    Raises:
        FileNotFoundError: If path does not exist.
        NotADirectoryError: If path exists, but is not a directory.
    """
    if not path.exists():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(path))
    if not path.is_dir():
        raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), str(path))


def analyze(
    path: str | Path | None = None,
    estimator: str | None = None,
    load_estimation: str | None = None,
    optimizer: str | None = None,
    fitness_function: str | None = None,
    segment: str | None = None,
    venv_path: str | Path | None = None,
) -> None:
    """Run REcover analysis.

    Args:
        path: Path to base directory where exported data will be loaded from and
            output files will be stored to. If not specified, the IDB's parent
            directory is used.
        estimator: Algorithm to use for initial compile-unit number estimation.
            Defaults to "apsnse" if not specified.
        load_estimation: Optional path to load an initial compile-unit estimation
            from.
        optimizer: Algorithm to use for compile-unit layout optimization.
            Defaults to "brute_fast" if not specified.
        fitness_function: Fitness function to use for compile-unit layout
            optimization. Defaults to "modularity" if not specified.
        segment: Segment name whose functions to split in compile-units. Defaults
            to ".text" if not specified.
        venv_path: Optional path to a Python virtual environment, where REcover
            and its dependencies must have been installed.
    """

    if path:
        if isinstance(path, str):
            path = Path(path)
        check_dir(path)
    else:
        path = Path(idc.get_idb_path()).parent

    if venv_path:
        if isinstance(venv_path, str):
            venv_path = Path(venv_path)
        check_dir(venv_path)
        context = functools.partial(ida_venv.venv_context, path)
    else:
        context = contextlib.nullcontext

    with context():
        recover = importlib.import_module("recover")
        config_path = importlib.resources.files("recover.data") / "logging.ini"
        logging.config.fileConfig(str(config_path))
        recover.analyze(
            path,
            estimator=estimator or "apsnse",
            load_estimation=load_estimation,
            optimizer=optimizer or "brute_fast",
            fitness_function=fitness_function or "modularity",
            segment=segment or ".text",
            pickle_path=path / "cu_map.pcl",
            json_path=path / "cu_map.json",
            debug=True,
        )


def export(path: str | Path | None = None, venv_path: str | Path | None = None) -> None:
    """Run REcover export logic.

    Args:
        path: Path to base directory where exported data will be stored. If not
            specified, the IDB's parent directory is used.
        venv_path: Optional path to a Python virtual environment, where REcover
            and its dependencies must have been installed.
    """

    if path:
        if isinstance(path, str):
            path = Path(path)
        check_dir(path)
    else:
        path = Path(idc.get_idb_path()).parent

    if venv_path:
        if isinstance(venv_path, str):
            venv_path = Path(venv_path)
        check_dir(venv_path)
        context = functools.partial(ida_venv.venv_context, path)
    else:
        context = contextlib.nullcontext

    with context():
        recover = importlib.import_module("recover")
        ida_pro = importlib.import_module("recover.exporters.ida_pro")
        config_path = importlib.resources.files("recover.data") / "logging.ini"
        logging.config.fileConfig(str(config_path))
        recover.export(ida_pro.IdaPro(), path)


def run_headless(actions: str) -> None:
    """Run REcover in headless mode. Input arguments to the export and analysis
    entry points are read from the environment.

    Args:
        actions: List of actions to perform in headless mode (read from the
            environment).
    """

    r = os.EX_OK

    actions_list = [action.strip() for action in actions.split(",")]

    try:
        if "export" in actions_list:
            export(
                path=os.getenv("RECOVER_PATH"),
                venv_path=os.getenv("RECOVER_VENV_PATH"),
            )
        if "analyze" in actions_list:
            analyze(
                path=os.getenv("RECOVER_PATH"),
                estimator=os.getenv("RECOVER_ESTIMATOR"),
                load_estimation=os.getenv("RECOVER_LOAD_ESTIMATION"),
                fitness_function=os.getenv("RECOVER_FITNESS_FUNCTION"),
                optimizer=os.getenv("RECOVER_OPTIMIZER"),
                segment=os.getenv("RECOVER_SEGMENT"),
            )
    except Exception:
        logging.exception("REcover raised exception")
        r = -1

    if os.getenv("RECOVER_EXIT"):
        idc.qexit(r)


class FunctionChooser(ida_kernwin.Choose):
    """A chooser that displays the functions of a compile-unit."""

    def __init__(self, form: Form, title: str) -> None:
        super().__init__(
            title,
            [["Address", 20], ["Name", 30]],
            flags=ida_kernwin.Choose.CH_MULTI
            | ida_kernwin.Choose.CH_CAN_REFRESH
            | ida_kernwin.Choose.CH_CAN_INS
            | ida_kernwin.Choose.CH_RESTORE,
            embedded=True,
            width=WIDTH // 2,
            height=HEIGHT,
        )
        self.form = form
        self.items: list[list[str]] = []

    def OnGetLine(self, i: int) -> list[str]:
        return self.items[i]

    def OnGetSize(self) -> int:
        return len(self.items)

    def OnSelectLine(self, i: list[int]) -> tuple[int, list[int]]:
        ea = int(self.items[i[0]][0], 16)
        idc.jumpto(ea)
        return ida_kernwin.Choose.NOTHING_CHANGED, i


class CompileUnitChooser(ida_kernwin.Choose):
    """A chooser that displays the recovered compile-units."""

    def __init__(self, form: Form, title: str) -> None:
        super().__init__(
            title,
            [["CU", 10], ["Size", 10]],
            flags=ida_kernwin.Choose.CH_MULTI
            | ida_kernwin.Choose.CH_CAN_REFRESH
            | ida_kernwin.Choose.CH_CAN_INS
            | ida_kernwin.Choose.CH_RESTORE,
            embedded=True,
            width=WIDTH // 2,
            height=HEIGHT,
        )
        self.form = form
        self.items: list[list[str]] = []

    def OnGetLine(self, i: int) -> list[str]:
        return self.items[i]

    def OnGetSize(self) -> int:
        return len(self.items)

    def OnSelectLine(self, i: list[int]) -> tuple[int, list[int]]:
        self.form.on_select(i[0])
        return ida_kernwin.Choose.NOTHING_CHANGED, i

    def OnSelectionChange(self, i: list[int]) -> None:
        self.form.on_select(i[0])


class ExplorationForm(Form):
    """REcover plug-in analysis results exploration menu."""

    def __init__(self):
        super().__init__(
            """REcover explorer

<CUMap JSON file\::{cumap_path}><Load:{load_button}>
<Compile-units\::{compile_unit_chooser}><Functions\::{function_chooser}>
        """,
            {
                "cumap_path": Form.FileInput(open=True, swidth=WIDTH),
                "load_button": Form.ButtonInput(self.on_load),
                "compile_unit_chooser": Form.EmbeddedChooserControl(
                    CompileUnitChooser(self, "Compile-units")
                ),
                "function_chooser": Form.EmbeddedChooserControl(
                    FunctionChooser(self, "Functions")
                ),
            },
        )
        self.Compile()
        self.cumap_path.value = str(Path(idc.get_idb_path()).parent / "cu_map.json")
        self.cu_funcs = None
        self.cus = None

    def on_load(self, code: int = 0) -> None:
        cumap_path = Path(self.GetControlValue(self.cumap_path))
        with open(cumap_path, "rb") as fp:
            data = json.load(fp)

        cu_funcs = collections.defaultdict(list)
        for i, cu in enumerate(data["func_to_cu"]):
            cu_funcs[cu].append(data["funcs"][i])
        self.cu_funcs = cu_funcs
        self.cus = list(sorted(cu_funcs))

        chooser = self.compile_unit_chooser.chooser
        chooser.items.clear()
        for cu in self.cus:
            chooser.items.append([f"CU #{cu}", f"{len(cu_funcs[cu])}"])
        chooser.Refresh()
        self.RefreshField(self.compile_unit_chooser)

    def on_select(self, i: int) -> None:
        cu = self.cus[i]
        funcs = self.cu_funcs[cu]
        chooser = self.function_chooser.chooser
        chooser.items.clear()
        for ea in funcs:
            chooser.items.append([f"{ea:#x}", ida_funcs.get_func_name(ea)])
        chooser.Refresh()
        self.RefreshField(self.function_chooser)


class AnalysisForm(Form):
    """REcover plug-in analysis menu."""

    def __init__(self) -> None:
        super().__init__(
            """BUTTON YES NONE
BUTTON CANCEL NONE
REcover analyzer
{on_form_change}

<Virtual environment\::{venv_path}>

<##Initial estimation method##agglnse (Agglomerative - No Sequence Edges):{agglnse}>
<agglpse (Agglomerative - Partial Sequence Edges):{agglpse}>
<apsnse (Articulation Points - No Sequence Edges):{apsnse}>
<apspse (Articulation Points - Partial Sequence Edges):{apspse}>
<Load from file:{file}>{estimator}>
<Input file\:         :{input_file}>

<##Optimization method##None:{none}>
<Fast brute-force:{brute_fast}>
<Brute-force:{brute}>
<Genetic:{genetic}>{optimizer}>

<##Fitness function##Modularity:{modularity}>{fitness_function}>

<Segment name\:       :{segment}>

<Output directory\:   :{output_path}>

<Analyze:{analyze_button}><Close:{close_button}>
""",
            {
                "venv_path": Form.DirInput(swidth=WIDTH),
                "estimator": Form.RadGroupControl(ESTIMATORS),
                "input_file": Form.FileInput(open=True, swidth=WIDTH),
                "optimizer": Form.RadGroupControl(OPTIMIZERS),
                "fitness_function": Form.RadGroupControl(FITNESS_FUNCTIONS),
                "segment": Form.StringInput(swidth=WIDTH),
                "output_path": Form.DirInput(swidth=WIDTH),
                "on_form_change": Form.FormChangeCb(self.on_form_change),
                "analyze_button": Form.ButtonInput(self.on_analyze),
                "close_button": Form.ButtonInput(self.on_close),
            },
        )
        self.Compile()
        self.venv_path.value = ""
        self.apsnse.selected = True
        self.brute_fast.selected = True
        self.modularity.selected = True
        self.input_file.value = ""
        self.segment.value = ".text"
        self.output_path.value = str(Path(idc.get_idb_path()).parent)

    def on_form_change(self, fid: int) -> int:
        i = self.GetControlValue(self.estimator)
        if ESTIMATORS[i] == "file":
            self.EnableField(self.input_file, True)
        else:
            self.EnableField(self.input_file, False)
        i = self.GetControlValue(self.optimizer)
        if OPTIMIZERS[i] != "none":
            self.EnableField(self.fitness_function, True)
        else:
            self.EnableField(self.fitness_function, False)
        return 1

    def on_analyze(self, code: int = 0) -> None:
        if venv_path := self.GetControlValue(self.venv_path):
            venv_path = Path(venv_path)
        estimator = ESTIMATORS[self.GetControlValue(self.estimator)]
        if load_estimation := self.GetControlValue(self.input_file):
            load_estimation = Path(load_estimation)
        optimizer = OPTIMIZERS[self.GetControlValue(self.optimizer)]
        fitness_function = FITNESS_FUNCTIONS[
            self.GetControlValue(self.fitness_function)
        ]
        segment = self.GetControlValue(self.segment)
        if output_path := self.GetControlValue(self.output_path):
            output_path = Path(output_path)
        analyze(
            path=output_path,
            estimator=estimator,
            load_estimation=load_estimation,
            optimizer=optimizer,
            fitness_function=fitness_function,
            segment=segment,
            venv_path=venv_path,
        )

    def on_close(self, code: int = 0) -> None:
        self.Close(code)


class ExportForm(Form):
    """REcover plug-in export menu."""

    def __init__(self) -> None:
        super().__init__(
            """BUTTON YES NONE
BUTTON CANCEL NONE
REcover exporter

<Virtual environment\::{venv_path}>
<Output directory\:   :{output_path}>

<Export:{export_button}><Close:{close_button}>
""",
            {
                "venv_path": Form.DirInput(swidth=WIDTH),
                "output_path": Form.DirInput(swidth=WIDTH),
                "export_button": Form.ButtonInput(self.on_export),
                "close_button": Form.ButtonInput(self.on_close),
            },
        )
        self.Compile()
        self.output_path.value = str(Path(idc.get_idb_path()).parent)

    def on_export(self, code: int = 0) -> None:
        if venv_path := self.GetControlValue(self.venv_path):
            venv_path = Path(venv_path)
        if output_path := self.GetControlValue(self.output_path):
            output_path = Path(output_path)
        export(path=output_path, venv_path=venv_path)

    def on_close(self, code: int = 0) -> None:
        self.Close(code)


class MainForm(Form):
    """REcover plug-in main menu."""

    def __init__(self) -> None:
        super().__init__(
            """BUTTON YES NONE
BUTTON CANCEL Close
REcover IDA Pro plug-in

Export IDB information            <##Export :{export_button}>
Recover compile-unit segmentation <##Analyze:{analyze_button}>
Explore analysis results          <##Explore:{explore_button}>
""",
            {
                "export_button": Form.ButtonInput(self.on_export),
                "analyze_button": Form.ButtonInput(self.on_analyze),
                "explore_button": Form.ButtonInput(self.on_explore),
            },
        )
        self.Compile()

    def on_export(self, code: int = 0) -> None:
        form = ExportForm()
        form.Execute()
        form.Free()

    def on_analyze(self, code: int = 0) -> None:
        form = AnalysisForm()
        form.Execute()
        form.Free()

    def on_explore(self, code: int = 0) -> None:
        form = ExplorationForm()
        form.Execute()
        form.Free()


class RecoverPlugin(plugin_t):
    """Main plug-in object as required by IDA Pro."""

    flags = 0
    comment = "REcover IDA Pro plug-in"
    help = "https://github.com/huku-/recover"
    wanted_name = "REcover"
    wanted_hotkey = "Ctrl+Alt+R"

    def init(self) -> int:
        if actions := os.getenv("RECOVER_HEADLESS"):
            ida_auto.auto_wait()
            run_headless(actions)
        return ida_idaapi.PLUGIN_KEEP

    def run(self, arg: int) -> None:
        form = MainForm()
        form.Execute()
        form.Free()

    def term(self) -> None:
        pass


def PLUGIN_ENTRY() -> plugin_t:
    return RecoverPlugin()
