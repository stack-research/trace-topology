# First Debug Session

This is the shortest path for a regular developer who sometimes vibe codes with an agent and wants to know what `trace-topology` is good for.

The goal is not to prove the model is wrong in some deep philosophical sense. The goal is to catch a familiar failure mode: the agent talks itself into a fix that the trace does not really support.

One practical note first: you do not need to read the reasoning stream live while it races by. Save it to a plaintext file, then analyze it after the run.

For terminal-based agents, common patterns are:

```bash
your-agent-command 2>&1 | tee transcript.txt
script -q transcript.txt your-agent-command
```

Then run:

```bash
tt analyze transcript.txt
```

## Situation

You asked a coding agent to debug a null pointer after a cache refactor.

The agent wandered a bit, mentioned a queue worker, dropped that branch, and then argued that the cache refactor must be the cause because the bug appeared after it. It ended by recommending a revert.

That kind of trace often feels suspicious, but it is tedious to reread by hand.

## The Sample

This repo includes a small fictional transcript you can run right now:

`data/samples/synthetic_agent_cycle_debug_0001.txt`

Its contents are:

```text
The agent says the null pointer started after the cache refactor.
Maybe the queue worker is involved, but I cannot finish that branch.
I will move on for now.
The cache refactor must be the cause because the bug appeared after it.
Therefore I should revert the cache refactor.
```

## Run It

From the repo root:

```bash
tt analyze data/samples/synthetic_agent_cycle_debug_0001.txt
```

You should see output like:

```text
trace: data/samples/synthetic_agent_cycle_debug_0001.txt

finding-summary: total=1 severe=1 moderate=0 low=0 top=cycle

findings:
  - cycle (severe) steps=s1,s2,s4,s5: Cycle detected in support graph.
```

## What That Means

In plain language:

- the trace is leaning on its own conclusion instead of bringing in new support
- the reasoning closes a loop rather than moving forward
- the agent mentioned another branch, then left it behind without resolving it

In project terms, the main finding here is `cycle`.

That does not prove the cache refactor is innocent. It does prove the trace you have is a weak reason to revert it.

## What You Do Next

A useful response as the developer is:

1. Stop treating the revert recommendation as justified.
2. Reopen the dropped branch and inspect the queue worker or another independent source of evidence.
3. Ask the agent for a narrower trace tied to logs, stack frames, or a failing test instead of broad causal storytelling.

This is the core use case for `trace-topology`: it helps you separate "the model sounds confident" from "the trace actually supports the move it wants to make."

## What to Try After This

- Run `tt analyze` on one of your own saved agent transcripts.
- If the trace is clean but still hard to read, run `tt graph` to inspect the bond layout directly.
- If you are evaluating changes to prompts or agents across many samples, move on to the README sections on JSON artifacts and `tt eval`.
