# Cases

Each case is a small system of contracts rebuilt from a real incident, in two versions. `vulnerable/` is exploitable; `fixed/` differs in one file and is not. Each version is reviewed on its own.

In a version, `layers/` holds one folder per contract, numbered by distance from the protocol under review (`0-target`); `exploit/` holds a Foundry test that runs the attack; `case.json` holds the expected verdict, the layer of the root cause and the threat model the review is judged under, which both versions share.
