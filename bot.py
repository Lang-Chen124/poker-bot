"""
My Bot — Hand-strength + SPR strategy bot

Strategy overview:
  SPR (Stack-to-Pot Ratio) tiers:
    SPR < 3  -> Short stack: strong hands go all-in, medium hands call
    SPR 3-6  -> Medium stack: strong hands bet big (all-in on flop/turn/river)
    SPR > 6  -> Deep stack: standard bet sizing (50% / 75% pot)

  Strong Hands:
    - Preflop:  short stack all-in; otherwise raise 3x BB
    - Flop:     short stack all-in; medium stack raise 75%; deep stack raise 50% / re-raise 75%
    - Turn:     SPR < 6 all-in; deep stack raise 50% / re-raise 75%
    - River:    SPR < 6 all-in; deep stack raise 50% / re-raise 75%

  Weak Hands:
    - Not in blind -> fold immediately
    - In blind -> check (free look); fold if facing a raise
"""

BOT_NAME = "StrategyBot"
BOT_AVATAR = "robot_1"

# ── Rank value mapping (for correct sorting, A is highest) ───────────────────
RANK_ORDER = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}

# ── Hand classification ───────────────────────────────────────────────────────

# Strong hands: preflop hands worth playing aggressively
STRONG_HANDS = {
    ("A", "A"), ("K", "K"), ("Q", "Q"), ("J", "J"), ("T", "T"),
    ("9", "9"), ("8", "8"),
    ("A", "K"), ("A", "Q"), ("A", "J"), ("A", "T"),
    ("K", "Q"), ("K", "J"),
    ("Q", "J"),
}

# Weak hands: starting hands to fold immediately (low pairs, unconnected low cards)
# Note: each tuple is high card first, consistent with get_hand_ranks output
WEAK_HANDS = {
    ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"),
    ("7", "2"), ("8", "2"), ("9", "2"), ("7", "3"), ("8", "3"),
    ("3", "2"), ("4", "2"), ("5", "2"), ("6", "2"),
    ("4", "3"), ("5", "3"), ("6", "3"),
    ("5", "4"), ("6", "4"), ("7", "4"),
}

# ── Utility functions ─────────────────────────────────────────────────────────

def get_hand_ranks(cards: list) -> tuple:
    """Return a tuple of the two card ranks sorted high-to-low using RANK_ORDER (A is highest)."""
    ranks = sorted([c[0] for c in cards], key=lambda r: RANK_ORDER[r], reverse=True)
    return tuple(ranks)

def is_suited(cards: list) -> bool:
    """Return True if both cards share the same suit."""
    return cards[0][1] == cards[1][1]

def classify_hand(cards: list) -> str:
    """
    Classify a starting hand as 'strong', 'weak', or 'medium'.
    """
    ranks = get_hand_ranks(cards)
    suited = is_suited(cards)

    # Strong hand check
    if ranks in STRONG_HANDS:
        return "strong"
    # Suited connectors with high cards count as medium (e.g. JTs, 98s)
    if suited and ranks[0] in "AKQJT98":
        return "medium"
    # Weak hand check
    if ranks in WEAK_HANDS:
        return "weak"
    # Everything else is medium
    return "medium"

def is_blind(state: dict) -> bool:
    """
    Return True if we posted the small or big blind this hand.
    Determined by scanning action_log for small_blind / big_blind entries matching our seat.
    """
    my_seat = state["seat_to_act"]
    for entry in state["action_log"]:
        if entry.get("seat") == my_seat and entry.get("action") in ("small_blind", "big_blind"):
            return True
    return False

def calc_spr(state: dict) -> float:
    """
    Calculate Stack-to-Pot Ratio (SPR = our stack / pot).
    SPR < 3  -> short stack, lean towards all-in
    SPR 3-6  -> medium stack, increase aggression
    SPR > 6  -> deep stack, use standard sizing
    Returns infinity when pot is 0 (treated as deep stack).
    """
    pot = state["pot"]
    if pot == 0:
        return float("inf")
    return state["your_stack"] / pot


