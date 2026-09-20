"""The one place a seed is set.

CLAUDE.md: "Every run sets seed=42 in numpy, torch, random, and transformers."
Import `set_all_seeds` rather than calling `random.seed` locally, so there is a
single definition of what "seeded" means and a single thing to audit.

torch and transformers are imported lazily and optionally: Phase 0 has no model
dependencies installed, and this module must stay importable without them.
"""

from __future__ import annotations

import os
import random

SEED = 42


def set_all_seeds(seed: int = SEED, *, deterministic_torch: bool = True) -> dict[str, bool]:
    """Seed every RNG this project can reach.

    Returns a record of which libraries were actually seeded, so a run can log
    what it did instead of asserting something it did not do.
    """
    seeded: dict[str, bool] = {"random": False, "numpy": False, "torch": False,
                               "transformers": False}

    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    seeded["random"] = True

    try:
        import numpy as np
    except ImportError:
        pass
    else:
        np.random.seed(seed)
        seeded["numpy"] = True

    try:
        import torch
    except ImportError:
        pass
    else:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        if deterministic_torch:
            # Trades speed for reproducibility. Worth it: an unreproducible
            # number cannot be defended in a viva.
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        seeded["torch"] = True

    try:
        import transformers
    except ImportError:
        pass
    else:
        transformers.set_seed(seed)
        seeded["transformers"] = True

    return seeded
