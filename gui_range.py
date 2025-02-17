import tkinter as tk
import threading, sqlite3, random
from poker import parse_board, generate_deck, evaluate_seven
from hand_helpers import get_valid_hand, hand_weight, equity_to_color, select_cells_by_percent
from tooltip import ToolTip

class RangeComparisonTab:
    def __init__(self, master):
        self.master = master
        controls_frame = tk.Frame(master)
        controls_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(controls_frame, text="Board Cards:").grid(row=0, column=0, sticky=tk.W)
        self.board_entry = tk.Entry(controls_frame, width=20)
        self.board_entry.grid(row=0, column=1, padx=5)
        self.board_entry.insert(0, "")
        tk.Label(controls_frame, text="Simulations:").grid(row=0, column=2, sticky=tk.W)
        self.sim_depth = tk.IntVar(value=1000)
        self.sim_slider = tk.Scale(controls_frame, from_=500, to=10000, resolution=500,
                                   orient=tk.HORIZONTAL, variable=self.sim_depth)
        self.sim_slider.grid(row=0, column=3, padx=5)
        tk.Label(controls_frame, text="Lower %:").grid(row=1, column=0, sticky=tk.W)
        self.range_lower = tk.IntVar(value=0)
        tk.Scale(controls_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.range_lower,
                 command=lambda v: self.update_range_selection()).grid(row=1, column=1, padx=5)
        tk.Label(controls_frame, text="Upper %:").grid(row=1, column=2, sticky=tk.W)
        self.range_upper = tk.IntVar(value=100)
        tk.Scale(controls_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.range_upper,
                 command=lambda v: self.update_range_selection()).grid(row=1, column=3, padx=5)
        btn_frame = tk.Frame(controls_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=5)
        tk.Button(btn_frame, text="Update Range Grids", command=self.update_range_grids).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Compare Ranges", command=self.compare_ranges).pack(side=tk.LEFT, padx=5)
        self.result_label = tk.Label(controls_frame, text="Left: N/A | Tie: N/A | Right: N/A")
        self.result_label.grid(row=3, column=0, columnspan=4, sticky="w", padx=10)
        canvas = tk.Canvas(master)
        canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        v_scrollbar = tk.Scrollbar(master, orient=tk.VERTICAL, command=canvas.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=v_scrollbar.set)
        grids_frame = tk.Frame(canvas)
        canvas.create_window((0,0), window=grids_frame, anchor="nw")
        grids_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        left_frame = tk.LabelFrame(grids_frame, text="Left Range")
        left_frame.grid(row=0, column=0, padx=5, pady=5)
        right_frame = tk.LabelFrame(grids_frame, text="Right Range")
        right_frame.grid(row=0, column=1, padx=5, pady=5)
        self.left_cells, self.left_selected = self.create_grid(left_frame, "left")
        self.right_cells, self.right_selected = self.create_grid(right_frame, "right")

    def create_grid(self, parent, grid_name):
        ranks = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
        cells = {}
        selected = set()
        for i, rank in enumerate(ranks):
            tk.Label(parent, text=rank, relief="ridge", width=2, height=1, bg="white").grid(row=i+1, column=0, padx=1, pady=1)
            tk.Label(parent, text=rank, relief="ridge", width=2, height=1, bg="white").grid(row=0, column=i+1, padx=1, pady=1)
        tk.Label(parent, text="", width=3, height=1, bg="white").grid(row=0, column=0, padx=1, pady=1)
        for i, r1 in enumerate(ranks):
            for j, r2 in enumerate(ranks):
                if i == j:
                    hand_cat = r1 * 2
                else:
                    high = ranks[min(i,j)]
                    low = ranks[max(i,j)]
                    hand_cat = high + low + ('s' if i < j else 'o')
                lbl = tk.Label(parent, text=hand_cat, width=4, height=1, bg="lightgrey", relief="ridge")
                lbl.grid(row=i+1, column=j+1, padx=1, pady=1)
                cells[(i,j)] = {"hand_cat": hand_cat, "label": lbl, "equity": None, "tooltip_text": "", "tooltip": ToolTip(lbl)}
                lbl.bind("<Button-1>", lambda e, pos=(i,j), grid=grid_name: self.toggle_cell(pos, grid))
                lbl.bind("<B1-Motion>", lambda e, pos=(i,j), grid=grid_name: self.drag_select(pos, grid))
                lbl.bind("<Enter>", lambda e, pos=(i,j), grid=grid_name: self.show_cell_tooltip(pos, grid))
                lbl.bind("<Leave>", lambda e, pos=(i,j), grid=grid_name: self.hide_cell_tooltip(pos, grid))
        return cells, selected

    def drag_select(self, pos, grid):
        if grid == "left":
            if pos not in self.left_selected:
                self.left_selected.add(pos)
                self.left_cells[pos]["label"].config(highlightbackground="blue", highlightthickness=2)
        else:
            if pos not in self.right_selected:
                self.right_selected.add(pos)
                self.right_cells[pos]["label"].config(highlightbackground="blue", highlightthickness=2)

    def toggle_cell(self, pos, grid):
        if grid == "left":
            if pos in self.left_selected:
                self.left_selected.remove(pos)
                self.left_cells[pos]["label"].config(highlightthickness=0)
            else:
                self.left_selected.add(pos)
                self.left_cells[pos]["label"].config(highlightbackground="blue", highlightthickness=2)
        else:
            if pos in self.right_selected:
                self.right_selected.remove(pos)
                self.right_cells[pos]["label"].config(highlightthickness=0)
            else:
                self.right_selected.add(pos)
                self.right_cells[pos]["label"].config(highlightbackground="blue", highlightthickness=2)

    def show_cell_tooltip(self, pos, grid):
        cell = self.left_cells[pos] if grid == "left" else self.right_cells[pos]
        cell["tooltip"].showtip(cell.get("tooltip_text", ""))

    def hide_cell_tooltip(self, pos, grid):
        if grid == "left":
            self.left_cells[pos]["tooltip"].hidetip()
        else:
            self.right_cells[pos]["tooltip"].hidetip()

    def get_range_from_grid(self, cells, selected):
        rng = []
        for pos, cell in cells.items():
            if pos in selected:
                rng.append(cell["hand_cat"])
        return rng

    def update_range_selection(self):
        lower = self.range_lower.get()/100.0
        upper = self.range_upper.get()/100.0
        self.left_selected = select_cells_by_percent(self.left_cells, lower, upper)
        self.right_selected = select_cells_by_percent(self.right_cells, lower, upper)
        for pos, cell in self.left_cells.items():
            if pos in self.left_selected:
                cell["label"].config(highlightbackground="blue", highlightthickness=2)
            else:
                cell["label"].config(highlightthickness=0)
        for pos, cell in self.right_cells.items():
            if pos in self.right_selected:
                cell["label"].config(highlightbackground="blue", highlightthickness=2)
            else:
                cell["label"].config(highlightthickness=0)

    def update_range_grids(self):
        try:
            board = parse_board(self.board_entry.get().strip())
        except Exception:
            board = []
        if len(board) == 0:
            try:
                conn = sqlite3.connect("preflop_equities.db")
                c = conn.cursor()
                right_range = self.get_range_from_grid(self.right_cells, self.right_selected)
                if not right_range:
                    right_range = [cell["hand_cat"] for cell in self.right_cells.values()]
                total_weight_R = sum(hand_weight(r) for r in right_range)
                for pos, cell in self.left_cells.items():
                    L = cell["hand_cat"]
                    sum_eq = 0.0
                    for r in right_range:
                        w = hand_weight(r)
                        c.execute("SELECT win, tie, true FROM preflop_equities WHERE user_hand=? AND opp_hand=?", (L, r))
                        row = c.fetchone()
                        if row:
                            win, tie, _ = row
                        else:
                            win, tie = 0, 0
                        eff = win + tie/2
                        sum_eq += eff * w
                    eq = sum_eq/total_weight_R if total_weight_R > 0 else 0
                    cell["equity"] = eq
                    cell["tooltip_text"] = f"{L}\nEquity vs opp: {eq*100:.1f}%"
                    cell["label"].config(bg=equity_to_color(eq))
                left_range = self.get_range_from_grid(self.left_cells, self.left_selected)
                if not left_range:
                    left_range = [cell["hand_cat"] for cell in self.left_cells.values()]
                total_weight_L = sum(hand_weight(r) for r in left_range)
                for pos, cell in self.right_cells.items():
                    R = cell["hand_cat"]
                    sum_eq = 0.0
                    for r in left_range:
                        w = hand_weight(r)
                        c.execute("SELECT win, tie, true FROM preflop_equities WHERE user_hand=? AND opp_hand=?", (R, r))
                        row = c.fetchone()
                        if row:
                            win, tie, _ = row
                        else:
                            win, tie = 0, 0
                        eff = win + tie/2
                        sum_eq += eff * w
                    eq = sum_eq/total_weight_L if total_weight_L > 0 else 0
                    cell["equity"] = eq
                    cell["tooltip_text"] = f"{R}\nEquity vs opp: {eq*100:.1f}%"
                    cell["label"].config(bg=equity_to_color(eq))
                conn.close()
                self.result_label.config(text="Range grids updated (preflop DB).")
            except Exception as e:
                print("DB update error:", e)
        else:
            sims = self.sim_depth.get()
            right_range = self.get_range_from_grid(self.right_cells, self.right_selected)
            if not right_range:
                right_range = [cell["hand_cat"] for cell in self.right_cells.values()]
            left_results = {cell["hand_cat"]: 0.0 for cell in self.left_cells.values()}
            count_left = {cell["hand_cat"]: 0 for cell in self.left_cells.values()}
            for _ in range(sims):
                deck = generate_deck()
                for card in board:
                    if card in deck: deck.remove(card)
                missing = 5 - len(board)
                runout = random.sample(deck, missing) if missing > 0 else []
                full_board = board + runout
                left_evals = {}
                for L in left_results.keys():
                    handL = get_valid_hand(L, set(full_board))
                    if handL:
                        left_evals[L] = evaluate_seven(handL + full_board)
                right_evals = {}
                for r in right_range:
                    handR = get_valid_hand(r, set(full_board))
                    if handR:
                        right_evals[r] = evaluate_seven(handR + full_board)
                if not right_evals:
                    continue
                for L, L_val in left_evals.items():
                    cnt = 0.0; tot = 0.0
                    for r, R_val in right_evals.items():
                        tot += 1
                        if L_val > R_val: 
                            cnt += 1
                        elif L_val == R_val: 
                            cnt += 0.5
                    if tot > 0:
                        left_results[L] += cnt/tot; count_left[L] += 1
            for L in left_results:
                eq = left_results[L] / count_left[L] if count_left[L] > 0 else 0
                for pos, cell in self.left_cells.items():
                    if cell["hand_cat"] == L:
                        cell["equity"] = eq
                        cell["tooltip_text"] = f"{L}\nEquity vs opp: {eq*100:.1f}%"
                        cell["label"].config(bg=equity_to_color(eq))
            left_range = self.get_range_from_grid(self.left_cells, self.left_selected)
            if not left_range:
                left_range = [cell["hand_cat"] for cell in self.left_cells.values()]
            right_results = {cell["hand_cat"]: 0.0 for cell in self.right_cells.values()}
            count_right = {cell["hand_cat"]: 0 for cell in self.right_cells.values()}
            for _ in range(sims):
                deck = generate_deck()
                for card in board:
                    if card in deck: deck.remove(card)
                missing = 5 - len(board)
                runout = random.sample(deck, missing) if missing > 0 else []
                full_board = board + runout
                left_evals = {}
                for L in left_range:
                    handL = get_valid_hand(L, set(full_board))
                    if handL:
                        left_evals[L] = evaluate_seven(handL + full_board)
                right_evals = {}
                for R in right_results.keys():
                    handR = get_valid_hand(R, set(full_board))
                    if handR:
                        right_evals[R] = evaluate_seven(handR + full_board)
                if not left_evals:
                    continue
                for R, R_val in right_evals.items():
                    cnt = 0.0; tot = 0.0
                    for L, L_val in left_evals.items():
                        tot += 1
                        if R_val > L_val: 
                            cnt += 1
                        elif R_val == L_val: 
                            cnt += 0.5
                    if tot > 0:
                        right_results[R] += cnt/tot; count_right[R] += 1
            for R in right_results:
                eq = right_results[R] / count_right[R] if count_right[R] > 0 else 0
                for pos, cell in self.right_cells.items():
                    if cell["hand_cat"] == R:
                        cell["equity"] = eq
                        cell["tooltip_text"] = f"{R}\nEquity vs opp: {eq*100:.1f}%"
                        cell["label"].config(bg=equity_to_color(eq))
            self.result_label.config(text="Range grids updated (postflop simulation).")

    def compare_ranges(self):
        """
        Simplified approach that only displays final left/right equity
        (ties split 0.5 each). We do one simulation pass for postflop.
        """
        import sqlite3

        # Parse the board
        try:
            board = parse_board(self.board_entry.get().strip())
        except Exception:
            board = []

        # Gather selected hands
        left_range = self.get_range_from_grid(self.left_cells, self.left_selected)
        if not left_range:
            left_range = [cell["hand_cat"] for cell in self.left_cells.values()]
        right_range = self.get_range_from_grid(self.right_cells, self.right_selected)
        if not right_range:
            right_range = [cell["hand_cat"] for cell in self.right_cells.values()]

        # Number of simulations
        sims = self.sim_depth.get()

        # ----- PRE-FLOP (No Board) -> Use DB approach (if you want) -----
        if len(board) == 0:
            try:
                conn = sqlite3.connect("preflop_equities.db")
                c = conn.cursor()

                total_weight = 0.0
                left_sum = 0.0
                right_sum = 0.0

                # For each hand L in left range, each hand R in right range,
                # gather (win, tie) from DB and add tie as 0.5 to each side
                for L in left_range:
                    wL = hand_weight(L)
                    for R in right_range:
                        wR = hand_weight(R)
                        total_weight += (wL * wR)

                        c.execute("SELECT win, tie, true FROM preflop_equities "
                                "WHERE user_hand=? AND opp_hand=?", (L, R))
                        row = c.fetchone()
                        if row:
                            win, tie, _ = row
                        else:
                            win, tie = 0, 0

                        # Add tie * 0.5 to each side
                        left_sum += (win + 0.5*tie) * wL * wR
                        # The other side's "win" is (1 - win - tie),
                        # but simpler is: right_sum += (lose + 0.5*tie).
                        # lose = 1 - win - tie
                        right_sum += ((1 - win - tie) + 0.5*tie) * wL * wR

                conn.close()

                if total_weight <= 0:
                    left_equity = 0
                    right_equity = 0
                else:
                    left_equity = left_sum / total_weight
                    right_equity = right_sum / total_weight

                self.result_label.config(
                    text=f"Left: {left_equity*100:.1f}% | Right: {right_equity*100:.1f}%"
                )
            except Exception as e:
                print("DB compare error:", e)
                self.result_label.config(text="Compare error (DB).")
            return

        # ----- POST-FLOP (Board given) -> Single-pass simulation -----
        import random
        from poker import generate_deck, evaluate_seven
        from hand_helpers import get_valid_hand

        left_sum = 0.0
        right_sum = 0.0
        total_weight = 0.0  # Sum of wL * wR for each matchup

        for _ in range(sims):
            deck = generate_deck()
            for card in board:
                if card in deck:
                    deck.remove(card)

            missing = 5 - len(board)
            runout = random.sample(deck, missing) if missing > 0 else []
            full_board = board + runout

            # Evaluate all valid combos in left range
            left_evals = {}
            for L in left_range:
                handL = get_valid_hand(L, set(full_board))
                if handL:
                    left_evals[L] = evaluate_seven(handL + full_board)

            # Evaluate all valid combos in right range
            right_evals = {}
            for R in right_range:
                handR = get_valid_hand(R, set(full_board))
                if handR:
                    right_evals[R] = evaluate_seven(handR + full_board)

            # If either side is empty this run, skip
            if not left_evals or not right_evals:
                continue

            # For every L vs R, compare
            for L, L_val in left_evals.items():
                wL = hand_weight(L)
                for R, R_val in right_evals.items():
                    wR = hand_weight(R)
                    # Weighted matchups
                    total_weight += (wL * wR)

                    if L_val > R_val:
                        left_sum += (wL * wR)
                    elif R_val > L_val:
                        right_sum += (wL * wR)
                    else:
                        # tie -> 0.5 each
                        left_sum += 0.5 * (wL * wR)
                        right_sum += 0.5 * (wL * wR)

        if total_weight <= 0:
            left_equity = 0.0
            right_equity = 0.0
        else:
            left_equity = left_sum / total_weight
            right_equity = right_sum / total_weight

        # Show final simplified results
        self.result_label.config(
            text=f"Left: {left_equity*100:.1f}% | Right: {right_equity*100:.1f}%"
        )