def someone_raised_this_street(state: dict) -> bool:
    """
    Return True if someone has bet or raised on the current street.
    Uses current_bet, which the engine resets to 0 at the start of each street.
    Preflop is a special case: the big blind posts 100 by default,
    so we need current_bet > 100 to detect an actual raise.
    Note: action_log entries have no 'street' field and cannot be used for this check.
    """
    if state["street"] == "preflop":
        return state["current_bet"] > 100
    return state["current_bet"] > 0

# ── Street strategies ─────────────────────────────────────────────────────────

def strategy_preflop(state: dict, strength: str) -> dict:
    """
    Preflop strategy:
      Strong hand:
        Short stack (SPR < 3) -> all-in
        Normal                -> raise to 3x BB
      Medium hand:
        Short stack (SPR < 3) -> call (folding is too costly)
        Normal                -> call only if owed <= 20% of pot
      Weak hand -> fold unless in blind (free check)
    """
    owed      = state["amount_owed"]
    pot       = state["pot"]
    stack     = state["your_stack"]
    min_raise = state["min_raise_to"]
    can_check = state["can_check"]
    spr       = calc_spr(state)

    if strength == "strong":
        if spr < 3:
            # Short stack: go all-in, no value in slow-playing
            return {"action": "all_in"}
        raise_to = max(min_raise, 300)
        raise_to = min(raise_to, stack + state["your_bet_this_street"])
        return {"action": "raise", "amount": raise_to}

    if strength == "medium":
        if can_check:
            return {"action": "check"}
        if spr < 3:
            # Short stack: calling is better than folding
            return {"action": "call"}
        if owed <= pot * 0.20:
            return {"action": "call"}
        return {"action": "fold"}

    # weak
    if can_check:
        return {"action": "check"}   # free look from the blind
    return {"action": "fold"}


def strategy_flop(state: dict, strength: str) -> dict:
    """
    Flop strategy:
      Strong hand:
        Short stack  (SPR < 3) -> all-in
        Medium stack (SPR < 6) -> raise 75% pot
        Deep stack             -> raise 50% if no bet; re-raise 75% if facing a bet
      Medium hand:
        Short stack (SPR < 3)  -> call (already pot-committed)
        Normal                 -> check / call if owed <= 25% pot
      Weak hand -> check or fold
    """
    owed      = state["amount_owed"]
    pot       = state["pot"]
    stack     = state["your_stack"]
    min_raise = state["min_raise_to"]
    can_check = state["can_check"]
    spr       = calc_spr(state)

    if strength == "strong":
        if spr < 3:
            return {"action": "all_in"}
        if spr < 6:
            # Medium stack: push hard to build the pot fast
            bet = max(int(pot * 0.75), min_raise)
            bet = min(bet, stack + state["your_bet_this_street"])
            return {"action": "raise", "amount": bet}
        # Deep stack: standard sizing
        if can_check:
            bet = max(int(pot * 0.50), min_raise)
            bet = min(bet, stack + state["your_bet_this_street"])
            return {"action": "raise", "amount": bet}
        bet = max(int(pot * 0.75), min_raise)
        bet = min(bet, stack + state["your_bet_this_street"])
        return {"action": "raise", "amount": bet}

    if strength == "medium":
        if spr < 3:
            # Short stack: call rather than fold
            if can_check:
                return {"action": "check"}
            return {"action": "call"}
        if can_check:
            return {"action": "check"}
        if owed <= pot * 0.25:
            return {"action": "call"}
        return {"action": "fold"}

    # weak
    if can_check:
        return {"action": "check"}
    return {"action": "fold"}


