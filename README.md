# compose-risk

compose-risk measures whether AI reviewers can spot risk that only appears when contracts are combined. Each case is a small system rebuilt from a real incident and split into layers by distance from the protocol under review. Every layer is correct on its own; the exploit only works through the way they depend on each other.

## How it works

A case comes in two versions: a vulnerable one with an exploit that proves the risk, and a fixed one that differs in one file. The model reviews all layers at once, under a stated threat model, and returns a verdict with the layer that holds the root cause. Scores are compared against the case's expected answer and against baselines that ignore the code.

## Cases

| Case | Incident | Root cause |
| --- | --- | --- |
| [`kelpdao-aave-2026`](cases/solidity/kelpdao-aave-2026) | KelpDAO rsETH bridge, April 2026 | one verifier is enough to deliver a message, two layers below the lending pool |

## Usage

Each version compiles on its own. Run its exploit with [Foundry](https://getfoundry.sh/):

```
FOUNDRY_SRC=cases/solidity/kelpdao-aave-2026/vulnerable/layers FOUNDRY_TEST=cases/solidity/kelpdao-aave-2026/vulnerable/exploit forge test
```

Check the cases, the review input and the scoring with [uv](https://docs.astral.sh/uv/):

```
uv run pytest
uv run mypy
```

Run the eval with [Inspect](https://inspect.aisi.org.uk/), through the local [Claude Code](https://claude.com/claude-code) login or the Anthropic API (`ANTHROPIC_API_KEY` in `.env`):

```
uv run inspect eval src/compose_risk/task.py --model claude-code/sonnet
uv run inspect eval src/compose_risk/task.py --model anthropic/claude-sonnet-5-5 -T cases=kelpdao-aave-2026
uv run inspect view
```

## License

Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE) or [MIT license](LICENSE-MIT), at your option.

## References

* [Inspect](https://inspect.aisi.org.uk/), the evaluation framework the reviews run on.
* [AgentDojo](https://github.com/ethz-spylab/agentdojo), for separating attacks, goals and injection points.
* [SCONE-bench](https://github.com/safety-research/SCONE-bench) and [EVMbench](https://github.com/paradigmxyz/evmbench), for exploit-verified smart contract benchmarks.
* [DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs), for reproductions of real incidents.
