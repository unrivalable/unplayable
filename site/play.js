const TEAM_LABELS = {
  VU: "VU Shield", BOLT: "Bolt", RED2: "Red 2", HAWK: "Hawk", V: "V Shield",
  TURTLE: "Turtle", Y: "Y", TOPHAT: "Top Hat", NODES: "Nodes", NONE: "No Team",
};

const HUMAN_IDX = 0;
const N_PLAYERS = 4;

let pyodide, gen, primed = false;
let cardMeta = {};       // id -> {name, team, bean, power}
let currentReq = null;
let snapshot = null;
let selectedCards = new Set();
let logLines = [];

function fmtSigned(n) {
  return (n > 0 ? "+" : "") + n;
}

function log(msg) {
  logLines.unshift(msg);
  logLines = logLines.slice(0, 60);
}

function playerName(idx) {
  return idx === HUMAN_IDX ? "You" : `Player ${idx}`;
}

// ---- Pyodide bridge ----
async function initEngine() {
  const [dataRes, srcRes] = await Promise.all([fetch("data.json"), fetch("simulate.py")]);
  const data = await dataRes.json();
  data.cards.forEach((c) => { cardMeta[c.id] = c; });
  const src = await srcRes.text();

  pyodide = await loadPyodide();
  pyodide.runPython(src);
  const playFn = pyodide.globals.get("play_game_interactive");
  gen = playFn(N_PLAYERS, HUMAN_IDX, 400);

  currentReq = stepGen();
  refreshSnapshot();
}

function stepGen(response) {
  let raw;
  if (!primed) {
    primed = true;
    raw = gen.next().value;
  } else {
    raw = gen.send(response === undefined ? null : response);
  }
  return raw.toJs({ dict_converter: Object.fromEntries });
}

function refreshSnapshot() {
  const getSnap = pyodide.globals.get("get_snapshot");
  snapshot = getSnap().toJs({ dict_converter: Object.fromEntries });
}

function respond(value, logMsg) {
  if (logMsg) log(logMsg);
  selectedCards = new Set();
  currentReq = stepGen(value);
  refreshSnapshot();
  render();
}

// ---- card rendering ----
function cardEl(cid, opts = {}) {
  const meta = cardMeta[cid] || { name: `#${cid}`, team: "NONE", bean: 0, power: 0 };
  const div = document.createElement("div");
  div.className = "card";
  if (opts.selectable) div.classList.add("selectable");
  if (opts.selected) div.classList.add("selected");
  if (opts.disabled) div.classList.add("disabled");
  if (opts.destroyed) div.classList.add("destroyed");
  div.innerHTML = `
    <span class="team-pill">${TEAM_LABELS[meta.team] || meta.team}</span>
    <div class="cname">${meta.name}${opts.subtitle ? ` <small>${opts.subtitle}</small>` : ""}</div>
    <div class="cstats"><span class="bean">${fmtSigned(meta.bean)}</span><span class="power">${fmtSigned(meta.power)}</span></div>
  `;
  if (opts.onClick) div.addEventListener("click", () => { if (!opts.disabled) opts.onClick(); });
  return div;
}

// ---- render pieces ----
function renderPlayers() {
  const wrap = document.getElementById("players-row");
  wrap.innerHTML = "";
  snapshot.players.forEach((p) => {
    const chip = document.createElement("div");
    chip.className = "player-chip" + (p.idx === HUMAN_IDX ? " is-human" : "");
    chip.innerHTML = `
      <div class="pname"><span>${playerName(p.idx)}</span><span class="trophy">${"🏆".repeat(p.trophies)}</span></div>
      <div class="prow">
        <span>${p.trophies}/3 trophies</span>
        <span>${p.idx === HUMAN_IDX ? p.hand.length : p.hand_size} cards</span>
        ${p.wounded ? '<span class="wound-badge">WOUNDED</span>' : ""}
      </div>
    `;
    wrap.appendChild(chip);
  });
}

function renderDeckRow() {
  document.getElementById("deck-count").textContent = snapshot.deck_remaining;
  const discardEl = document.getElementById("discard-top");
  discardEl.innerHTML = "";
  if (snapshot.discard_top !== null && snapshot.discard_top !== undefined) {
    discardEl.appendChild(cardEl(snapshot.discard_top));
  } else {
    discardEl.textContent = "(empty)";
  }
  const traderWrap = document.getElementById("trader-cards");
  traderWrap.innerHTML = "";
  snapshot.trader.forEach((cid) => traderWrap.appendChild(cardEl(cid)));
}

