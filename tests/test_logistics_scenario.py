"""Verify the public logistics pack can be consumed by existing scenario routing."""
import csv
import json
from pathlib import Path

import pytest

from qa_core.scenarios.registry import ScenarioRegistry
from qa_core.scenarios.boundary import rank_source_matches


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("query,expected", [
    ("物流轨迹未更新，运单显示运输异常", "tracking"),
    ("破损理赔要不要外包装照片和价值证明", "claims"),
    ("退件可以改址和拦截吗", "returns"),
])
def test_logistics_source_routing(query, expected):
    scenario = ScenarioRegistry(ROOT / "scenarios").resolve("logistics_after_sales")
    assert scenario.scenario_id == "logistics_after_sales"
    assert rank_source_matches(query, scenario)[0].source == expected


def test_faq_eval_and_document_sources_are_consistent():
    scenario = ScenarioRegistry(ROOT / "scenarios").resolve("logistics_after_sales")
    with open(scenario.faq_csv_path, encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert {row["source"] for row in rows} == set(scenario.valid_sources)
    for source in scenario.valid_sources:
        docs = list((Path(scenario.data_root) / f"{source}_data").glob("*.md"))
        assert docs
        assert all("合成演示政策" in doc.read_text(encoding="utf-8") for doc in docs)
    cases = json.loads((ROOT / "eval_sets/logistics_after_sales.json").read_text(encoding="utf-8"))
    faqs = {row["question"]: row["answer"] for row in rows}
    for case in cases:
        assert case["scenario_id"] == scenario.scenario_id
        assert case["source_filter"] in scenario.valid_sources
        if case.get("expected_hit_type") == "faq_direct":
            assert all(term in faqs[case["query"]] for term in case["expected_keywords"])
