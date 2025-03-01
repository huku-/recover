# REcover IDA Pro plug-in

## Installation

REcover depends on [ida-venv](https://github.com/Skwteinopteros/ida-venv), so,
install this first:

    curl -sLo $IDAUSR/plugins/ida_venv.py https://raw.githubusercontent.com/Skwteinopteros/ida-venv/refs/heads/main/ida_venv.py

Then, to install REcover:

    cp recover.py $IDAUSR/plugins

## Using the plug-in

Just press Ctrl+R for the main UI to pop-up, or manually navigate to
`Edit` &rarr; `Plugins` &rarr; `REcover`.
