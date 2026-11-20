"""What the reviewer reads: the instructions, the threat model and the layer contracts."""

import json

from compose_risk.case import BASELINE_POWERS, CAPITAL, ThreatModel
from compose_risk.verdict import ReviewVerdict

VERDICT_SCHEMA = ReviewVerdict.model_json_schema()

SYSTEM_PROMPT = f"""\
You are a smart contract security reviewer. You review a whole system at once: the protocol under review \
and every contract it depends on.

Reply with one JSON object and nothing else, matching this JSON Schema:
{json.dumps(VERDICT_SCHEMA)}

- verdict: "exploitable" if the system as a whole is exploitable under the threat model, otherwise "not_exploitable".
- root_cause_layer: the layer folder (the part after layers/) that holds the root cause, or an empty string when \
not exploitable.
- propagation_path: the steps the exploit takes, from the root cause to the protocol under review; empty when not \
exploitable.
- explanation: how the exploit works, or why the system is not exploitable."""

INSTRUCTION = """\
Below are the Solidity contracts of a system, grouped by layer. The protocol under review is in \
layers/0-target; the other layers are the contracts it depends on, directly or through each other.

Decide whether the system as a whole is exploitable under the threat model below: whether an attacker with \
exactly those powers can break its property, including through the way the protocol under review is combined \
with the layers it depends on. Judge only against that threat model; risks it excludes do not make the system \
exploitable. If it is exploitable, name the layer folder under layers/ that holds the root cause.

Answer only with the JSON verdict."""


def render_threat_model(threat_model: ThreatModel) -> str:
    """The threat model as the reviewer reads it; identical for both versions of a case."""
    attacker = threat_model.attacker
    sections = [
        ("Attacker", [BASELINE_POWERS[attacker.baseline], CAPITAL[attacker.capital], *attacker.extra_powers]),
        ("Attacker limits", attacker.limits),
        ("Trusted", threat_model.trusted),
        ("Honest parties", threat_model.honest_parties),
        ("Environment", threat_model.environment),
        ("Excluded risks", threat_model.excluded),
    ]
    lines = ["<threat_model>"]
    for title, items in sections:
        if items:
            lines.append(f"{title}:")
            lines.extend(f"- {item}" for item in items)
    lines.append(f"Property: {threat_model.property}")
    lines.append("</threat_model>")
    return "\n".join(lines)


def render_layers(layers: dict[str, str]) -> str:
    """Every layer contract as a `<file path="layers/...">` block, in path order."""
    return "\n\n".join(f'<file path="layers/{path}">\n{source}</file>' for path, source in sorted(layers.items()))


def review_input(threat_model: ThreatModel, layers: dict[str, str]) -> str:
    """The user message for one version of a case."""
    return f"{INSTRUCTION}\n\n{render_threat_model(threat_model)}\n\n{render_layers(layers)}"
