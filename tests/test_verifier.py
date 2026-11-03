"""Certificates, move legality, final checkmate, and attacks against proof completeness."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import LineInput, LineOutput, MateInput, MateStatus, ProofEdge, ProofNode, ProofReason, Side
from plugin import check_mate_line, find_forced_mate

CASES = Path(__file__).parent / "cases"


def fixture(name):
    given = json.loads((CASES / (name + ".input.json")).read_text())
    expected = json.loads((CASES / (name + ".expected.json")).read_text())
    task = expected["task"]
    return build_output(given, MateInput if task == "forced-mate" else LineInput), expected


def result(name, tmp_path):
    given, expected = fixture(name)
    return given, (find_forced_mate if expected["task"] == "forced-mate" else check_mate_line)(given, tmp_path)


@pytest.mark.parametrize("path", sorted(CASES.glob("*.input.json")), ids=lambda p: p.stem)
def test_declared_puzzle_and_line_examples(path, tmp_path):
    given, expected = fixture(path.name.removesuffix(".input.json"))
    original = copy.deepcopy(given)
    tool = "find_forced_mate" if expected["task"] == "forced-mate" else "check_mate_line"
    made = (find_forced_mate if tool == "find_forced_mate" else check_mate_line)(given, tmp_path)
    raw = plain_output(made)
    for key, value in expected.items():
        if key != "task":
            assert (len(raw["line"]) if key == "line_length" else raw[key]) == value
    assert verifier.verify_input(tool, given)["valid"]
    assert verifier.verify_output(tool, given, made, "")["valid"]
    assert verifier.verify_task(expected["task"], given, made, None, "")["valid"]
    assert given == original and not list(tmp_path.iterdir())


@pytest.mark.parametrize("field", ["request", "status", "first_move", "line", "proof"])
def test_every_mate_result_field_is_checked(field, tmp_path):
    given, made = result("mate-one", tmp_path)
    wrong = {
        "request": replace(given, max_moves=2),
        "status": MateStatus.NO_FORCED_MATE,
        "first_move": "g6h6",
        "line": [],
        "proof": [],
    }
    assert not verifier.verify_task("forced-mate", given, replace(made, **{field: wrong[field]}), None, "")["valid"]


@pytest.mark.parametrize("field", ["move", "fen", "in_check", "checkmate"])
def test_every_illustrative_position_field_is_checked(field, tmp_path):
    given, made = result("mate-one", tmp_path)
    wrong = {"move": "g6h6", "fen": given.fen, "in_check": False, "checkmate": False}
    bad = replace(made.line[0], **{field: wrong[field]})
    assert not verifier.verify_task("forced-mate", given, replace(made, line=[bad]), None, "")["valid"]


@pytest.mark.parametrize(
    "mutation",
    [
        "omit_defense",
        "illegal_edge",
        "cycle",
        "shared",
        "extra_node",
        "fake_mate",
        "fake_stalemate",
        "fake_horizon",
        "flip_winner",
    ],
)
def test_strategy_forgery_fails(mutation, tmp_path):
    given, made = result("mate-three", tmp_path)
    proof = copy.deepcopy(made.proof)
    if mutation == "omit_defense":
        index = next(i for i, node in enumerate(proof) if len(node.children) > 1)
        proof[index].children.pop()
    elif mutation == "illegal_edge":
        proof[0].children[0] = replace(proof[0].children[0], move="a1a8")
    elif mutation == "cycle":
        proof[0].children[0] = replace(proof[0].children[0], child=0)
    elif mutation == "shared":
        index = next(i for i, node in enumerate(proof) if len(node.children) > 1)
        proof[index].children[1] = replace(proof[index].children[1], child=proof[index].children[0].child)
    elif mutation == "extra_node":
        proof.append(copy.deepcopy(proof[-1]))
    elif mutation.startswith("fake_"):
        proof[0] = ProofNode(
            True,
            {
                "fake_mate": ProofReason.CHECKMATE,
                "fake_stalemate": ProofReason.STALEMATE,
                "fake_horizon": ProofReason.HORIZON,
            }[mutation],
            [],
        )
    else:
        proof[-1].winning = False
    assert not verifier.verify_task("forced-mate", given, replace(made, proof=proof), None, "")["valid"]


def test_no_mate_requires_every_attacker_move_to_fail(tmp_path):
    given, made = result("starting-no-mate", tmp_path)
    assert len(made.proof[0].children) == 20
    proof = copy.deepcopy(made.proof)
    proof[0].children.pop()
    assert not verifier.verify_task("forced-mate", given, replace(made, proof=proof), None, "")["valid"]
    forged = replace(made, status=MateStatus.FORCED_MATE, first_move="e2e4")
    assert not verifier.verify_task("forced-mate", given, forged, None, "")["valid"]


def test_an_alternative_valid_winning_move_is_accepted(tmp_path):
    given, made = result("promotion-mate", tmp_path)
    # Rook promotion is a different valid mate from the solver's queen promotion.
    move = "f7f8r"
    line = check_mate_line(LineInput(given.fen, [move]), tmp_path)
    assert line.is_mating_line and made.first_move != move
    alternative = replace(
        made,
        first_move=move,
        line=line.steps,
        proof=[ProofNode(True, ProofReason.BRANCH, [ProofEdge(move, 1)]), ProofNode(True, ProofReason.CHECKMATE, [])],
    )
    assert verifier.verify_task("forced-mate", given, alternative, None, "")["valid"]


def test_one_mating_line_does_not_replace_all_defenses(tmp_path):
    given, made = result("mate-three", tmp_path)
    checked = check_mate_line(LineInput(given.fen, [s.move for s in made.line]), tmp_path)
    assert checked.legal and checked.is_mating_line
    # Keep just the illustrative line. It ends in mate but omits alternative defenses.
    proof = [ProofNode(True, ProofReason.BRANCH, [ProofEdge(s.move, i + 1)]) for i, s in enumerate(made.line)]
    proof.append(ProofNode(True, ProofReason.CHECKMATE, []))
    assert not verifier.verify_task("forced-mate", given, replace(made, proof=proof), None, "")["valid"]


@pytest.mark.parametrize(
    "field",
    ["request", "legal", "first_illegal_index", "steps", "final_fen", "ends_in_checkmate", "winner", "is_mating_line"],
)
def test_every_line_result_field_is_checked(field, tmp_path):
    given, made = result("line-mate", tmp_path)
    wrong = {
        "request": replace(given, moves=[]),
        "legal": False,
        "first_illegal_index": 0,
        "steps": [],
        "final_fen": given.fen,
        "ends_in_checkmate": False,
        "winner": Side.BLACK,
        "is_mating_line": False,
    }
    assert not verifier.verify_task("mate-line", given, replace(made, **{field: wrong[field]}), None, "")["valid"]


@pytest.mark.parametrize(
    "fen",
    [
        "8/8/8/8/8/8/8/8 w - - 0 1",
        "7k/8/8/8/8/8/4k3/4K3 w - - 0 1",
        "7k/8/8/8/8/8/8/P3K3 w - - 0 1",
        "k7/8/8/8/8/8/8/R3K3 w - - 0 1",
        "7k/8/8/8/8/8/8/4K3 w K - 0 1",
        "7k/8/8/8/8/8/8/4K3 w - a6 0 1",
        "7k/8/8/8/8/8/8/4K3 x - - 0 1",
        "7k/8/8/8/8/8/8/4K3 w - - -1 1",
        "7k/8/8/8/8/8/8/4K3 w - - 0 0",
        "7k/8/8/8/8/8/8/4K3 w - -",
        "7k/8/8/8/8/8/8/4K3 w - - 1000001 1",
    ],
)
def test_invalid_starting_fens(fen, tmp_path):
    given = MateInput(fen, 1)
    assert not verifier.verify_input("find_forced_mate", given)["valid"]
    with pytest.raises(ValueError):
        find_forced_mate(given, tmp_path)


@pytest.mark.parametrize("bound", [0, 4, -1, True])
def test_invalid_depth_bounds(bound, tmp_path):
    given, _ = fixture("mate-one")
    given = replace(given, max_moves=bound)
    assert not verifier.verify_input("find_forced_mate", given)["valid"]
    with pytest.raises(ValueError):
        find_forced_mate(given, tmp_path)


def test_line_limits_and_missing_output(tmp_path):
    given, _ = fixture("line-mate")
    for bad in [replace(given, moves=["g6g7"] * 13), replace(given, moves=["far too long"])]:
        assert not verifier.verify_input("check_mate_line", bad)["valid"]
        with pytest.raises(ValueError):
            check_mate_line(bad, tmp_path)
    assert not verifier.verify_task("mate-line", given, None, None, "")["valid"]
    assert not verifier.verify_input("unknown", given)["valid"]
    assert not verifier.verify_task("unknown", given, None, None, "")["valid"]
    with pytest.raises((ValueError, TypeError)):
        build_output({"fen": given.fen}, MateInput)
    raw = plain_output(check_mate_line(given, tmp_path))
    raw["legal"] = "yes"
    with pytest.raises((ValueError, TypeError)):
        build_output(raw, LineOutput)


def test_search_budget_exhaustion_is_undecided(monkeypatch, tmp_path):
    import plugin.mate as engine

    given, _ = fixture("mate-three")
    monkeypatch.setattr(engine, "SEARCH_LIMIT", 1)
    with pytest.raises(ValueError, match="undecided"):
        find_forced_mate(given, tmp_path)


def test_proof_budget_exhaustion_is_undecided(monkeypatch, tmp_path):
    import plugin.mate as engine

    given, _ = fixture("mate-one")
    monkeypatch.setattr(engine, "PROOF_LIMIT", 1)
    with pytest.raises(ValueError, match="undecided"):
        find_forced_mate(given, tmp_path)
