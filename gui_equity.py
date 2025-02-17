import tkinter as tk
from tkinter import ttk
import threading, concurrent.futures, sqlite3
from poker import parse_hand, parse_board, generate_deck, evaluate_seven, compare_hands, compute_equity
from hand_helpers import canonicalize_hand, get_valid_hand, hand_weight, static_hand_rank, equity_to_color, select_cells_by_percent
from tooltip import ToolTip

class EquityGUI:
    def __init__(self, master):
        self.master = master
        main_frame = tk.Frame(master)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel for user input and controls
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
        tk.Label(left_frame, text="Select Range Lower %:").pack(anchor=tk.W, pady=(10,0))
        self.range_lower = tk.IntVar(value=0)
        tk.Scale(left_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.range_lower,
                 command=lambda v: self.update_range_selection()).pack(anchor=tk.W)
        tk.Label(left_frame, text="Select Range Upper %:").pack(anchor=tk.W, pady=(5,0))
        self.range_upper = tk.IntVar(value=100)
        tk.Scale(left_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.range_upper,
                 command=lambda v: self.update_range_selection()).pack(anchor=tk.W)
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
        
        # Right panel for the grid
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
        
        # Create a grid of cells showing hand categories
        self.ranks = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
        self.cells = {}
        self.selected_cells = set()
        for i, rank in enumerate(self.ranks):
            tk.Label(self.grid_frame, text=rank, relief="ridge", width=3, height=2, bg="white").grid(row=i+1, column=0, padx=1, pady=1)
            tk.Label(self.grid_frame, text=rank, relief="ridge", width=3, height=2, bg="white").grid(row=0, column=i+1, padx=1, pady=1)
        tk.Label(self.grid_frame, text="", width=4, height=2, bg="white").grid(row=0, column=0, padx=1, pady=1)
        for i, r1 in enumerate(self.ranks):
            for j, r2 in enumerate(self.ranks):
                if i == j:
                    hand_cat = r1 * 2
                else:
                    high = self.ranks[min(i,j)]
                    low = self.ranks[max(i,j)]
                    hand_cat = high + low + ('s' if i < j else 'o')
                label = tk.Label(self.grid_frame, text=hand_cat, width=5, height=2, bg="lightgrey", relief="ridge")
                label.grid(row=i+1, column=j+1, padx=1, pady=1)
                ttip = ToolTip(label)
                self.cells[(i,j)] = {"hand_cat": hand_cat, "label": label, "equity": None, "tie": None, "tooltip": ttip}
                label.bind("<Button-1>", lambda e, pos=(i,j): self.toggle_cell(pos))
                label.bind("<B1-Motion>", lambda e, pos=(i,j): self.drag_select(pos))
                label.bind("<Enter>", lambda e, pos=(i,j): self.show_tooltip(pos))
                label.bind("<Leave>", lambda e, pos=(i,j): self.hide_tooltip(pos))
                
    def drag_select(self, pos):
        if pos not in self.selected_cells:
            self.selected_cells.add(pos)
            self.cells[pos]["label"].config(highlightbackground="blue", highlightthickness=2)
            self.update_compound_equity()

    def toggle_cell(self, pos):
        if pos in self.selected_cells:
            self.selected_cells.remove(pos)
            self.cells[pos]["label"].config(highlightthickness=0)
        else:
            self.selected_cells.add(pos)
            self.cells[pos]["label"].config(highlightbackground="blue", highlightthickness=2)
        self.update_compound_equity()

    def update_grid(self):
        self.status_label.config(text="Updating grid...")
        self.master.update_idletasks()
        hand_str = self.hand_entry.get().strip()
        board_str = self.board_entry.get().strip()
        if not hand_str:
            self.status_label.config(text="No user hand given. Enter a hand, then click Update Grid.")
            return
        try:
            user_hand = parse_hand(hand_str)
        except Exception as e:
            self.status_label.config(text=f"Error in user hand: {e}")
            return
        try:
            board = parse_board(board_str)
        except Exception as e:
            self.status_label.config(text=f"Error in board: {e}")
            return
        threading.Thread(target=self.compute_all_equities, args=(user_hand, board), daemon=True).start()

    def compute_all_equities(self, user_hand, board):
        results = {}
        if len(board) == 0:
            try:
                conn = sqlite3.connect("preflop_equities.db")
                c = conn.cursor()
                canonical_user = canonicalize_hand(user_hand)
                for pos, data in self.cells.items():
                    opp_cat = data["hand_cat"]
                    c.execute("SELECT win, tie, true FROM preflop_equities WHERE user_hand=? AND opp_hand=?", (canonical_user, opp_cat))
                    row = c.fetchone()
                    if row:
                        win, tie, true_eq = row
                        results[pos] = (win, tie)
                    else:
                        results[pos] = None
                conn.close()
            except Exception as e:
                print("DB lookup failed:", e)
                results = {}
        if not results or any(v is None for v in results.values()):
            forbidden = set(board + user_hand)
            sims = self.sim_depth.get()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_pos = {}
                for pos, data in self.cells.items():
                    opp_hand = get_valid_hand(data["hand_cat"], forbidden)
                    if opp_hand is None:
                        results[pos] = None
                    else:
                        future = executor.submit(compute_equity, user_hand, opp_hand, board, num_simulations=sims)
                        future_to_pos[future] = pos
                for future in concurrent.futures.as_completed(future_to_pos):
                    pos = future_to_pos[future]
                    try:
                        win, tie, _ = future.result()
                        results[pos] = (win, tie)
                    except Exception as e:
                        results[pos] = "error"
        self.master.after(0, lambda: self.update_grid_ui(results))

    def update_grid_ui(self, results):
        for pos, data in self.cells.items():
            hand_cat = data["hand_cat"]
            result = results.get(pos, None)
            if result is None:
                data["equity"] = None; data["tie"] = None
                data["label"].config(bg="grey")
                data["tooltip"].text = f"{hand_cat}\nN/A"
            elif result == "error":
                data["equity"] = None; data["tie"] = None
                data["label"].config(bg="grey")
                data["tooltip"].text = f"{hand_cat}\nErr"
            else:
                win, tie = result
                data["equity"] = win; data["tie"] = tie
                eff = win + tie/2
                data["label"].config(bg=equity_to_color(eff))
                data["tooltip"].text = f"{hand_cat}\nWin: {win*100:.1f}%, Tie: {tie*100:.1f}%"
        self.status_label.config(text="Grid updated.")
        self.update_compound_equity()

    def update_range_selection(self):
        lower = self.range_lower.get()/100.0
        upper = self.range_upper.get()/100.0
        sel = select_cells_by_percent(self.cells, lower, upper)
        self.selected_cells = sel
        for pos, data in self.cells.items():
            if pos in sel:
                data["label"].config(highlightbackground="blue", highlightthickness=2)
            else:
                data["label"].config(highlightthickness=0)
        self.update_compound_equity()

    def update_compound_equity(self):
        total_w = 0
        total_eff = 0
        for data in self.cells.values():
            if data["equity"] is not None:
                w = hand_weight(data["hand_cat"])
                total_w += w
                total_eff += (data["equity"] + data["tie"]/2) * w
        comp_all = total_eff/total_w if total_w > 0 else 0
        sel_w = 0
        sel_eff = 0
        for pos in self.selected_cells:
            data = self.cells[pos]
            if data["equity"] is not None:
                w = hand_weight(data["hand_cat"])
                sel_w += w
                sel_eff += (data["equity"] + data["tie"]/2) * w
        comp_range = sel_eff/sel_w if sel_w > 0 else 0
        self.compound_all_label.config(text=f"Compound Equity vs All: {comp_all*100:.1f}%")
        self.compound_range_label.config(text=f"Compound Equity vs Selected Range: {comp_range*100:.1f}%")
        def po(eq):
            if eq <= 0:
                return "∞"
            return f"{(1-eq)/eq:.2f} : 1"
        self.pot_odds_all_label.config(text=f"Pot Odds Needed (All): {po(comp_all)}")
        self.pot_odds_range_label.config(text=f"Pot Odds Needed (Range): {po(comp_range)}")

    def show_tooltip(self, pos):
        self.cells[pos]["tooltip"].showtip(self.cells[pos]["tooltip"].text)

    def hide_tooltip(self, pos):
        self.cells[pos]["tooltip"].hidetip()
