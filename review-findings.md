# Unemployables: Unplayable — Pre-Print Review Findings

Companion to `card-database.md`. Four sections: rules questions, balance analysis, copyedit list,
and sample combat walkthroughs used to verify the above. Everything here is a recommendation or
question, not yet an applied change — nothing in the PDF or rulebook has been edited.

---

## 1. Rules consistency questions

These are places where card text depends on something the rulebook doesn't fully pin down. Ranked
by how much they affect actual play (top ones will change how every combat resolves).

### 1a. When do abilities actually resolve? — RESOLVED
**Answer (confirmed): abilities resolve after each round**, not bundled at the end of Round 3.
The rulebook was wrong as written — it said "Resolve Hero Abilities" only happens after Round 3,
which contradicted the ~third of cards written as round-triggered ("Round 1: +1 Power," "This
card must be played on round 1," etc.) or "at any time." Fixed directly in
`Unemployables game.md`: the Combat section's per-round list now has a 4th step, "Resolve the
Hero Abilities of the cards played this round," and the end-of-Round-3 step now only covers Team
Bonus + Power totaling.

### 1b. Does "Prepare" mean all four bullets, or pick one? — RESOLVED
**Confirmed: all four bullets happen together, every Prepare turn** (draw 2, cycle duplicates,
discard 2, refill Trader). Rulebook updated with a "Do all of the following:" lead-in under
Prepare to remove the ambiguity against "choose one action."

### 1c. Who gets wounded when more than 2 players are in a combat? — RESOLVED
**Confirmed: only the player(s) with the lowest total Power get wounded** — anyone in between the
winner and the bottom is unaffected (no Trophy, no Wound). Rulebook's End of Combat section now
states this explicitly.

### 1d. Unopposed-challenge Trophy value — RESOLVED (for now)
Keeping the unopposed-challenge reward at **2 Trophies** (vs. 1 for a contested win) as-is for
now. Worth revisiting after playtesting if it turns out to be too fast/swingy a win path in
practice, but no change going into print.

### 1e. "Board" / "area" / "column" terminology — RESOLVED
**Confirmed structure:** each player has their own **Board** (their whole play area for the
combat); each round creates its own **Column** on that Board, so after 3 rounds a Board is a
3-column array. A card moved onto another player's Board lands in the **current round's Column**
and its Power counts toward that player's total from then on. Rulebook's Combat section now
defines this explicitly and states where moved cards land.

**Remaining copyedit item, not a rules question:** Grup Scrooge's printed card text says "an
opponent's **area**" while the rulebook now standardizes on **Board**. Recommend re-printing that
card's text as "opponent's Board" to match — see Section 3.

### 1j. "Move any card" abilities — RESOLVED (both redesigned)
Surfaced by simulating actual games: Displeased Avian and Voodude both came out as extreme
outliers (73–75% combat win rate) under the initial "can steal an opponent's card" assumption.
Both have now been redefined:
- **Displeased Avian**: can only move a card off its own board — a defensive tool for ejecting a
  negative-Power card an opponent dumped on you. Simulated win rate normalized to ~40–43%.
- **Voodude** (stats unchanged, -2 Bean/2 Power): destroy the strongest card anywhere in play,
  then Voodude moves into that card's former board/column slot. Simulated win rate normalized to
  ~31%.
- **Captain Crunch** (stats unchanged, -2 Bean/2 Power), also redesigned in the same pass: no
  longer moves itself — instead it moves the strongest card among the *other* combat participants
  onto whichever of them is currently weakest, a pure threat-redistribution tool with no
  self-harm. Simulated win rate normalized from 7.9–9.5% to ~40%.

**Printed card text for Voodude and Captain Crunch needs updating** to match these redesigns
before print — see Section 3.

### 1k. Duplicate-Hero rules — RESOLVED
Confirmed: the deck is **108 cards, two copies of each of the 54 designs**. Prepare's
discard-and-redraw and Combat's "cannot play duplicate Heroes" are real rules now, not dead text,
and are implemented/enforced in `simulate.py`.

### 1f. Debit's "extra Beans" (#41)
"+1 Power for every 2 extra Beans you have" — extra relative to what baseline? Total Beans
generated this combat? Beans left unspent? Needs a concrete definition to know its ceiling.

### 1g. Proctor Odd's transfer wording (#48)
"Draw a card and place it under this one; its power level is now this card's bean level" — as
worded it's ambiguous which card's stat changes to match which. Needs a rewrite for clarity
regardless of the intended direction.

### 1h. Flip mechanic — RESOLVED (not actually inconsistent)
Confirmed by designer: **Handfoot** flips 3 Bean/2 Power → **2 Bean/3 Power** (a Bean/Power swap;
I'd misread the mirrored digits on the card image). **Craig 8** flips 2/2 → **4 Bean/0 Power** (a
wholly new stat line, not a swap). Two different flavors of the same keyword, both intentional —
no fix needed.

### 1i. Port Melanin (#54) has no team icon — RESOLVED
Confirmed intentional by the designer — Port Melanin is deliberately teamless. Fits its own
ability ("+3 Power if this is the only card you play this round"): a lone-wolf card that
never benefits from Team Bonus by design. No fix needed.

---

## 2. Balance analysis

### Overall numbers
Across all 54 cards: Bean values sum to **-4** (average ≈ 0 per card — the resource is designed
net-neutral, as expected for something you generate and spend within the same combat). Power
values sum to **91** (average ≈ **1.69** per card), ranging from **-6** (Moonhawk) to **7** (Gym
Shark).

### Vanilla-card efficiency (Gym Shark vs. James Madison) — RESOLVED
Six cards have no ability text at all (confirmed intentional): James Madison (-5/6), Burger King
(3/1), The Corn Maiden (5/0), Gym Shark (-7/7), Tickle Monster (-1/3), Bee's Knees (0/2). Gym Shark
pays 7 Beans for 7 Power (1:1) vs. James Madison's 5 Beans for 6 Power (better than 1:1) despite a
harder-to-reach cost — flagged as a possible rate inconsistency, but **designer confirmed both are
fine as-is for now.** No change.

### High-Power cards mostly carry a real cost or drawback — except one
Bitey Whiteys (-3/6, must destroy one of your own cards), Shoulder Blades (-2/6, self-inflicted
"-2 Power" — see copyedit note below on whether that's a real second effect), James Madison
(-5/6, no ability) all pair big Power with a real cost. **Chair Beard is the outlier**: 0 Bean
cost, 5 Power, *and* an ability ("your other cards' abilities don't apply this round") — that
last part is a real drawback (it silences your own combos that round), but it still delivers the
second-highest Power in the deck for zero Bean investment. Recommend double-checking this one in
actual play; it may be fine once you weigh how often silencing your own abilities actually hurts,
but it's the one vanilla-adjacent card that doesn't fit the "big power = big cost" pattern.

### Team size vs. Team Bonus reliability — RESOLVED
Team sizes range from 4 (Turtle) to 7 (Bolt, Red2). Team Bonus needs 2+ same-team cards in a
single combat, drawn from a 7-card hand out of the 54-card deck. Larger teams are proportionally
*easier* to trigger the bonus with, not harder — expected same-team cards in a 7-card hand scales
directly with team size (~0.9 for a 7-card team like Bolt/Red2 vs. ~0.5 for the 4-card Turtle
team), making Turtle structurally the least likely team to ever trigger its own Team Bonus.
Flagged since Turtle's cards (Captain Trumpet, Gym Shark) happen to be individually strong, which
could be deliberate compensation — but **designer confirmed team sizes are fine as-is.** No change.

### The 3-card combo (Footrun Joyfun / Jetplace Joyface / Junkrat Crotchrocket) has one clearly stronger piece
All three require every member played in the same round to activate, which is a hard ask (uses 3
of your round's up-to-3 card slots on just the combo, leaving zero room for anything else that
round). Two of the three payoffs are minor (+1 Bean; draw a card), but Junkrat Crotchrocket's
payoff — "destroy one card from every other player" — is a multi-player board wipe. Given how
hard the combo already is to assemble (drawing and holding all three in one hand, then committing
your entire round to them), the actual payoff seems fine as the "big" reward for the hardest
combo in the deck; flagging mainly so you can confirm the power level is appropriately load-bearing
given how rarely it'll actually come together in games with normal hand sizes.

### Negative-Power cards — RESOLVED
Moonhawk (-2 Bean/-6 Power) and Grup Scrooge (-1/-3) work as intentional debuffs: their abilities
offload the negative Power onto someone else (Moonhawk's combo moves it away; Grup Scrooge moves
itself to an opponent's Board), and abilities resolve immediately after the round they're played
in (1a) directly into the current round's Column on the target's Board (1e) — so the move happens
*before* the final Power tally, and the card genuinely dumps its negative Power onto whoever it's
moved to. Both mechanics now fully check out end-to-end.

### Captain Crunch — RESOLVED (redesigned)
Originally simulated as the worst card in the deck (7.9-9.5% combat win rate) -- its old ability
shipped itself plus one more card to an opponent's board with no stated benefit. Redesigned
(stats unchanged, -2 Bean/2 Power): it no longer moves itself, and instead moves the strongest
card among the other combat participants onto whichever of them is currently weakest -- pure
threat redistribution, no self-harm. Simulated win rate normalized to ~40%. Card text needs
updating to match before print (see Section 3).

---

## 3. Copyedit list

Genuine errors (not stylistic joke names/spellings):

| Card / doc | Current text | Fix |
|---|---|---|
| Chair Beard (#12) | "Your other card's abilities don't apy this round" | "Your other cards' abilities don't apply this round" |
| Faceplant (#15) | "Either draw a crad or gain +2 power" | "Either draw a card or gain +2 Power" (also capitalize "Power" for consistency with other cards) |
| Grup Scrooge (#44) | "Move this card to an opponent's area" — printed as "opponets" on the card | "opponents" |
| Proctor Odd (#48) | "it's power level is now this card's bean level" | "its power level..." |
| Shoulder Blades (#45) | Ability box just says "-2 Power" | Either write this as a real effect clause (e.g. "This card enters play with -2 Power") or confirm it's meant as a plain restatement — as printed it reads like unfinished placeholder text, not an ability |
| Rulebook, Combat section | "Battleverse has two phases" | Only place the name "Battleverse" appears anywhere in the game — either use it consistently as the game's setting name elsewhere, or replace with "Unemployables" / drop the proper noun if it was a leftover from an earlier draft |
| Grup Scrooge (#44) | "Move this card to an opponent's **area**" | Reprint as "opponent's **Board**" to match the now-standardized rulebook terminology (Board/Column, see resolved question 1e) |
| Voodude (#26) | "Swap places with any card on the board" | Reprint to match the redesign: "Destroy any card, then move this card to its location" (or similar) |
| Captain Crunch (#7) | "Choose an opponent's board: move this card and another card of your choice to it" | Reprint to match the redesign: "Move the strongest card from an opponent's board to the board of whichever opponent has the least Power" (or similar) |

Confirmed **intentional** and left as-is: "Defrilibatorator," "Digeridon't," "Smurtle Gurtle
Cheesecake Woman," "Craig 8," and other pun-based Hero names — these read as deliberate jokes, not
typos.

One item downgraded after re-checking the PDF directly: Accordion Joe's (#50) "its" is printed
correctly on the card — an earlier pass had flagged this in error.

---

## 4. Simulation results (3,000 simulated games)
Built `simulate.py`, a full game simulator implementing all 54 cards and the resolved rules above,
with heuristic "reasonable" AI decisions (not perfect play). Full results, methodology, and
assumptions in `simulation-results.md`. Headline takeaways already folded into Sections 1 and 2
above: question 1j (move-ability targeting) and the Captain Crunch/duplicate-Hero findings. Other
results: team win rates are tight (35.9%–43.6% band, aside from the intentionally teamless Port
Melanin), the 3-card combo triggers about as rarely as expected, and the two 2-card combos look
well-tuned.

## 5. Sample combat walkthroughs (verification)

Attempted three 2-player sample combats by hand, applying the rulebook plus card database exactly
as written, specifically to see where ambiguities in Section 1 actually block play (rather than
just being theoretical concerns):

- **Walkthrough A** (no combo/move cards, all round-tagged abilities): resolves cleanly either way
  under question 1a — round-tagged abilities happen to give the same final total whether resolved
  per-round or all at once, since none of them interact with each other. Confirms 1a doesn't matter
  for *simple* hands, only ones with move/destroy/combo interactions.
- **Walkthrough B** (includes Moonhawk + They combo): fully resolves now — abilities resolve after
  each round (1a) directly into the target's current-round Column (1e), so Moonhawk's owner avoids
  the -6 and it lands on whoever it's moved to instead.
- **Walkthrough C** (Team Bonus + Junkrat Crotchrocket trio): confirms the math in Section 2 by
  hand — assembling the 3-card combo does cost an entire round's plays, and the Team Bonus is easy
  to trigger for a 7-card team, harder for a 4-card team, exactly as the probability estimate
  predicted (team sizes confirmed fine as-is, no change needed).

**Bottom line:** all structural rules questions (1a–1e) are now resolved and reflected in the
rulebook. The remaining open items are narrower text/wording fixes (1f, 1g) and the copyedit list
in Section 3 — nothing left blocks playtesting any hand in the deck.
