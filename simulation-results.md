# Simulation Results

**Latest run (3rd pass) headline: no more extreme outliers.** After redesigning Voodude and
Captain Crunch (see "What changed" below), the widest card-level spread in the whole deck is now
27.2%–61.7% — nothing above ~62% or below ~27%. Both prior runs had cards at 73-75% and as low as
7.9-9.5%. This is a much healthier distribution and the two redesigns look like clean fixes rather
than needing further iteration.

3,000 simulated 4-player games via `simulate.py` (latest run), using the rules as resolved in
`review-findings.md` and heuristic ("reasonable but not perfect") AI decisions. Full methodology
and every simplifying assumption are documented in the docstring at the top of `simulate.py` —
read that before treating any number here as gospel. Two big caveats up front:

1. **Correlation, not causation.** "Win rate when card X was played" mixes two things: how good
   the card is, and what kind of hand tends to include it. Expensive cards (big negative Bean
   cost) can only get played in already-Bean-rich hands, which tend to be strong hands overall —
   so those cards' win rates are inflated by the company they keep, not necessarily their own
   power level. Treat the extremes as *leads to investigate*, not verdicts.
2. **The AI plans with a scoring heuristic, not the real resolution engine.** It's combo-aware
   (values Snow Angel/Christingle, Iron Pan/Dishwasher, and Moonhawk/They synergy correctly when
   picking what to play) but does **not** know that Captain Crunch's own ability sends it away
   from its owner's board — so it gets picked as if it keeps its Power, then under-delivers in
   actual resolution. That mismatch is itself informative (see below), but it means some
   under/over-performance reflects "the AI doesn't understand this card" rather than "this card
   is weak/strong."

## What changed since the first run
- **Deck is now 108 cards** — two copies of each of the 54 designs, confirmed by the designer.
  Duplicate-Hero rules (Prepare's discard-and-redraw, Combat's "no duplicate Heroes") are now
  real and enforced in the simulator, not dead text.
- **Displeased Avian fixed**: confirmed it can only move a card off its *own* board (a defensive
  tool for ejecting a negative-Power card an opponent dumped on you). Win rate 74.9% → 40.1% →
  **43.2%** in this run — stable in the normal band across two re-runs.
