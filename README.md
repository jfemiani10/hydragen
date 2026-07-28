# Hydragen

A terminal UI for exploring and launching [Hydra](https://hydra.cc) configurations.

Hydragen provides a terminal UI experience for Hydra applications while
remaining a separate package from Hydra itself.

## Install

For regular use, install directly from GitHub:

```bash
pip install "git+https://github.com/jfemiani10/hydragen.git@main"
```

Hydra is installed automatically as a dependency.

## Development

Clone and install with development dependencies:

```bash
git clone https://github.com/jfemiani10/hydragen.git
cd hydragen
pip install -e ".[dev]"
```

Enable local hooks:

```bash
pre-commit install
pre-commit run --all-files
```

## Try it

Run the example app with:

```bash
hydragen example/my_app.py
```

You can also pass Hydra overrides:

```bash
hydragen example/my_app.py model=cnn dataset=cifar
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
