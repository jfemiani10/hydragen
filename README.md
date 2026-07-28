# Hydragen

A terminal UI for exploring and launching [Hydra](https://hydra.cc) configurations.



Hydragen was inspired by the idea behind
[hydra-tui](https://pypi.org/project/hydra-tui/). When we began this project,
however, we could not locate a source repository suitable to fork or get the
available package running successfully with our Hydra applications. Hydragen
is therefore an independent implementation, not a fork of `hydra-tui`.

## Setup from a fresh clone

The `--tui` flag currently exists only on the companion Hydra fork, so both repositories must be installed in the same Python environment.

Building Hydra from source requires Java because its configuration-override grammar is generated with ANTLR at build time. The ANTLR JAR is vendored in `build_helpers/bin/`.

Verify that Java is available:

```bash
java -version
```

### Windows

Enable long paths before cloning Hydra:

```bash
git config --global core.longpaths true
```

Hydra contains test fixtures whose paths exceed the traditional 260-character Windows `MAX_PATH` limit. Cloning into a short directory such as `C:\src` also helps.

If a clone already failed with `Filename too long`, enable long paths and restore the missing files:

```bash
git restore --source=HEAD :/
```

### Install Hydra and Hydragen

Clone both repositories into the same parent directory:

```bash
git clone -b tui https://github.com/jfemiani10/hydra.git
git clone https://github.com/jfemiani10/hydragen.git
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Linux or macOS:

```bash
source .venv/bin/activate
```

Windows:

```powershell
.venv\Scripts\activate
```

Install the patched Hydra fork and the standalone Hydragen plugin:

```bash
pip install -r hydra/requirements/dev.txt
pip install -e ./hydra
pip install -e ./hydragen
```

Verify that the patched Hydra installation provides `--tui`:

```bash
python -c "from hydra._internal.utils import get_args_parser; print('--tui' in [o for a in get_args_parser()._actions for o in a.option_strings])"
```

The result should be:

```text
True
```

## Try it

Hydragen includes a self-contained example:

```bash
python hydragen/example/my_app.py --tui
```

It also works with Hydra’s existing examples without modifying the applications:

```bash
python hydra/examples/tutorials/basic/your_first_hydra_app/6_composition/my_app.py --tui
```

On Windows, run Hydragen from Windows Terminal. Textual renders poorly in the legacy console host.

## What it does

* Lists every configuration group and option exposed by the running application’s `ConfigLoader`, allowing it to adapt to any Hydra project without additional configuration.
* Recomposes the configuration as you move through options using `load_configuration()`, the same mechanism used by `@hydra.main`.
* Shows the exact `python my_app.py ...` command represented by the current selection, so the interface teaches Hydra’s command-line syntax instead of hiding it.
* Displays composition errors, including invalid types and unknown keys, in the interface instead of crashing.
* Launches the selected job in a subprocess and streams its output.
* Supports Hydra multiruns.

## Keys

| Key        | Action                                |
| ---------- | ------------------------------------- |
| Arrow keys | Change the selected option in a group |
| `r`        | Run the composed job                  |
| `m`        | Toggle `--multirun`                   |
| `x`        | Clear the log pane                    |
| `q`        | Quit                                  |
