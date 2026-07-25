const TEAM_LABELS = {
  VU: "VU Shield", BOLT: "Bolt", RED2: "Red 2", HAWK: "Hawk", V: "V Shield",
  TURTLE: "Turtle", Y: "Y", TOPHAT: "Top Hat", NODES: "Nodes", NONE: "No Team",
};

function pct(x) {
  return x === null || x === undefined ? "—" : (x * 100).toFixed(1) + "%";
}

function rateColor(rate, min, max) {
  if (rate === null || rate === undefined) return "var(--text-dim)";
  const t = max > min ? (rate - min) / (max - min) : 0.5;
  if (t < 0.5) {
    return mix("var(--bad)", "var(--mid)", t / 0.5);
  }
  return mix("var(--mid)", "var(--good)", (t - 0.5) / 0.5);
}

function mix(a, b, t) {
  return `color-mix(in srgb, ${b} ${Math.round(t * 100)}%, ${a})`;
}

function rateCell(rate, min, max, barMax) {
  const wrap = document.createElement("div");
  wrap.className = "rate-cell";
  const label = document.createElement("span");
  label.textContent = pct(rate);
  label.style.color = rateColor(rate, min, max);
  label.style.fontWeight = "600";
  const track = document.createElement("div");
  track.className = "bar-track";
  const fill = document.createElement("div");
  fill.className = "bar-fill";
  const width = rate === null ? 0 : Math.max(2, (rate / barMax) * 100);
  fill.style.width = width + "%";
  fill.style.background = rateColor(rate, min, max);
  track.appendChild(fill);
  wrap.appendChild(label);
  wrap.appendChild(track);
  return wrap;
}

function makeSortable(table, getRows, renderRows) {
  const ths = table.querySelectorAll("th[data-key]");
  let currentKey = null;
  let currentDir = 1;
  ths.forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (currentKey === key) {
        currentDir *= -1;
      } else {
        currentKey = key;
        currentDir = th.dataset.defaultDir === "desc" ? -1 : 1;
      }
      ths.forEach((t) => t.classList.remove("sorted"));
      th.classList.add("sorted");
      th.dataset.dir = currentDir === 1 ? "▲" : "▼";
      const rows = getRows().slice().sort((a, b) => {
        let va = a[key], vb = b[key];
        if (va === null || va === undefined) va = -Infinity;
        if (vb === null || vb === undefined) vb = -Infinity;
        if (typeof va === "string") return va.localeCompare(vb) * currentDir;
        return (va - vb) * currentDir;
      });
      renderRows(rows);
    });
  });
}

