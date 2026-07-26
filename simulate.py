"""
Unemployables: Unplayable -- balance simulator.

Simulates games using the rules as resolved in review-findings.md:
  - Abilities resolve immediately after each round (not bundled at end of Round 3).
  - Each player has a Board with 3 Columns (one per round); moved cards land in the
    target's current-round Column.
  - Team Bonus: 2+ same-team cards on a Board => each of those cards +1 Power.
  - Only the lowest total-Power player(s) get Wounded (capped next hand-refill at 6).
  - Unopposed challenge = 2 Trophies. Contested win = 1 Trophy. First to 3 Trophies wins.

ASSUMPTIONS made to turn ambiguous/underspecified card text into code (all noted in the
final report, not silently):
  - Player count: 4, fixed turn rotation.
  - Deck is 108 cards: TWO copies of each of the 54 unique designs (confirmed by designer).
    Duplicate-Hero rules are therefore real and enforced: Prepare will discard-and-redraw a
    duplicate Hero from hand, and a single combat can never play two copies of the same
    Hero (across all 3 rounds combined, not just per round).
  - Named-partner Combos require BOTH/ALL partner cards be played by the SAME player in the
    same round (not across different players' boards).
  - Displeased Avian (confirmed by designer): can only move a card that is already on ITS
    OWN player's board -- a defensive tool for ejecting a negative-Power card an opponent
    dumped on you (e.g. via Grup Scrooge/Moonhawk). Implemented as: eject your own
    worst/most-negative card onto a random other player's board, only when that card's
    Power is actually negative (otherwise there's nothing to gain and the AI leaves it).
  - Voodude (confirmed redesign, stats unchanged at -2 Bean/2 Power): destroy the single
    highest-Power card anywhere in play (any player's board), then Voodude itself moves
    into that destroyed card's former column/board slot. If the best target happened to be
    sitting on Voodude's own board (e.g. a dumped negative-Power card), this is pure
    upside; if the best target was an opponent's strong card, Voodude trades removing it
    for gifting that opponent its own 2 Power in exchange.
  - Captain Crunch (confirmed redesign, stats unchanged at -2 Bean/2 Power): no longer
    moves itself. Instead it finds the single highest-Power card among the OTHER
    combat participants' boards and relocates it onto whichever other participant
    currently has the lowest total Power -- a pure threat-redistribution tool with no
    self-harm. Needs 3+ combat participants to have a valid "weaker opponent" target;
    with only 2 participants it's a no-op that turn (just sits at its printed stats).
  - Porthole: look at top 3 of deck, keep the highest-Power one into hand, return the other
    two to the bottom of the deck.
  - Proctor Odd: draw a card, then gain Power equal to this card's own Bean value (so with
    Bean 0, this is effectively just "draw a card"). Ambiguous wording, simplified.
  - Debit's "extra Beans" = current Bean balance (generated minus spent) at time of
    resolution, floor-divided by 2.
  - Jonnakiss's "return to hand to draw a card" is not used by the AI (kept simple: it just
    contributes its printed stats). Noted as an unused/unmodeled option, not a balance claim.
  - Wound: caps the very next Prepare-phase net hand size at 6 instead of 7 (discard 3
    instead of 2 that turn), then clears.
  - Deck reshuffles from the discard pile (leaving the top card behind) if it empties.
  - Ties for highest Power in combat all receive a Trophy; ties for lowest all get Wounded.

This is a balance-signal tool, not a rules-perfect digital implementation -- some of the
weirder single-card interactions are approximated. Where an approximation could matter, it's
listed above.
"""

import random
import statistics
from collections import Counter, defaultdict
from itertools import combinations


def _to_py(x):
    """Normalize a value that may have arrived from JS via Pyodide's .send(). Scalars
    (str/int/bool/None) already cross as native Python types; arrays arrive as a JsProxy
    and need an explicit conversion to a real Python list."""
    return x.to_py() if hasattr(x, "to_py") else x

random.seed()

# ---------------------------------------------------------------------------
# Card data: id, name, bean, power, team, ability tag, ability params, flip data
# ---------------------------------------------------------------------------
# ability tag / params vocabulary:
#   ('none', {})
#   ('round_bonus', {round:int -> {'power':x,'bean':y}, ...})       one or more rounds
#   ('round_bonus_dynamic', {'round':n, 'stat':'unplayed'|'extra_beans_half'})
#   ('cond_wound', {'power':x})
#   ('cond_solo', {'power':x})
#   ('constraint_round1', {})            # Speedo: must be played round 1
#   ('extra_slot', {})                   # Contortoise: can be a 4th card in a round
#   ('shield_round', {'round':n})        # Digeridon't: cards can't be destroyed this combat
#   ('immune', {})                       # Guy Yacht: can't be moved or destroyed
#   ('silence_own_round', {})            # Chair Beard
#   ('self_debuff', {'power':-2})        # Shoulder Blades
#   ('destroy_own', {})                  # Bitey Whiteys
#   ('destroy_any', {})                  # Mute-Ant
#   ('destroy_any_round', {'round':n})   # Machete Man
#   ('destroy_self_for_any', {})         # Floss
#   ('draw', {'n':1})                    # Jeanne Gris / Winter Wondergirl
#   ('draw_and_play', {})                # Pakrat
#   ('play_from_discard', {})            # Defrilibatorator
#   ('scry_draw', {'n':3})               # Porthole
#   (Belt Tungus has no active/on-play ability tag -- its "immediately replaces a
#    destroyed card while in hand" effect is passive and handled centrally by
#    Game._mark_destroyed(), triggered whenever ANY card is destroyed, not on play.)
#   ('remove_ability', {})               # Accordion Joe
#   ('draw_place_under', {})             # Proctor Odd
#   ('move_self_round', {'round':n})     # Grup Scrooge
#   ('move_own_out', {})                 # Displeased Avian: eject own worst card defensively
#   ('voodude_destroy_move', {})         # Voodude: destroy best target, move self to its spot
#   ('redirect_threat', {})              # Captain Crunch: move an opponent's best card to
#                                         # whichever other opponent is currently weakest
#   ('combo', {'group': 'name'})         # named combo participant
#   ('bean_per_other', {})               # Brain Freeze: +1 bean per other card played this round

BELT_TUNGUS_ID = 49  # referenced by Game._mark_destroyed() for its reactive replacement ability