function renderBoards() {
  const grid = document.getElementById("board-grid");
  grid.innerHTML = "";
  const anyCards = snapshot.players.some((p) => p.columns.some((c) => c.length));
  if (!anyCards) {
    grid.innerHTML = '<p class="section-note" style="color:var(--text-dim)">No combat in progress.</p>';
    return;
  }
  snapshot.players.forEach((p) => {
    const box = document.createElement("div");
    box.className = "board-player";
    box.innerHTML = `<h4>${playerName(p.idx)} — Board</h4>`;
    const cols = document.createElement("div");
    cols.className = "board-columns";
    p.columns.forEach((col, i) => {
      const colEl = document.createElement("div");
      colEl.className = "board-column";
      colEl.innerHTML = `<div class="round-label">Round ${i + 1}</div>`;
      col.forEach((entry) => {
        colEl.appendChild(cardEl(entry.cid, {
          destroyed: entry.destroyed,
          subtitle: entry.owner !== p.idx ? `(from ${playerName(entry.owner)})` : "",
        }));
      });
      cols.appendChild(colEl);
    });
    box.appendChild(cols);
    grid.appendChild(box);
  });
}

function projectedBeanBalance() {
  if (!currentReq || currentReq.type !== "round_play") return null;
  const base = currentReq.bean_balance;
  const selectedBean = selectedCardIds().reduce((sum, cid) => sum + (cardMeta[cid]?.bean || 0), 0);
  return base + selectedBean;
}

function renderHand() {
  const wrap = document.getElementById("hand-row");
  wrap.innerHTML = "";
  const hand = snapshot.players[HUMAN_IDX].hand || [];
  const selecting = currentReq && (currentReq.type === "round_play" || currentReq.type === "prepare_discard");
  const cap = currentReq && currentReq.type === "round_play" ? currentReq.max_slots
    : currentReq && currentReq.type === "prepare_discard" ? currentReq.count : null;
  const isRoundPlay = currentReq && currentReq.type === "round_play";
  const balanceSoFar = isRoundPlay ? projectedBeanBalance() : null;

  hand.forEach((cid, i) => {
    const key = i; // use index so duplicate ids are distinguishable
    const isSelected = selectedCards.has(key);
    const atCap = cap !== null && selectedCards.size >= cap && !isSelected;
    const bean = cardMeta[cid]?.bean || 0;
    const unaffordable = isRoundPlay && !isSelected && bean < 0 && (balanceSoFar + bean) < 0;
    wrap.appendChild(cardEl(cid, {
      selectable: selecting,
      selected: isSelected,
      disabled: selecting && (atCap || unaffordable),
      subtitle: unaffordable ? "(not enough Beans)" : "",
      onClick: selecting ? () => {
        if (isSelected) selectedCards.delete(key); else selectedCards.add(key);
        renderHand();
        renderDecisionPanel();
      } : null,
    }));
  });
}

function selectedCardIds() {
  const hand = snapshot.players[HUMAN_IDX].hand || [];
  return [...selectedCards].map((i) => hand[i]);
}