async function main() {
  const res = await fetch("data.json");
  const data = await res.json();

  document.getElementById("generated-at").textContent =
    new Date(data.generated_at).toLocaleString();
  document.getElementById("games-count").textContent = data.games.toLocaleString();
  document.getElementById("seed-value").textContent = data.seed ?? "random";

  const p = data.pacing;
  document.getElementById("stat-turns").textContent = p.avg_turns.toFixed(1);
  document.getElementById("stat-combats").textContent = p.avg_combats.toFixed(2);
  document.getElementById("stat-unopposed").textContent = pct(p.unopposed_pct);
  document.getElementById("stat-wounds").textContent = p.avg_wounds.toFixed(2);

  const seatWrap = document.getElementById("seat-rates");
  p.seat_win_rate.forEach((rate, i) => {
    const chip = document.createElement("div");
    chip.className = "seat-chip";
    chip.textContent = `Seat ${i}: ${pct(rate)}`;
    seatWrap.appendChild(chip);
  });

  const comboList = document.getElementById("combo-list");
  data.combos.forEach((c) => {
    const li = document.createElement("li");
    li.textContent = `${c.name}: ${c.total} triggers (${c.per_game.toFixed(3)} per game)`;
    comboList.appendChild(li);
  });
  if (data.combos.length === 0) {
    comboList.innerHTML = "<li>No combos triggered in this batch.</li>";
  }

  // Teams table
  const teamRates = data.teams.map((t) => t.win_rate);
  const teamMin = Math.min(...teamRates), teamMax = Math.max(...teamRates);
  const teamBody = document.getElementById("team-body");
  function renderTeams(rows) {
    teamBody.innerHTML = "";
    rows.forEach((t) => {
      const tr = document.createElement("tr");
      const tdTeam = document.createElement("td");
      tdTeam.innerHTML = `<span class="pill">${TEAM_LABELS[t.team] || t.team}</span>`;
      const tdPlayed = document.createElement("td");
      tdPlayed.textContent = t.played.toLocaleString();
      const tdRate = document.createElement("td");
      tdRate.appendChild(rateCell(t.win_rate, teamMin, teamMax, Math.max(teamMax, 0.5)));
      tr.append(tdTeam, tdPlayed, tdRate);
      teamBody.appendChild(tr);
    });
  }
  renderTeams(data.teams.slice().sort((a, b) => b.win_rate - a.win_rate));
  makeSortable(document.getElementById("team-table"), () => data.teams, renderTeams);

  // Cards table
  const validRates = data.cards.filter((c) => !c.low_sample).map((c) => c.win_rate);
  const cardMin = Math.min(...validRates), cardMax = Math.max(...validRates);
  const cardBody = document.getElementById("card-body");
  let cardRows = data.cards.slice().sort((a, b) => (b.win_rate ?? -1) - (a.win_rate ?? -1));

  function renderCards(rows) {
    cardBody.innerHTML = "";
    rows.forEach((c) => {
      const tr = document.createElement("tr");
      if (c.low_sample) tr.className = "low-sample";
      const tdName = document.createElement("td");
      tdName.textContent = c.name;
      const tdTeam = document.createElement("td");
      tdTeam.innerHTML = `<span class="pill">${TEAM_LABELS[c.team] || c.team}</span>`;
      const tdBean = document.createElement("td");
      tdBean.textContent = (c.bean > 0 ? "+" : "") + c.bean;
      const tdPower = document.createElement("td");
      tdPower.textContent = (c.power > 0 ? "+" : "") + c.power;
      const tdPlayed = document.createElement("td");
      tdPlayed.textContent = c.played.toLocaleString();
      const tdRate = document.createElement("td");
      tdRate.appendChild(rateCell(c.win_rate, cardMin, cardMax, Math.max(cardMax, 0.5)));
      if (c.low_sample) {
        const note = document.createElement("span");
        note.className = "meta";
        note.style.marginLeft = "0.4rem";
        note.textContent = "low sample";
        tdRate.appendChild(note);
      }
      tr.append(tdName, tdTeam, tdBean, tdPower, tdPlayed, tdRate);
      cardBody.appendChild(tr);
    });
  }
  renderCards(cardRows);
  makeSortable(document.getElementById("card-table"), () => cardRows, renderCards);

  const search = document.getElementById("card-search");
  const teamFilter = document.getElementById("team-filter");
  Object.keys(TEAM_LABELS).forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = TEAM_LABELS[t];
    teamFilter.appendChild(opt);
  });

  function applyFilters() {
    const q = search.value.trim().toLowerCase();
    const team = teamFilter.value;
    cardRows = data.cards
      .filter((c) => (!q || c.name.toLowerCase().includes(q)))
      .filter((c) => (!team || c.team === team))
      .sort((a, b) => (b.win_rate ?? -1) - (a.win_rate ?? -1));
    renderCards(cardRows);
  }
  search.addEventListener("input", applyFilters);
  teamFilter.addEventListener("change", applyFilters);
}

main().catch((err) => {
  document.getElementById("error-banner").style.display = "block";
  document.getElementById("error-banner").textContent =
    "Couldn't load data.json: " + err.message;
  console.error(err);
});
