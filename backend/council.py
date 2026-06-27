"""3-stage LLM Council orchestration."""

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable, List, Dict, Any, Tuple
from .openrouter import build_cost_call, build_cost_summary, query_model, query_model_detailed
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL

STAGE2_MAX_ATTEMPTS = 2
STAGE2_MODEL_TIMEOUT_SECONDS = 110.0
STAGE1_MAX_OUTPUT_TOKENS = 3500
STAGE2_MAX_OUTPUT_TOKENS = 3000
STAGE3_MAX_OUTPUT_TOKENS = 4500
STAGE2_REVIEW_RESPONSE_CHAR_LIMIT = 10000
STAGE2_MIN_VALID_RANKINGS_TO_SYNTHESIZE = 2
STAGE1_SYSTEM_PROMPT = """You are one member of a multi-model analysis council.

Produce a complete, self-contained answer, but keep it bounded so the full council can review it.

Requirements:
- Target roughly 1,800-2,500 words unless the user explicitly asks for a shorter answer.
- Prioritize the strongest reasoning, evidence, tradeoffs, and conclusions over exhaustive coverage.
- If the question asks for rankings or scenarios, include the key rankings and rationale, but do not create sprawling appendices.
- Finish with a concise bottom-line conclusion.
- Do not continue past the point where the answer is complete."""


