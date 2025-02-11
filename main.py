#!/usr/bin/env python3
import tkinter as tk
import itertools
import random
import time
import threading
import concurrent.futures
from collections import Counter

# =====================================
# Poker Hand Evaluation Code
# =====================================

def rank_char_to_int(ch):
    mapping = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
        '7': 7, '8': 8, '9': 9, 'T': 10,
        'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    ch = ch.upper()
    if ch not in mapping:
        raise ValueError("Invalid rank character: " + ch)
    return mapping[ch]

def parse_card(card_str):
    card_str = card_str.strip()
    if len(card_str) != 2:
        raise ValueError("Card must be exactly 2 chars (e.g. 'Ah') - got: " + card_str)
    rank = rank_char_to_int(card_str[0])
    suit = card_str[1].lower()
    if suit not in ['h', 'd', 'c', 's']:
        raise ValueError("Invalid suit: " + suit)
    return (rank, suit)

def parse_hand(hand_str):
    """
    Parses a 2-card 'hand' string, either:
       - shorthand (e.g. "KTs", "A8o", "33"), or
       - explicit (e.g. "KSTS", "AhKh").
    For shorthand, a default assignment of suits is made.
    """
    hand_str = hand_str.strip()
    if not hand_str:
        return None
    if " " in hand_str:
        parts = hand_str.split()
        if len(parts) != 2:
            raise ValueError("Please supply exactly two cards for a hand.")
        return [parse_card(part) for part in parts]
    else:
        if len(hand_str) in [2, 3]:
            if len(hand_str) == 2:  # e.g. "33"
                rank = rank_char_to_int(hand_str[0])
                return [(rank, 'h'), (rank, 's')]
            else:  # e.g. "KTs"
                r1 = rank_char_to_int(hand_str[0])
                r2 = rank_char_to_int(hand_str[1])
                style = hand_str[2].lower()
                if style == 's':
                    return [(r1, 'h'), (r2, 'h')]
                elif style == 'o':
                    return [(r1, 'h'), (r2, 's')]
                else:
                    raise ValueError("Invalid shorthand (expect 's' or 'o'): " + hand_str)
        elif len(hand_str) == 4:  # e.g. "KSTS"
            return [parse_card(hand_str[0:2]), parse_card(hand_str[2:4])]
        else:
            raise ValueError("Invalid hand format: " + hand_str)

def parse_board(board_str):
    """
    Parse a board string (0-5 cards) from e.g. "AhKhQh" or "Ah Kh Qh".
    """
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
    ranks = range(2,15)
    suits = ['h','d','c','s']
    return [(r,s) for r in ranks for s in suits]

def evaluate_five(cards):
    """
    Evaluate a 5-card hand. Returns a tuple that can be compared
    (higher tuple => stronger hand). Categories:
      8: Straight flush, 7: 4-of-a-kind, 6: Full house,
      5: Flush, 4: Straight, 3: Trips, 2: Two pair,
      1: One pair, 0: High card.
    """
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    flush = (len(set(suits)) == 1)
    counts = Counter(ranks)
    freq = sorted(counts.values(), reverse=True)
    unique_ranks = sorted(counts.keys(), reverse=True)
    
    # check straight
    straight = False
    top_str = None
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            straight = True
            top_str = unique_ranks[0]
        elif unique_ranks == [14,5,4,3,2]:
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
    """
    Given 7 cards, return best 5-card hand rank.
    """
    best = None
    for combo in itertools.combinations(cards, 5):
        score = evaluate_five(combo)
        if best is None or score > best:
            best = score
    return best

def compare_hands(hand1, hand2, board):
    """
    Compare two 2–card hands with the given board.
    Returns: 1 if hand1 better, -1 if hand2 better, 0 tie.
    """
    s1 = evaluate_seven(hand1 + board)
    s2 = evaluate_seven(hand2 + board)
    if s1 > s2: return 1
    elif s2 > s1: return -1
    else: return 0

def compute_equity(hand1, hand2, board, num_simulations=5000, time_cap=None):
    """
    Return (win1, win2, tie) fractional probabilities that
    hand1 wins, hand2 wins, or tie, given possibly partial board.
    If missing board cards <=2, do full enumeration; else Monte Carlo.
    If time_cap (in seconds) is specified and needed>2, then use a timed simulation loop.
    """
    deck = generate_deck()
    used = set(hand1+hand2+board)
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
        if time_cap is not None:
            start_time = time.time()
            iterations = 0
            while time.time() - start_time < time_cap:
                combo = random.sample(deck, needed)
                res = compare_hands(hand1, hand2, board + combo)
                if res == 1:
                    wins1 += 1
                elif res == -1:
                    wins2 += 1
                else:
                    ties += 1
                iterations += 1
            total = iterations
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
    return (wins1/total, wins2/total, ties/total)

