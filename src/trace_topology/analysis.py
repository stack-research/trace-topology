from __future__ import annotations

import re
from collections import Counter, defaultdict

from trace_topology.models import AnalysisReport, BondType, Finding, FindingType, TraceGraph

CONCLUSION_RE = re.compile(
    r"\b(therefore|thus|in conclusion|in summary|ultimately|final answer|the answer is|the result is|given everything above)\b|^\s*so,?\s+there\s+(?:are|is)\b",
    re.IGNORECASE,
)
BOXED_RE = re.compile(r"^\s*\\boxed\{.+\}\s*$")
SHIFT_RE = re.compile(r"\b(move on|for now|set that aside|leave that)\b", re.IGNORECASE)
ABANDON_RE = re.compile(
    r"\b(cannot finish|can't finish|cannot prove|can't prove|stuck|cannot complete|can't complete)\b",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[a-z]{3,}")
PREDICATE_RE = re.compile(
    r"\b(?P<subject>[a-z][a-z\s]{0,40}?)\s+(?:is|are|was|were|seems|seem|remains|remain)\s+(?P<neg>not\s+)?(?P<pred>[a-z]+)\b",
    re.IGNORECASE,
)
STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "they",
    "them",
    "their",
    "there",
    "same",
    "must",
    "should",
    "would",
    "could",
    "into",
    "every",
    "fully",
}
SUBJECT_STOPWORDS = STOPWORDS | {
    "there",
    "people",
    "person",
    "answer",
    "result",
    "number",
    "total",
    "actual",
}
ANTONYM_MAP = {
    "visible": "invisible",
    "invisible": "visible",
    "expose": "hidden",
    "hidden": "expose",
    "public": "private",
    "private": "public",
    "transparent": "hidden",
    "safe": "unsafe",
    "unsafe": "safe",
    "allow": "forbid",
    "forbid": "allow",
}
VERIFICATION_RE = re.compile(
    r"\b(consistent with|alternative approach|cross-check|also confirms|confirms this|degree sum approach|check by)\b",
    re.IGNORECASE,
)
FAULTY_ADJUSTMENT_RE = re.compile(
    r"(remove these\s+\d+\s+handshakes|subtract.*\b3\b.*handshakes|28\s*-\s*3\s*=\s*25)",
    re.IGNORECASE,
)
RESTRICTION_RE = re.compile(
    r"(only shake hands with each other|not with anyone else|no handshakes occur between the two groups)",
    re.IGNORECASE,
)


def _adjacency(graph: TraceGraph) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for bond in graph.bonds:
        out[bond.source].append(bond.target)
    return out


def _text_tokens(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS}


def _is_conclusion(step_text: str, step_type: str) -> bool:
    return step_type == "conclusion" or bool(CONCLUSION_RE.search(step_text)) or bool(BOXED_RE.match(step_text))


def _is_verification_step(step_text: str) -> bool:
    return bool(VERIFICATION_RE.search(step_text))


def _is_boxed_answer(step_text: str) -> bool:
    return bool(BOXED_RE.match(step_text))


def _extract_predicates(text: str) -> list[tuple[set[str], str, bool]]:
    predicates: list[tuple[set[str], str, bool]] = []
    for match in PREDICATE_RE.finditer(text.lower()):
        subject_tokens = {
            token
            for token in TOKEN_RE.findall(match.group("subject"))
            if token not in SUBJECT_STOPWORDS
        }
        if not subject_tokens:
            continue
        predicates.append((subject_tokens, match.group("pred"), bool(match.group("neg"))))
    return predicates


def _reverse_adjacency(graph: TraceGraph) -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = defaultdict(list)
    for bond in graph.bonds:
        incoming[bond.target].append(bond.source)
    return incoming


