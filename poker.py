import itertools, random
from collections import Counter

def rank_char_to_int(ch):
    mapping = {'2':2, '3':3, '4':4, '5':5, '6':6,
               '7':7, '8':8, '9':9, 'T':10, 'J':11,
               'Q':12, 'K':13, 'A':14}
    ch = ch.upper()
    if ch not in mapping:
        raise ValueError("Invalid rank character: " + ch)
    return mapping[ch]

def parse_card(card_str):
    card_str = card_str.strip()
    if len(card_str) != 2:
        raise ValueError("Card must be exactly 2 chars (e.g. 'Ah')")
    rank = rank_char_to_int(card_str[0])
    suit = card_str[1].lower()
    if suit not in ['h', 'd', 'c', 's']:
        raise ValueError("Invalid suit: " + suit)
    return (rank, suit)

def parse_hand(hand_str):
    hand_str = hand_str.strip()
    if not hand_str:
        return None
    if " " in hand_str:
        parts = hand_str.split()
        if len(parts) != 2:
            raise ValueError("Please supply exactly two cards for a hand.")
        return [parse_card(part) for part in parts]
    else:
        if len(hand_str) in [2,3]:
            if len(hand_str) == 2:
                rank = rank_char_to_int(hand_str[0])
                return [(rank, 'h'), (rank, 's')]
            else:
                r1 = rank_char_to_int(hand_str[0])
                r2 = rank_char_to_int(hand_str[1])
                style = hand_str[2].lower()
                if style == 's':
                    return [(r1, 'h'), (r2, 'h')]
                elif style == 'o':
                    return [(r1, 'h'), (r2, 's')]
                else:
                    raise ValueError("Invalid shorthand (expect 's' or 'o'): " + hand_str)
        elif len(hand_str) == 4:
            return [parse_card(hand_str[0:2]), parse_card(hand_str[2:4])]
        else:
            raise ValueError("Invalid hand format: " + hand_str)

def parse_board(board_str):
    board_str = board_str.strip()
    if not board_str:
        return []
    if " " in board_str:
        parts = board_str.split()
    else:
        if len(board_str) % 2 != 0:
            raise ValueError("Board string length must be multiple of 2.")
        parts = [board_str[i:i+2] for i in range(0, len(board_str), 2)]
    return [parse_card(card) for card in parts]

def generate_deck():
    ranks = range(2, 15)
    suits = ['h', 'd', 'c', 's']
    return [(r, s) for r in ranks for s in suits]

def evaluate_five(cards):
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
            straight = True; top_str = unique_ranks[0]
        elif unique_ranks == [14, 5, 4, 3, 2]:
            straight = True; top_str = 5
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

def compare_hands(hand1, hand2, board):
    s1 = evaluate_seven(hand1 + board)
    s2 = evaluate_seven(hand2 + board)
    if s1 > s2: 
        return 1
    elif s2 > s1: 
        return -1
    else: 
        return 0

def compute_equity(hand1, hand2, board, num_simulations=5000):
    deck = generate_deck()
    used = set(hand1 + hand2 + board)
    deck = [c for c in deck if c not in used]
    needed = 5 - len(board)
    wins1 = wins2 = ties = 0
    total = 0
    if needed <= 2:
        all_combos = list(itertools.combinations(deck, needed))
        total = len(all_combos)
        for combo in all_combos:
            res = compare_hands(hand1, hand2, board + list(combo))
            if res == 1: 
                wins1 += 1
            elif res == -1: 
                wins2 += 1
            else: 
                ties += 1
    else:
        total = num_simulations
        for _ in range(num_simulations):
            combo = random.sample(deck, needed)
            res = compare_hands(hand1, hand2, board + combo)
            if res == 1: 
                wins1 += 1
            elif res == -1: 
                wins2 += 1
            else: 
                ties += 1
    return (wins1/total, ties/total, wins1/total + (ties/2)/total)
