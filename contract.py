"""Standard-chess mate puzzles and independently replayable AND/OR certificates."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    FIND_FORCED_MATE = "find_forced_mate"
    CHECK_MATE_LINE = "check_mate_line"


class Task(Enum):
    FORCED_MATE = "forced-mate"
    MATE_LINE = "mate-line"


class Side(Enum):
    WHITE = "white"
    BLACK = "black"


class MateStatus(Enum):
    FORCED_MATE = "forced_mate"
    NO_FORCED_MATE = "no_forced_mate_within_bound"


class ProofReason(Enum):
    BRANCH = "branch"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    HORIZON = "horizon"


@dataclass
class MateInput(Output):
    fen: Annotated[
        str,
        "Copy the complete six-field FEN exactly; Python decodes the board. No move calculation is needed to call. "
        "Side to move is the attacker. A diagram alone does not establish historical rights; clarify missing facts.",
    ]
    max_moves: Annotated[
        int,
        "1, 2, or 3 attacker moves: at most 1, 3, or 5 plies. Choose 1 if unspecified. "
        "This is a bounded mate puzzle; repetition and move-count draw adjudications are excluded.",
    ]


@dataclass
class LineStep(Output):
    move: Annotated[str, "Legal UCI coordinate move, e.g. e2e4, e1g1, a7a8n; never null moves"]
    fen: Annotated[str, "Complete resulting FEN, with en-passant field in strict FEN form"]
    in_check: bool
    checkmate: bool


@dataclass
class ProofEdge(Output):
    move: str
    child: Annotated[int, "Index of a later proof node; each non-root node has exactly one parent"]


@dataclass
class ProofNode(Output):
    winning: Annotated[bool, "Whether the original side to move forces mate within the remaining ply bound"]
    reason: ProofReason
    children: Annotated[
        list[ProofEdge],
        "Attacker win: one winning move. Defender win for attacker: every legal defense. "
        "Attacker failure: every legal attacker move. Defender escape: one escaping reply. Leaves have no children.",
    ]


@dataclass
class LineInput(Output):
    fen: Annotated[str, "Complete six-field standard-chess starting FEN; historical rights must be stated"]
    moves: Annotated[list[str], "0 to 12 UCI coordinate moves in order, with q/r/b/n suffix for promotion"]


@dataclass
class LineOutput(Output):
    request: LineInput
    legal: Annotated[bool, "True only if every supplied move is legal from its preceding position"]
    first_illegal_index: Annotated[int | None, "Zero-based index of first illegal move; null if all are legal"]
    steps: Annotated[list[LineStep], "The legal prefix, stopping before the first illegal move"]
    final_fen: Annotated[str, "Position after the legal prefix; starting FEN if prefix empty"]
    ends_in_checkmate: Annotated[
        bool, "True only when the entire supplied line is legal and its final position is mate"
    ]
    winner: Side | None
    is_mating_line: Annotated[
        bool,
        "True only for a nonempty legal line ending in checkmate by the original side to move. "
        "A mating line alone does not prove the opponent cannot defend differently.",
    ]


@dataclass
class MateOutput(Output):
    answer: Annotated[str, "Ready-to-display answer, including checked SAN, independently verified with the result"]
    request: MateInput
    status: MateStatus
    first_move: Annotated[str | None, "First certified winning UCI move, or null when no mate within the bound"]
    line: Annotated[list[LineStep], "One illustrative legal mate line; [] for no forced mate"]
    line_audit: Annotated[
        LineOutput | None,
        "The actual line-checker result for the exact returned line and original FEN, executed inside this call; "
        "null for no forced mate. No second chat tool call is needed.",
    ]
    proof: Annotated[list[ProofNode], "Complete-defense or escape certificate; root 0, at most 4096 nodes"]


TOOLS = {Tool.FIND_FORCED_MATE: (MateInput, MateOutput), Tool.CHECK_MATE_LINE: (LineInput, LineOutput)}
TASKS = {Task.FORCED_MATE: (MateInput, MateOutput), Task.MATE_LINE: (LineInput, LineOutput)}
