"""Claim-level folds for cross-fitted stance scoring (Phase 6, decision D2).

The learned aggregator trains on stance outputs for AVeriTeC TRAIN claims, and
the trained stance models learned from those same claims -- every QA answer of a
train claim, labelled with that claim's verdict. Scored by a model that saw
them, train claims would look far more confidently right than any unseen claim,
and the aggregator would learn to trust stance that much. So each train claim
is scored by a model trained on the OTHER folds.

Folds are by CLAIM, never by answer: two answers of one claim in different
folds would leak its verdict across the boundary.

Assignment is a seeded hash of the claim's source_id, not a shuffle of a file:
it depends on nothing but the id, so the training scripts, the scorer and the
tests cannot disagree about which fold a claim is in.
"""

from __future__ import annotations

import hashlib

from common.seeds import SEED

N_FOLDS = 5


def fold_of(claim_source_id: str, n_folds: int = N_FOLDS, seed: int = SEED) -> int:
    """The fold of an AVeriTeC claim, e.g. `averitec:train.json:133`."""
    if not claim_source_id.startswith("averitec:"):
        # A stance row's id (`averitec_stance:...:q0:a1`) must be mapped to its
        # parent claim first; hashing it directly would scatter one claim's
        # answers across folds -- exactly the leak this module prevents.
        raise ValueError(f"fold_of takes a CLAIM source_id, got {claim_source_id!r}")
    digest = hashlib.sha256(f"{seed}:{claim_source_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % n_folds
