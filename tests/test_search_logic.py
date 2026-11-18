"""Abstention + hybrid reranking logic, with Qdrant faked out (no network, no models)."""

from types import SimpleNamespace

import pytest

from api import search
from lexicon import Tags


def hit(score, entity):
    return {"score": score, "dense": score, "entity": entity, "shared": {}, "payload": {}}


def test_abstain_on_empty_or_low_score():
    assert search.abstain([], Tags(), 0.5)
    assert search.abstain([hit(0.49, 0)], Tags(), 0.5)
    assert not search.abstain([hit(0.51, 0)], Tags(), 0.5)


def test_abstain_when_query_entities_not_shared():
    # high score but the query named turmeric and the hit has none of it
    assert search.abstain([hit(0.9, 0.0)], Tags(plants=["turmeric"]), 0.5)
    assert not search.abstain([hit(0.9, 0.6)], Tags(plants=["turmeric"]), 0.5)


class FakeClient:
    def __init__(self, dense, filtered):
        self.dense, self.filtered = dense, filtered

    def query_points(self, collection, query, limit, with_payload, query_filter=None):
        return SimpleNamespace(points=self.filtered if query_filter else self.dense)


def point(pid, score, plants=(), conditions=()):
    return SimpleNamespace(id=pid, score=score,
                           payload={"plants": list(plants), "conditions": list(conditions)})


def test_hybrid_rerank_prefers_entity_match(monkeypatch):
    # dense search alone ranks a turmeric-free chunk first; the filtered
    # pass brings in the turmeric chunk, and hybrid scoring puts it on top
    fake = FakeClient(dense=[point(1, 0.80, plants=["neem"])],
                      filtered=[point(2, 0.60, plants=["turmeric"], conditions=["skin_disease"])])
    monkeypatch.setattr(search, "get_client", lambda: fake)
    q = Tags(plants=["turmeric"], conditions=["skin_disease"])
    res = search.hybrid_search("c", [0.0], q, k=2)
    assert [r["payload"]["plants"] for r in res] == [["turmeric"], ["neem"]]
    assert res[0]["score"] == pytest.approx(0.5 * 0.60 + 0.5 * 1.0)
    assert res[0]["shared"] == {"plants": ["turmeric"], "conditions": ["skin_disease"]}


def test_hybrid_pure_dense_without_query_entities(monkeypatch):
    fake = FakeClient(dense=[point(1, 0.7), point(2, 0.4)], filtered=[])
    monkeypatch.setattr(search, "get_client", lambda: fake)
    res = search.hybrid_search("c", [0.0], Tags(), k=5)
    assert [r["score"] for r in res] == [0.7, 0.4]