- **Voodude redesigned** (stats unchanged, -2 Bean/2 Power): now "destroy the strongest card
  anywhere in play, then Voodude moves into that card's former spot." Win rate 74.8% → **31.0%**.
  This is a clean, reliable removal spell that costs you something when the best target is an
  opponent's (you hand them Voodude's 2 Power in exchange for the removal) and pure upside when
  the best target happens to be sitting on your own board (e.g. something an opponent dumped on
  you). 31% is on the lower side but not alarming — similar to other utility/removal cards
  (Digeridon't 27.2%, Junkrat Crotchrocket 32.7%).
- **Captain Crunch redesigned** (stats unchanged, -2 Bean/2 Power): no longer moves itself.
  Now "move the strongest card among the other combat participants to whichever of them is
  currently weakest" — a pure threat-redistribution tool with no self-harm. Win rate 9.5% →
  **39.6%**, squarely in the normal band. Needs 3+ combat participants to have a "weaker opponent"
  to redirect to; with only 2 participants it's a no-op that turn.

## Game pacing
- Avg turns/game: **18.0** (min 2, max 60)
- Avg combats/game: **4.49**
- Avg wounds given/game: **4.10**
- Unopposed challenges: **11.2%** of all combats — stable across all three runs, still looks like
  a meaningful-but-not-dominant path to winning at 2 Trophies.
- Seat/turn-order win rate: Seat 0 22.1%, Seat 1 27.6%, Seat 2 25.3%, Seat 3 25.0% — same mild
  first-seat softness as before, not alarming.

## Team balance
| Team | Times played | Win rate when played |
|---|---:|---:|
| TURTLE | 13,518 | 44.8% |
| Y | 28,457 | 44.6% |
| VU | 19,887 | 44.0% |
| RED2 | 29,873 | 43.8% |
| HAWK | 14,621 | 42.7% |
| NODES | 20,315 | 43.0% |
| TOPHAT | 20,228 | 42.3% |
| BOLT | 23,335 | 41.8% |
| V | 16,102 | 38.9% |
| NONE (Port Melanin) | 2,520 | 31.7% |

Tight band (38.9%–44.8%) except NONE, which is lowest by design (Port Melanin never gets a Team
Bonus). V dipped a bit this run — expected, since it now contains the redesigned (weaker) Voodude
plus the weak-alone 3-card combo pieces. Not a concern on its own.

## Card-level findings

### Both redesigns landed cleanly — this closes out the original headline finding
**Voodude: 31.0% (n=2,676)**, **Captain Crunch: 39.6% (n=2,724)** — both now comfortably inside
the normal range, down from 74.8% and 9.5%/7.9% respectively across the earlier runs. See "What
changed" above for the mechanics. No further action needed on either card unless you want
Voodude's win rate nudged up slightly (31% is on the low end of the pack, similar to other
utility/removal cards like Digeridon't and Junkrat Crotchrocket, not an outlier).

### Mildly overperforming, likely fine but worth a glance
- **Mute-Ant (61.7%, n=1,834)** — cheap (-3 Bean) unconditional "destroy any card," now the
  single highest win rate in the deck after the two redesigns removed the bigger outliers.
  Consistent across all three runs; worth a look if you want to tighten the top end further, but
  a reliable removal spell will always read strong in this kind of analysis.
- **Gym Shark (54.6%, n=1,523)** and **James Madison (51.9%, n=2,980)** — consistent with prior
  runs and with your earlier call that both are fine as-is (the Bean-affordability selection-bias
  caveat applies to both).

### The 3-card combo (Footrun/Jetplace/Junkrat) still confirms the earlier prediction
Triggered **21 times across 3,000 games** (0.007/game) — same story as both earlier runs: a
high-commitment combo that's appropriately rare and weak on its own otherwise. No action needed.

### Moonhawk still barely played (14 times in 3,000 games)
Consistent with both earlier runs — pairing Moonhawk with They in the same hand and committing a
round to their combo remains rare under this AI's heuristics. Sample too small (n=14) to read a
win rate at all.

### Snow Angel/Christingle and Iron Pan/Dishwasher combos still look well-tuned
Trigger rates (0.31/game and 0.30/game) and win rates (43–45%) are essentially unchanged across
all three runs. No changes suggested.

### Low-sample cards (treat any rate here as a weak signal, not a verdict)
Digeridon't (n=405, 27.2%), Grup Scrooge (n=25), Accordion Joe (n=26), Belt Tungus (n=1,118,
41.1%), Machete Man (n=1,158, 40.8%) — sample sizes small enough that these numbers could shift
with a different random seed.

## Resolved across the three runs
- **Deck size / duplicate-Hero rules**: confirmed 108 cards, 2 copies each. Implemented and
  enforced in the simulator.
- **Displeased Avian targeting**: confirmed own-board-only, defensive. Stable in the normal band.
- **Voodude redesign**: destroy-and-reposition, stats unchanged. Normalized from the strongest to
  a middling card.
- **Captain Crunch redesign**: threat-redistribution, no longer self-harming. Normalized from the
  weakest card in the deck to squarely average.

## Still open
- Everything already tracked in `review-findings.md` (Debit/Proctor Odd wording, Brain Freeze
  artwork, Grup Scrooge's "area"→"Board" reprint) — plus now **Voodude and Captain Crunch's
  printed card text needs updating to match the redesigned abilities** before print.

## How to reproduce or extend
Run `python3 simulate.py` from the repo root for a fresh 3,000-game batch (takes ~10 seconds).
Edit `n_games`/`n_players` in `main()` to try other batch sizes or table sizes — player count is
still an assumption (the rulebook doesn't specify one).