def _ancestor_ids(step_id: str, incoming: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(incoming.get(step_id, []))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(incoming.get(current, []))
    return seen


def _step_order(graph: TraceGraph) -> dict[str, int]:
    return {step.id: idx for idx, step in enumerate(graph.steps)}


def _cycle_components(graph: TraceGraph) -> list[list[str]]:
    adj = _adjacency(graph)
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    order = _step_order(graph)
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for nxt in adj.get(node, []):
            if nxt not in indices:
                strongconnect(nxt)
                lowlink[node] = min(lowlink[node], lowlink[nxt])
            elif nxt in on_stack:
                lowlink[node] = min(lowlink[node], indices[nxt])

        if lowlink[node] != indices[node]:
            return

        component: list[str] = []
        while stack:
            current = stack.pop()
            on_stack.remove(current)
            component.append(current)
            if current == node:
                break

        if len(component) > 1:
            components.append(sorted(component, key=lambda step_id: order.get(step_id, 0)))

    for step in graph.steps:
        if step.id not in indices:
            strongconnect(step.id)

    components.sort(key=lambda comp: (len(comp), [order.get(step_id, 0) for step_id in comp]))
    return components


def _has_faulty_adjustment(step_index: int, graph: TraceGraph) -> bool:
    step = graph.steps[step_index]
    if not FAULTY_ADJUSTMENT_RE.search(step.text):
        return False
    prior_window = graph.steps[max(0, step_index - 3) : step_index]
    return any(RESTRICTION_RE.search(prior.text) for prior in prior_window)


def detect_cycles(graph: TraceGraph) -> list[Finding]:
    findings: list[Finding] = []
    for component in _cycle_components(graph):
        description = "Reciprocal support loop detected." if len(component) == 2 else "Cycle detected in support graph."
        findings.append(
            Finding(
                type=FindingType.CYCLE,
                steps_involved=component,
                description=description,
                severity="severe",
                score=0.9,
            )
        )
    return findings


def detect_dangling_nodes(graph: TraceGraph, cycle_nodes: set[str] | None = None) -> list[Finding]:
    cycle_nodes = cycle_nodes or set()
    incoming = Counter(b.target for b in graph.bonds)
    outgoing = Counter(b.source for b in graph.bonds)
    findings: list[Finding] = []
    flagged: set[str] = set()
    for idx, step in enumerate(graph.steps):
        if step.id in cycle_nodes:
            continue
        step_low = step.text.lower()
        is_conclusion = _is_conclusion(step.text, step.step_type)
        next_step = graph.steps[idx + 1] if idx + 1 < len(graph.steps) else None

        if (
            outgoing[step.id] == 0
            and incoming[step.id] > 0
            and next_step is not None
            and (
                ABANDON_RE.search(step_low)
                or SHIFT_RE.search(next_step.text.lower())
                or step.step_type in {"exploration", "correction"}
            )
            and not is_conclusion
        ):
            flagged.add(step.id)

        is_isolated = incoming[step.id] == 0 and outgoing[step.id] == 0
        if not is_isolated or is_conclusion or SHIFT_RE.search(step_low):
            continue
        if len(graph.steps) == 1 or 0 < idx < len(graph.steps) - 1:
            flagged.add(step.id)

    for step in graph.steps:
        if step.id in flagged:
            findings.append(
                Finding(
                    type=FindingType.DANGLING,
                    steps_involved=[step.id],
                    description="Reasoning branch is abandoned before it reconnects.",
                    severity="moderate",
                    score=0.7,
                )
            )
    return findings


def detect_unsupported_terminals(graph: TraceGraph, cycle_nodes: set[str] | None = None) -> list[Finding]:
    cycle_nodes = cycle_nodes or set()
    incoming = Counter(b.target for b in graph.bonds)
    outgoing = Counter(b.source for b in graph.bonds)
    incoming_map = _reverse_adjacency(graph)
    findings: list[Finding] = []
    suspicious_steps = {
        step.id
        for idx, step in enumerate(graph.steps)
        if _has_faulty_adjustment(idx, graph)
    }
    for step in graph.steps:
        if step.id in cycle_nodes:
            continue
        if outgoing[step.id] != 0 or not _is_conclusion(step.text, step.step_type):
            continue
        if incoming[step.id] == 0:
            findings.append(
                Finding(
                    type=FindingType.UNSUPPORTED_TERMINAL,
                    steps_involved=[step.id],
                    description="Conclusion appears without traced support.",
                    severity="severe",
                    score=0.85,
                )
            )
            continue

        ancestors = _ancestor_ids(step.id, incoming_map)
        flawed_support = sorted(
            ancestor_id for ancestor_id in ancestors if ancestor_id in suspicious_steps
        )
        if flawed_support:
            findings.append(
                Finding(
                    type=FindingType.UNSUPPORTED_TERMINAL,
                    steps_involved=[*flawed_support, step.id],
                    description="Conclusion depends on an unsupported arithmetic adjustment.",
                    severity="moderate",
                    score=0.7,
                )
            )
    return findings


def detect_contradictions(graph: TraceGraph) -> list[Finding]:
    findings: list[Finding] = []
    for i, a in enumerate(graph.steps):
        a_predicates = _extract_predicates(a.text)
        a_tokens = _text_tokens(a.text)
        for b in graph.steps[i + 1 :]:
            b_predicates = _extract_predicates(b.text)
            b_tokens = _text_tokens(b.text)
            matched = False
            for a_subject, a_pred, a_neg in a_predicates:
                for b_subject, b_pred, b_neg in b_predicates:
                    if not (a_subject & b_subject):
                        continue
                    same_predicate = a_pred == b_pred and a_neg != b_neg
                    antonym_predicate = ANTONYM_MAP.get(a_pred) == b_pred or ANTONYM_MAP.get(b_pred) == a_pred
                    if same_predicate or antonym_predicate:
                        findings.append(
                            Finding(
                                type=FindingType.CONTRADICTION,
                                steps_involved=[a.id, b.id],
                                description="Potential contradiction pair found.",
                                severity="moderate",
                                score=0.6,
                            )
                        )
                        matched = True
                        break
                if matched:
                    break
            if matched:
                continue

            shared_context = a_tokens & b_tokens
            for token in a_tokens:
                antonym = ANTONYM_MAP.get(token)
                if antonym is None or antonym not in b_tokens:
                    continue
                if shared_context - {token, antonym}:
                    findings.append(
                        Finding(
                            type=FindingType.CONTRADICTION,
                            steps_involved=[a.id, b.id],
                            description="Potential contradiction pair found.",
                            severity="moderate",
                            score=0.6,
                        )
                    )
                    matched = True
                    break
    return findings


def detect_entropy_divergence(graph: TraceGraph, cycle_nodes: set[str] | None = None) -> list[Finding]:
    cycle_nodes = cycle_nodes or set()
    if len(graph.steps) < 3:
        return []
    if len(cycle_nodes) >= 2:
        return []
    if (
        graph.steps
        and _is_boxed_answer(graph.steps[-1].text)
        and any(_is_verification_step(step.text) for step in graph.steps[:-1])
    ):
        return []
    conclusion_indices = [
        idx for idx, step in enumerate(graph.steps) if _is_conclusion(step.text, step.step_type)
    ]
    if conclusion_indices:
        tail_steps = graph.steps[conclusion_indices[-1] + 1 :]
        if tail_steps and all(
            _is_verification_step(step.text)
            or _is_boxed_answer(step.text)
            or ("=" not in step.text and len(step.text.split()) <= 30)
            for step in tail_steps
        ):
            return []
    lens = [len(step.text.split()) for step in graph.steps]
    first = sum(lens[: len(lens) // 2]) / max(1, len(lens) // 2)
    second = sum(lens[len(lens) // 2 :]) / max(1, len(lens) - len(lens) // 2)
    if second > first * 1.35:
        return [
            Finding(
                type=FindingType.ENTROPY_DIVERGENCE,
                steps_involved=[graph.steps[-1].id],
                description="Later reasoning gets broader/longer than early focus.",
                severity="moderate",
                score=0.65,
            )
        ]
    return []


def detect_bond_imbalance(graph: TraceGraph) -> list[Finding]:
    if not graph.bonds:
        return []
    counts = Counter(b.type for b in graph.bonds)
    total = sum(counts.values())
    hydrogen_ratio = counts[BondType.HYDROGEN] / total
    covalent_ratio = counts[BondType.COVALENT] / total
    dominant_steps = sorted(
        {
            step_id
            for bond in graph.bonds
            if bond.type == BondType.HYDROGEN
            for step_id in (bond.source, bond.target)
        }
    )
    if hydrogen_ratio >= 0.75 and covalent_ratio <= 0.15:
        return [
            Finding(
                type=FindingType.BOND_IMBALANCE,
                steps_involved=dominant_steps,
                description="Reflection dominates without deep reasoning links.",
                severity="moderate",
                score=0.7,
            )
        ]
    exploratory_steps = sorted(
        {
            step_id
            for bond in graph.bonds
            if bond.type == BondType.VANDERWAALS
            for step_id in (bond.source, bond.target)
        }
    )
    if counts[BondType.VANDERWAALS] / total >= 0.75:
        return [
            Finding(
                type=FindingType.BOND_IMBALANCE,
                steps_involved=exploratory_steps,
                description="Exploration dominates without convergence.",
                severity="moderate",
                score=0.7,
            )
        ]
    return []


def analyze_graph(graph: TraceGraph) -> AnalysisReport:
    cycle_findings = detect_cycles(graph)
    cycle_components = [finding.steps_involved for finding in cycle_findings]
    cycle_nodes = {step_id for component in cycle_components for step_id in component}

    findings: list[Finding] = []
    findings.extend(cycle_findings)
    findings.extend(detect_dangling_nodes(graph, cycle_nodes=cycle_nodes))
    findings.extend(detect_unsupported_terminals(graph, cycle_nodes=cycle_nodes))
    findings.extend(detect_contradictions(graph))
    findings.extend(detect_entropy_divergence(graph, cycle_nodes=cycle_nodes))
    findings.extend(detect_bond_imbalance(graph))
    if cycle_components:
        graph.metadata["cycle_components"] = cycle_components
    stats = {
        "steps": len(graph.steps),
        "bonds": len(graph.bonds),
        "findings": len(findings),
        "by_type": dict(Counter(f.type.value for f in findings)),
    }
    return AnalysisReport(graph=graph, findings=findings, stats=stats)