# =====================================
# Helpers for Range & Weighting
# =====================================

def hand_weight(hand_cat):
    """Number of combos for that category.  Pairs=6, suited=4, offsuit=12."""
    if len(hand_cat) == 2:
        return 6
    elif len(hand_cat) == 3:
        if hand_cat[-1].lower() == 's': return 4
        if hand_cat[-1].lower() == 'o': return 12
    return 0

def static_hand_rank(hand_cat):
    """
    Simple “strength” measure for ordering hands top to bottom.
    """
    try:
        if len(hand_cat) == 2:
            r = rank_char_to_int(hand_cat[0])
            return 200 + r
        elif len(hand_cat) == 3:
            r1 = rank_char_to_int(hand_cat[0])
            r2 = rank_char_to_int(hand_cat[1])
            if r2 > r1: r1, r2 = r2, r1
            bonus = (5 if hand_cat[-1].lower()=='s' else 0)
            return r1*10 + r2 + bonus
    except:
        pass
    return 0

def get_valid_hand(hand_cat, forbidden):
    """
    Convert a category label (e.g. "KTs", "AQo", "AA") to an actual 2-card hand
    that doesn't conflict with `forbidden`.
    Return None if no suits left.
    """
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
        if r2 > r1: r1, r2 = r2, r1
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

def equity_to_color(equity):
    """
    Map an equity value (0..1) to a color.
    Using effective equity (win + tie/2) prevents high tie equity from showing as deep red.
    """
    r = int(255 * (1 - equity))
    g = int(255 * equity)
    return f'#{r:02x}{g:02x}00'

# =====================================
# Simple Tooltip
# =====================================

class ToolTip:
    def __init__(self, widget, text=''):
        self.widget = widget
        self.text = text
        self.tipwindow = None

    def showtip(self, text):
        self.text = text
        if self.tipwindow or not text:
            return
        x, y, cx, cy = 0, 0, 0, 0
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except:
            pass
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma","8","normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None

# =====================================
# The Main GUI Class
# =====================================