// ---- decision panel ----
function renderDecisionPanel() {
  const panel = document.getElementById("decision-panel");
  panel.innerHTML = "";
  if (!currentReq) return;
  const t = currentReq.type;

  if (t === "prepare_action") {
    panel.innerHTML = `<h3>Your turn</h3><p class="prompt-note">Prepare your hand, or Challenge to start a Combat.</p>`;
    const row = document.createElement("div");
    row.className = "btn-row";
    const bPrep = mkBtn("Prepare", "primary", () => respond("prepare", "You chose to Prepare."));
    const bChal = mkBtn("JUICE IT UP! (Challenge)", "", () => respond("challenge", "You challenged!"));
    row.append(bPrep, bChal);
    panel.appendChild(row);

  } else if (t === "prepare_draw") {
    panel.innerHTML = `<h3>Draw ${currentReq.draw_number} of 2</h3><p class="prompt-note">Pick a card from the Trader, the Discard pile, or draw blind from the Deck.</p>`;
    const opts = document.createElement("div");
    opts.className = "option-list";
    opts.appendChild(mkOptionBtn("Deck (blind draw)", () => respond("deck", "Drew blind from the deck.")));
    if (snapshot.discard_top !== null && snapshot.discard_top !== undefined) {
      const nm = cardMeta[snapshot.discard_top]?.name || snapshot.discard_top;
      opts.appendChild(mkOptionBtn(`Discard pile top: ${nm}`, () => respond("discard", `Took ${nm} from the discard pile.`)));
    }
    snapshot.trader.forEach((cid) => {
      opts.appendChild(cardEl(cid, { selectable: true, onClick: () => respond(cid, `Took ${cardMeta[cid]?.name} from the Trader.`) }));
    });
    panel.appendChild(opts);

  } else if (t === "prepare_dedupe") {
    panel.innerHTML = `<h3>Duplicate Hero: ${currentReq.duplicate_name}</h3><p class="prompt-note">You have two copies. Discard one and draw a replacement, or keep both (you just can't play both in the same combat).</p>`;
    const row = document.createElement("div");
    row.className = "btn-row";
    row.appendChild(mkBtn("Discard & Redraw", "primary", () => respond("redraw", `Discarded a duplicate ${currentReq.duplicate_name} and redrew.`)));
    row.appendChild(mkBtn("Keep Both", "", () => respond("keep", "Kept both copies.")));
    panel.appendChild(row);

  } else if (t === "prepare_discard") {
    panel.innerHTML = `<h3>Discard ${currentReq.count} cards</h3><p class="prompt-note">Select exactly ${currentReq.count} cards from your hand below.</p>`;
    const row = document.createElement("div");
    row.className = "btn-row";
    const confirmBtn = mkBtn(`Discard ${selectedCards.size}/${currentReq.count} selected`, "primary", () => {
      const ids = selectedCardIds();
      respond(ids, `Discarded ${ids.map((c) => cardMeta[c]?.name).join(", ")}.`);
    });
    confirmBtn.disabled = selectedCards.size !== currentReq.count;
    row.appendChild(confirmBtn);
    panel.appendChild(row);

  } else if (t === "join_or_decline") {
    panel.innerHTML = `<h3>${playerName(currentReq.challenger)} is challenging!</h3><p class="prompt-note">Join the combat, or stay out (you can't join later once combat starts).</p>`;
    const row = document.createElement("div");
    row.className = "btn-row";
    row.appendChild(mkBtn("Join", "primary", () => respond("join", "You joined the combat.")));
    row.appendChild(mkBtn("Decline", "", () => respond("decline", "You declined to join.")));
    panel.appendChild(row);

  } else if (t === "round_play") {
    const proj = projectedBeanBalance();
    panel.innerHTML = `<h3>Round ${currentReq.round}: choose cards to play</h3><p class="prompt-note">Pick up to ${currentReq.max_slots} cards from your hand below. Projected Bean balance: <strong style="color:${proj < 0 ? 'var(--bad)' : 'inherit'}">${proj}</strong> (cards you can't afford yet are greyed out).</p>`;
    const row = document.createElement("div");
    row.className = "btn-row";
    row.appendChild(mkBtn(`Play ${selectedCards.size} card(s)`, "primary", () => {
      const ids = selectedCardIds();
      respond(ids, `Round ${currentReq.round}: played ${ids.length ? ids.map((c) => cardMeta[c]?.name).join(", ") : "nothing"}.`);
    }));
    panel.appendChild(row);

  } else if (t === "ability_target") {
    panel.innerHTML = `<h3>${currentReq.card_name}: choose a target</h3><p class="prompt-note">${describeSubtype(currentReq.subtype)}</p>`;
    const opts = document.createElement("div");
    opts.className = "option-list";
    currentReq.options.forEach((o) => {
      opts.appendChild(mkOptionBtn(`${o.name} — ${playerName(o.owner)} (${fmtSigned(o.power)} Power)`,
        () => respond(o.uid, `${currentReq.card_name} targeted ${o.name}.`)));
    });
    panel.appendChild(opts);

  } else if (t === "ability_choice_discard") {
    panel.innerHTML = `<h3>${currentReq.card_name}: choose a card from the Discard pile</h3>`;
    const opts = document.createElement("div");
    opts.className = "option-list";
    currentReq.discard.forEach((cid) => {
      opts.appendChild(cardEl(cid, { selectable: true, onClick: () => respond(cid, `Played ${cardMeta[cid]?.name} back from the discard pile.`) }));
    });
    panel.appendChild(opts);

  } else if (t === "ability_choice_scry") {
    panel.innerHTML = `<h3>${currentReq.card_name}: choose a card to draw</h3><p class="prompt-note">Top of the deck (the other cards go back).</p>`;
    const opts = document.createElement("div");
    opts.className = "option-list";
    currentReq.options.forEach((cid) => {
      opts.appendChild(cardEl(cid, { selectable: true, onClick: () => respond(cid, `Drew ${cardMeta[cid]?.name} via ${currentReq.card_name}.`) }));
    });
    panel.appendChild(opts);

  } else if (t === "ability_choice_opponent") {
    panel.innerHTML = `<h3>${currentReq.card_name}: choose an opponent</h3>`;
    const opts = document.createElement("div");
    opts.className = "option-list";
    currentReq.options.forEach((idx) => {
      opts.appendChild(mkOptionBtn(playerName(idx), () => respond(idx, `${currentReq.card_name} targeted ${playerName(idx)}.`)));
    });
    panel.appendChild(opts);

  } else if (t === "combat_unopposed") {
    panel.innerHTML = `<h3>Unopposed challenge!</h3><p class="prompt-note">${playerName(currentReq.challenger)}'s challenge went unopposed and they gain 2 Trophies.</p>`;
    panel.appendChild(mkBtn("Continue", "primary", () => respond(null)));

  } else if (t === "combat_result") {
    const lines = currentReq.joiners.map((i) => {
      const tag = currentReq.winners.includes(i) ? " 🏆" : currentReq.losers.includes(i) ? " 🩹" : "";
      return `${playerName(i)}: ${currentReq.totals[i]} Power${tag}`;
    });
    panel.innerHTML = `<h3>Combat result</h3><p class="prompt-note">${lines.join(" · ")}</p>`;
    panel.appendChild(mkBtn("Continue", "primary", () => respond(null)));

  } else if (t === "game_over") {
    renderGameOver();
  }
}

