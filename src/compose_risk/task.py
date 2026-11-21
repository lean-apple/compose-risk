"""The eval: every version of every case, all layers reviewed at once, scored against its `case.json`."""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ChatMessageSystem, ResponseSchema
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import JSONSchema

from compose_risk.case import CASES_DIR, find_version_dirs, load_case
from compose_risk.prepare import read_layers
from compose_risk.prompt import SYSTEM_PROMPT, VERDICT_SCHEMA, review_input
from compose_risk.scorer import verdict_scorer

RESPONSE_SCHEMA = ResponseSchema(
    name="review_verdict",
    json_schema=JSONSchema.model_validate(VERDICT_SCHEMA),
    description="The reviewer's verdict for the whole system.",
)


def version_sample(version_dir: Path) -> Sample:
    """One sample per version; only its stripped layer contracts and the threat model reach the input.

    The validated `case.json` is stored with the sample, so a saved log is scored against the expected answer it
    was run with, even if the case changes later.
    """
    case = load_case(version_dir)
    return Sample(
        id=f"{case.id}/{case.variant}",
        input=review_input(case.threat_model, read_layers(version_dir)),
        target=case.expected_verdict,
        metadata={"case_id": case.id, "variant": case.variant, "expected": case.model_dump(mode="json")},
    )


@solver
def review_all_layers() -> Solver:
    """The reviewer sees every layer in one prompt and answers with one verdict."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.messages.insert(0, ChatMessageSystem(content=SYSTEM_PROMPT))
        return await generate(state, response_schema=RESPONSE_SCHEMA)

    return solve


@task
def compose_risk(cases: str | list[str] | None = None) -> Task:
    """Does the reviewer give the right verdict and root-cause layer?

    `cases` filters by case id: a list, or ids separated by commas. `-T cases=a,b` on the command line gives a list.
    """
    version_dirs = find_version_dirs(CASES_DIR)
    if cases is not None:
        wanted = set(cases.split(",") if isinstance(cases, str) else cases)
        unknown = wanted - {d.parent.name for d in version_dirs}
        if unknown:
            raise ValueError(f"unknown case(s): {', '.join(sorted(unknown))}")
        version_dirs = [d for d in version_dirs if d.parent.name in wanted]
    samples = [version_sample(d) for d in version_dirs]
    return Task(
        dataset=MemoryDataset(samples, name="compose-risk"), solver=review_all_layers(), scorer=verdict_scorer()
    )
