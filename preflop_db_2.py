#!/usr/bin/env python3
"""
Incremental Preflop DB Generator (with Proper Resumption)

This generator simulates matchups and stores both raw counts and computed
probabilities. When restarted it loads the previous raw counts and iteration
count from the database, so the simulation properly resumes.
"""

import sqlite3
import random
import itertools
import time
from collections import defaultdict

# -------------- Poker Hand Evaluation Code --------------

def rank_char_to_int(ch):
    mapping = {'2':2, '3':3, '4':4, '5':5, '6':6,
               '7':7, '8':8, '9':9, 'T':10, 'J':11,
               'Q':12, 'K':13, 'A':14}
    return mapping[ch.upper()]

def generate_deck():
    return [(r, s) for r in range(2,15) for s in ['h','d','c','s']]

def evaluate_five(cards):
    from collections import Counter
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    flush = (len(set(suits)) == 1)
    counts = Counter(ranks)
    freq = sorted(counts.values(), reverse=True)
    unique_ranks = sorted(counts.keys(), reverse=True)
    
    straight = False
    top_str = None
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            straight = True
            top_str = unique_ranks[0]
        elif unique_ranks == [14, 5, 4, 3, 2]:
            straight = True
            top_str = 5

    if flush and straight:
        return (8, top_str)
    elif 4 in freq:
        four_rank = max(r for r, c in counts.items() if c == 4)
        kicker = max(r for r in ranks if r != four_rank)
        return (7, four_rank, kicker)
    elif 3 in freq and 2 in freq:
        triple_rank = max(r for r, c in counts.items() if c == 3)
        pair_rank = max(r for r, c in counts.items() if c >= 2 and r != triple_rank)
        return (6, triple_rank, pair_rank)
    elif flush:
        return (5, tuple(ranks))
    elif straight:
        return (4, top_str)
    elif 3 in freq:
        triple_rank = max(r for r, c in counts.items() if c == 3)
        kickers = tuple(sorted((r for r in ranks if r != triple_rank), reverse=True))
        return (3, triple_rank, kickers)
    elif freq.count(2) >= 2:
        pairs = sorted([r for r, c in counts.items() if c == 2], reverse=True)
        kicker = max(r for r in ranks if r not in pairs)
        return (2, tuple(pairs), kicker)
    elif 2 in freq:
        pair_rank = max(r for r, c in counts.items() if c == 2)
        kickers = tuple(sorted([r for r in ranks if r != pair_rank], reverse=True))
        return (1, pair_rank, kickers)
    else:
        return (0, tuple(ranks))

def evaluate_seven(cards):
    best = None
    for combo in itertools.combinations(cards, 5):
        score = evaluate_five(combo)
        if best is None or score > best:
            best = score
    return best

# -------------- Canonical Hands Helpers --------------

def get_valid_hand(hand_cat, forbidden):
    suits = ['h','d','c','s']
    if len(hand_cat) == 2:
        r = rank_char_to_int(hand_cat[0])
        for i in range(4):
            for j in range(i+1,4):
                c1 = (r, suits[i])
                c2 = (r, suits[j])
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
                c1 = (r1, s)
                c2 = (r2, s)
                if c1 not in forbidden and c2 not in forbidden:
                    return [c1, c2]
            return None
        elif typ == 'o':
            for s1 in suits:
                for s2 in suits:
                    if s1 == s2:
                        continue
                    c1 = (r1, s1)
                    c2 = (r2, s2)
                    if c1 not in forbidden and c2 not in forbidden:
                        return [c1, c2]
            return None
    return None

def get_second_valid_hand(hand_cat):
    suits = ['h','d','c','s']
    if len(hand_cat) == 2:
        r = rank_char_to_int(hand_cat[0])
        combos = []
        for i in range(4):
            for j in range(i+1,4):
                combos.append([(r, suits[i]), (r, suits[j])])
        return combos[1] if len(combos) >= 2 else combos[0] if combos else None
    elif len(hand_cat) == 3:
        r1 = rank_char_to_int(hand_cat[0])
        r2 = rank_char_to_int(hand_cat[1])
        typ = hand_cat[-1].lower()
        if typ == 's':
            combos = []
            for s in suits:
                combos.append([(r1, s), (r2, s)])
            return combos[1] if len(combos) >= 2 else combos[0] if combos else None
        elif typ == 'o':
            combos = []
            for s1 in suits:
                for s2 in suits:
                    if s1 == s2:
                        continue
                    combos.append([(r1, s1), (r2, s2)])
            return combos[1] if len(combos) >= 2 else combos[0] if combos else None
    return None

def generate_canonical_hands():
    ranks = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
    canonical = []
    for i, r1 in enumerate(ranks):
        for j, r2 in enumerate(ranks):
            if i == j:
                hand_cat = r1 * 2
            else:
                high = ranks[min(i, j)]
                low  = ranks[max(i, j)]
                hand_cat = high + low + ('s' if i < j else 'o')
            if hand_cat not in canonical:
                canonical.append(hand_cat)
    return canonical

