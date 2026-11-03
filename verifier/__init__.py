"""Audit legal moves, final checkmate, and exhaustive defense/escape certificates."""

from contract import LineOutput, LineStep, MateStatus, ProofReason, Side

from .board import checked, fen, insufficient, legal_moves, parse, require


def verdict(valid, message, **details):
    return {"valid": valid, "score": 1.0 if valid else 0.0, "message": message, "details": details}


def prepare(tool, value):
    require(tool in ("find_forced_mate", "check_mate_line"), "unknown tool")
    initial = parse(value.fen)
    if tool == "find_forced_mate":
        require(type(value.max_moves) is int and 1 <= value.max_moves <= 3, "max_moves must be 1, 2, or 3")
    else:
        require(
            len(value.moves) <= 12 and all(len(move) <= 5 for move in value.moves),
            "line exceeds 12 moves or UCI length",
        )
    return initial


def verify_input(tool, value):
    try:
        prepare(tool, value)
    except ValueError as error:
        return verdict(False, str(error))
    return verdict(True, "well-formed bounded standard-chess mate puzzle input")


def line_step(move, position, legal):
    in_check = checked(position)
    return LineStep(move, fen(position), in_check, in_check and not legal)


def check_line(given, made):
    position = prepare("check_mate_line", given)
    attacker, steps, illegal = position.turn, [], None
    legal = legal_moves(position)
    for index, move in enumerate(given.moves):
        if insufficient(position) or move not in legal:
            illegal = index
            break
        position = legal[move]
        legal = legal_moves(position)
        steps.append(line_step(move, position, legal))
    all_legal = illegal is None
    mate = all_legal and checked(position) and not legal
    winner = (Side.BLACK if position.turn == "w" else Side.WHITE) if mate else None
    expected = LineOutput(
        given,
        all_legal,
        illegal,
        steps,
        fen(position),
        mate,
        winner,
        bool(mate and given.moves and position.turn != attacker),
    )
    require(made == expected, "line legality, first illegal move, position, or final checkmate claim is incorrect")


def check_strategy(given, made):
    initial = prepare("find_forced_mate", given)
    require(made.request == given, "returned request differs from the supplied puzzle")
    require(0 < len(made.proof) <= 4096, "proof must contain 1 to 4096 nodes")
    require(
        sum(len(node.children) for node in made.proof) == len(made.proof) - 1,
        "certificate must be one bounded tree, with exactly one edge per non-root node",
    )
    attacker, seen = initial.turn, set()
    depth = 2 * given.max_moves - 1

    def replay(index, position, remaining):
        require(
            type(index) is int and 0 <= index < len(made.proof) and index not in seen,
            "proof has an unknown, shared, or cyclic node",
        )
        seen.add(index)
        node = made.proof[index]
        legal = legal_moves(position)
        if not legal:
            expected_reason = ProofReason.CHECKMATE if checked(position) else ProofReason.STALEMATE
            expected_win = expected_reason == ProofReason.CHECKMATE and position.turn != attacker
        elif insufficient(position):
            expected_reason, expected_win = ProofReason.INSUFFICIENT_MATERIAL, False
        elif remaining == 0:
            expected_reason, expected_win = ProofReason.HORIZON, False
        else:
            require(node.reason == ProofReason.BRANCH, "nonterminal node needs a branching proof")
            moves = [edge.move for edge in node.children]
            require(
                len(set(moves)) == len(moves) and all(move in legal for move in moves),
                "proof contains duplicate or illegal moves",
            )
            # Existential cases: winning attacker choice or one escaping defense.
            # Universal cases: every attacker attempt fails or every defense loses.
            existential = node.winning == (position.turn == attacker)
            require(
                len(moves) == 1 if existential else set(moves) == set(legal),
                "proof omits a required legal move or supplies the wrong number of choices",
            )
            for edge in node.children:
                require(edge.child > index, "child indices must point forward")
                child_win = replay(edge.child, legal[edge.move], remaining - 1)
                require(child_win == node.winning, "branch does not support its parent's claimed outcome")
            return node.winning
        require(
            node.reason == expected_reason and node.winning == expected_win and not node.children,
            "leaf is not the claimed mate, stalemate, material draw, or exhausted horizon",
        )
        return expected_win

    winning = replay(0, initial, depth)
    require(len(seen) == len(made.proof), "proof includes unreachable extra nodes")
    require(made.status == (MateStatus.FORCED_MATE if winning else MateStatus.NO_FORCED_MATE), "wrong mate outcome")
    if winning:
        require(made.first_move == made.proof[0].children[0].move, "first move differs from the winning strategy")
        line, index, position = [], 0, initial
        while made.proof[index].children:
            edge = made.proof[index].children[0]
            position = legal_moves(position)[edge.move]
            line.append(line_step(edge.move, position, legal_moves(position)))
            index = edge.child
        require(
            line and line[-1].checkmate and made.line == line, "illustrative line is not the certified legal mate line"
        )
    else:
        require(
            made.first_move is None and not made.line, "a negative result cannot advertise a winning move or mate line"
        )


def check_result(tool, given, made):
    if made is None:
        return verdict(False, "missing chess result")
    try:
        if tool == "find_forced_mate":
            check_strategy(given, made)
        elif tool == "check_mate_line":
            check_line(given, made)
        else:
            return verdict(False, "unknown tool")
    except (ValueError, IndexError, KeyError) as error:
        return verdict(False, str(error))
    return verdict(True, "legal moves and mate/escape evidence independently checked", tool=tool)


def verify_output(tool, input_value, output_value, workspace):
    return check_result(tool, input_value, output_value)


def verify_task(task, arguments, output, reference, workspace):
    tools = {"forced-mate": "find_forced_mate", "mate-line": "check_mate_line"}
    return check_result(tools[task], arguments, output) if task in tools else verdict(False, "unknown task")
