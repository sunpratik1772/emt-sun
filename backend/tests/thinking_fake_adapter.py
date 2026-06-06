"""Deterministic fake LLM adapter for thinking-monologue unit tests."""
from __future__ import annotations


class ThinkingFakeAdapter:
    """Returns varied, acceptable monologue text keyed off the user turn."""

    def single_shot(self, prompt, *, system_prompt=None, temperature=0.0, max_output_tokens=None):
        return self._text(prompt)

    def chat_turn_stream(
        self,
        *,
        system_prompt,
        history,
        user_turn,
        model=None,
        temperature=0.0,
        json_mode=True,
    ):
        text = self._text(user_turn)
        for part in text.split("\n"):
            yield part + "\n"

    def _text(self, user_turn: str) -> str:
        lower = (user_turn or "").lower()
        if "improve" in lower or "join comms" in lower:
            return (
                'Examining "Join Comms Messages with HS Alerts and Rank" on the canvas.\n'
                "I'll add validation, a branch for failures, and an Outlook summary "
                "without rebuilding from scratch.\n"
                "Drafting now."
            )
        if "why did the join fail" in lower or "route: ask" in lower:
            return (
                'Tracing why the join failed against recent canvas errors.\n'
                "I'll walk through the error log and rank recovery options.\n"
                "Drafting the answer now."
            )
        if "route: load" in lower or "library search" in lower:
            return (
                "Searching saved workflows in the library for a close match.\n"
                "I'll open the best hit for \"orders pipeline\" onto the canvas.\n"
                "Drafting the result now."
            )
        if "route: automate" in lower:
            return (
                "Checking schedule wording and the workflow already on the canvas.\n"
                "I'll save the workflow and wire the daily automation they described.\n"
                "Drafting now."
            )
        if "route: failure" in lower or "validation errors" in lower:
            return (
                "Tracing why generation did not produce a runnable workflow.\n"
                "I'll walk through validation issues and the smallest recovery patch.\n"
                "Writing the recovery plan now."
            )
        if "route: explain_run" in lower or "run log:" in lower:
            return (
                "Pulling the latest run log and per-node row counts.\n"
                "I'll summarize what each step produced before suggesting a fix.\n"
                "Writing the run summary now."
            )
        if "hs_trades" in lower:
            return (
                "Examining hs_trades columns and the export they asked for.\n"
                "I'll load from the surveillance catalog, flag the rows that matter, "
                "and wire a terminal CSV export.\n"
                "Drafting now."
            )
        if "market_ticks" in lower or "spread_pips" in lower:
            return (
                "Mapping market_ticks schema and the spread filter they described.\n"
                "I'll filter where spread_pips exceeds their threshold and export CSV.\n"
                "Drafting now."
            )
        if "accounts.csv" in lower and "join" in lower:
            return (
                "Examining leads.csv and accounts.csv join keys on the canvas path.\n"
                "I'll inner-join on email and sanity-check match rate before export.\n"
                "Drafting now."
            )
        if "sort" in lower and "score" in lower:
            return (
                "Checking leads.csv for the score column they named.\n"
                "I'll sort descending and terminate with a concrete CSV filename.\n"
                "Drafting now."
            )
        if "high-risk" in lower or "high risk" in lower:
            return (
                "Examining leads.csv and how to interpret high-risk rows.\n"
                "I'll treat high-risk as score >= 80 once columns are confirmed, then export CSV.\n"
                "Drafting now."
            )
        return (
            "Mapping datasets and transforms from their build request.\n"
            "I'll wire a minimal DAG with a deterministic export node.\n"
            "Drafting now."
        )