# -------------- Database Helpers (with Resumption Support) --------------

DB_FILE = "preflop_equities.db"
BATCH_SIZE = 1000

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Table for computed probabilities (final output)
    c.execute('''
        CREATE TABLE IF NOT EXISTS preflop_equities (
            user_hand TEXT,
            opp_hand TEXT,
            win REAL,
            tie REAL,
            true REAL,
            PRIMARY KEY (user_hand, opp_hand)
        )
    ''')
    # Table for raw cumulative counts (for resumption)
    c.execute('''
        CREATE TABLE IF NOT EXISTS preflop_equities_counts (
            user_hand TEXT,
            opp_hand TEXT,
            wins INTEGER,
            ties INTEGER,
            total INTEGER,
            PRIMARY KEY (user_hand, opp_hand)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def load_iterations():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM meta WHERE key='iterations'")
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 0

def load_counters(canonical):
    # Start with a dictionary of zero counts.
    counters = {h1: {h2: {"wins": 0, "ties": 0, "total": 0} for h2 in canonical} for h1 in canonical}
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT user_hand, opp_hand, wins, ties, total FROM preflop_equities_counts")
        rows = c.fetchall()
        for user_hand, opp_hand, wins, ties, total in rows:
            counters[user_hand][opp_hand] = {"wins": wins, "ties": ties, "total": total}
    except Exception as e:
        print("No counts loaded:", e)
    conn.close()
    return counters

def save_counters(counters, iterations):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for user_hand, opp_dict in counters.items():
        for opp_hand, stats in opp_dict.items():
            total = stats["total"]
            wins = stats["wins"]
            ties = stats["ties"]
            if total > 0:
                win_prob = wins / total
                tie_prob = ties / total
                true_eq  = win_prob + 0.5 * tie_prob
            else:
                win_prob = 0.0
                tie_prob = 0.0
                true_eq  = 0.0
            # Save raw counts:
            c.execute('''
                INSERT OR REPLACE INTO preflop_equities_counts (user_hand, opp_hand, wins, ties, total)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_hand, opp_hand, wins, ties, total))
            # Save computed probabilities:
            c.execute('''
                INSERT OR REPLACE INTO preflop_equities (user_hand, opp_hand, win, tie, true)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_hand, opp_hand, win_prob, tie_prob, true_eq))
    c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('iterations', ?)", (str(iterations),))
    conn.commit()
    conn.close()

# -------------- Main Simulation Loop --------------

def main():
    canonical = generate_canonical_hands()  # 169 canonical hands
    counters = load_counters(canonical)
    iterations = load_iterations()
    print(f"Resuming simulation from {iterations} iterations.")

    # Precompute a fixed assignment for each canonical hand.
    canonical_assignments = {h: get_valid_hand(h, set()) for h in canonical}
    deck = generate_deck()

    start_time = time.time()
    batch_start = start_time
    try:
        while True:
            iterations += 1

            # Draw a random board of 5 cards.
            board = random.sample(deck, 5)

            # For each canonical hand, if its fixed hole cards conflict with the board, skip it.
            valid_results = {}
            for hand in canonical:
                hole = canonical_assignments[hand]
                if any(card in board for card in hole):
                    continue
                hand_value = evaluate_seven(hole + board)
                valid_results[hand] = hand_value

            # Compare every ordered pair of distinct valid canonical hands.
            valid_hands = list(valid_results.keys())
            for i in range(len(valid_hands)):
                h1 = valid_hands[i]
                for j in range(i+1, len(valid_hands)):
                    h2 = valid_hands[j]
                    counters[h1][h2]["total"] += 1
                    counters[h2][h1]["total"] += 1
                    val1 = valid_results[h1]
                    val2 = valid_results[h2]
                    if val1 > val2:
                        counters[h1][h2]["wins"] += 1
                    elif val1 < val2:
                        counters[h2][h1]["wins"] += 1
                    else:
                        counters[h1][h2]["ties"] += 1
                        counters[h2][h1]["ties"] += 1

            # --- Self Matchup Simulation ---
            for hand in valid_results:
                primary_value = valid_results[hand]
                second_assignment = get_second_valid_hand(hand)
                if second_assignment is None or any(card in board for card in second_assignment):
                    continue
                second_value = evaluate_seven(second_assignment + board)
                counters[hand][hand]["total"] += 1
                if primary_value > second_value:
                    counters[hand][hand]["wins"] += 1
                elif primary_value < second_value:
                    counters[hand][hand]["wins"] += 1
                else:
                    counters[hand][hand]["ties"] += 1

            if iterations % BATCH_SIZE == 0:
                save_counters(counters, iterations)
                batch_time = time.time() - batch_start
                print(f"Completed {iterations} iterations (last {BATCH_SIZE} in {batch_time:.1f} s)")
                batch_start = time.time()

    except KeyboardInterrupt:
        print("Interrupted! Saving progress...")
        save_counters(counters, iterations)
        print(f"Saved after {iterations} iterations.")

if __name__ == '__main__':
    init_db()
    main()