def _bounded_review_text(text: str, limit: int = STAGE2_REVIEW_RESPONSE_CHAR_LIMIT) -> Tuple[str, bool]:
    if len(text or "") <= limit:
        return text or "", False
    head = max(limit * 2 // 3, 1)
    tail = max(limit - head, 1)
    return (
        (text or "")[:head]
        + "\n\n[...middle omitted for peer-review runtime; full response remains stored in Stage 1...]\n\n"
        + (text or "")[-tail:],
        True,
    )


def _ordered_stage1_results(models: List[str], results_by_model: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return Stage 1 results in stable council order (not completion order)."""
    return [results_by_model[model] for model in models if model in results_by_model]


def build_stage1_execution_metadata(
    attempted_models: List[str],
    results_by_model: Dict[str, Dict[str, Any]],
    failed_models: List[str],
    pending_models: List[str],
) -> Dict[str, Any]:
    completed_models = [model for model in attempted_models if model in results_by_model]
    return {
        "attempted_models": list(attempted_models),
        "completed_models": completed_models,
        "failed_models": list(failed_models),
        "pending_models": list(pending_models),
        "expected_count": len(attempted_models),
        "completed_count": len(completed_models),
        "is_partial": len(completed_models) < len(attempted_models),
    }


async def stage1_collect_responses(
    user_query: str,
    council_models: List[str] = None,
    progress_callback: Callable[[List[Dict[str, Any]], Dict[str, Any]], Awaitable[None]] = None,
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question
        council_models: Optional explicit council model list
        progress_callback: Optional async callback invoked as each model finishes,
            with (ordered partial results, stage1 execution metadata)

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [
        {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    models = council_models or COUNCIL_MODELS
    results_by_model: Dict[str, Dict[str, Any]] = {}
    failed_models: List[str] = []
    pending_models = list(models)

    async def query_one(model: str) -> Tuple[str, Any]:
        response = await query_model(model, messages, max_tokens=STAGE1_MAX_OUTPUT_TOKENS)
        return model, response

    # Query all models in parallel, but surface each result the moment it lands so
    # the UI can show a live per-model race.
    tasks = [asyncio.create_task(query_one(model)) for model in models]
    for task in asyncio.as_completed(tasks):
        model, response = await task
        pending_models = [pending for pending in pending_models if pending != model]
        if response is not None:  # Only include successful responses
            results_by_model[model] = {
                "model": model,
                "response": response.get('content', ''),
                "cost_call": build_cost_call("stage1", "individual_response", model, response),
            }
        else:
            failed_models.append(model)

        if progress_callback is not None:
            await progress_callback(
                _ordered_stage1_results(models, results_by_model),
                build_stage1_execution_metadata(models, results_by_model, failed_models, pending_models),
            )

    return _ordered_stage1_results(models, results_by_model)


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    council_models: List[str] = None,
    progress_callback: Callable[[List[Dict[str, Any]], Dict[str, str], Dict[str, Any]], Awaitable[None]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, Any]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        progress_callback: Optional async callback called as ranking progress changes

    Returns:
        Tuple of (rankings list, label_to_model mapping, execution metadata)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    bounded_responses = []
    review_truncation = {}
    for label, result in zip(labels, stage1_results):
        bounded_text, was_truncated = _bounded_review_text(result.get('response', ''))
        bounded_responses.append(f"Response {label}:\n{bounded_text}")
        review_truncation[f"Response {label}"] = {
            "model": result.get("model"),
            "original_chars": len(result.get('response', '') or ''),
            "review_chars": len(bounded_text),
            "truncated_for_review": was_truncated,
        }

    responses_text = "\n\n".join(bounded_responses)

    expected_ranking_example = "\n".join(
        f"{index}. {label}"
        for index, label in enumerate(label_to_model.keys(), start=1)
    )

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized). Very long responses may be shortened for review runtime, but the full original Stage 1 responses remain stored in the conversation:

{responses_text}

Your task:
1. First, provide the final ranking in the exact format below.
2. Then briefly evaluate each response individually.

IMPORTANT: Your response MUST START with the final ranking formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list every response exactly once from best to worst as a numbered list
- Each line must be: number, period, space, then ONLY the response label
- Use only these labels, exactly once each: {", ".join(label_to_model.keys())}

Template for the required opening:

FINAL RANKING:
{expected_ranking_example}

After the ranking, provide concise notes on what each response does well and poorly. Keep the explanation compact.

Now provide your ranking first, then evaluation:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in retry waves. Each wave runs in parallel,
    # but Stage 2 is not complete until every expected reviewer returns usable content.
    models = council_models or COUNCIL_MODELS
    results_by_model = {}
    attempts_by_model = {model: 0 for model in models}
    attempt_diagnostics = {model: [] for model in models}
    pending_models = list(models)

    async def query_reviewer(model: str) -> Tuple[str, Any, Any]:
        attempts_by_model[model] += 1
        attempt_number = attempts_by_model[model]
        detailed = await query_model_detailed(
            model,
            messages,
            timeout=STAGE2_MODEL_TIMEOUT_SECONDS,
            max_tokens=STAGE2_MAX_OUTPUT_TOKENS,
        )
        response = detailed.get("response")
        diagnostic = detailed.get("diagnostic")
        if diagnostic:
            diagnostic = {
                **diagnostic,
                "attempt": attempt_number,
                "stage": "stage2",
                "call_type": "peer_ranking",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        return model, response, diagnostic

    for _ in range(STAGE2_MAX_ATTEMPTS):
        if not pending_models:
            break

        tasks = [asyncio.create_task(query_reviewer(model)) for model in pending_models]
        for task in asyncio.as_completed(tasks):
            model, response, diagnostic = await task
            if diagnostic:
                attempt_diagnostics[model].append(diagnostic)
            if response is not None and response.get('content'):
                full_text = response.get('content', '')
                parsed = parse_ranking_from_text(full_text)
                validation = validate_peer_ranking(parsed, label_to_model)
                results_by_model[model] = {
                    "model": model,
                    "ranking": full_text,
                    "parsed_ranking": parsed,
                    "ranking_valid": validation["valid"],
                    "ranking_issues": validation["issues"],
                    "cost_call": build_cost_call("stage2", "peer_ranking", model, response),
                }
                if validation["valid"]:
                    pending_models = [pending for pending in pending_models if pending != model]
                else:
                    attempt_diagnostics[model].append({
                        "requested_model": model,
                        "provider_source": response.get("provider_source", "unknown"),
                        "error_type": "invalid_peer_ranking",
                        "message": "; ".join(validation["issues"]),
                        "timeout_seconds": STAGE2_MODEL_TIMEOUT_SECONDS,
                        "attempt": attempts_by_model[model],
                        "stage": "stage2",
                        "call_type": "peer_ranking",
                        "finish_reason": response.get("finish_reason"),
                        "native_finish_reason": response.get("native_finish_reason"),
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                    })

            if progress_callback is not None:
                await progress_callback(
                    list(results_by_model.values()),
                    label_to_model,
                    build_stage2_execution_metadata(models, list(results_by_model.values()), attempts_by_model, pending_models, attempt_diagnostics, review_truncation),
                )

    execution_metadata = build_stage2_execution_metadata(
        models,
        list(results_by_model.values()),
        attempts_by_model,
        pending_models,
        attempt_diagnostics,
        review_truncation,
    )

    return list(results_by_model.values()), label_to_model, execution_metadata


def build_stage2_execution_metadata(
    attempted_models: List[str],
    stage2_results: List[Dict[str, Any]],
    attempts_by_model: Dict[str, int],
    pending_models: List[str],
    attempt_diagnostics: Dict[str, List[Dict[str, Any]]] = None,
    review_truncation: Dict[str, Dict[str, Any]] = None,
) -> Dict[str, Any]:
    valid_models = [result["model"] for result in stage2_results if result.get("ranking_valid") is not False]
    returned_models = [result["model"] for result in stage2_results]
    invalid_models = [result["model"] for result in stage2_results if result.get("ranking_valid") is False]
    failed_models = [
        model
        for model in attempted_models
        if model not in valid_models and attempts_by_model.get(model, 0) >= STAGE2_MAX_ATTEMPTS
    ]
    diagnostics = attempt_diagnostics or {}
    return {
        "attempted_models": attempted_models,
        "successful_models": valid_models,
        "returned_models": returned_models,
        "invalid_models": invalid_models,
        "pending_models": pending_models,
        "failed_models": failed_models,
        "attempts_by_model": attempts_by_model,
        "attempt_diagnostics": diagnostics,
        "review_truncation": review_truncation or {},
        "latest_diagnostics": {
            model: entries[-1]
            for model, entries in diagnostics.items()
            if entries
        },
        "max_attempts": STAGE2_MAX_ATTEMPTS,
        "timeout_seconds": STAGE2_MODEL_TIMEOUT_SECONDS,
        "expected_rankings_count": len(attempted_models),
        "completed_rankings_count": len(valid_models),
        "returned_rankings_count": len(returned_models),
        "minimum_valid_rankings_to_synthesize": STAGE2_MIN_VALID_RANKINGS_TO_SYNTHESIZE,
        "is_partial": len(valid_models) < len(attempted_models),
    }


def validate_peer_ranking(parsed_ranking: List[str], label_to_model: Dict[str, str]) -> Dict[str, Any]:
    expected = list(label_to_model.keys())
    issues = []
    if len(parsed_ranking) != len(expected):
        issues.append(f"expected {len(expected)} ranked labels, parsed {len(parsed_ranking)}")

    duplicates = sorted({label for label in parsed_ranking if parsed_ranking.count(label) > 1})
    if duplicates:
        issues.append(f"duplicate labels: {', '.join(duplicates)}")

    missing = [label for label in expected if label not in parsed_ranking]
    if missing:
        issues.append(f"missing labels: {', '.join(missing)}")

    extra = [label for label in parsed_ranking if label not in label_to_model]
    if extra:
        issues.append(f"unknown labels: {', '.join(extra)}")

    return {
        "valid": not issues,
        "issues": issues,
        "missing_labels": missing,
        "duplicate_labels": duplicates,
        "unknown_labels": extra,
    }


def format_stage2_incomplete_error(stage2_execution_metadata: Dict[str, Any]) -> str:
    expected = stage2_execution_metadata.get("expected_rankings_count", 0)
    completed = stage2_execution_metadata.get("completed_rankings_count", 0)
    max_attempts = stage2_execution_metadata.get("max_attempts", STAGE2_MAX_ATTEMPTS)
    timeout_seconds = stage2_execution_metadata.get("timeout_seconds", STAGE2_MODEL_TIMEOUT_SECONDS)
    missing_models = stage2_execution_metadata.get("pending_models") or stage2_execution_metadata.get("failed_models") or []
    attempts_by_model = stage2_execution_metadata.get("attempts_by_model") or {}
    latest_diagnostics = stage2_execution_metadata.get("latest_diagnostics") or {}
    missing_list = ", ".join(missing_models) if missing_models else "one or more reviewers"
    attempt_details = ", ".join(
        f"{model}: {attempts_by_model.get(model, 0)}/{max_attempts}"
        for model in missing_models
    )
    details = f" Attempts: {attempt_details}." if attempt_details else ""
    latest_details = "; ".join(
        (
            f"{model}: {latest_diagnostics[model].get('error_type', 'unknown')}"
            f"{' ' + str(latest_diagnostics[model].get('status_code')) if latest_diagnostics[model].get('status_code') else ''}"
            f" from {latest_diagnostics[model].get('provider_source', 'unknown')}"
            f" - {latest_diagnostics[model].get('message', '')}"
        ).strip()
        for model in missing_models
        if model in latest_diagnostics
    )
    latest_text = f" Latest diagnostics: {latest_details}." if latest_details else ""
    return (
        "Stage 2 peer review incomplete. "
        f"Expected {expected} peer ranking{'s' if expected != 1 else ''}; completed {completed}. "
        f"Missing reviewer{'s' if len(missing_models) != 1 else ''} after {max_attempts} attempts "
        f"with a {int(timeout_seconds)}s timeout per attempt: {missing_list}."
        f"{details}{latest_text} Stage 3 synthesis did not run."
    )


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_model: str = None,
    council_models: List[str] = None,
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        chairman_model: Model to use as chairman (defaults to CHAIRMAN_MODEL)
        council_models: List of council models for fallback if chairman fails

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        (
            f"Model: {result['model']}\n"
            f"Ranking valid: {result.get('ranking_valid') is not False}\n"
            f"Issues: {'; '.join(result.get('ranking_issues') or []) or 'none'}\n"
            f"Ranking: {result['ranking']}"
        )
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The valid peer rankings and what they reveal about response quality
- Any invalid or incomplete peer reviews, without treating malformed rankings as reliable votes
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    model = chairman_model or CHAIRMAN_MODEL

    # Query the chairman model — with retry and fallback
    response = None
    attempts = [model]
    cost_calls = []

    # If chairman fails, try any council model as fallback
    fallback_models = [m for m in (council_models or []) if m != model]
    for m in fallback_models[:2]:  # try up to 2 fallbacks
        attempts.append(m)

    for attempt_model in attempts:
        response = await query_model(
            attempt_model,
            messages,
            timeout=180.0,
            max_tokens=STAGE3_MAX_OUTPUT_TOKENS,
        )
        if response and response.get('content'):
            cost_calls.append(build_cost_call("stage3", "synthesis", attempt_model, response))
            return {
                "model": attempt_model,
                "response": response.get('content', ''),
                "used_fallback": attempt_model != model,
                "cost_calls": cost_calls,
            }
        cost_calls.append(build_cost_call("stage3", "synthesis", attempt_model, response, status="failed" if response is None else None))
        print(f"Chairman synthesis failed on {attempt_model}, trying next…")

    # All attempts failed — build a best-effort synthesis from stage1 instead
    if stage1_results:
        best_response = max(stage1_results, key=lambda r: len(r.get('response', '')))
        return {
            "model": f"{model} (fallback: top stage-1 response)",
            "response": (
                "⚠️ Chairman synthesis unavailable. "
                "Showing the top individual response:\n\n"
                + best_response.get('response', '')
            ),
            "used_fallback": True,
            "cost_calls": cost_calls,
        }

    return {
        "model": model,
        "response": "⚠️ Unable to generate synthesis. All council models failed to respond.",
        "used_fallback": True,
        "cost_calls": cost_calls,
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        parsed_ranking = ranking.get('parsed_ranking') or parse_ranking_from_text(ranking.get('ranking', ''))
        if not validate_peer_ranking(parsed_ranking, label_to_model)["valid"]:
            continue

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def improve_user_prompt(user_query: str, model: str) -> str:
    """
    Rewrite a user's draft question to be clearer and more effective for an LLM.

    Args:
        user_query: The user's original draft question.
        model: The OpenRouter model id to use as the enhancer.

    Returns:
        The improved question text, or the original text on failure.
    """
    original = (user_query or "").strip()
    if not original:
        return original

    system_prompt = (
        "You are a prompt editor. Rewrite the user's question so it is clearer, "
        "more specific, and self-contained for a large language model to answer well. "
        "Preserve the user's original intent, meaning, and language. Do not answer the "
        "question, add new requirements they did not imply, or invent facts. Keep it "
        "concise. Return only the rewritten question with no preamble, quotes, or commentary."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": original},
    ]

    response = await query_model(model, messages, timeout=45.0)

    if response is None:
        return original

    improved = (response.get("content") or "").strip()
    improved = improved.strip('"\'')

    if not improved:
        return original

    return improved


def _stage_cost_calls(
    stage_results: List[Dict[str, Any]],
    stage: str,
    call_type: str,
    attempted_models: List[str],
) -> List[Dict[str, Any]]:
    calls = [
        result["cost_call"]
        for result in stage_results
        if isinstance(result, dict) and isinstance(result.get("cost_call"), dict)
    ]
    successful = {call.get("requested_model") for call in calls}
    for model in attempted_models or []:
        if model not in successful:
            calls.append(build_cost_call(stage, call_type, model, None, status="failed"))
    return calls


def collect_council_cost_calls(
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    stage3_result: Dict[str, Any],
    council_models: List[str],
) -> List[Dict[str, Any]]:
    """Return all model-call billing records for one council run."""
    calls = []
    calls.extend(_stage_cost_calls(stage1_results, "stage1", "individual_response", council_models))
    calls.extend(_stage_cost_calls(stage2_results, "stage2", "peer_ranking", council_models))
    calls.extend(stage3_result.get("cost_calls") or [])
    return calls


def build_council_cost_summary(
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    stage3_result: Dict[str, Any],
    council_models: List[str],
) -> Dict[str, Any]:
    return build_cost_summary(
        collect_council_cost_calls(stage1_results, stage2_results, stage3_result, council_models)
    )


async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect individual responses
    council_models = COUNCIL_MODELS
    stage1_results = await stage1_collect_responses(user_query, council_models=council_models)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model, stage2_execution_metadata = await stage2_collect_rankings(
        user_query,
        stage1_results,
        council_models=council_models,
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    if (
        int(stage2_execution_metadata.get("completed_rankings_count") or 0)
        < int(stage2_execution_metadata.get("minimum_valid_rankings_to_synthesize") or STAGE2_MIN_VALID_RANKINGS_TO_SYNTHESIZE)
    ):
        raise RuntimeError(format_stage2_incomplete_error(stage2_execution_metadata))

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        council_models=council_models,
    )
    cost_summary = build_council_cost_summary(
        stage1_results,
        stage2_results,
        stage3_result,
        council_models,
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "stage2_execution": stage2_execution_metadata,
        "cost_summary": cost_summary,
    }
    if stage2_execution_metadata.get("is_partial"):
        metadata["stage2_warning"] = format_stage2_incomplete_error(stage2_execution_metadata)

    return stage1_results, stage2_results, stage3_result, metadata
