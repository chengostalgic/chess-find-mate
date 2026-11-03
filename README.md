# Chess Forced Mate

**Find a mating move and check every legal defense.** Solve mate-in-one puzzles,
try bounded mate-in-two/three searches, or check a continuation you already have.
Inspect board diagrams, legal move sequences, and independently checked evidence.

This is a **standard-chess mate-puzzle plugin**, not a general position evaluator.
The side to move is the attacker. It proves mate **within** a chosen bound; a
negative result means no forced mate within that bound, not that the position
is lost. Repetition and move-count draw adjudications are excluded from these
history-free puzzles; the result card states this limitation.

## Tools

| Tool | Input → output | Purpose |
|---|---|---|
| `find_forced_mate` | `MateInput` → `MateOutput` | Find mate within 1, 2, or 3 attacker moves, with a complete-defense or no-mate certificate. |
| `check_mate_line` | `LineInput` → `LineOutput` | Check up to 12 ordered UCI moves, identify an illegal move, and check final mate/winner. |

| Task | Runner/tool | Purpose |
|---|---|---|
| `forced-mate` | `tool` / `find_forced_mate` | Solve a bounded forced-mate puzzle. |
| `mate-line` | `tool` / `check_mate_line` | Audit a proposed continuation, without claiming it is forced. |

### Try it in chat

```text
Find mate in one from this FEN:
7k/8/5KQ1/8/8/8/8/8 w - - 0 1
Show the winning move and resulting board.
```

