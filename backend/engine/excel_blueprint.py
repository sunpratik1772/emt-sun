"""
Excel export blueprint selection for registry data bundles.
"""
from __future__ import annotations

from pathlib import Path

from generation.harness.intent import Intent

from engine.data_bundle_catalog import (
    build_join_excel_skeleton,
    build_single_bundle_excel_skeleton,
    datasets_in_scenario,
    excel_filename_for,
    resolve_join_pair,
)
from engine.demo_paths import demo_workflow_path

from generation.harness.blueprint_router import BlueprintDecision, ParallelSubtask


def _wants_excel(intent: Intent, text: str) -> bool:
    if "excel" in intent.artifacts:
        return True
    return any(k in text for k in ("excel", "xlsx", "spreadsheet"))


def _collect_datasets(scenario: str, intent: Intent) -> list[str]:
    datasets = list(intent.datasets)
    for ds in datasets_in_scenario(scenario):
        if ds not in datasets:
            datasets.append(ds)
    return sorted(set(datasets))


def select_excel_blueprint(scenario: str, intent: Intent) -> BlueprintDecision | None:
    text = (scenario or "").lower()
    if not _wants_excel(intent, text):
        return None

    datasets = _collect_datasets(scenario, intent)
    if not datasets:
        return None

    filename = excel_filename_for(datasets, scenario)

    if len(datasets) >= 2:
        pair = resolve_join_pair(datasets)
        if pair is None:
            return None
        if pair.demo_filename:
            path = demo_workflow_path(pair.demo_filename)
            if path.is_file():
                return BlueprintDecision(
                    blueprint_id=f"excel_{pair.left_id}_{pair.right_id}",
                    title=f"Excel join: {pair.left_id} + {pair.right_id}",
                    workflow_path=path,
                    why=(
                        f"Detected Excel export over {pair.left_id} and {pair.right_id}; "
                        "using vetted join + export topology."
                    ),
                    parallel_tasks=(
                        ParallelSubtask(
                            subagent_type="explore",
                            description="Join key validation",
                            prompt=(
                                f"Confirm join keys {pair.left_key}/{pair.right_key} and "
                                f"column overlap between {pair.left_id} and {pair.right_id}."
                            ),
                        ),
                    ),
                )
        skeleton = build_join_excel_skeleton(pair, filename)
        return BlueprintDecision(
            blueprint_id=f"excel_{pair.left_id}_{pair.right_id}",
            title=f"Excel join: {pair.left_id} + {pair.right_id}",
            workflow_path=None,
            workflow_skeleton=skeleton,
            why=(
                f"Detected Excel export joining {pair.left_id} and {pair.right_id} "
                f"on {pair.left_key}."
            ),
            parallel_tasks=(
                ParallelSubtask(
                    subagent_type="explore",
                    description="Join key validation",
                    prompt=(
                        f"Confirm join keys {pair.left_key}/{pair.right_key} and "
                        f"column overlap between {pair.left_id} and {pair.right_id}."
                    ),
                ),
            ),
        )

    bundle_id = datasets[0]
    skeleton = build_single_bundle_excel_skeleton(bundle_id, filename)
    return BlueprintDecision(
        blueprint_id=f"excel_{bundle_id.replace('.', '_')}",
        title=f"Excel export: {bundle_id}",
        workflow_path=None,
        workflow_skeleton=skeleton,
        why=f"Detected single-bundle Excel export for {bundle_id}.",
    )
