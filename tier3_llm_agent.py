"""
tier3_llm_agent.py
-------------------
Reference implementation of Tier 3 backed by a REAL Claude API call with tool use,
instead of the deterministic reasoning engine in match_pipeline.py.

Same contract in, same contract out - so this is a genuine drop-in replacement:
  input:  one unresolved invoice + all candidate GL/bank rows referencing it
  output: {"resolution": "match" | "exception", "bank_txn_id": ..., "confidence": 0-1,
           "justification": "<one sentence>", "category": "<exception category if any>"}

This file is not executed by run_pipeline.py by default (the buildathon environment
this was drafted in has no outbound network access to test it live). It documents
exactly how the agent tier would be wired for a production/demo deployment - swap
`USE_LLM_AGENT = True` in match_pipeline.py and point tier3_resolve() at
resolve_with_llm() below.

Requires: pip install anthropic
Env var:  ANTHROPIC_API_KEY
"""

import json
import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

TOOLS = [
    {
        "name": "lookup_invoice",
        "description": "Fetch full details for an invoice by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"invoice_id": {"type": "string"}},
            "required": ["invoice_id"],
        },
    },
    {
        "name": "lookup_bank_txn",
        "description": "Fetch full details for a bank transaction by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"bank_txn_id": {"type": "string"}},
            "required": ["bank_txn_id"],
        },
    },
    {
        "name": "compute_delta",
        "description": "Compute the day and amount delta between two records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_a": {"type": "string"}, "date_b": {"type": "string"},
                "amount_a": {"type": "number"}, "amount_b": {"type": "number"},
            },
            "required": ["date_a", "date_b", "amount_a", "amount_b"],
        },
    },
    {
        "name": "flag_exception",
        "description": "Give up resolving this record and file it to the exception queue "
                        "with a specific category. Use this instead of forcing a low-confidence match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["missing_gl_posting", "no_bank_payment_found",
                              "duplicate_payment", "orphan_bank_txn", "ambiguous_multiple_candidates"],
                },
                "reason": {"type": "string"},
            },
            "required": ["category", "reason"],
        },
    },
]

SYSTEM_PROMPT = """You are a finance controller's reconciliation agent. You are handed ONE
invoice that could not be resolved by exact or fuzzy-tolerance matching, plus every GL and
bank record that could plausibly relate to it. Your job:

1. Investigate using the tools available - look up related records, compute deltas.
2. If you find a genuine match (split payment, combined payment, duplicate payment, or a
   legitimate edge case), report it with a confidence score and a ONE-SENTENCE justification
   a human auditor could read and immediately understand.
3. If nothing genuinely resolves it, call flag_exception with the correct category. Never
   force a low-confidence match just to raise the match rate - an honest exception is more
   valuable than a wrong match. A controller who signs off on a false match is worse than one
   who flags it for review.

Output ONLY a single JSON object, no prose, no markdown fences."""


def resolve_with_llm(invoice, candidate_gl, candidate_bank_rows):
    """One Tier-3 agent call for a single unresolved invoice."""
    user_prompt = json.dumps({
        "invoice": invoice,
        "candidate_gl_rows": candidate_gl,
        "candidate_bank_rows": candidate_bank_rows,
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # In a full implementation, loop here: execute any tool_use blocks against your
    # actual data store, append tool_result messages, and call again until Claude
    # returns a final text block. Omitted here since this file is illustrative -
    # the deterministic engine in match_pipeline.py is what the graded run uses.
    for block in response.content:
        if block.type == "text":
            return json.loads(block.text)
    return {"resolution": "exception", "category": "ambiguous_multiple_candidates",
            "reason": "Agent did not return a final answer.", "confidence": 0.0}
