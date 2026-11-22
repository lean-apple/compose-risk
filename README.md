# compose-risk

compose-risk measures whether AI reviewers can spot risk that only appears when contracts are combined. Each case is a small system rebuilt from a real incident and split into layers by distance from the protocol under review. The cases are built so that no layer shows the risk when read alone: it appears through the way the layers depend on each other.

## How it works

A case comes in two versions: a vulnerable one with an exploit that proves the risk, and a fixed one that differs in one file and against which the same exploit fails. Its expected verdict, `not_exploitable`, is a judgment that no attack within the threat model breaks the case's property; the failing exploit supports that judgment but does not prove it. The model reviews all layers at once, under the stated threat model, and returns a verdict with the layer that holds the root cause. The root cause is defined as the layer of the file the fix changes, so a diagnosis that blames another layer scores as wrong even when it is defensible. Scores are compared against the case's expected answer and against baselines that ignore the code.

## Cases

| Case | Incident | Root cause |
| --- | --- | --- |
| [`2025-06-26-resupplyfi`](cases/solidity/2025-06-26-resupplyfi) | ResupplyFi crvUSD/wstUSR market, June 2025 | an oracle passes an unbounded vault share price to a pair that divides 1e36 by it, one layer below the pair |
| [`2026-04-18-kelpdao-aave`](cases/solidity/2026-04-18-kelpdao-aave) | KelpDAO rsETH bridge, April 2026 | one verifier is enough to deliver a message, two layers below the lending pool |

## Usage

Each version compiles on its own. Run its exploit with [Foundry](https://getfoundry.sh/):

```
FOUNDRY_SRC=cases/solidity/2026-04-18-kelpdao-aave/vulnerable/layers FOUNDRY_TEST=cases/solidity/2026-04-18-kelpdao-aave/vulnerable/exploit forge test
```

Check the cases, the review input and the scoring with [uv](https://docs.astral.sh/uv/):

```
uv run pytest
uv run mypy
```

Run the eval with [Inspect](https://inspect.aisi.org.uk/), through the local [Claude Code](https://claude.com/claude-code) login or the Anthropic API (`ANTHROPIC_API_KEY` in `.env`, or `ANTHROPIC_AUTH_TOKEN` set to the token of an `ant auth login`):

```
uv run inspect eval src/compose_risk/task.py --model claude-code/sonnet
uv run inspect eval src/compose_risk/task.py --model anthropic/claude-sonnet-5-5 -T cases=2026-04-18-kelpdao-aave
uv run inspect view
```

## Results

The logs of each run are in `results/<date>/`; open them with `uv run inspect view --log-dir results/<date>`.

On 2026-11-21, each model reviewed both versions of `2026-04-18-kelpdao-aave` over three epochs, called through the Anthropic API with Inspect's default settings. Every model gives the right verdict on every sample and places the root cause in `2-upstream` on every epoch of the vulnerable version, with no refusals. A reviewer that always answers "exploitable" gets 3 of the 6 verdicts.

| Model | Verdict | Root-cause layer | Output tokens | Of which reasoning | Time |
| --- | --- | --- | --- | --- | --- |
| `claude-haiku-5-5` | 6/6 | 3/3 | 7,802 | 5,043 | 11 s |
| `claude-sonnet-5-5` | 6/6 | 3/3 | 4,355 | 1,605 | 10 s |
| `claude-opus-5-5` | 6/6 | 3/3 | 3,454 | 624 | 8 s |
| `claude-fable-5-2` | 6/6 | 3/3 | 6,074 | 2,880 | 15 s |

Every model solves the pair: it flags the vulnerable version and clears the fixed one in the same epoch, which a reviewer that always answers "exploitable" never does. All four read the same 25,398 input tokens. Haiku uses the most output tokens and Opus the fewest, and the gap is reasoning: Haiku spends eight times as many reasoning tokens as Opus, while the rest of the output stays between 2,750 and 3,194 tokens for every model. With one case and six samples per model, these numbers show that the eval works end to end; they do not rank the models.

Each model also reviewed both versions of `2025-06-26-resupplyfi` over three epochs through the Anthropic API.

| Model | Verdict | Root-cause layer | Refused | Output tokens | Of which reasoning | Time |
| --- | --- | --- | --- | --- | --- | --- |
| `claude-haiku-5-5` | 6/6 | 0/3 | 0/6 | 93,338 | 90,664 | 1 min 59 s |
| `claude-sonnet-5-5` | 6/6 | 0/3 | 0/6 | 26,188 | 22,823 | 1 min 1 s |
| `claude-opus-5-5` | 5/5 | 0/2 | 1/6 | 10,485 | 7,564 | 22 s |
| `claude-fable-5-2` | 2/2 | | 4/6 | 11,212 | 10,175 | 1 min 4 s |

All completed reviews give the correct verdict. Haiku and Sonnet locate the root cause in the vault, and Opus in the pair; none selects the expected oracle layer. They identify the zero-rate mechanism, but several proposed attacks contain arithmetic or token-handling errors. API-reported refusals are excluded from accuracy.

## Limitations

The scorer checks only the verdict and the root-cause layer. The model's explanation and propagation path are kept in the logs but not graded, so a right verdict reached for the wrong reason still scores. The cases are small and rebuilt from public incidents, so a right answer may come from recognizing the incident or from spotting the one changed value rather than from reasoning across layers; the results do not yet separate these.

## License

Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE) or [MIT license](LICENSE-MIT), at your option.

## References

* [Inspect](https://inspect.aisi.org.uk/), the evaluation framework the reviews run on.
* [AgentDojo](https://github.com/ethz-spylab/agentdojo), for separating attacks, goals and injection points.
* [SCONE-bench](https://github.com/safety-research/SCONE-bench) and [EVMbench](https://github.com/paradigmxyz/evmbench), for exploit-verified smart contract benchmarks.
* [DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs), for reproductions of real incidents.
