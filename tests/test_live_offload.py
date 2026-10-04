"""The live-verdict models visit the GPU only for a forward pass (NFR-3).

Three large models resident beside the offline stack peaked at 6.2 GiB on a 6 GiB card, so
the live models are held in CPU RAM and moved over for one call. These tests use fakes: they
check the choreography (to GPU, compute, ALWAYS back to CPU, even on an error), not the models.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from preprocess.translate import NllbTranslator  # both import torch lazily
from stance.nli import NLIStance

torch = pytest.importorskip("torch", reason="torch lives in the ML lock")


class FakeEncoding(dict):
    def to(self, _device):
        return self


class FakeModel:
    def __init__(self, fail=False):
        self.moves, self.fail = [], fail

    def to(self, device):
        self.moves.append(device)
        return self

    def __call__(self, **enc):
        if self.fail:
            raise RuntimeError("cuda out of memory")
        return SimpleNamespace(logits=torch.tensor([[3.0, 0.0, -3.0]] * enc["n"]))

    def generate(self, **kw):
        if self.fail:
            raise RuntimeError("cuda out of memory")
        return torch.tensor([[1, 2, 3]])


def fake_tokenizer(premises, hypotheses, **_kw):
    return FakeEncoding(n=len(premises))


def make_nli(fail=False, offload=True):
    nli = NLIStance(model_id="fake", device="cuda", offload=offload, batch_size=2)
    nli._model, nli._tokenizer = FakeModel(fail), fake_tokenizer
    nli._id2stance = {0: "Supports", 1: "Neutral", 2: "Refutes"}
    return nli


def test_an_offloaded_model_goes_to_the_gpu_and_back():
    nli = make_nli()
    out = nli.label("claim", ["a", "b", "c"])            # 3 pairs, batch size 2
    assert [r.stance for r in out] == ["Supports"] * 3
    assert nli._model.moves == ["cuda", "cpu"]            # once each way for the whole call


def test_an_error_inside_the_forward_pass_still_returns_the_model_to_the_cpu():
    nli = make_nli(fail=True)
    with pytest.raises(RuntimeError):
        nli.label("claim", ["a"])
    assert nli._model.moves == ["cuda", "cpu"]            # the next click must not find it stranded


def test_a_resident_model_is_never_moved():
    nli = make_nli(offload=False)
    nli.label("claim", ["a"])
    assert nli._model.moves == []


def make_translator(fail=False):
    tr = NllbTranslator(device="cuda")
    tr._model = FakeModel(fail)
    tr._tok = _Tok()
    return tr


class _Tok:
    src_lang = None

    def __call__(self, *_a, **_k):
        return FakeEncoding(input_ids=torch.tensor([[1]]))

    def convert_tokens_to_ids(self, _x):
        return 7

    def batch_decode(self, *_a, **_k):
        return [" Mumbai "]


def test_the_translator_visits_the_gpu_only_while_translating():
    tr = make_translator()
    assert tr.translate("मुंबई", "hi", "en") == "Mumbai"
    assert tr._model.moves == ["cuda", "cpu"]
    tr.translate("मुंबई", "hi", "en")                      # cached: no second trip
    assert tr._model.moves == ["cuda", "cpu"]


def test_a_failed_translation_still_returns_the_translator_to_the_cpu():
    tr = make_translator(fail=True)
    with pytest.raises(RuntimeError):
        tr.translate("मुंबई", "hi", "en")
    assert tr._model.moves == ["cuda", "cpu"]