CARDS = [
    (1, "Mr Unemployable", 0, 1, "VU", ('round_bonus', {3: {'power': 2}})),
    (2, "James Madison", -5, 6, "VU", ('none', {})),
    (3, "Porthole", 1, 1, "VU", ('scry_draw', {'n': 3})),
    (4, "Handfoot", 3, 2, "VU", ('round_bonus', {2: {'flip': True}})),  # flip handled via flip_at
    (5, "Burger King", 3, 1, "VU", ('none', {})),
    (6, "Defrilibatorator", -1, 1, "BOLT", ('play_from_discard', {})),
    (7, "Captain Crunch", -1, 2, "BOLT", ('redirect_threat', {})),
    (8, "Floss", 0, 2, "BOLT", ('destroy_self_for_any', {})),
    (9, "Snow Angel", 2, 1, "BOLT", ('combo', {'group': 'snow_christingle'})),
    (10, "Brain Freeze", 2, 1, "BOLT", ('bean_per_other', {})),
    (11, "Man Guy", -4, 2, "BOLT", ('cond_wound', {'power': 4})),
    (12, "Chair Beard", 0, 5, "BOLT", ('silence_own_round', {})),
    (13, "Bitey Whiteys", -3, 6, "RED2", ('destroy_own', {})),
    (14, "Speedo", 4, 1, "RED2", ('constraint_round1', {})),
    (15, "Faceplant", 2, 2, "RED2", ('draw', {'n': 1, 'or_power': 2})),
    (16, "Ultraviolet", 2, 1, "RED2", ('round_bonus', {1: {'power': 1}})),
    (17, "Jonnakiss", 2, 2, "RED2", ('none', {})),  # bounce-for-draw option unmodeled
    (18, "Digeridon't", 1, 0, "RED2", ('shield_round', {'round': 2})),
    (19, "Grom From Brawl Stars", -1, 3, "RED2", ('round_bonus', {2: {'power': 1}})),
    (20, "Moonhawk", -2, -6, "HAWK", ('combo', {'group': 'moonhawk_they'})),
    (21, "Guy Yacht", -3, 3, "HAWK", ('immune', {})),
    (22, "Displeased Avian", -3, 2, "HAWK", ('move_own_out', {})),
    (23, "Iron Pan", -1, 2, "HAWK", ('combo', {'group': 'ironpan_dishwasher'})),
    (24, "They", 2, 1, "HAWK", ('combo', {'group': 'moonhawk_they'})),
    (25, "The Corn Maiden", 5, 0, "HAWK", ('none', {})),
    (26, "Voodude", -2, 1, "V", ('voodude_destroy_move', {})),
    (27, "Mute-Ant", -3, 1, "V", ('destroy_any', {})),
    (28, "Footrun Joyfun", 0, 1, "V", ('combo', {'group': 'trio'})),
    (29, "Jetplace Joyface", 0, 1, "V", ('combo', {'group': 'trio'})),
    (30, "Junkrat Crotchrocket", 0, 1, "V", ('combo', {'group': 'trio'})),
    (31, "Dishwasher", 2, 1, "V", ('combo', {'group': 'ironpan_dishwasher'})),
    (32, "Smurtle Gurtle Cheesecake Woman", 0, 1, "TURTLE", ('round_bonus', {1: {'power': 3}})),
    (33, "Captain Trumpet", 1, 1, "TURTLE", ('round_bonus', {1: {'bean': 2}, 2: {'bean': 1, 'power': 1}, 3: {'power': 2}})),
    (34, "Contortoise", 1, 2, "TURTLE", ('extra_slot', {})),
    (35, "Gym Shark", -7, 7, "TURTLE", ('none', {})),
    (36, "Powerpoint", 2, 2, "Y", ('round_bonus', {2: {'bean': 1}, 3: {'bean': 2}})),
    (37, "Tickle Monster", -1, 3, "Y", ('none', {})),
    (38, "Jeanne Gris", 2, 2, "Y", ('draw', {'n': 1})),
    (39, "Winter Wondergirl", -1, 2, "Y", ('draw', {'n': 2})),
    (40, "Yeast", 0, 2, "Y", ('round_bonus_dynamic', {'round': 3, 'stat': 'unplayed'})),
    (41, "Debit", 0, 1, "Y", ('round_bonus_dynamic', {'round': 3, 'stat': 'extra_beans_half'})),
    (42, "Shan't Dance", 1, 1, "TOPHAT", ('round_bonus', {2: {'bean': 3}})),
    (43, "Machete Man", -2, 1, "TOPHAT", ('destroy_any_round', {'round': 3})),
    (44, "Grup Scrooge", 0, -3, "TOPHAT", ('move_self_round', {'round': 1})),
    (45, "Shoulder Blade", -2, 6, "TOPHAT", ('self_debuff', {'power': -2})),
    (46, "Bee's Knees", 0, 2, "TOPHAT", ('none', {})),
    (47, "Captain Christingle", 1, 2, "TOPHAT", ('combo', {'group': 'snow_christingle'})),
    (48, "Proctor Odd", 0, 1, "NODES", ('draw_place_under', {})),
    (49, "Belt Tungus", 0, 2, "NODES", ('none', {})),  # reactive-from-hand ability, see BELT_TUNGUS_ID / _mark_destroyed
    (50, "Accordion Joe", -1, 1, "NODES", ('remove_ability', {})),
    (51, "Pakrat", 2, 2, "NODES", ('draw_and_play', {})),
    (52, "Glubsmack McDougie", 1, 2, "NODES", ('round_bonus', {3: {'bean': -1, 'power': 1}})),
    (53, "Craig 8", 2, 2, "NODES", ('none', {})),  # flip handled via flip_at
    (54, "Port Melanin", 0, 1, "NONE", ('cond_solo', {'power': 4})),
]

# Human-readable ability text for each card -- matches current behavior (redesigned cards
# describe their current ability, not the original printed text; typos from the printed
# cards are corrected here rather than reproduced). Empty string = vanilla, no ability.
CARD_ABILITY_TEXT = {
    1: "Round 3: +2 Power",
    2: "",
    3: "Look at the top three cards of the deck, draw one and either add it to your hand or play it to this round",
    4: "Round 2: Flip this card (swaps Bean and Power)",
    5: "",
    6: "Choose a card from the discard pile and play it to this round",
    7: "Move the strongest card from an opponent's board to whichever opponent has the least Power -- this card moves there too",
    8: "At any time, you may destroy this card to destroy another card of your choice",
    9: "Combo: Captain Christingle -- +2 Beans, +2 Power",
    10: "+1 Bean for every other card you play this round",
    11: "+4 Power if you have a Wound",
    12: "Your other cards' abilities don't apply this round",
    13: "Destroy one of your cards",
    14: "This card must be played on Round 1",
    15: "Either draw a card or gain +2 Power",
    16: "Round 1: +1 Power",
    17: "At any point, you may return this card to your hand to draw a card",
    18: "Round 2: Your cards can't be destroyed during this combat",
    19: "Round 2: +1 Power",
    20: "Combo: They -- Move this card to another player's board",
    21: "This card can't be moved or destroyed",
    22: "Move one of your own cards to another player's board (defensive -- great for getting rid of a card someone dumped on you)",
    23: "Combo: Dishwasher -- +2 Power",
    24: "Combo: Moonhawk -- Destroy this card",
    25: "",
    26: "Destroy the strongest card in play, then move this card to its former spot",
    27: "Destroy any card",
    28: "Combo: Jetplace Joyface + Junkrat Crotchrocket -- +1 Bean",
    29: "Combo: Footrun Joyfun + Junkrat Crotchrocket -- Draw a card",
    30: "Combo: Footrun Joyfun + Jetplace Joyface -- Destroy one card from every other player",
    31: "Combo: Iron Pan -- +2 Beans",
    32: "Round 1: +3 Power",
    33: "Round 1: +2 Beans / Round 2: +1 Bean, +1 Power / Round 3: +2 Power",
    34: "This card can be played as a 4th card in any round",
    35: "",
    36: "Round 2: +1 Bean / Round 3: +2 Beans",
    37: "",
    38: "Draw a card",
    39: "Draw 2 cards",
    40: "Round 3: +1 Power for each of your unplayed cards this combat",
    41: "Round 3: +1 Power for every 2 leftover Beans you have",
    42: "Round 2: +3 Beans",
    43: "Round 3: Destroy any card",
    44: "Round 1: Move this card to an opponent's board",
    45: "Enters play with -2 Power",
    46: "",
    47: "Combo: Snow Angel -- +2 Beans, +2 Power",
    48: "Draw a card and place it under this one; this card gains Power equal to its own Bean value",
    49: "If one of your cards is destroyed while this is in your hand, this card immediately replaces it",
    50: "Choose any card played this round and remove its ability",
    51: "Draw a card and play it to this round",
    52: "Round 3: -1 Bean, +1 Power",
    53: "You can flip this card when played (changes stats to 4 Bean / 0 Power)",
    54: "+4 Power if this is the only card you play this round",
}