function renderGameOver() {
  document.getElementById("decision-panel").classList.add("hidden");
  const wrap = document.getElementById("game-over-wrap");
  const youWon = currentReq.winner === HUMAN_IDX;
  wrap.innerHTML = `
    <div class="game-over-banner">
      <div class="big">${youWon ? "🎉 You win!" : `${playerName(currentReq.winner)} wins.`}</div>
      <div>Trophies — ${currentReq.trophies.map((t, i) => `${playerName(i)}: ${t}`).join(" · ")}</div>
      <div class="btn-row" style="justify-content:center">
        <button class="primary" onclick="location.reload()">Play Again</button>
      </div>
    </div>
  `;
}

function mkBtn(label, cls, onClick) {
  const b = document.createElement("button");
  b.textContent = label;
  if (cls) b.className = cls;
  b.addEventListener("click", onClick);
  return b;
}

function mkOptionBtn(label, onClick) {
  const b = document.createElement("button");
  b.className = "option-btn";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

function describeSubtype(subtype) {
  const map = {
    destroy_own: "Destroy one of your own cards.",
    destroy_any: "Destroy any eligible opposing card.",
    destroy_any_round: "Destroy any eligible opposing card.",
    destroy_self_for_any: "This card destroys itself along with your chosen target.",
    remove_ability: "Remove the ability from a card played this round.",
  };
  return map[subtype] || "Choose a target.";
}

function renderLog() {
  const panel = document.getElementById("log-panel");
  panel.innerHTML = logLines.map((l) => `<div class="log-line">${l}</div>`).join("");
}

function render() {
  document.getElementById("decision-panel").classList.remove("hidden");
  renderPlayers();
  renderDeckRow();
  renderBoards();
  renderHand();
  renderDecisionPanel();
  renderLog();
}

window.__debugState = () => ({
  type: currentReq && currentReq.type,
  req: currentReq,
  handSize: (snapshot && snapshot.players[HUMAN_IDX].hand || []).length,
});

async function main() {
  await initEngine();
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("game").classList.remove("hidden");
  log("Game started. You are Player 0.");
  render();
}

main().catch((err) => {
  document.getElementById("loading").innerHTML =
    `<p style="color:var(--bad)">Failed to load: ${err.message}</p>`;
  console.error(err);
});
