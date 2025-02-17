import sqlite3
import random
from poker import rank_char_to_int, generate_deck

def get_valid_hand(hand_cat, forbidden):
    suits = ['h', 'd', 'c', 's']
    if len(hand_cat) == 2:
        r = rank_char_to_int(hand_cat[0])
        for i in range(4):
            for j in range(i+1, 4):
                c1 = (r, suits[i]); c2 = (r, suits[j])
                if c1 not in forbidden and c2 not in forbidden:
                    return [c1, c2]
        return None
    elif len(hand_cat) == 3:
        r1 = rank_char_to_int(hand_cat[0])
        r2 = rank_char_to_int(hand_cat[1])
        typ = hand_cat[-1].lower()
        if r2 > r1: 
            r1, r2 = r2, r1
        if typ == 's':
            for s in suits:
                c1 = (r1, s); c2 = (r2, s)
                if c1 not in forbidden and c2 not in forbidden:
                    return [c1, c2]
            return None
        elif typ == 'o':
            for s1 in suits:
                for s2 in suits:
                    if s1 == s2: 
                        continue
                    c1 = (r1, s1); c2 = (r2, s2)
                    if c1 not in forbidden and c2 not in forbidden:
                        return [c1, c2]
            return None
    return None

def hand_weight(hand_cat):
    if len(hand_cat) == 2: 
        return 6
    elif len(hand_cat) == 3: 
        return 4 if hand_cat[-1].lower() == 's' else 12
    return 0

_static_hand_rankings = None

def load_static_hand_rankings():
    """
    Loads the average 'true' equity for every canonical hand from preflop_equities.db.
    """
    global _static_hand_rankings
    _static_hand_rankings = {}
    try:
        conn = sqlite3.connect("preflop_equities.db")
        c = conn.cursor()
        ranks = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
        canonical_hands = []
        for i, r1 in enumerate(ranks):
            for j, r2 in enumerate(ranks):
                if i == j:
                    hand_cat = r1 * 2
                elif i < j:
                    hand_cat = r1 + r2 + 's'
                else:
                    hand_cat = r1 + r2 + 'o'
                if hand_cat not in canonical_hands:
                    canonical_hands.append(hand_cat)
        for hand in canonical_hands:
            c.execute("SELECT true FROM preflop_equities WHERE user_hand=?", (hand,))
            rows = c.fetchall()
            if rows and len(rows) > 0:
                avg_equity = sum(row[0] for row in rows) / len(rows)
                _static_hand_rankings[hand] = avg_equity
            else:
                _static_hand_rankings[hand] = 0.0
        conn.close()
    except Exception as e:
        print("Error loading static hand rankings:", e)
        for hand in canonical_hands:
            _static_hand_rankings[hand] = 0.0
    return _static_hand_rankings

def static_hand_rank(hand_cat):
    global _static_hand_rankings
    if _static_hand_rankings is None:
        load_static_hand_rankings()
    return _static_hand_rankings.get(hand_cat, 0.0)

def canonicalize_hand(hand):
    rank_letter = {14:'A', 13:'K', 12:'Q', 11:'J', 10:'T',
                   9:'9', 8:'8', 7:'7', 6:'6', 5:'5',
                   4:'4', 3:'3', 2:'2'}
    r1, s1 = hand[0]
    r2, s2 = hand[1]
    if r1 == r2:
        return rank_letter[r1] * 2
    else:
        high = max(r1, r2)
        low = min(r1, r2)
        if s1 == s2:
            return rank_letter[high] + rank_letter[low] + 's'
        else:
            return rank_letter[high] + rank_letter[low] + 'o'

def equity_to_color(equity):
    equity = max(0, min(1, equity))
    r = int(255 * (1 - equity))
    g = int(255 * equity)
    return f'#{r:02x}{g:02x}00'

def select_cells_by_percent(cells, lower_pct, upper_pct):
    items = []
    total_w = 0
    for pos, data in cells.items():
        w = hand_weight(data["hand_cat"])
        total_w += w
        sr = static_hand_rank(data["hand_cat"])
        items.append((pos, sr, w))
    items.sort(key=lambda x: x[1], reverse=True)
    selected = set()
    cum = 0
    for pos, sr, w in items:
        prev = cum
        cum += w
        if prev < total_w * lower_pct and cum > total_w * lower_pct:
            selected.add(pos)
        elif prev >= total_w * lower_pct and cum <= total_w * upper_pct:
            selected.add(pos)
        elif prev < total_w * upper_pct and cum >= total_w * upper_pct:
            selected.add(pos)
    return selected
