"""Independent rule engine against known perft counts and python-chess legal playouts."""

import random

import chess
import pytest

import verifier
from contract import LineInput
from plugin import check_mate_line
from verifier.board import checked, fen, insufficient, legal_moves, notation, parse

START = chess.STARTING_FEN
KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
ENDGAME = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"


def perft(position, depth):
    if depth == 0:
        return 1
    return sum(perft(following, depth - 1) for following in legal_moves(position).values())


@pytest.mark.parametrize("start,depth,count", [(START, 3, 8902), (KIWIPETE, 2, 2039), (ENDGAME, 3, 2812)])
def test_known_legal_move_tree_counts(start, depth, count):
    assert perft(parse(start), depth) == count


@pytest.mark.parametrize("start", [START, KIWIPETE, ENDGAME])
def test_240_seeded_playout_positions_and_every_child_fen(start):
    rng = random.Random(480)
    board = chess.Board(start)
    for _ in range(80):
        ours = parse(board.fen(en_passant="fen"))
        legal = legal_moves(ours)
        assert set(legal) == {m.uci() for m in board.legal_moves}
        assert checked(ours) == board.is_check() and insufficient(ours) == board.is_insufficient_material()
        for move, following in legal.items():
            assert notation(ours, move, legal) == board.san(chess.Move.from_uci(move))
            board.push_uci(move)
            assert fen(following) == board.fen(en_passant="fen")
            assert checked(following) == board.is_check()
            board.pop()
        if board.is_game_over() or not legal:
            board = chess.Board(start)
        else:
            board.push_uci(rng.choice(sorted(legal)))


@pytest.mark.parametrize(
    "start,move",
    [
        ("4kr2/8/8/8/8/8/8/4K2R w K - 0 1", "e1g1"),  # through check
        ("4k3/8/8/8/8/8/8/4K2R w - - 0 1", "e1g1"),  # no historical right
        ("k3r3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6"),  # en passant exposes own king
        ("k3r3/8/8/8/8/8/4R3/4K3 w - - 0 1", "e2d2"),  # pinned rook
        ("8/8/8/8/8/4k3/8/4K2R w - - 0 1", "e1e2"),  # adjacent kings
        ("7k/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8"),  # missing promotion choice
    ],
)
def test_illegal_special_and_king_safety_moves(start, move, tmp_path):
    assert chess.Board(start).is_valid()
    assert move not in legal_moves(parse(start))
    given = LineInput(start, [move])
    made = check_mate_line(given, tmp_path)
    assert not made.legal and made.first_illegal_index == 0
    assert verifier.verify_task("mate-line", given, made, None, "")["valid"]


def test_all_promotion_choices_and_castling_rights_updates():
    start = "4k3/P7/8/8/8/8/8/4K3 w - - 0 1"
    legal = legal_moves(parse(start))
    assert {"a7a8q", "a7a8r", "a7a8b", "a7a8n"} <= set(legal)
    for move in legal:
        board = chess.Board(start)
        board.push_uci(move)
        assert fen(legal[move]) == board.fen(en_passant="fen")
    castles = legal_moves(parse("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"))
    assert castles["e1g1"].rights == castles["e1c1"].rights == "kq"
    assert castles["a1a8"].rights == "Kk"
