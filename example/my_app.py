# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
"""Self-contained example for hydra-tui.

    python my_app.py --tui        # open the terminal UI
    python my_app.py              # run normally
    python my_app.py model=cnn    # the UI just drives these overrides
"""
import logging

import hydra
from omegaconf import DictConfig, OmegaConf

log = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="conf", config_name="config")
def my_app(cfg: DictConfig) -> None:
    log.info("Running with:\n%s", OmegaConf.to_yaml(cfg))


if __name__ == "__main__":
    my_app()
