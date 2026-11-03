"""Independent standard-chess rules on a 64-square character board.

No third-party chess library, runtime imports, IO, or search is used here.
Historical reachability and repetition/move-count draw adjudication are outside
the mate-puzzle contract. Castling, en passant, and every promotion are included.
"""

import re
from dataclasses import dataclass


def require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass
class Position:
    board: tuple[str, ...]
    turn: str
    rights: str
    ep: int | None
    half: int
    full: int


def side(piece):
    return "w" if piece.isupper() else "b"


def other(color):
    return "b" if color == "w" else "w"


def square(name):
    return ord(name[0]) - ord("a") + 8 * (int(name[1]) - 1)


def name(index):
    return "abcdefgh"[index % 8] + str(1 + index // 8)


def attackers(position, target, color):
    found = []
    tx, ty = target % 8, target // 8
    for index, piece in enumerate(position.board):
        if piece == "." or side(piece) != color:
            continue
        x, y = index % 8, index // 8
        dx, dy = tx - x, ty - y
        kind = piece.lower()
        if kind == "p":
            hits = abs(dx) == 1 and dy == (1 if color == "w" else -1)
        elif kind == "n":
            hits = (abs(dx), abs(dy)) in ((1, 2), (2, 1))
        elif kind == "k":
            hits = max(abs(dx), abs(dy)) == 1
        else:
            diagonal = abs(dx) == abs(dy) and dx != 0
            straight = (dx == 0) != (dy == 0)
            hits = (kind in "bq" and diagonal) or (kind in "rq" and straight)
            if hits:
                sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
                hits = all(
                    position.board[x + sx * i + 8 * (y + sy * i)] == "." for i in range(1, max(abs(dx), abs(dy)))
                )
        if hits:
            found.append(index)
    return found


def checked(position, color=None):
    color = position.turn if color is None else color
    king = "K" if color == "w" else "k"
    return bool(attackers(position, position.board.index(king), other(color)))


def parse(fen):
    require(isinstance(fen, str) and len(fen) <= 200, "FEN must be at most 200 characters")
    fields = fen.split()
    require(len(fields) == 6, "supply all six standard FEN fields")
    placement, turn, rights, ep, half, full = fields
    ranks = placement.split("/")
    require(len(ranks) == 8, "FEN needs eight ranks")
    board = ["."] * 64
    for y, rank in zip(range(7, -1, -1), ranks):
        x, digit = 0, False
        for token in rank:
            if token in "12345678":
                require(not digit, "adjacent FEN empty-square counts are invalid")
                x += int(token)
                digit = True
            else:
                require(token in "PNBRQKpnbrqk" and x < 8, "invalid FEN piece or rank")
                board[x + 8 * y] = token
                x += 1
                digit = False
        require(x == 8, "each FEN rank must contain eight squares")
    require(turn in ("w", "b"), "FEN turn must be w or b")
    require(rights == "-" or bool(re.fullmatch(r"K?Q?k?q?", rights)), "use ordered standard KQkq castling flags")
    require(ep == "-" or bool(re.fullmatch(r"[a-h][36]", ep)), "invalid en-passant square")
    require(
        bool(re.fullmatch(r"[0-9]{1,7}", half)) and bool(re.fullmatch(r"[0-9]{1,7}", full)), "invalid move counters"
    )
    require(0 <= int(half) <= 1000000 and 1 <= int(full) <= 1000000, "FEN move counters outside supported bounds")
    require(board.count("K") == board.count("k") == 1, "exactly one king per side is required")
    for color, pawn in (("w", "P"), ("b", "p")):
        require(
            sum(p != "." and side(p) == color for p in board) <= 16 and board.count(pawn) <= 8,
            "too many pieces or pawns",
        )
    require(all(p.lower() != "p" for p in board[:8] + board[56:]), "pawns cannot occupy the first or eighth rank")
    castling = {"K": (4, "K", 7, "R"), "Q": (4, "K", 0, "R"), "k": (60, "k", 63, "r"), "q": (60, "k", 56, "r")}
    for flag in rights.replace("-", ""):
        king_sq, king, rook_sq, rook = castling[flag]
        require(
            board[king_sq] == king and board[rook_sq] == rook, "castling rights require the original king/rook squares"
        )
    target = None if ep == "-" else square(ep)
    if target is not None:
        step = 8 if turn == "w" else -8
        require(target // 8 == (5 if turn == "w" else 2), "en-passant rank contradicts side to move")
        require(
            board[target] == board[target + step] == "." and board[target - step] == ("p" if turn == "w" else "P"),
            "en-passant field requires the preceding double pawn push",
        )
        require(int(half) == 0, "a preceding double pawn push resets the halfmove clock")
    result = Position(tuple(board), turn, rights.replace("-", ""), target, int(half), int(full))
    require(not checked(result, other(turn)), "the side that just moved cannot have left its own king in check")
    require(
        len(attackers(result, board.index("K" if turn == "w" else "k"), other(turn))) <= 2,
        "more than two simultaneous checkers is not a legal starting position",
    )
    return result


def fen(position):
    ranks = []
    for y in range(7, -1, -1):
        row, empty = "", 0
        for piece in position.board[8 * y : 8 * y + 8]:
            if piece == ".":
                empty += 1
            else:
                row += (str(empty) if empty else "") + piece
                empty = 0
        ranks.append(row + (str(empty) if empty else ""))
    return " ".join(
        (
            "/".join(ranks),
            position.turn,
            position.rights or "-",
            "-" if position.ep is None else name(position.ep),
            str(position.half),
            str(position.full),
        )
    )


def push(position, move):
    start, end = square(move[:2]), square(move[2:4])
    board = list(position.board)
    piece, captured = board[start], board[end]
    if piece.lower() == "p" and end == position.ep and captured == "." and start % 8 != end % 8:
        board[end - (8 if position.turn == "w" else -8)] = "."
        captured = "p" if position.turn == "w" else "P"
    board[start], board[end] = ".", piece
    if len(move) == 5:
        board[end] = move[4].upper() if position.turn == "w" else move[4]
    if piece.lower() == "k" and abs(end - start) == 2:
        rook_from, rook_to = (start + 3, start + 1) if end > start else (start - 4, start - 1)
        board[rook_to], board[rook_from] = board[rook_from], "."
    rights = position.rights
    if piece == "K":
        rights = rights.replace("K", "").replace("Q", "")
    if piece == "k":
        rights = rights.replace("k", "").replace("q", "")
    for corner, flag in ((0, "Q"), (7, "K"), (56, "q"), (63, "k")):
        if start == corner or end == corner:
            rights = rights.replace(flag, "")
    ep = (start + end) // 2 if piece.lower() == "p" and abs(end - start) == 16 else None
    half = 0 if piece.lower() == "p" or captured != "." else position.half + 1
    return Position(tuple(board), other(position.turn), rights, ep, half, position.full + (position.turn == "b"))


def candidates(position):
    board, color = position.board, position.turn
    for start, piece in enumerate(board):
        if piece == "." or side(piece) != color:
            continue
        kind, x, y = piece.lower(), start % 8, start // 8

        def emit(end, start=start, kind=kind):
            prefix = name(start) + name(end)
            return [prefix + p for p in "qrbn"] if kind == "p" and end // 8 in (0, 7) else [prefix]

        if kind == "p":
            direction = 1 if color == "w" else -1
            end = start + 8 * direction
            if 0 <= end < 64 and board[end] == ".":
                yield from emit(end)
                if y == (1 if color == "w" else 6) and board[end + 8 * direction] == ".":
                    yield from emit(end + 8 * direction)
            for dx in (-1, 1):
                tx, ty = x + dx, y + direction
                if 0 <= tx < 8 and 0 <= ty < 8:
                    end = tx + 8 * ty
                    target = board[end]
                    if (target != "." and side(target) != color and target.lower() != "k") or end == position.ep:
                        yield from emit(end)
            continue
        if kind in "nk":
            vectors = (
                [(a, b) for a in range(-2, 3) for b in range(-2, 3) if (abs(a), abs(b)) in ((1, 2), (2, 1))]
                if kind == "n"
                else [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]
            )
        else:
            vectors = []
            if kind in "bq":
                vectors += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            if kind in "rq":
                vectors += [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for dx, dy in vectors:
            tx, ty = x + dx, y + dy
            while 0 <= tx < 8 and 0 <= ty < 8:
                end = tx + 8 * ty
                target = board[end]
                if target == "." or (side(target) != color and target.lower() != "k"):
                    yield from emit(end)
                if target != "." or kind in "nk":
                    break
                tx, ty = tx + dx, ty + dy
        if kind == "k" and start == (4 if color == "w" else 60) and not checked(position):
            for flag, delta, rook_sq in (
                ("K" if color == "w" else "k", 2, start + 3),
                ("Q" if color == "w" else "q", -2, start - 4),
            ):
                stride = 1 if delta > 0 else -1
                clear = range(start + stride, rook_sq, stride)
                if (
                    flag in position.rights
                    and all(board[i] == "." for i in clear)
                    and all(not attackers(position, i, other(color)) for i in (start + stride, start + delta))
                ):
                    yield name(start) + name(start + delta)


def legal_moves(position):
    return {
        move: following
        for move in sorted(candidates(position))
        if not checked(following := push(position, move), position.turn)
    }


def insufficient(position):
    material = [(sq, p.lower()) for sq, p in enumerate(position.board) if p != "." and p.lower() != "k"]
    if any(p in "pqr" for _, p in material):
        return False
    if len(material) <= 1:
        return True
    return all(p == "b" for _, p in material) and len({(sq % 8 + sq // 8) % 2 for sq, _ in material}) == 1


def notation(position, move, legal):
    """Standard algebraic notation derived from our own legal moves and attacks."""
    require(move in legal, "notation requires a legal move")
    start, end = square(move[:2]), square(move[2:4])
    piece = position.board[start].upper()
    capture = position.board[end] != "." or (piece == "P" and start % 8 != end % 8)
    if piece == "K" and abs(end - start) == 2:
        text = "O-O" if end > start else "O-O-O"
    else:
        text = "" if piece == "P" else piece
        if piece == "P" and capture:
            text += move[0]
        elif piece != "P":
            rivals = [
                square(candidate[:2])
                for candidate in legal
                if candidate[:2] != move[:2]
                and candidate[2:4] == move[2:4]
                and position.board[square(candidate[:2])].upper() == piece
            ]
            if rivals:
                if all(other % 8 != start % 8 for other in rivals):
                    text += move[0]
                elif all(other // 8 != start // 8 for other in rivals):
                    text += move[1]
                else:
                    text += move[:2]
        text += ("x" if capture else "") + move[2:4]
        if len(move) == 5:
            text += "=" + move[4].upper()
    following = legal[move]
    if checked(following):
        text += "+" if legal_moves(following) else "#"
    return text