class EquityGUI:
    def __init__(self, master):
        self.master = master
        master.title("Texas Hold'em Equity Calculator")

        # Left frame for controls
        main_frame = tk.Frame(master)
        main_frame.pack(fill=tk.BOTH, expand=True)
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        tk.Label(left_frame, text="Your Hand:").pack(anchor=tk.W)
        self.hand_entry = tk.Entry(left_frame, width=10)
        self.hand_entry.pack(anchor=tk.W, pady=2)
        self.hand_entry.insert(0, "")

        tk.Label(left_frame, text="Board Cards:").pack(anchor=tk.W)
        self.board_entry = tk.Entry(left_frame, width=20)
        self.board_entry.pack(anchor=tk.W, pady=2)

        tk.Label(left_frame, text="Simulation Depth (# iterations):").pack(anchor=tk.W, pady=2)
        self.sim_depth = tk.IntVar(value=1000)
        self.sim_slider = tk.Scale(left_frame, from_=500, to=30000, resolution=500,
                                   orient=tk.HORIZONTAL, variable=self.sim_depth)
        self.sim_slider.pack(anchor=tk.W)

        # Time cap controls
        self.use_time_cap = tk.BooleanVar(value=False)
        tk.Checkbutton(left_frame, text="Use Time Cap", variable=self.use_time_cap).pack(anchor=tk.W)
        tk.Label(left_frame, text="Simulation Time Cap (s):").pack(anchor=tk.W, pady=2)
        self.time_cap = tk.IntVar(value=10)
        self.time_cap_slider = tk.Scale(left_frame, from_=1, to=120, orient=tk.HORIZONTAL, variable=self.time_cap)
        self.time_cap_slider.pack(anchor=tk.W)

        tk.Label(left_frame, text="Opponent Range (% top hands):").pack(anchor=tk.W, pady=2)
        self.range_pct = tk.IntVar(value=100)
        self.range_slider = tk.Scale(left_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                                     variable=self.range_pct, command=lambda v: self.update_range_selection())
        self.range_slider.pack(anchor=tk.W)

        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(anchor=tk.W, pady=5)
        tk.Button(btn_frame, text="Update Grid", command=self.update_grid).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Update Compound Equity", command=self.update_compound_equity).pack(side=tk.LEFT)

        self.status_label = tk.Label(left_frame, text="", fg="red")
        self.status_label.pack(anchor=tk.W, pady=5)

        self.compound_all_label = tk.Label(left_frame, text="Compound Equity vs All: N/A")
        self.compound_all_label.pack(anchor=tk.W, pady=2)
        self.compound_range_label = tk.Label(left_frame, text="Compound Equity vs Selected Range: N/A")
        self.compound_range_label.pack(anchor=tk.W, pady=2)

        self.pot_odds_all_label = tk.Label(left_frame, text="Pot Odds Needed (All): N/A")
        self.pot_odds_all_label.pack(anchor=tk.W, pady=2)
        self.pot_odds_range_label = tk.Label(left_frame, text="Pot Odds Needed (Range): N/A")
        self.pot_odds_range_label.pack(anchor=tk.W, pady=2)

        # Right frame for grid
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(right_frame)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        hscroll = tk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.configure(xscrollcommand=hscroll.set)
        self.grid_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0,0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Build 13x13 grid
        self.ranks = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
        self.cells = {}
        self.selected_cells = set()
        for i, rank in enumerate(self.ranks):
            lbl = tk.Label(self.grid_frame, text=rank, relief="ridge", width=3, height=2, bg="white")
            lbl.grid(row=i+1, column=0, padx=1, pady=1)
            lbl = tk.Label(self.grid_frame, text=rank, relief="ridge", width=3, height=2, bg="white")
            lbl.grid(row=0, column=i+1, padx=1, pady=1)
        corner_lbl = tk.Label(self.grid_frame, text="", width=4, height=2, bg="white")
        corner_lbl.grid(row=0, column=0, padx=1, pady=1)
        for i, r1 in enumerate(self.ranks):
            for j, r2 in enumerate(self.ranks):
                if i == j:
                    hand_cat = r1*2
                else:
                    high = self.ranks[min(i,j)]
                    low  = self.ranks[max(i,j)]
                    if i < j:
                        hand_cat = high + low + 's'
                    else:
                        hand_cat = high + low + 'o'
                label = tk.Label(self.grid_frame, text=hand_cat, width=5, height=2,
                                 bg="lightgrey", relief="ridge")
                label.grid(row=i+1, column=j+1, padx=1, pady=1)
                ttip = ToolTip(label)
                self.cells[(i,j)] = {
                    "hand_cat": hand_cat,
                    "label": label,
                    "equity": None,
                    "tie": None,
                    "tooltip": ttip
                }
                label.bind("<Enter>", lambda e, pos=(i,j): self.show_tooltip(pos))
                label.bind("<Leave>", lambda e, pos=(i,j): self.hide_tooltip(pos))
                label.bind("<Button-1>", lambda e, pos=(i,j): self.toggle_cell(pos))

    def show_tooltip(self, pos):
        cell = self.cells[pos]
        txt = cell.get("tooltip_text", "")
        cell["tooltip"].showtip(txt)

    def hide_tooltip(self, pos):
        self.cells[pos]["tooltip"].hidetip()

    def toggle_cell(self, pos):
        if pos in self.selected_cells:
            self.selected_cells.remove(pos)
            self.cells[pos]["label"].config(highlightthickness=0)
        else:
            self.selected_cells.add(pos)
            self.cells[pos]["label"].config(highlightbackground="blue", highlightthickness=2)
        self.update_compound_equity()

    def update_grid(self):
        """
        Initiate grid update by parsing input and starting a background thread.
        """
        self.status_label.config(text="Updating grid...")
        self.master.update_idletasks()
        hand_str = self.hand_entry.get().strip()
        board_str = self.board_entry.get().strip()
        if not hand_str:
            self.status_label.config(text="No user hand given. Enter a hand, then click Update Grid.")
            return
        try:
            user_hand = parse_hand(hand_str)
            if user_hand is None:
                self.status_label.config(text="No user hand given.")
                return
        except Exception as e:
            self.status_label.config(text=f"Error in user hand: {e}")
            return
        try:
            board = parse_board(board_str)
        except Exception as e:
            self.status_label.config(text=f"Error in board: {e}")
            return
        # Run the heavy computation off the main thread.
        threading.Thread(target=self.compute_all_equities, args=(user_hand, board), daemon=True).start()

    def compute_all_equities(self, user_hand, board):
        """
        Compute equities for all grid cells in background using a thread pool.
        """
        forbidden = set(board + user_hand)
        simulation_mode = self.use_time_cap.get()
        simulations = self.sim_depth.get()
        time_cap = self.time_cap.get() if simulation_mode else None
        results = {}

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_pos = {}
            for pos, data in self.cells.items():
                hand_cat = data["hand_cat"]
                opp_hand = get_valid_hand(hand_cat, forbidden)
                if opp_hand is None:
                    results[pos] = None
                else:
                    if simulation_mode:
                        future = executor.submit(compute_equity, user_hand, opp_hand, board,
                                                   num_simulations=simulations, time_cap=time_cap)
                    else:
                        future = executor.submit(compute_equity, user_hand, opp_hand, board,
                                                   num_simulations=simulations)
                    future_to_pos[future] = pos

            for future in concurrent.futures.as_completed(future_to_pos):
                pos = future_to_pos[future]
                try:
                    win1, win2, tie = future.result()
                    results[pos] = (win1, tie)
                except Exception as e:
                    results[pos] = "error"
        # Update UI in the main thread.
        self.master.after(0, lambda: self.update_grid_ui(results))

    def update_grid_ui(self, results):
        """
        Update each cell’s UI based on simulation results.
        """
        for pos, data in self.cells.items():
            hand_cat = data["hand_cat"]
            result = results.get(pos, None)
            if result is None:
                data["equity"] = None
                data["tie"] = None
                data["label"].config(bg="grey")
                data["tooltip_text"] = f"{hand_cat}\nN/A"
            elif result == "error":
                data["equity"] = None
                data["tie"] = None
                data["label"].config(bg="grey")
                data["tooltip_text"] = f"{hand_cat}\nErr"
            else:
                win1, tie = result
                data["equity"] = win1
                data["tie"] = tie
                effective = win1 + tie/2
                clr = equity_to_color(effective)
                data["label"].config(bg=clr)
                eq_str = f"Win: {win1*100:.1f}%, Tie: {tie*100:.1f}%"
                data["tooltip_text"] = f"{hand_cat}\n{eq_str}"
        self.status_label.config(text="Grid updated.")
        self.update_compound_equity()

    def update_range_selection(self):
        """
        Auto-select the top X% of hands based on a static ranking.
        """
        self.selected_cells.clear()
        items = []
        total_w = 0
        for pos, data in self.cells.items():
            eq = data["equity"]
            if eq is not None:
                w = hand_weight(data["hand_cat"])
                total_w += w
                sr = static_hand_rank(data["hand_cat"])
                items.append((pos, sr, w))
        items.sort(key=lambda x: x[1], reverse=True)
        fraction = self.range_pct.get()/100.0
        threshold = total_w * fraction
        accum = 0
        for pos, sr, w in items:
            if accum < threshold:
                self.selected_cells.add(pos)
                accum += w
            else:
                break
        for pos, data in self.cells.items():
            if pos in self.selected_cells:
                data["label"].config(highlightbackground="blue", highlightthickness=2)
            else:
                data["label"].config(highlightthickness=0)
        self.update_compound_equity()

    def update_compound_equity(self):
        """
        Compute weighted compound equity vs all valid hands and vs the selected range.
        """
        total_weight = 0
        total_eff_equity = 0
        for data in self.cells.values():
            eq = data["equity"]
            tie = data["tie"]
            if eq is not None:
                w = hand_weight(data["hand_cat"])
                e = eq + (tie/2)
                total_weight += w
                total_eff_equity += e*w
        comp_all = total_eff_equity / total_weight if total_weight > 0 else 0

        sel_weight = 0
        sel_eff_equity = 0
        for pos in self.selected_cells:
            data = self.cells[pos]
            eq = data["equity"]
            tie = data["tie"]
            if eq is not None:
                w = hand_weight(data["hand_cat"])
                e = eq + (tie/2)
                sel_weight += w
                sel_eff_equity += e*w
        comp_range = sel_eff_equity / sel_weight if sel_weight > 0 else 0

        self.compound_all_label.config(text=f"Compound Equity vs All: {comp_all*100:.1f}%")
        self.compound_range_label.config(text=f"Compound Equity vs Selected Range: {comp_range*100:.1f}%")

        def pot_odds_needed(eq):
            if eq <= 0:
                return "∞"
            ratio = (1-eq)/eq
            return f"{ratio:.2f} : 1"
        self.pot_odds_all_label.config(text=f"Pot Odds Needed (All): {pot_odds_needed(comp_all)}")
        self.pot_odds_range_label.config(text=f"Pot Odds Needed (Range): {pot_odds_needed(comp_range)}")

def main():
    root = tk.Tk()
    gui = EquityGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