def description_of(cid):
    return CARD_ABILITY_TEXT.get(cid, "")


# Flip data: card id -> (new_bean, new_power), and which round it happens (None = optional/on play)
FLIP = {
    4: (2, 3, 2),    # Handfoot: swap to 2/3 at round 2
    53: (4, 0, None),  # Craig 8: flip to 4/0, optional on play -- AI always flips if it improves board
}

COMBOS = {
    'snow_christingle': {'cards': ['Snow Angel', 'Captain Christingle'], 'bonus': {'bean': 2, 'power': 2}},
    'ironpan_dishwasher': {'cards': ['Iron Pan', 'Dishwasher'],
                            'self_bonus': {'Iron Pan': {'power': 2}, 'Dishwasher': {'bean': 2}}},
    'trio': {'cards': ['Footrun Joyfun', 'Jetplace Joyface', 'Junkrat Crotchrocket']},
    'moonhawk_they': {'cards': ['Moonhawk', 'They']},
}

CARD_BY_ID = {c[0]: c for c in CARDS}
CARD_BY_NAME = {c[1]: c for c in CARDS}
ALL_IDS = [c[0] for c in CARDS]


def base_bean(cid):
    return CARD_BY_ID[cid][2]


def base_power(cid):
    return CARD_BY_ID[cid][3]


def team_of(cid):
    return CARD_BY_ID[cid][4]


def name_of(cid):
    return CARD_BY_ID[cid][1]


def ability_of(cid):
    return CARD_BY_ID[cid][5]


AVG_VALUE = statistics.mean(base_power(c) + 0.3 * base_bean(c) for c in ALL_IDS)


def card_value(cid):
    return base_power(cid) + 0.3 * base_bean(cid)


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

class Entry:
    """A card sitting on a Board (in a Column) during a combat."""
    __slots__ = ('cid', 'owner', 'bonus_power', 'bonus_bean', 'ability_disabled',
                 'destroyed', 'flipped')

    def __init__(self, cid, owner):
        self.cid = cid
        self.owner = owner
        self.bonus_power = 0
        self.bonus_bean = 0
        self.ability_disabled = False
        self.destroyed = False
        self.flipped = False

    def power(self):
        p = base_power(self.cid)
        if self.flipped:
            p = FLIP[self.cid][1]
        return p + self.bonus_power

    def bean(self):
        b = base_bean(self.cid)
        if self.flipped:
            b = FLIP[self.cid][0]
        return b + self.bonus_bean


class Player:
    def __init__(self, idx):
        self.idx = idx
        self.hand = []
        self.trophies = 0
        self.wound_pending = False  # capped next prepare
        self.columns = [[], [], []]
        self.bean_balance = 0
        self.shield_active = False
        self.extra_slot_used = False

    def board_all_entries(self):
        return [e for col in self.columns for e in col if not e.destroyed]

    def total_power(self):
        return sum(e.power() for e in self.board_all_entries())


