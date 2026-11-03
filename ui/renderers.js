import { dataTable, disclosure, h, statusPill } from "./kit/components.js";

const glyphs = { K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙", k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };
const limitation = "Mate-puzzle rules: repetition and move-count draws are excluded. Starting history and special-move rights are assumed as supplied.";
const board = (fen) => {
  const [placement, turn] = fen.split(" ");
  const squares = [];
  placement.split("/").forEach((row, rank) => {
    let file = 0;
    for (const token of row) {
      const count = "12345678".includes(token) ? Number(token) : 1;
      for (let index = 0; index < count; index += 1) {
        const coordinate = "abcdefgh"[file] + (8 - rank);
        const piece = glyphs[token] ?? "";
        squares.push(h("div", { class: "square " + ((rank + file) % 2 ? "dark" : "light"), title: coordinate + (piece ? " " + token : " empty") },
          h("small", { class: "coordinate", text: coordinate }), h("span", { class: token === token.toUpperCase() ? "white-piece" : "black-piece", text: piece }),
        ));
        file += 1;
      }
    }
  });
  return h("div", { class: "board-block" }, h("p", { text: (turn === "w" ? "White" : "Black") + " to move" }), h("div", { class: "chessboard" }, squares));
};

const line = (steps) => steps.map((step, index) => disclosure({ summary: (index + 1) + ". " + step.move + (step.checkmate ? " — checkmate" : step.in_check ? " — check" : "") },
  board(step.fen), h("code", { class: "fen", text: step.fen }),
));
const rejected = (verdict) => h("section", { class: "chess" }, statusPill("Verification failed", "bad"), h("p", { text: verdict.message }));

export default {
  MateOutput: (value, { verdict }) => {
    if (verdict?.valid === false) return rejected(verdict);
    const winning = value.status === "forced_mate";
    return h("section", { class: "chess" },
      statusPill("Verified analysis", "ok"),
      h("h3", { text: winning ? "Forced mate within " + value.request.max_moves + " move(s)" : "No forced mate within " + value.request.max_moves + " move(s)" }),
      h("p", { text: winning ? "Play " + value.first_move + ". The certificate covers every legal defense." : "The certificate supplies an escape against every candidate first move. Longer wins may still exist." }),
      board(value.request.fen),
      winning ? h("p", { text: "Illustrative line: " + value.line.map((step) => step.move).join(" → ") }) : null,
      line(value.line),
      disclosure({ summary: "Complete " + value.proof.length + "-node strategy certificate" }, dataTable({ columns: [
        { key: "index", label: "Node", numeric: true }, { key: "winning", label: "Attacker forces mate" },
        { key: "reason", label: "Reason" }, { key: "children", label: "Move → child node" },
      ], rows: value.proof.map((node, index) => ({ index, winning: node.winning ? "Yes" : "No", reason: node.reason, children: node.children.map((edge) => edge.move + " → #" + edge.child).join("; ") || "Leaf" })), caption: "Every legal defense is checked at universal nodes" }).element),
      h("p", { class: "muted", text: limitation }),
    );
  },
  LineOutput: (value, { verdict }) => {
    if (verdict?.valid === false) return rejected(verdict);
    return h("section", { class: "chess" },
      statusPill("Verified line analysis", "ok"),
      h("h3", { text: value.legal ? (value.ends_in_checkmate ? "Legal line ending in checkmate" : "Legal line; no final checkmate") : "Illegal move at step " + (value.first_illegal_index + 1) }),
      h("p", { text: value.winner ? "Winner: " + value.winner + ". Original side's mating line: " + (value.is_mating_line ? "yes" : "no") + "." : "No checkmate winner is certified for the complete supplied line." }),
      disclosure({ summary: "Starting position" }, board(value.request.fen)),
      line(value.steps),
      h("h4", { text: value.legal ? "Final position" : "Position before the first illegal move" }),
      board(value.final_fen),
      h("p", { text: "A legal mating line alone does not establish forced mate against different defenses." }),
      h("p", { class: "muted", text: limitation }),
    );
  },
};