def strategy_turn(state: dict, strength: str) -> dict:
    """
    Turn strategy:
      Strong hand:
        Short/medium stack (SPR < 6) -> all-in (last chance to protect the pot)
        Deep stack                   -> re-raise 75% if facing a bet; raise 50% otherwise
      Medium / weak hand:
        Short stack (SPR < 3)        -> call
        Normal                       -> check / call if owed <= 20% pot
    """
    owed      = state["amount_owed"]
    pot       = state["pot"]
    stack     = state["your_stack"]
    min_raise = state["min_raise_to"]
    can_check = state["can_check"]
    raised    = someone_raised_this_street(state)
    spr       = calc_spr(state)

    if strength == "strong":
        if spr < 6:
            # Short / medium stack: shove on the turn
            return {"action": "all_in"}
        if raised or owed > 0:
            # Deep stack facing a bet: re-raise 75% pot
            bet = max(int(pot * 0.75), min_raise)
            bet = min(bet, stack + state["your_bet_this_street"])
            return {"action": "raise", "amount": bet}
        else:
            # Deep stack, no bet yet: lead out 50% pot
            bet = max(int(pot * 0.50), min_raise)
            bet = min(bet, stack + state["your_bet_this_street"])
            return {"action": "raise", "amount": bet}

    if strength == "medium":
        if spr < 3:
            if can_check:
                return {"action": "check"}
            return {"action": "call"}
        if can_check:
            return {"action": "check"}
        if owed <= pot * 0.20:
            return {"action": "call"}
        return {"action": "fold"}

    # weak
    if can_check:
        return {"action": "check"}
    return {"action": "fold"}


def strategy_river(state: dict, strength: str) -> dict:
    """
    River strategy:
      Strong hand:
        Short/medium stack (SPR < 6) -> all-in (last street, maximise value)
        Deep stack                   -> re-raise 75% if facing a bet; raise 50% otherwise
      Medium / weak hand:
        Short stack (SPR < 3)        -> call
        Normal                       -> check / call if owed <= 15% pot (tighter on river)
    """
    owed      = state["amount_owed"]
    pot       = state["pot"]
    stack     = state["your_stack"]
    min_raise = state["min_raise_to"]
    can_check = state["can_check"]
    raised    = someone_raised_this_street(state)
    spr       = calc_spr(state)

    if strength == "strong":
        if spr < 6:
            # Short / medium stack: shove to extract maximum value
            return {"action": "all_in"}
        if raised or owed > 0:
            # Deep stack facing a bet: re-raise 75% pot
            bet = max(int(pot * 0.75), min_raise)
            bet = min(bet, stack + state["your_bet_this_street"])
            return {"action": "raise", "amount": bet}
        else:
            bet = max(int(pot * 0.50), min_raise)
            bet = min(bet, stack + state["your_bet_this_street"])
            return {"action": "raise", "amount": bet}

    if strength == "medium":
        if spr < 3:
            if can_check:
                return {"action": "check"}
            return {"action": "call"}
        if can_check:
            return {"action": "check"}
        if owed <= pot * 0.15:   # tighter call threshold on the river
            return {"action": "call"}
        return {"action": "fold"}

    # weak
    if can_check:
        return {"action": "check"}
    return {"action": "fold"}


# ── Main entry point ──────────────────────────────────────────────────────────

def decide(game_state: dict) -> dict:
    """
    Called once per action. Must return within 2 seconds.
    """
    street   = game_state["street"]
    my_cards = game_state["your_cards"]
    strength = classify_hand(my_cards)

    # Weak hand preflop: fold immediately unless we're in the blind
    if strength == "weak" and street == "preflop":
        if not is_blind(game_state) and not game_state["can_check"]:
            return {"action": "fold"}

    # Dispatch to per-street strategy
    if street == "preflop":
        return strategy_preflop(game_state, strength)
    elif street == "flop":
        return strategy_flop(game_state, strength)
    elif street == "turn":
        return strategy_turn(game_state, strength)
    elif street == "river":
        return strategy_river(game_state, strength)

    # Fallback
    return {"action": "fold"}