White plays **g6g7** (Qg7#). The verifier checks that it is legal, Black is in
check, and Black has no legal response.

```text
Find a forced mate within three moves:
7k/8/6Q1/5K2/8/8/8/8 w - - 0 1
Show an illustrative line and verify every possible defense.
```

This position has no forced mate within two moves, but has one within three.
The tool returns a strategy covering every legal defense. Its displayed line
is only one path through that strategy; the strategy is the actual evidence.

```text
Check this continuation from the standard starting position:
f2f3, e7e5, g2g4, d8h4.
Are all moves legal, and does the final move give checkmate? Who wins?
```

The moves are legal and Black wins by checkmate. Because the original side to
move was White, `is_mating_line` is false even though `ends_in_checkmate` is true.
A correct analysis of a losing or illegal line still receives a valid verifier
verdict: that verdict checks the analysis, not whether the user's line wins.

You may describe a position in words instead of providing FEN. The host converts
that description, preserving piece squares and side to move. **Castling and
en-passant rights require historical information**; a diagram alone does not
establish them. State those rights, or explicitly state there are none. For a
composed puzzle with no prior history, counters may be `0 1`. The host should
clarify missing information rather than invent it. Users need not construct JSON.

### Rules and bounds

- Standard chess only: all normal moves, captures, check evasion, pins, king
  safety, castling, en passant, and queen/rook/bishop/knight promotion.
- `max_moves` is **1, 2, or 3 attacker turns**, giving a horizon of 1, 3, or 5
  plies. The host chooses 1 if unspecified. The tool finds one strategy, not
  necessarily a unique move, and does not certify a minimum mate distance.
- Starting FEN must have all six fields, at most 200 characters, ordered standard
  castling flags `KQkq` or `-`, and supported move counters: halfmove 0–1,000,000,
  fullmove 1–1,000,000. An en-passant target requires the preceding double pawn
  push and a zero halfmove clock. Invalid kings, king exposure, pawn back ranks,
  impossible rights, excessive pieces, and malformed fields are rejected.
- Searches have a fixed **50,000-position budget** and certificates at most
  **4,096 nodes**. Exceeding either raises an explicit **undecided** error. It
  must never become a fabricated negative result. Open middlegame searches can
  exceed these bounds even at the supported depth; small puzzles are the focus.
- Proposed lines contain **0–12 UCI moves**, each at most five characters. UCI
  means origin/destination: `e2e4`; promotion adds `q/r/b/n`, such as `a7a8n`.
  Standard castling is `e1g1` or `e1c1` (Black: `e8g8`/`e8c8`). Null moves and
  drops are not legal. Moves after mate or detected insufficient material fail.
- Checkmate requires **check and no legal response**; stalemate is not mate.
  Detected insufficient material is terminal. Repetition, 50/75-move draws,
  clocks/time forfeits, resignations, and draw agreements are outside this
  puzzle policy. Prior game history is not reconstructed from FEN.

[FIDE's Laws of Chess](https://handbook.fide.com/chapter/e012023) describe board
move legality and checkmate. The puzzle draw-policy exclusions above are
explicit limitations, not a claim to implement every tournament adjudication.
The runtime uses the locked [python-chess board API](https://python-chess.readthedocs.io/en/latest/core.html);
the verifier uses its own standard-library implementation instead.

### How verification works

A single legal line ending in mate can rely on cooperative opponent moves.
**Forced mate requires quantifying over every defense.** The solver returns a
flat indexed AND/OR tree. Its checker replays legal moves independently:

| Claimed state | Required children |
|---|---|
| Attacker to move, forces mate | One winning attacker move |
| Defender to move, attacker forces mate | Every legal defense, each still winning for attacker |
| Attacker to move, no forced mate | Every legal attacker move, each failing |
| Defender to move, escapes | One legal escaping defense |

A positive proof ends every branch with actual checkmate of the defender, within
the horizon. A negative proof can end with the horizon exhausted, stalemate,
insufficient material, or checkmate of the attacker. Its claim is only bounded
nonexistence. Missing defenses, shared/cyclic/unreachable proof nodes, wrong
leaf reasons, illegal moves, and contradictory outcomes fail verification.
Different correct winning moves and valid strategy certificates are accepted.

The runtime uses python-chess and bounded search. The verifier imports no chess
library or runtime code. It parses FEN independently, represents the board as
64 characters, generates its own attacks/legal moves, and checks the supplied
certificate without repeating the solver's search. It checks every output
field, including echoed input, first move, illustrative line's FEN/check/mate
flags, and all proof edges/leaves. Strict output FEN includes an en-passant
square after any double pawn push, even when no capture is available.

The line tool independently replays each supplied move, stopping before the
first illegal move. It returns the legal prefix and zero-based illegal index.
`ends_in_checkmate` is true only if the **entire** line is legal and finishes in
mate; `winner` is otherwise null. `is_mating_line` additionally requires a
nonempty line and victory by the original side to move. The final FEN is always
the position after the legal prefix. This tool certifies a line, not force.

The verifier is pure, deterministic standard-library code, with no model,
network, randomness, clock, or workspace IO. Correct analyses score 1; wrong or
missing outputs score 0. Malformed contract payloads fail at the schema boundary.
The local tools require no API key or external engine. Hosted chat uses its
configured model to interpret English requests.

### Limitations

Static FEN checks and legal continuations do **not** prove that an arbitrary
starting position is reachable from the usual initial position. Castling and
en-passant history are assumed as supplied. The runtime's validity checks are
more extensive than the verifier's structural checks; neither is a complete
retrograde reachability proof. The independent checker is tested software,
not a formally verified chess implementation. Its insufficient-material test
handles standard material cases, not every possible dead-position theorem.

The mathematical verdict applies to the interpreted FEN, bound, and moves. The
host model can misread prose, select the wrong side, or mistranslate notation;
this translation is outside the deterministic guarantee. Echoed input, board
diagrams, and move traces let users inspect what was actually analyzed. SAN/PGN
files, image recognition, Chess960, variants, arbitrary-depth engine analysis,
material evaluations, uniqueness, and shortest-mate proofs are outside scope.
No live hosted model or real-browser behavior is established by local tests.

## Layout

```text
chess-forced-mate/
├── nanoagent.yaml
├── contract.py
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env                   # comments only, no credentials
├── src/plugin/            # MCP and python-chess runtime search/line audit
├── verifier/              # independent board rules and certificate checker
├── tests/
│   ├── cases/             # declared FENs, task inputs and expected claims
│   ├── test_board.py      # perft, special moves, differential playouts
│   └── test_verifier.py
├── ui/                    # boards, move sequences, proof table
└── product/               # marketplace description and original icon
```

This folder is its own Git repository and uv project, with no dependency on
the other milestone plugins. Keep report logs/packages outside this repository.

## Develop and run

```bash
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
```

Install the separately pinned NanoAgent CLI if needed:

```bash
uv tool install 'nanoagent @ git+https://github.com/RUSH-LAB/nanoagent.git@57714f62880eee11319765854e398af61e67b7b7#subdirectory=nanoagent'
nanoagent plugin inspect .
```

Save a YAML config **outside the repository**, replacing absolute paths:

```yaml
_ > nanoagent.cli.plugin.PluginRunConfig:
plugin: /absolute/path/to/chess-forced-mate
task: forced-mate
arguments: /absolute/path/to/chess-forced-mate/tests/cases/mate-three.input.json
inputs: []
timeout: 60.0
```

Run and package:

```bash
nanoagent plugin run config=/absolute/path/to/run.yaml home=/absolute/path/to/evidence/run
nanoagent plugin pack . /absolute/path/to/evidence/chess-forced-mate.tar.gz
```

For line examples, select task `mate-line` and a `line-*.input.json` fixture.
Local tasks require no model/API key. The repository is initialized on `main`.
Create its own GitHub remote and push, then publish through RUSH's marketplace;
no remote, commit, push, publication, or paid chat test is implied by local work.
