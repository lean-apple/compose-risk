# compose-risk

compose-risk asks whether an AI reviewer can find a risk that only appears when contracts are combined. Each case is a small system rebuilt from a real incident, and the cases focus on mismatches between what one contract assumes and another guarantees. The reviewer reads the whole system and has to say whether it can be attacked, and where the problem starts.

## How a case is built

Each system is split into layers by distance from the protocol under review: `0-target` is the protocol itself, `1-upstream` is what it calls directly, and `2-upstream` is one step further. Each layer can be correct on its own terms. In ResupplyFi the vault redeems shares at their fair value and the oracle reports exactly that value, but the lending pair assumes the price stays small enough to divide 1e36 by it, and nothing between them guarantees that.

Every case comes in two versions that differ in exactly one file. In the vulnerable version an exploit test shows that the attack works, and the expected verdict is `exploitable`. In the fixed version the same exploit fails, and the expected verdict is `not_exploitable`, meaning a judgment that no attack within the threat model works rather than as a proof. Both versions share a threat model that says what the attacker can do, what is trusted, and what property must hold.

## How a review is scored

The model sees all layers and the threat model in one prompt, and answers with a verdict and the layer it thinks holds the root cause. The verdict is scored on both versions and the root-cause layer on the vulnerable one. A reviewer that always answers `exploitable` already gets half the verdicts, so what matters is whether it flags the vulnerable version and clears the fixed one in the same run. Refusals are counted separately and left out of accuracy.

The expected root-cause layer is the layer of the file the fix changes. This is a convention, not the only reasonable one: in ResupplyFi the fix bounds the oracle, but a check in the pair that rejects a zero exchange rate would close the attack too, so a model that blames the pair is wrong by this rule without being wrong about the mechanism. Perhaps a layer is not the right unit, and the reviewer should name the edge instead: which layer assumes something another layer does not guarantee.

## Cases

| Case | Incident | Root cause |
| --- | --- | --- |
| [`2025-06-26-resupplyfi`](cases/solidity/2025-06-26-resupplyfi) | ResupplyFi crvUSD/wstUSR market, June 2025 | an oracle passes an unbounded vault share price to a lending pair that divides by it (`1-upstream`) |
| [`2026-04-18-kelpdao-aave`](cases/solidity/2026-04-18-kelpdao-aave) | KelpDAO rsETH bridge, April 2026 | a single verifier is enough to deliver a bridge message (`2-upstream`) |

## Results

Four models reviewed both versions of each case three times (three epochs), through the Anthropic API. The logs are in `results/`.

### KelpDAO

| Model | Verdict | Root-cause layer | Output tokens | Of which reasoning | Time |
| --- | --- | --- | --- | --- | --- |
| `claude-haiku-5-5` | 6/6 | 3/3 | 7,802 | 5,043 | 11 s |
| `claude-sonnet-5-5` | 6/6 | 3/3 | 4,355 | 1,605 | 10 s |
| `claude-opus-5-5` | 6/6 | 3/3 | 3,454 | 624 | 8 s |
| `claude-fable-5-2` | 6/6 | 3/3 | 6,074 | 2,880 | 15 s |

Every model gives the correct verdict on every review and the expected root-cause layer on every vulnerable one, with no refusals. All four read the same 25,398 input tokens. Haiku spends the most reasoning tokens and Opus the fewest, while the rest of the output is about the same size for every model.

### ResupplyFi

| Model | Verdict | Root-cause layer | Refused | Output tokens | Of which reasoning | Time |
| --- | --- | --- | --- | --- | --- | --- |
| `claude-haiku-5-5` | 6/6 | 0/3 | 0/6 | 93,338 | 90,664 | 1 min 59 s |
| `claude-sonnet-5-5` | 6/6 | 0/3 | 0/6 | 26,188 | 22,823 | 1 min 1 s |
| `claude-opus-5-5` | 5/5 | 0/2 | 1/6 | 10,485 | 7,564 | 22 s |
| `claude-fable-5-2` | 2/2 | | 4/6 | 11,212 | 10,175 | 1 min 4 s |

All completed reviews give the correct verdict. Haiku and Sonnet locate the root cause in the vault, and Opus in the pair. None selects the expected oracle layer. They identify the zero-rate mechanism, but several proposed attacks contain arithmetic or token-handling errors.

### What this shows

All completed reviews give the correct verdict on both cases, but they find the expected root-cause layer only on KelpDAO. On ResupplyFi the risk involves three contracts, and the models blame the vault or the pair rather than the oracle between them. With two cases and six reviews per case per model, these numbers show that the eval works end to end, but they are too few to rank the models.

## Limitations

Only the verdict and the root-cause layer are scored. The model's explanation is kept in the logs but not graded, so a correct verdict reached for the wrong reason still scores. The cases are small and rebuilt from public incidents, so a correct answer may come from recognizing the incident or from spotting the one changed file rather than from reasoning across layers, and the results do not yet separate these.

## Next steps

* Run on more layers. The layer scheme has no fixed depth, so a case can follow a longer chain of dependencies, which shows how far a reviewer traces a risk before it loses it.
* Add risks that come from contracts built on top of the protocol, not only from the ones it depends on.
* Add renamed and reworded variants of each case, to see whether models reason across layers or recognize the incident.
* Grade the explanation, or ask for a working exploit, to check that a correct verdict comes from the right reasoning.

## Run it

Run a version's exploit with [Foundry](https://getfoundry.sh/):

```
FOUNDRY_SRC=cases/solidity/2026-04-18-kelpdao-aave/vulnerable/layers FOUNDRY_TEST=cases/solidity/2026-04-18-kelpdao-aave/vulnerable/exploit forge test
```

Check the cases and the scoring with [uv](https://docs.astral.sh/uv/):

```
uv run pytest
uv run mypy
```

Run the eval with [Inspect](https://inspect.aisi.org.uk/), through the local [Claude Code](https://claude.com/claude-code) login or the Anthropic API (`ANTHROPIC_API_KEY`, or `ANTHROPIC_AUTH_TOKEN` from `ant auth login`):

```
uv run inspect eval src/compose_risk/task.py --model claude-code/sonnet
uv run inspect eval src/compose_risk/task.py --model anthropic/claude-sonnet-5-5 -T cases=2026-04-18-kelpdao-aave
uv run inspect view --log-dir results/2026-11-21
```

## License

Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE) or [MIT license](LICENSE-MIT), at your option.

## References

* [Inspect](https://inspect.aisi.org.uk/), the evaluation framework the reviews run on.
* [AgentDojo](https://github.com/ethz-spylab/agentdojo), for separating attacks, goals and injection points.
* [SCONE-bench](https://github.com/safety-research/SCONE-bench) and [EVMbench](https://github.com/paradigmxyz/evmbench), for exploit-verified smart contract benchmarks.
* [DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs), for reproductions of real incidents.
