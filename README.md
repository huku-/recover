# REcover

![REcover](logo/recover-logo.png?raw=true "REcover")

REcover is a tool for approximately recovering the compile-unit layout from
stripped binary executables. REcover consists of an IDAPython plug-in, used for
exporting information, and a command-line tool for running various analyses.


## Installation

1. Create and activate a new virtual environment:

        $ python -m venv /tmp/recover-venv
        $ . /tmp/recover-venv/bin/activate

2. Clone and install REcover and its dependencies:

        $ cd /tmp
        $ git clone --recurse-submodules https://github.com/huku-/recover.git
        $ cd recover
        $ pip install .

3. Make sure everything works as expected:

        $ recover -h

4. Additionally, you can install the *experimental* IDA Pro plug-in. Find source
   code [here](plugins/ida_pro/) and instructions [here](doc/ida_pro_plugin.md).


## Using REcover

Let's analyze ELF binary `sha256sum` from `coreutils-7.6-O3` of the DeepBinDiff
dataset:

    $ ls -la /tmp/sha256sum
    -rwxr-x--- 1 huku huku 239696 Jun  4 18:57 /tmp/sha256sum
    $ file /tmp/sha256sum
    /tmp/sha256sum: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 2.6.32, BuildID[sha1]=c08bcb9aede425a19d263c5e5d9c55b8f9f63701, with debug_info, not stripped

Even though the above executable comes with debug information (i.e., it's not
actually stripped), the latter is not used by REcover to estimate the compile-unit
layout.


### <u>Export data using IDA Pro</u>

Fire up IDA Pro and run the REcover exporter. Either navigate to `File` &rarr;
`Script file...` and choose **main.py** or run the following command:

    RECOVER_EXIT=1 ida64 -A -S/tmp/recover/src/recover/main.py \
        /tmp/sha256sum

This creates a directory named **sha256sum.export** (the IDB database name with
its extension replaced by **.export**), in the same directory as the ELF executable,
containing the following files:

    $ ls -la /tmp/sha256sum.export/*.pcl
    -rw-r--r-- 1 huku huku 34817 Jun  4 22:35 /tmp/sha256sum.export/afcg.pcl
    -rw-r--r-- 1 huku huku 35010 Jun  4 22:35 /tmp/sha256sum.export/dfg.pcl
    -rw-r--r-- 1 huku huku 60956 Jun  4 22:35 /tmp/sha256sum.export/pdg.pcl
    -rw-r--r-- 1 huku huku  1354 Jun  4 22:35 /tmp/sha256sum.export/segs.pcl


### <u>Estimate compile-units</u>

To run an actual compile-unit estimation analysis, use `recover` from the command
line as shown below:

    $ recover --estimator agglnse \
        --fitness-function modularity \
        --optimizer brute \
        -k /tmp/estimated_cu_map.pcl \
        -j /tmp/estimated_cu_map.json \
        --debug \
        /tmp/sha256sum.export

There is a variety of estimators (`--estimator`), fitness functions (`--fitness-function`)
and optimizers (`--optimizer`) to choose from. See `recover -h` for more information.


## Documentation

* See [Extending REcover](doc/extending.md) for more information on how to extend
  REcover.

* Complete API reference is on the way!


## Cite

    @article{karamitas2025,
        title={REcover: towards recovering object files from stripped binary executables},
        author={Karamitas, Chariton and Kehagias, Athanasios},
        journal={Journal of Computer Virology and Hacking Techniques},
        volume={21},
        number={1},
        pages={29},
        year={2025},
        publisher={Springer}
    }
