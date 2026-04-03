# Artifact Contract

`trace-topology` writes four machine-readable artifact types:

- `parse`
- `graph`
- `analysis`
- `eval`

Each top-level artifact includes:

```json
{
  "artifact_type": "parse|graph|analysis|eval",
  "schema_version": 1
}
```

## Compatibility rule

Schema version `1` is additive-only.

- Adding new fields is allowed.
- Removing fields is not allowed.
- Renaming fields is not allowed.
- Changing nesting is not allowed.

Any removal, rename, or nesting change requires a schema version bump.

## Parse artifact

```json
{
  "artifact_type": "parse",
  "schema_version": 1,
  "transcript_id": "data/samples/synthetic_cycle_trust_0001.txt",
  "steps": [
    {
      "id": "s1",
      "text": "Trustworthy systems should be trusted.",
      "start_char": 0,
      "end_char": 38,
      "step_type": "claim",
      "summary": "Trustworthy systems should be trusted."
    }
  ],
  "stats": {
    "step_count": 1,
    "char_count": 38
  }
}
```

## Graph artifact

```json
{
  "artifact_type": "graph",
  "schema_version": 1,
  "transcript_id": "data/samples/synthetic_cycle_trust_0001.txt",
  "steps": [],
  "bonds": [
    {
      "source": "s1",
      "target": "s2",
      "type": "covalent",
      "confidence": 0.8,
      "reason": "logical-marker"
    }
  ],
  "metadata": {
    "bond_counts": {
      "covalent": 1
    }
  }
}
```

## Analysis artifact

```json
{
  "artifact_type": "analysis",
  "schema_version": 1,
  "graph": {
    "transcript_id": "data/samples/synthetic_cycle_trust_0001.txt",
    "steps": [],
    "bonds": [],
    "metadata": {}
  },
  "findings": [
    {
      "type": "cycle",
      "steps_involved": ["s1", "s2"],
      "description": "Cycle detected among reasoning steps.",
      "severity": "high",
      "score": 0.9
    }
  ],
  "stats": {
    "step_count": 2,
    "bond_count": 2
  }
}
```

The nested `graph` object keeps the same shape as the standalone graph payload, without its own top-level artifact header.

## Eval artifact

```json
{
  "artifact_type": "eval",
  "schema_version": 1,
  "results": [
    {
      "transcript_file": "synthetic_cycle_trust_0001.txt",
      "step_count_delta": 0,
      "bond_precision": 1.0,
      "bond_recall": 1.0,
      "finding_precision": 1.0,
      "finding_recall": 1.0
    }
  ],
  "summary": {
    "count": 1,
    "avg_step_count_delta": 0.0,
    "avg_bond_precision": 1.0,
    "avg_bond_recall": 1.0,
    "avg_finding_precision": 1.0,
    "avg_finding_recall": 1.0
  }
}
```