class Game:
    def __init__(self, n_players=4, human_idx=None):
        self.n = n_players
        self.human_idx = human_idx
        self.players = [Player(i) for i in range(n_players)]
        self.deck = ALL_IDS + ALL_IDS  # 108 cards: two copies of each of the 54 designs
        random.shuffle(self.deck)
        self.discard = []
        self.trader = []
        self.stats = defaultdict(Counter)
        self.combo_triggers = Counter()
        self.combats = 0
        self.unopposed = 0
        self.wounds_given = 0
        self.turns = 0
        self.card_played = Counter()
        self.card_combat_won = Counter()
        self.team_played = Counter()
        self.team_combat_won = Counter()

        for p in self.players:
            for _ in range(7):
                p.hand.append(self._draw_raw())
        for _ in range(4):
            self.trader.append(self._draw_raw())
        self.discard.append(self._draw_raw())

    # -- deck plumbing --
    def _draw_raw(self):
        if not self.deck:
            if len(self.discard) > 1:
                top = self.discard[-1]
                self.deck = self.discard[:-1]
                random.shuffle(self.deck)
                self.discard = [top]
            else:
                return None
        return self.deck.pop() if self.deck else None

    def draw_to_hand(self, p, n=1):
        for _ in range(n):
            c = self._draw_raw()
            if c is not None:
                p.hand.append(c)

    def _mark_destroyed(self, entry):
        """Central destroy path -- every place in the engine that destroys a card must
        call this (never set .destroyed directly) so Belt Tungus's reactive replacement
        ("If one of your cards is destroyed while this is in your hand, this card
        immediately replaces it") fires no matter which ability caused the destruction,
        including a card destroying itself."""
        if entry.destroyed:
            return
        entry.destroyed = True
        owner = self.players[entry.owner]
        if BELT_TUNGUS_ID in owner.hand:
            for col in owner.columns:
                if entry in col:
                    owner.hand.remove(BELT_TUNGUS_ID)
                    replacement = Entry(BELT_TUNGUS_ID, entry.owner)
                    col.append(replacement)
                    self._played_this_combat[entry.owner].append(replacement)
                    break

    # -- prepare phase --
    def prepare(self, p):
        for _ in range(2):
            candidates = []
            for c in self.trader:
                candidates.append(('trader', c))
            if self.discard:
                candidates.append(('discard', self.discard[-1]))
            candidates.sort(key=lambda x: card_value(x[1]), reverse=True)
            if candidates and card_value(candidates[0][1]) > AVG_VALUE:
                src, cid = candidates[0]
                if src == 'trader':
                    self.trader.remove(cid)
                else:
                    self.discard.pop()
                p.hand.append(cid)
            else:
                self.draw_to_hand(p, 1)

        for _ in range(10):
            counts = Counter(p.hand)
            dup_id = next((cid for cid, n in counts.items() if n > 1), None)
            if dup_id is None:
                break
            p.hand.remove(dup_id)
            self.discard.append(dup_id)
            self.draw_to_hand(p, 1)

        discard_n = 3 if p.wound_pending else 2
        p.wound_pending = False
        if len(p.hand) > discard_n:
            p.hand.sort(key=card_value)
            worst = p.hand[:discard_n]
            for cid in worst:
                p.hand.remove(cid)
                self.discard.append(cid)

        while len(self.trader) < 4:
            c = self._draw_raw()
            if c is None:
                break
            self.trader.append(c)

    def _apply_draw_choice(self, p, choice):
        """choice is 'deck', 'discard', or an int Trader card id (see prepare_interactive)."""
        if choice == 'deck':
            self.draw_to_hand(p, 1)
        elif choice == 'discard':
            if self.discard:
                p.hand.append(self.discard.pop())
            else:
                self.draw_to_hand(p, 1)
        else:
            cid = int(choice)
            if cid in self.trader:
                self.trader.remove(cid)
                p.hand.append(cid)
            else:
                self.draw_to_hand(p, 1)

    def prepare_interactive(self, p):
        """Generator version of prepare() for the human player. Yields DecisionRequest
        dicts and receives the human's answer via .send(). Mirrors prepare() exactly, just
        with each automatic choice replaced by a yield/response pair."""
        for i in range(2):
            choice = yield {
                'type': 'prepare_draw',
                'player': p.idx,
                'draw_number': i + 1,
                'hand': list(p.hand),
                'trader': list(self.trader),
                'discard_top': self.discard[-1] if self.discard else None,
                'deck_remaining': len(self.deck),
            }
            self._apply_draw_choice(p, choice)

        while True:
            counts = Counter(p.hand)
            dup_id = next((cid for cid, n in counts.items() if n > 1), None)
            if dup_id is None:
                break
            choice = yield {
                'type': 'prepare_dedupe',
                'player': p.idx,
                'duplicate_id': dup_id,
                'duplicate_name': name_of(dup_id),
                'hand': list(p.hand),
            }
            if choice == 'redraw':
                p.hand.remove(dup_id)
                self.discard.append(dup_id)
                self.draw_to_hand(p, 1)
            else:
                break

        discard_n = 3 if p.wound_pending else 2
        p.wound_pending = False
        if len(p.hand) > discard_n:
            chosen = _to_py(
                (yield {
                    'type': 'prepare_discard',
                    'player': p.idx,
                    'hand': list(p.hand),
                    'count': discard_n,
                })
            )
            for cid in chosen:
                if cid in p.hand:
                    p.hand.remove(cid)
                    self.discard.append(cid)

        while len(self.trader) < 4:
            c = self._draw_raw()
            if c is None:
                break
            self.trader.append(c)

    # -- decision heuristics --
    def hand_power_estimate(self, p):
        """Rough estimate of best achievable combat Power from current hand."""
        cards = sorted(p.hand, key=lambda c: base_power(c), reverse=True)
        balance = 0
        total = 0
        played = 0
        for cid in cards:
            if played >= 9:
                break
            b = base_bean(cid)
            if b < 0 and balance + b < 0:
                continue
            balance += b
            total += base_power(cid)
            played += 1
        return total

    def wants_to_challenge(self, p):
        est = self.hand_power_estimate(p)
        threshold = 9  # tuned so challenges happen at a reasonable pace
        prob = 1 / (1 + pow(2.71828, -(est - threshold) / 2.5))
        return random.random() < max(prob, 0.03)

    def wants_to_join(self, p, challenger_est):
        est = self.hand_power_estimate(p)
        prob = 1 / (1 + pow(2.71828, -(est - challenger_est * 0.65) / 3))
        return random.random() < prob

    # -- combat --
    def run_combat(self, challenger):
        self.combats += 1
        joiners = [challenger]
        challenger_est = self.hand_power_estimate(self.players[challenger])
        for i, p in enumerate(self.players):
            if i == challenger:
                continue
            if self.wants_to_join(p, challenger_est):
                joiners.append(i)

        if len(joiners) == 1:
            self.unopposed += 1
            self.players[challenger].trophies += 2
            return

        self._played_this_combat = defaultdict(list)  # owner_at_play_time -> [Entry, ...]
        for i in joiners:
            self.players[i].columns = [[], [], []]
            self.players[i].bean_balance = 0
            self.players[i].shield_active = False

        # plan plays for each participant across 3 rounds greedily
        plans = {}
        for i in joiners:
            plans[i] = self._plan_rounds(self.players[i])

        for rnd in range(3):
            for i in joiners:
                p = self.players[i]
                for cid in plans[i][rnd]:
                    if cid in p.hand:
                        p.hand.remove(cid)
                        e = Entry(cid, i)
                        if cid in FLIP and FLIP[cid][2] == rnd + 1:
                            e.flipped = True
                        p.columns[rnd].append(e)
                        self._played_this_combat[i].append(e)

            # resolve abilities revealed this round, in fixed id order across all boards
            all_entries_this_round = []
            for i in joiners:
                all_entries_this_round.extend((i, e) for e in self.players[i].columns[rnd])
            all_entries_this_round.sort(key=lambda x: x[1].cid)

            for owner_i, e in all_entries_this_round:
                if e.destroyed:
                    continue
                self._resolve_ability(e, owner_i, rnd, joiners, all_entries_this_round)

        # Team Bonus
        for i in joiners:
            p = self.players[i]
            teams_count = Counter(team_of(e.cid) for e in p.board_all_entries())
            for e in p.board_all_entries():
                t = team_of(e.cid)
                if t != "NONE" and teams_count[t] >= 2:
                    e.bonus_power += 1

        totals = {i: self.players[i].total_power() for i in joiners}
        best = max(totals.values())
        worst = min(totals.values())
        winners = [i for i in joiners if totals[i] == best]
        losers = [i for i in joiners if totals[i] == worst]

        for i in joiners:
            for e in self._played_this_combat[i]:
                self.card_played[e.cid] += 1
                self.team_played[team_of(e.cid)] += 1
        for i in winners:
            # credit every card the winning player played this combat, whether or not it
            # personally survived to the final tally (self-sacrifice/utility cards can
            # still have helped their owner win even though they destroy themselves)
            for e in self._played_this_combat[i]:
                self.card_combat_won[e.cid] += 1
                self.team_combat_won[team_of(e.cid)] += 1

        for i in winners:
            self.players[i].trophies += 1
        if best != worst:
            for i in losers:
                self.players[i].wound_pending = True
                self.wounds_given += 1

        for i in joiners:
            p = self.players[i]
            for cid in [e.cid for e in p.board_all_entries()]:
                self.discard.append(cid)
            # Always draw back to 7 here -- the Wound only caps the *next* Prepare phase's
            # draw (handled in prepare()/prepare_interactive()), not this immediate refill.
            need = max(0, 7 - len(p.hand))
            self.draw_to_hand(p, need)
            p.columns = [[], [], []]

        while len(self.trader) < 4:
            c = self._draw_raw()
            if c is None:
                break
            self.trader.append(c)

        for i in joiners:
            self.stats['power_totals'][i] += totals[i]

    def _max_round_slots(self, p):
        if p.extra_slot_used:
            return 3
        return 4 if any(ability_of(c)[0] == 'extra_slot' for c in p.hand) else 3

    def _validate_round_play(self, p, chosen, rnd):
        """Defensive server-side enforcement of the round-size cap and Bean affordability
        (the rulebook: a negative-Bean Hero can only be played if enough Beans were
        generated earlier in the combat OR DURING THE CURRENT ROUND -- cards revealed
        simultaneously, so the whole set's aggregate Bean total is what matters, not the
        order the human happened to click them in). The UI is expected to prevent invalid
        picks in the first place; this is just a backstop so the engine can never end up
        in an illegal state.

        Checks the full requested set as a whole first (order-independent); only falls
        back to a Bean-value-descending greedy trim if the whole set genuinely isn't
        affordable together."""
        cap = self._max_round_slots(p)
        hand_pool = list(p.hand)
        filtered = []
        for cid in chosen:
            if cid in hand_pool:
                hand_pool.remove(cid)
                filtered.append(cid)
        filtered = filtered[:cap]

        if p.bean_balance + self._combo_bean(filtered, rnd) >= 0:
            return filtered

        balance = p.bean_balance
        valid = []
        for cid in sorted(filtered, key=base_bean, reverse=True):
            b = base_bean(cid)
            if b < 0 and balance + b < 0:
                continue
            balance += b
            valid.append(cid)
        return valid

    def run_combat_interactive(self, challenger):
        """Generator version of run_combat() for a game with a human player. Identical
        rules/resolution to run_combat() -- AI participants use the exact same heuristics
        (_plan_rounds, wants_to_join, _resolve_ability) with no yields at all. Only the
        human player's decisions (join/decline, which cards to play each round, and the
        explicitly-"choice" ability targets) pause via yield."""
        self.combats += 1
        joiners = [challenger]
        challenger_est = self.hand_power_estimate(self.players[challenger])
        for i, p in enumerate(self.players):
            if i == challenger:
                continue
            if i == self.human_idx:
                decision = yield {
                    'type': 'join_or_decline',
                    'player': i,
                    'challenger': challenger,
                    'hand': list(p.hand),
                }
                if decision == 'join':
                    joiners.append(i)
            elif self.wants_to_join(p, challenger_est):
                joiners.append(i)

        if len(joiners) == 1:
            self.unopposed += 1
            self.players[challenger].trophies += 2
            yield {'type': 'combat_unopposed', 'challenger': challenger}
            return

        self._played_this_combat = defaultdict(list)
        for i in joiners:
            self.players[i].columns = [[], [], []]
            self.players[i].bean_balance = 0
            self.players[i].shield_active = False
            self.players[i].extra_slot_used = False

        plans = {}
        for i in joiners:
            if i != self.human_idx:
                plans[i] = self._plan_rounds(self.players[i])

        for rnd in range(3):
            for i in joiners:
                p = self.players[i]
                if i == self.human_idx:
                    chosen = _to_py((yield {
                        'type': 'round_play',
                        'player': i,
                        'round': rnd + 1,
                        'hand': list(p.hand),
                        'bean_balance': p.bean_balance,
                        'max_slots': self._max_round_slots(p),
                    }))
                    for cid in self._validate_round_play(p, chosen, rnd):
                        if cid in p.hand:
                            p.hand.remove(cid)
                            e = Entry(cid, i)
                            if cid in FLIP and FLIP[cid][2] == rnd + 1:
                                e.flipped = True
                            p.columns[rnd].append(e)
                            self._played_this_combat[i].append(e)
                            if ability_of(cid)[0] == 'extra_slot':
                                p.extra_slot_used = True
                else:
                    for cid in plans[i][rnd]:
                        if cid in p.hand:
                            p.hand.remove(cid)
                            e = Entry(cid, i)
                            if cid in FLIP and FLIP[cid][2] == rnd + 1:
                                e.flipped = True
                            p.columns[rnd].append(e)
                            self._played_this_combat[i].append(e)

            all_entries_this_round = []
            for i in joiners:
                all_entries_this_round.extend((i, e) for e in self.players[i].columns[rnd])
            all_entries_this_round.sort(key=lambda x: x[1].cid)

            for owner_i, e in all_entries_this_round:
                if e.destroyed:
                    continue
                yield from self._resolve_ability_interactive(e, owner_i, rnd, joiners, all_entries_this_round)

        for i in joiners:
            p = self.players[i]
            teams_count = Counter(team_of(e.cid) for e in p.board_all_entries())
            for e in p.board_all_entries():
                t = team_of(e.cid)
                if t != "NONE" and teams_count[t] >= 2:
                    e.bonus_power += 1

        totals = {i: self.players[i].total_power() for i in joiners}
        best = max(totals.values())
        worst = min(totals.values())
        winners = [i for i in joiners if totals[i] == best]
        losers = [i for i in joiners if totals[i] == worst]

        for i in joiners:
            for e in self._played_this_combat[i]:
                self.card_played[e.cid] += 1
                self.team_played[team_of(e.cid)] += 1
        for i in winners:
            for e in self._played_this_combat[i]:
                self.card_combat_won[e.cid] += 1
                self.team_combat_won[team_of(e.cid)] += 1

        for i in winners:
            self.players[i].trophies += 1
        if best != worst:
            for i in losers:
                self.players[i].wound_pending = True
                self.wounds_given += 1

        for i in joiners:
            p = self.players[i]
            for cid in [e.cid for e in p.board_all_entries()]:
                self.discard.append(cid)
            # Always draw back to 7 here -- the Wound only caps the *next* Prepare phase's
            # draw (handled in prepare()/prepare_interactive()), not this immediate refill.
            need = max(0, 7 - len(p.hand))
            self.draw_to_hand(p, need)
            p.columns = [[], [], []]

        while len(self.trader) < 4:
            c = self._draw_raw()
            if c is None:
                break
            self.trader.append(c)

        for i in joiners:
            self.stats['power_totals'][i] += totals[i]

        yield {
            'type': 'combat_result',
            'joiners': joiners,
            'totals': totals,
            'winners': winners,
            'losers': losers,
        }

    # -- interactive ability targeting (human-owned cards only; AI cards are
    #    resolved exactly as before via the shared _resolve_ability) --
    def _target_request(self, subtype, e, pool):
        return {
            'type': 'ability_target',
            'subtype': subtype,
            'player': e.owner,
            'card': e.cid,
            'card_name': name_of(e.cid),
            'options': [
                {'uid': id(x), 'cid': x.cid, 'name': name_of(x.cid), 'owner': x.owner, 'power': x.power()}
                for x in pool
            ],
        }

    def _find_by_uid(self, uid, pool):
        uid = int(_to_py(uid))
        for x in pool:
            if id(x) == uid:
                return x
        return None

    def _destroy_by_uid(self, uid, pool):
        target = self._find_by_uid(uid, pool)
        if target:
            self._mark_destroyed(target)

    def _disable_by_uid(self, uid, pool):
        target = self._find_by_uid(uid, pool)
        if target:
            target.ability_disabled = True

    def _eligible_destroy_targets(self, owner_i, joiners):
        pool = []
        for i in joiners:
            if i == owner_i or self.players[i].shield_active:
                continue
            pool.extend([x for x in self.players[i].board_all_entries()
                         if not x.destroyed and ability_of(x.cid)[0] != 'immune'])
        return pool

    def _resolve_ability_interactive(self, e, owner_i, rnd, joiners, all_entries_this_round):
        if owner_i != self.human_idx:
            self._resolve_ability(e, owner_i, rnd, joiners, all_entries_this_round)
            return
        if e.ability_disabled or e.destroyed:
            return
        tag, params = ability_of(e.cid)
        p = self.players[owner_i]
        others = [i for i in joiners if i != owner_i]

        if tag == 'destroy_own':
            mine = [x for x in p.board_all_entries() if x is not e and not x.destroyed]
            if mine:
                uid = yield self._target_request(tag, e, mine)
                self._destroy_by_uid(uid, mine)
        elif tag in ('destroy_any', 'destroy_any_round'):
            if not (tag == 'destroy_any_round' and params.get('round') != rnd + 1):
                pool = self._eligible_destroy_targets(owner_i, joiners)
                if pool:
                    uid = yield self._target_request(tag, e, pool)
                    self._destroy_by_uid(uid, pool)
        elif tag == 'destroy_self_for_any':
            pool = []
            for i in joiners:
                if i == owner_i or self.players[i].shield_active:
                    continue
                pool.extend([x for x in self.players[i].board_all_entries()
                             if not x.destroyed and ability_of(x.cid)[0] != 'immune'])
            if pool:
                uid = yield self._target_request(tag, e, pool)
                self._destroy_by_uid(uid, pool)
            self._mark_destroyed(e)
        elif tag == 'play_from_discard':
            if self.discard and len(p.columns[rnd]) < 3:
                choice = _to_py((yield {
                    'type': 'ability_choice_discard', 'player': owner_i, 'card': e.cid,
                    'card_name': name_of(e.cid), 'discard': list(self.discard),
                }))
                if choice in self.discard:
                    self.discard.remove(choice)
                    ne = Entry(choice, owner_i)
                    p.columns[rnd].append(ne)
                    self._played_this_combat[owner_i].append(ne)
        elif tag == 'scry_draw':
            n = min(params.get('n', 3), len(self.deck))
            top = [self.deck.pop() for _ in range(n)]
            if top:
                choice = _to_py((yield {
                    'type': 'ability_choice_scry', 'player': owner_i, 'card': e.cid,
                    'card_name': name_of(e.cid), 'options': list(top),
                }))
                if choice in top:
                    top.remove(choice)
                    p.hand.append(choice)
                self.deck = top + self.deck
        elif tag == 'remove_ability':
            pool_pairs = [(oi, x) for oi, x in all_entries_this_round
                          if oi != owner_i and x is not e and not x.destroyed and not x.ability_disabled]
            options = [x for _, x in pool_pairs]
            if options:
                uid = yield self._target_request(tag, e, options)
                self._disable_by_uid(uid, options)
        elif tag == 'move_self_round':
            if params['round'] == rnd + 1 and others:
                target = others[0]
                if len(others) > 1:
                    target = int(_to_py((yield {
                        'type': 'ability_choice_opponent', 'player': owner_i, 'card': e.cid,
                        'card_name': name_of(e.cid), 'options': others,
                    })))
                p.columns[rnd].remove(e)
                e.owner = target
                self.players[target].columns[rnd].append(e)
        else:
            self._resolve_ability(e, owner_i, rnd, joiners, all_entries_this_round)
            return  # the shared resolver already applied the bean_balance update below

        p.bean_balance += e.bean() if tag != 'draw_place_under' else 0

    def snapshot(self):
        """Full serializable game state for the UI to render between generator steps."""
        return {
            'players': [
                {
                    'idx': pl.idx,
                    'hand': list(pl.hand) if pl.idx == self.human_idx else None,
                    'hand_size': len(pl.hand),
                    'trophies': pl.trophies,
                    'wounded': pl.wound_pending,
                    'columns': [
                        [{'cid': x.cid, 'name': name_of(x.cid), 'power': x.power(),
                          'bean': x.bean(), 'destroyed': x.destroyed, 'owner': x.owner}
                         for x in col]
                        for col in pl.columns
                    ],
                }
                for pl in self.players
            ],
            'trader': list(self.trader),
            'discard_top': self.discard[-1] if self.discard else None,
            'discard_count': len(self.discard),
            'deck_remaining': len(self.deck),
            'human_idx': self.human_idx,
        }

    def _combo_score(self, combo, round_index):
        """Planning-time Power estimate for a candidate combo, aware of round bonuses,
        self-debuffs, and named-combo synergy -- so the AI doesn't undervalue cards whose
        downside is designed to be moved onto someone else before the final tally."""
        names_in_combo = [name_of(c) for c in combo]
        total = 0
        for cid in combo:
            tag, params = ability_of(cid)
            score = base_power(cid)
            if tag == 'round_bonus':
                spec = params.get(round_index + 1)
                if spec:
                    score += spec.get('power', 0)
            elif tag == 'self_debuff':
                score += params['power']
            elif tag == 'move_self_round' and params['round'] == round_index + 1:
                score = 0
            elif tag == 'cond_solo' and len(combo) == 1:
                score += params['power']
            elif tag == 'combo':
                spec = COMBOS[params['group']]
                if set(spec['cards']).issubset(names_in_combo):
                    if params['group'] == 'snow_christingle':
                        score += spec['bonus']['power']
                    elif params['group'] == 'ironpan_dishwasher':
                        score += spec['self_bonus'].get(name_of(cid), {}).get('power', 0)
                    elif params['group'] == 'moonhawk_they':
                        score = 0  # Moonhawk moves off-board, They is destroyed -- both net 0
            total += score
        return total

    def _combo_bean(self, combo, round_index):
        names_in_combo = [name_of(c) for c in combo]
        total = 0
        for cid in combo:
            tag, params = ability_of(cid)
            b = base_bean(cid)
            if tag == 'round_bonus':
                spec = params.get(round_index + 1)
                if spec:
                    b += spec.get('bean', 0)
            elif tag == 'combo':
                spec = COMBOS[params['group']]
                if set(spec['cards']).issubset(names_in_combo):
                    if params['group'] == 'snow_christingle':
                        b += spec['bonus']['bean']
                    elif params['group'] == 'ironpan_dishwasher':
                        b += spec['self_bonus'].get(name_of(cid), {}).get('bean', 0)
            total += b
        return total

    def _plan_rounds(self, p):
        """For each round in turn, brute-force the best-scoring (highest total Power)
        combination of remaining hand cards that fits the per-round cap (3, or 4 if it
        includes a Contortoise-style extra-slot card) and is affordable given the running
        Bean balance -- prior rounds' generation plus this round's own generation, per the
        rulebook's "earlier in the combat or during the current round" wording."""
        pool = list(p.hand)
        forced_r1_raw = [c for c in pool if ability_of(c)[0] == 'constraint_round1']
        forced_r1 = []  # at most one copy of a given Hero, even if 2 copies are in hand --
        seen = set()    # duplicate Heroes can't both play in the same combat
        for c in forced_r1_raw:
            if c not in seen:
                forced_r1.append(c)
                seen.add(c)

        remaining = [c for c in pool if c not in forced_r1]

        rounds = [[], [], []]
        used_ids = set()
        for c in forced_r1:
            rounds[0].append(c)
            used_ids.add(c)

        balance = 0
        extra_slot_used = False
        for r in range(3):
            base_cap = 3 - len(rounds[r])
            eligible = [c for c in remaining if c not in used_ids]
            best_combo, best_score = (), -1
            max_size = min(len(eligible), base_cap + 1)
            for size in range(max_size + 1):
                for combo in combinations(eligible, size):
                    if len(set(combo)) != len(combo):
                        continue  # can't play two copies of the same Hero in one combat
                    has_extra = any(ability_of(c)[0] == 'extra_slot' for c in combo)
                    cap_here = base_cap + (1 if (has_extra and not extra_slot_used) else 0)
                    if size > cap_here:
                        continue
                    bean_sum = self._combo_bean(combo, r)
                    if balance + bean_sum < 0:
                        continue
                    score = self._combo_score(combo, r)
                    if score > best_score:
                        best_score, best_combo = score, combo
            rounds[r].extend(best_combo)
            for c in best_combo:
                remaining.remove(c)
                used_ids.add(c)
                if ability_of(c)[0] == 'extra_slot':
                    extra_slot_used = True
            balance += self._combo_bean(best_combo, r)
        return rounds

    def _resolve_ability(self, e, owner_i, rnd, joiners, all_entries_this_round):
        if e.ability_disabled or e.destroyed:
            return
        tag, params = ability_of(e.cid)
        p = self.players[owner_i]
        others = [i for i in joiners if i != owner_i]

        if tag == 'none':
            return
        if tag == 'round_bonus':
            spec = params.get(rnd + 1)
            if spec:
                e.bonus_power += spec.get('power', 0)
                e.bonus_bean += spec.get('bean', 0)
        elif tag == 'round_bonus_dynamic':
            if params['round'] == rnd + 1:
                if params['stat'] == 'unplayed':
                    e.bonus_power += len(p.hand)
                elif params['stat'] == 'extra_beans_half':
                    e.bonus_power += max(0, p.bean_balance // 2)
        elif tag == 'cond_wound':
            if p.wound_pending:
                e.bonus_power += params['power']
        elif tag == 'cond_solo':
            if sum(len(col) for col in p.columns) == 1:
                e.bonus_power += params['power']
        elif tag == 'self_debuff':
            e.bonus_power += params['power']
        elif tag == 'destroy_own':
            mine = [x for x in p.board_all_entries() if x is not e and not x.destroyed]
            if mine:
                victim = min(mine, key=lambda x: x.power())
                self._mark_destroyed(victim)
        elif tag in ('destroy_any', 'destroy_any_round'):
            if tag == 'destroy_any_round' and params.get('round') != rnd + 1:
                pass
            else:
                pool = []
                for oi in others:
                    if self.players[oi].shield_active:
                        continue
                    pool.extend([x for x in self.players[oi].board_all_entries()
                                 if not x.destroyed and ability_of(x.cid)[0] != 'immune'])
                if pool:
                    victim = max(pool, key=lambda x: x.power())
                    self._mark_destroyed(victim)
        elif tag == 'destroy_self_for_any':
            all_others = []
            for i in joiners:
                if i == owner_i or self.players[i].shield_active:
                    continue
                all_others.extend([x for x in self.players[i].board_all_entries()
                                    if not x.destroyed and ability_of(x.cid)[0] != 'immune'])
            if all_others:
                victim = max(all_others, key=lambda x: x.power())
                self._mark_destroyed(victim)
                self._mark_destroyed(e)
        elif tag == 'draw':
            self.draw_to_hand(p, params.get('n', 1))
        elif tag == 'draw_and_play':
            before = len(p.hand)
            self.draw_to_hand(p, 1)
            if len(p.hand) > before and len(p.columns[rnd]) < 3:
                new_c = p.hand.pop()
                ne = Entry(new_c, owner_i)
                p.columns[rnd].append(ne)
                self._played_this_combat[owner_i].append(ne)
        elif tag == 'play_from_discard':
            if self.discard and len(p.columns[rnd]) < 3:
                c = self.discard.pop()
                ne = Entry(c, owner_i)
                p.columns[rnd].append(ne)
                self._played_this_combat[owner_i].append(ne)
        elif tag == 'scry_draw':
            top = []
            for _ in range(min(params.get('n', 3), len(self.deck))):
                top.append(self.deck.pop())
            if top:
                best = max(top, key=lambda c: base_power(c))
                top.remove(best)
                p.hand.append(best)
                self.deck = top + self.deck
        elif tag == 'remove_ability':
            pool = [(oi, x) for oi, x in all_entries_this_round
                    if oi != owner_i and x is not e and not x.destroyed and not x.ability_disabled]
            if pool:
                oi, victim = max(pool, key=lambda t: base_power(t[1].cid))
                victim.ability_disabled = True
        elif tag == 'draw_place_under':
            self.draw_to_hand(p, 1)
            e.bonus_power += e.bean()  # simplified: gain power equal to own bean value
        elif tag == 'move_self_round':
            if params['round'] == rnd + 1 and others:
                target = random.choice(others)
                p.columns[rnd].remove(e)
                e.owner = target
                self.players[target].columns[rnd].append(e)
        elif tag == 'voodude_destroy_move':
            candidates = []
            for i2 in joiners:
                for r_idx, col in enumerate(self.players[i2].columns):
                    for x in col:
                        if x is e or x.destroyed or ability_of(x.cid)[0] == 'immune':
                            continue
                        candidates.append((i2, r_idx, x))
            if candidates:
                target_owner, target_r, target_entry = max(candidates, key=lambda t: t[2].power())
                self._mark_destroyed(target_entry)
                if e in p.columns[rnd]:
                    p.columns[rnd].remove(e)
                    e.owner = target_owner
                    self.players[target_owner].columns[target_r].append(e)
        elif tag == 'redirect_threat':
            if len(others) >= 2:
                opponent_entries = []
                for i2 in others:
                    for r_idx, col in enumerate(self.players[i2].columns):
                        for x in col:
                            if x.destroyed or ability_of(x.cid)[0] == 'immune':
                                continue
                            opponent_entries.append((i2, r_idx, x))
                if opponent_entries:
                    src_owner, src_r, target_entry = max(opponent_entries, key=lambda t: t[2].power())
                    weaker = [i2 for i2 in others if i2 != src_owner]
                    if weaker:
                        dest = min(weaker, key=lambda i2: self.players[i2].total_power())
                        self.players[src_owner].columns[src_r].remove(target_entry)
                        target_entry.owner = dest
                        self.players[dest].columns[src_r].append(target_entry)
                        # Captain Crunch follows the card it redirected to the same spot
                        if e in p.columns[rnd]:
                            p.columns[rnd].remove(e)
                            e.owner = dest
                            self.players[dest].columns[src_r].append(e)
        elif tag == 'move_own_out':
            mine = [x for x in p.board_all_entries()
                    if x is not e and not x.destroyed and ability_of(x.cid)[0] != 'immune']
            if mine and others:
                worst = min(mine, key=lambda x: x.power())
                if worst.power() < 0:
                    target = random.choice(others)
                    for r in range(3):
                        if worst in p.columns[r]:
                            p.columns[r].remove(worst)
                            worst.owner = target
                            self.players[target].columns[r].append(worst)
                            break
        elif tag == 'bean_per_other':
            others_this_round = len(p.columns[rnd]) - 1
            e.bonus_bean += max(0, others_this_round)
        elif tag == 'shield_round':
            if params['round'] == rnd + 1:
                p.shield_active = True
        elif tag == 'immune':
            pass
        elif tag == 'silence_own_round':
            for x in p.columns[rnd]:
                if x is not e:
                    x.ability_disabled = True
        elif tag == 'combo':
            self._resolve_combo(e, owner_i, rnd, params['group'])
        elif tag == 'constraint_round1':
            pass
        elif tag == 'extra_slot':
            pass

        p.bean_balance += e.bean() if tag != 'draw_place_under' else 0

    def _resolve_combo(self, e, owner_i, rnd, group_name):
        group = COMBOS[group_name]
        p = self.players[owner_i]
        names_needed = set(group['cards'])
        names_present = {name_of(x.cid) for x in p.columns[rnd] if not x.destroyed}
        if not names_needed.issubset(names_present):
            return

        self.combo_triggers[group_name] += 1

        if group_name == 'snow_christingle':
            e.bonus_power += group['bonus']['power']
            e.bonus_bean += group['bonus']['bean']
        elif group_name == 'ironpan_dishwasher':
            spec = group['self_bonus'].get(name_of(e.cid))
            if spec:
                e.bonus_power += spec.get('power', 0)
                e.bonus_bean += spec.get('bean', 0)
        elif group_name == 'trio':
            if name_of(e.cid) == 'Footrun Joyfun':
                e.bonus_bean += 1
            elif name_of(e.cid) == 'Jetplace Joyface':
                self.draw_to_hand(p, 1)
            elif name_of(e.cid) == 'Junkrat Crotchrocket':
                for i in self.players:
                    if i.idx == owner_i or i.shield_active:
                        continue
                    pool = [x for x in i.board_all_entries()
                            if not x.destroyed and ability_of(x.cid)[0] != 'immune']
                    if pool:
                        victim = max(pool, key=lambda x: x.power())
                        self._mark_destroyed(victim)
        elif group_name == 'moonhawk_they':
            if name_of(e.cid) == 'Moonhawk':
                others = [i for i in self.players if i.idx != owner_i]
                if others:
                    target = random.choice(others).idx
                    p.columns[rnd].remove(e)
                    e.owner = target
                    self.players[target].columns[rnd].append(e)
            elif name_of(e.cid) == 'They':
                self._mark_destroyed(e)


def joinable_targets(joiners):
    return joiners


# ---------------------------------------------------------------------------
# Full game loop
# ---------------------------------------------------------------------------

def run_game(n_players=4, max_turns=400):
    g = Game(n_players)
    turn = 0
    while turn < max_turns:
        turn += 1
        g.turns += 1
        cur = turn % n_players
        p = g.players[cur]
        if g.wants_to_challenge(p):
            g.run_combat(cur)
        else:
            g.prepare(p)

        if any(pl.trophies >= 3 for pl in g.players):
            break
    winner = max(g.players, key=lambda pl: pl.trophies)
    return g, winner, turn


_current_game = None  # exposes the Game instance living inside play_game_interactive's
                       # frame to the browser, since a generator's locals aren't reachable
                       # via pyodide.globals -- call get_snapshot() from JS instead


def get_snapshot():
    return _current_game.snapshot() if _current_game else None


def play_game_interactive(n_players=4, human_idx=0, max_turns=400):
    """Generator-driven full game with one human player among (n_players - 1) AI
    opponents. Yields DecisionRequest dicts for every human decision (and a couple of
    informational events); receives the human's answer via .send(). Call get_snapshot()
    after every step to render full state -- the yielded payloads only carry what's
    specific to that particular decision/event."""
    global _current_game
    g = Game(n_players, human_idx=human_idx)
    _current_game = g
    turn = 0
    while turn < max_turns:
        turn += 1
        g.turns += 1
        cur = turn % n_players
        p = g.players[cur]
        if cur == human_idx:
            action = yield {'type': 'prepare_action', 'player': cur}
            if action == 'challenge':
                yield from g.run_combat_interactive(cur)
            else:
                yield from g.prepare_interactive(p)
        else:
            if g.wants_to_challenge(p):
                yield from g.run_combat_interactive(cur)
            else:
                g.prepare(p)

        if any(pl.trophies >= 3 for pl in g.players):
            break

    winner = max(g.players, key=lambda pl: pl.trophies)
    yield {
        'type': 'game_over',
        'winner': winner.idx,
        'trophies': [pl.trophies for pl in g.players],
        'turns': turn,
    }
    return g


def run_batch(n_games=3000, n_players=4, min_sample=30):
    """Run a batch of games and return a structured results dict (used by both the text
    report in main() and the JSON export for the results website)."""
    win_by_seat = Counter()
    trophies_final = []
    turns_final = []
    combats_final = []
    unopposed_final = []
    wounds_final = []
    combo_totals = Counter()
    card_played = Counter()
    card_combat_won = Counter()
    team_played = Counter()
    team_combat_won = Counter()

    for _ in range(n_games):
        g, winner, turns = run_game(n_players)
        win_by_seat[winner.idx] += 1
        trophies_final.append(winner.trophies)
        turns_final.append(turns)
        combats_final.append(g.combats)
        unopposed_final.append(g.unopposed)
        wounds_final.append(g.wounds_given)
        for k, v in g.combo_triggers.items():
            combo_totals[k] += v
        card_played.update(g.card_played)
        card_combat_won.update(g.card_combat_won)
        team_played.update(g.team_played)
        team_combat_won.update(g.team_combat_won)

    cards = []
    for cid in ALL_IDS:
        played = card_played[cid]
        won = card_combat_won[cid]
        cards.append({
            'id': cid,
            'name': name_of(cid),
            'team': team_of(cid),
            'bean': base_bean(cid),
            'power': base_power(cid),
            'description': description_of(cid),
            'played': played,
            'win_rate': (won / played) if played else None,
            'low_sample': played < min_sample,
        })
    cards.sort(key=lambda c: (c['win_rate'] is None, c['win_rate']))

    teams = [{'team': t, 'played': played, 'win_rate': team_combat_won[t] / played}
             for t, played in team_played.most_common()]
    teams.sort(key=lambda t: t['win_rate'])

    combos = [{'name': k, 'total': v, 'per_game': v / n_games}
              for k, v in combo_totals.most_common()]

    return {
        'games': n_games,
        'players': n_players,
        'pacing': {
            'avg_turns': statistics.mean(turns_final),
            'min_turns': min(turns_final),
            'max_turns': max(turns_final),
            'avg_combats': statistics.mean(combats_final),
            'avg_unopposed': statistics.mean(unopposed_final),
            'unopposed_pct': sum(unopposed_final) / max(1, sum(combats_final)),
            'avg_wounds': statistics.mean(wounds_final),
            'seat_win_rate': [win_by_seat[i] / n_games for i in range(n_players)],
        },
        'combos': combos,
        'teams': teams,
        'cards': cards,
        'min_sample': min_sample,
    }


def print_report(results):
    n_games = results['games']
    pacing = results['pacing']
    print(f"Games simulated: {n_games} ({results['players']} players each)\n")
    print("Win rate by seat position (turn order):")
    for i, rate in enumerate(pacing['seat_win_rate']):
        print(f"  Seat {i}: {rate:.1%}")
    print()
    print(f"Avg turns per game: {pacing['avg_turns']:.1f} "
          f"(min {pacing['min_turns']}, max {pacing['max_turns']})")
    print(f"Avg combats per game: {pacing['avg_combats']:.2f}")
    print(f"Avg unopposed challenges per game: {pacing['avg_unopposed']:.2f} "
          f"({pacing['unopposed_pct']:.1%} of all combats)")
    print(f"Avg wounds given per game: {pacing['avg_wounds']:.2f}")
    print()
    print("Combo trigger totals across all games:")
    for c in results['combos']:
        print(f"  {c['name']}: {c['total']} ({c['per_game']:.3f} per game)")
    print()

    print("Team combat win-rate (share of combats won when a team's card was on the board):")
    for t in sorted(results['teams'], key=lambda t: -t['played']):
        print(f"  {t['team']:8s} played {t['played']:6d} times, won {t['win_rate']:.1%} of those combats")
    print()

    print(f"Per-card combat win-rate (min {results['min_sample']} plays), sorted low to high:")
    for c in results['cards']:
        if c['low_sample']:
            continue
        print(f"  {c['win_rate']:.1%}  (n={c['played']:5d})  {c['name']}")

    low_play = [c for c in results['cards'] if c['low_sample']]
    if low_play:
        print()
        print(f"Cards played fewer than {results['min_sample']} times total "
              "(too rare for a reliable win-rate read):")
        for c in sorted(low_play, key=lambda c: c['played']):
            print(f"  {c['played']:4d}  {c['name']}")


def main(n_games=3000, n_players=4, seed=None, json_path=None, quiet=False):
    if seed is not None:
        random.seed(seed)
    results = run_batch(n_games, n_players)
    if not quiet:
        print_report(results)
    if json_path:
        import json
        import datetime
        payload = dict(results)
        payload['generated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload['seed'] = seed
        with open(json_path, 'w') as f:
            json.dump(payload, f, indent=2)
        if not quiet:
            print(f"\nWrote JSON results to {json_path}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Unemployables: Unplayable balance simulator")
    parser.add_argument('--games', type=int, default=3000)
    parser.add_argument('--players', type=int, default=4)
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--json', type=str, default=None, help="Write JSON results to this path")
    parser.add_argument('--quiet', action='store_true', help="Suppress the text report")
    args = parser.parse_args()
    main(n_games=args.games, n_players=args.players, seed=args.seed,
         json_path=args.json, quiet=args.quiet)
