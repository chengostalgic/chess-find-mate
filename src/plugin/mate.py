"""Bounded python-chess search; emit a strategy certificate, never trust a PV alone."""

import re
from dataclasses import dataclass
from pathlib import Path

import chess

from contract import (
    LineInput,
    LineOutput,
    LineStep,
    MateInput,
    MateOutput,
    MateStatus,
    ProofEdge,
    ProofNode,
    ProofReason,
    Side,
)

SEARCH_LIMIT = 50000
PROOF_LIMIT = 4096


def load(fen):
    if not isinstance(fen, str) or len(fen) > 200 or len(fen.split()) != 6:
        raise ValueError("supply a complete six-field standard FEN of at most 200 characters")
    _, _, flags, _, half, full = fen.split()
    if flags != "-" and not re.fullmatch(r"K?Q?k?q?", flags):
        raise ValueError("use ordered standard KQkq castling flags")
    if not re.fullmatch(r"[0-9]{1,7}", half) or not re.fullmatch(r"[0-9]{1,7}", full):
        raise ValueError("invalid FEN move counters")
    if not 0 <= int(half) <= 1000000 or not 1 <= int(full) <= 1000000:
        raise ValueError("FEN move counters outside supported bounds")
    board = chess.Board(fen, chess960=False)
    if not board.is_valid():
        raise ValueError("invalid standard-chess starting position: " + str(board.status()))
    if board.ep_square is not None and board.halfmove_clock != 0:
        raise ValueError("a preceding double pawn push resets the halfmove clock")
    return board


def step(move, board):
    return LineStep(move, board.fen(en_passant="fen"), board.is_check(), board.is_checkmate())


def check_mate_line(value: LineInput, workspace: Path) -> LineOutput:
    board = load(value.fen)
    if len(value.moves) > 12 or any(len(move) > 5 for move in value.moves):
        raise ValueError("line checks support at most 12 UCI moves, each at most five characters")
    attacker, steps, illegal = board.turn, [], None
    for index, text in enumerate(value.moves):
        if board.is_insufficient_material():
            illegal = index
            break
        try:
            move = chess.Move.from_uci(text)
        except ValueError:
            illegal = index
            break
        if move not in board.legal_moves:
            illegal = index
            break
        board.push(move)
        steps.append(step(text, board))
    legal = illegal is None
    mate = legal and board.is_checkmate()
    winner = (Side.BLACK if board.turn == chess.WHITE else Side.WHITE) if mate else None
    return LineOutput(
        value,
        legal,
        illegal,
        steps,
        board.fen(en_passant="fen"),
        mate,
        winner,
        bool(mate and value.moves and board.turn != attacker),
    )


@dataclass
class Branch:
    winning: bool
    reason: ProofReason
    children: list


def find_forced_mate(value: MateInput, workspace: Path) -> MateOutput:
    board = load(value.fen)
    if type(value.max_moves) is not int or not 1 <= value.max_moves <= 3:
        raise ValueError("max_moves must be 1, 2, or 3 attacker moves")
    attacker, visited = board.turn, 0

    def search(remaining):
        nonlocal visited
        visited += 1
        if visited > SEARCH_LIMIT:
            raise ValueError("undecided: search exceeded 50000 positions; reduce the mate bound or simplify the puzzle")
        moves = list(board.legal_moves)
        if not moves:
            if board.is_check():
                return Branch(board.turn != attacker, ProofReason.CHECKMATE, [])
            return Branch(False, ProofReason.STALEMATE, [])
        if board.is_insufficient_material():
            return Branch(False, ProofReason.INSUFFICIENT_MATERIAL, [])
        if remaining == 0:
            return Branch(False, ProofReason.HORIZON, [])
        attacking = board.turn == attacker
        moves.sort(key=lambda move: (not board.gives_check(move), move.uci()))
        children = []
        for move in moves:
            board.push(move)
            result = search(remaining - 1)
            board.pop()
            item = (move.uci(), result)
            if result.winning == attacking:
                return Branch(attacking, ProofReason.BRANCH, [item])
            children.append(item)
        return Branch(not attacking, ProofReason.BRANCH, children)

    # Earlier winning certificates remain valid within a larger requested bound.
    # Only the last (full-depth) failure certificate can establish a negative result.
    result = None
    for depth in range(1, 2 * value.max_moves, 2):
        result = search(depth)
        if result.winning:
            break
    proof = []

    def flatten(node):
        if len(proof) >= PROOF_LIMIT:
            raise ValueError("undecided: proof exceeds 4096 nodes; reduce the requested mate bound")
        index = len(proof)
        record = ProofNode(node.winning, node.reason, [])
        proof.append(record)
        for move, child in node.children:
            record.children.append(ProofEdge(move, flatten(child)))
        return index

    flatten(result)
    line = []
    cursor = result
    if result.winning:
        while cursor.children:
            move, cursor = cursor.children[0]
            board.push_uci(move)
            line.append(step(move, board))
    return MateOutput(
        value,
        MateStatus.FORCED_MATE if result.winning else MateStatus.NO_FORCED_MATE,
        result.children[0][0] if result.winning else None,
        line,
        proof,
    )
