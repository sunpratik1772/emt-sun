"""
Data-driven response formatters for agent-layer nodes.

Replaces the 120-line if/elif chain in dag_runner._agent_response()
with a registry of small formatter functions — one per agent node type.

Each formatter receives:
  - node:       the node dict (has config, id, type, etc.)
  - new_values: dict of ctx.values that changed during this node's execution
  - ctx:        the full RunContext (for fallback reads)
  - pick:       helper fn(default_key) → value from new_values or ctx

And returns a short human-readable string (or None to skip).

Adding a formatter for a new agent node is a decorator call:

    @register("MY_NEW_NODE")
    def _fmt_my_node(node, new_values, ctx, pick):
        return "Did something."
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .context import RunContext

Formatter = Callable[[dict, dict, "RunContext", Callable], Optional[str]]

_REGISTRY: dict[str, Formatter] = {}


def register(node_type: str) -> Callable[[Formatter], Formatter]:
    def decorator(fn: Formatter) -> Formatter:
        _REGISTRY[node_type] = fn
        return fn
    return decorator


def get_agent_response(node: dict, new_values: dict, ctx: RunContext) -> Optional[str]:
    node_type = node.get("type")
    formatter = _REGISTRY.get(node_type)
    if not formatter:
        return None
    cfg = node.get("config") or {}

    def pick(default_key: str) -> Any:
        key = str(cfg.get("output_name") or default_key)
        if key in new_values:
            return new_values[key]
        return ctx.get(key)

    return formatter(node, new_values, ctx, pick)


# ---------------------------------------------------------------------------
# Helpers shared across formatters
# ---------------------------------------------------------------------------
def _validity_sentence(result: object, subject: str) -> str:
    if not isinstance(result, dict):
        return f"{subject} validation completed."
    valid = bool(result.get("valid"))
    errors = result.get("errors") or result.get("issues") or []
    text = f"{subject} validation {'passed' if valid else 'failed'}."
    if errors:
        text += " " + "; ".join(map(str, errors[:3])) + "."
    return text


def _payload_text(payload: object) -> Optional[str]:
    if payload is None:
        return None
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("response", "text", "summary", "memo", "narrative", "answer", "final_output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        result = payload.get("result")
        if isinstance(result, dict):
            done = result.get("done")
            confidence = result.get("confidence")
            missing = result.get("missing") or []
            if done is not None or confidence is not None or missing:
                text = f"Escalation readiness is {'complete' if done else 'incomplete'}"
                if confidence is not None:
                    text += f" with confidence {confidence}"
                text += "."
                if missing:
                    text += " Missing: " + "; ".join(map(str, missing[:3])) + "."
                return text
    return None


# ---------------------------------------------------------------------------
# Formatters — one per agent node type
# ---------------------------------------------------------------------------
@register("LLM_PLANNER")
def _fmt_planner(node, new_values, ctx, pick):
    plan = pick("plan")
    steps = plan.get("steps") if isinstance(plan, dict) else []
    if steps:
        first = steps[0]
        action = first.get("action") or first.get("tool") or "next step"
        return f"Planned {len(steps)} step(s). First step: {action}."
    return "Created an investigation plan."


@register("PLAN_VALIDATOR")
def _fmt_plan_validator(node, new_values, ctx, pick):
    return _validity_sentence(pick("plan_validation"), "Plan")


@register("LLM_ACTION")
def _fmt_action(node, new_values, ctx, pick):
    action = pick("action")
    if isinstance(action, dict):
        tool = action.get("tool") or "tool"
        reasoning = action.get("reasoning")
        confidence = action.get("confidence")
        suffix = f" Confidence: {confidence}." if confidence is not None else ""
        return f"Selected `{tool}` as the next action.{suffix}" + (f" {reasoning}" if reasoning else "")
    return "Selected the next action."


@register("ACTION_VALIDATOR")
def _fmt_action_validator(node, new_values, ctx, pick):
    return _validity_sentence(pick("action_validation"), "Action")


@register("GUARDRAIL")
def _fmt_guardrail(node, new_values, ctx, pick):
    return _validity_sentence(pick("guardrail_result"), "Safety guardrail")


@register("TOOL_EXECUTOR")
def _fmt_tool_executor(node, new_values, ctx, pick):
    result = pick("last_result")
    if isinstance(result, dict):
        status = result.get("status", "ok")
        output = result.get("output_name") or result.get("artifact_path") or result.get("node_type")
        rows = result.get("rows")
        bits = [f"Tool execution finished with status `{status}`."]
        if output:
            bits.append(f"Output: {output}.")
        if rows is not None:
            bits.append(f"Rows: {rows}.")
        return " ".join(bits)
    return "Executed the selected tool."


@register("LLM_CRITIC")
def _fmt_critic(node, new_values, ctx, pick):
    result = pick("validation")
    if isinstance(result, dict):
        valid = bool(result.get("valid"))
        confidence = result.get("confidence")
        issues = result.get("issues") or []
        suggestions = result.get("suggestions") or []
        status = "accepted the result" if valid else "found issues"
        text = f"The critic {status}"
        if confidence is not None:
            text += f" with confidence {confidence}"
        text += "."
        if issues:
            text += " Issues: " + "; ".join(map(str, issues[:3])) + "."
        if suggestions:
            text += " Suggestions: " + "; ".join(map(str, suggestions[:3])) + "."
        return text
    return "Critiqued the latest result."


@register("STATE_MANAGER")
def _fmt_state_manager(node, new_values, ctx, pick):
    state = pick("retry_context")
    iteration = state.get("iteration") if isinstance(state, dict) else None
    return "Updated agent memory." + (f" Iteration is now {iteration}." if iteration is not None else "")


@register("LLM_EVALUATOR")
def _fmt_evaluator(node, new_values, ctx, pick):
    result = pick("evaluator_status")
    if isinstance(result, dict):
        done = bool(result.get("done"))
        confidence = result.get("confidence")
        missing = result.get("missing") or []
        text = "The goal is satisfied" if done else "The goal is not satisfied yet"
        if confidence is not None:
            text += f" with confidence {confidence}"
        text += "."
        if missing:
            text += " Missing: " + "; ".join(map(str, missing[:3])) + "."
        return text
    return "Evaluated goal satisfaction."


@register("LOOP_CONTROLLER")
def _fmt_loop_controller(node, new_values, ctx, pick):
    result = pick("loop_decision")
    if isinstance(result, dict):
        action = "continue" if result.get("continue") else "stop"
        reason = result.get("stop_reason") or "decision made"
        iteration = result.get("iteration")
        return f"Loop controller decided to {action}. Reason: {reason}. Iteration: {iteration}."
    return "Updated loop control."


@register("LLM_SYNTHESIZER")
def _fmt_synthesizer(node, new_values, ctx, pick):
    return _payload_text(pick("final_output")) or "Synthesized the final response."


@register("LLM_CONTEXTUALIZER")
def _fmt_contextualizer(node, new_values, ctx, pick):
    return _payload_text(pick("enriched_context")) or "Enriched the context for downstream reasoning."


@register("AGGREGATOR_NODE")
def _fmt_aggregator(node, new_values, ctx, pick):
    return "Aggregated selected context values and datasets."


@register("DATA_REDUCER")
def _fmt_data_reducer(node, new_values, ctx, pick):
    cfg = node.get("config") or {}
    summary_key = f"{str(cfg.get('output_name') or 'reduced_data')}_summary"
    result = new_values.get(summary_key) or ctx.get(summary_key)
    return _payload_text(result) or "Reduced the dataset for agent review."


@register("ERROR_HANDLER")
def _fmt_error_handler(node, new_values, ctx, pick):
    return _payload_text(pick("recovery_strategy")) or "Selected a recovery strategy."
