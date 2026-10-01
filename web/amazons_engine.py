"""Standalone Amazons game engine bundled for WebAssembly (Pyodide).

Contains Board (bitboard-based), Move, Evaluators, and AI engines
(Random, Minimax, MCTS, Iterative Deepening) adapted for high-speed
in-browser execution via JSON messaging.
"""

import json
import math
import random
import time
from typing import Dict, List, Optional, Tuple


class Color:
    """Player color definitions."""
    W = "W"
    B = "B"

    @classmethod
    def opponent(cls, color: str) -> str:
        return cls.B if color == cls.W else cls.W


class Move:
    """Represents a complete move: queen displacement and arrow shot."""

    def __init__(self, start_pos: int, end_pos: int, arrow_pos: int):
        self.start_pos = int(start_pos)
        self.end_pos = int(end_pos)
        self.arrow_pos = int(arrow_pos)

    @staticmethod
    def to_algebraic(pos: int, size: int) -> str:
        if not (0 <= pos < size * size):
            return f"?{pos}"
        row = pos // size
        col = pos % size
        letter = chr(ord("a") + col)
        number = size - row
        return f"{letter}{number}"

    @staticmethod
    def from_algebraic(coord: str, size: int) -> int:
        coord = coord.lower().strip()
        col = ord(coord[0]) - ord("a")
        row_num = int(coord[1:])
        row = size - row_num
        return row * size + col

    def to_dict(self, size: int) -> dict:
        return {
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "arrow_pos": self.arrow_pos,
            "start_alg": self.to_algebraic(self.start_pos, size),
            "end_alg": self.to_algebraic(self.end_pos, size),
            "arrow_alg": self.to_algebraic(self.arrow_pos, size),
            "notation": f"{self.to_algebraic(self.start_pos, size)}-{self.to_algebraic(self.end_pos, size)}/{self.to_algebraic(self.arrow_pos, size)}"
        }

    def __repr__(self) -> str:
        return f"Move({self.start_pos} -> {self.end_pos} / arrow {self.arrow_pos})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Move):
            return False
        return (
            self.start_pos == other.start_pos
            and self.end_pos == other.end_pos
            and self.arrow_pos == other.arrow_pos
        )


class Board:
    """Bitboard-based Amazons board."""

    def __init__(self, size: int = 6):
        self.size = size
        self.white_bb = 0
        self.black_bb = 0
        self.arrow_bb = 0
        self.init_board()

    def copy(self) -> "Board":
        nb = Board(self.size)
        nb.white_bb = self.white_bb
        nb.black_bb = self.black_bb
        nb.arrow_bb = self.arrow_bb
        return nb

    def init_board(self) -> None:
        n = self.size
        self.white_bb = 0
        self.black_bb = 0
        self.arrow_bb = 0

        if n == 4:
            whites = [(0, 0), (0, n - 1)]
        elif n == 5:
            middle_row = n // 2
            offset = max(1, n // 4)
            whites = [
                (0, middle_row - offset),
                (0, middle_row + offset),
                (offset, middle_row),
            ]
        else:
            third = n // 3
            whites = [
                (third, 0),
                (third, n - 1),
                (0, third),
                (0, n - 1 - third),
            ]

        for row, col in whites:
            pos_white = row * n + col
            pos_black = (n - 1 - row) * n + (n - 1 - col)
            self.white_bb |= 1 << pos_white
            self.black_bb |= 1 << pos_black

    def occupied(self) -> int:
        return self.white_bb | self.black_bb | self.arrow_bb

    def get_queen_moves_iterator(self, start_pos: int, occupied_bb: int):
        row_start = start_pos // self.size
        col_start = start_pos % self.size
        directions = [
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (-1, 1), (1, -1), (1, 1),
        ]
        for dr, dc in directions:
            row = row_start
            col = col_start
            while True:
                row += dr
                col += dc
                if not (0 <= row < self.size and 0 <= col < self.size):
                    break
                pos = row * self.size + col
                if occupied_bb & (1 << pos):
                    break
                yield pos

    def get_legal_queen_destinations(self, start_pos: int) -> List[int]:
        return list(self.get_queen_moves_iterator(start_pos, self.occupied()))

    def get_legal_arrow_destinations(self, end_pos: int, start_pos: int) -> List[int]:
        occupied_after = (self.occupied() ^ (1 << start_pos)) | (1 << end_pos)
        return list(self.get_queen_moves_iterator(end_pos, occupied_after))

    def get_legal_moves(self, color: str):
        my_bb = self.white_bb if color == Color.W else self.black_bb
        occupied = self.occupied()
        temp_bb = my_bb
        while temp_bb:
            lsb = temp_bb & -temp_bb
            start_pos = lsb.bit_length() - 1
            temp_bb &= temp_bb - 1

            for end_pos in self.get_queen_moves_iterator(start_pos, occupied):
                mask_start = 1 << start_pos
                mask_end = 1 << end_pos
                occupied_after = (occupied & ~mask_start) | mask_end
                for arrow_pos in self.get_queen_moves_iterator(end_pos, occupied_after):
                    yield Move(start_pos, end_pos, arrow_pos)

    def has_moves(self, color: str) -> bool:
        my_bb = self.white_bb if color == Color.W else self.black_bb
        occupied = self.occupied()
        temp_bb = my_bb
        while temp_bb:
            lsb = temp_bb & -temp_bb
            pos = lsb.bit_length() - 1
            temp_bb &= temp_bb - 1
            moves = self.get_queen_moves_iterator(pos, occupied)
            try:
                next(moves)
                return True
            except StopIteration:
                continue
        return False

    def is_valid_queen_move(self, start_pos: int, end_pos: int, color: str) -> bool:
        my_bb = self.white_bb if color == Color.W else self.black_bb
        if not (my_bb & (1 << start_pos)):
            return False
        for pos in self.get_queen_moves_iterator(start_pos, self.occupied()):
            if pos == end_pos:
                return True
        return False

    def is_valid_arrow_shot(self, end_pos: int, arrow_pos: int, start_pos: int) -> bool:
        occupied_after = (self.occupied() ^ (1 << start_pos)) | (1 << end_pos)
        for pos in self.get_queen_moves_iterator(end_pos, occupied_after):
            if pos == arrow_pos:
                return True
        return False

    def is_valid_move(self, move: Move, color: str) -> bool:
        if not self.is_valid_queen_move(move.start_pos, move.end_pos, color):
            return False
        return self.is_valid_arrow_shot(move.end_pos, move.arrow_pos, move.start_pos)

    def move_queen(self, start_pos: int, end_pos: int, color: str) -> None:
        if color == Color.W:
            self.white_bb ^= 1 << start_pos
            self.white_bb |= 1 << end_pos
        else:
            self.black_bb ^= 1 << start_pos
            self.black_bb |= 1 << end_pos

    def place_arrow(self, arrow_pos: int) -> None:
        self.arrow_bb |= 1 << arrow_pos

    def make_move(self, move: Move, color: str) -> None:
        self.move_queen(move.start_pos, move.end_pos, color)
        self.place_arrow(move.arrow_pos)

    def play_move(self, move: Move) -> None:
        if (self.white_bb >> move.start_pos) & 1:
            color = Color.W
        elif (self.black_bb >> move.start_pos) & 1:
            color = Color.B
        else:
            raise ValueError(f"No queen at {move.start_pos}")
        self.make_move(move, color)

    def undo_move(self, move: Move, color: str) -> None:
        self.arrow_bb &= ~(1 << move.arrow_pos)
        if color == Color.W:
            self.white_bb &= ~(1 << move.end_pos)
            self.white_bb |= 1 << move.start_pos
        else:
            self.black_bb &= ~(1 << move.end_pos)
            self.black_bb |= 1 << move.start_pos

    def get_board_array(self) -> List[List[str]]:
        board_array = []
        for row in range(self.size):
            line = []
            for col in range(self.size):
                pos = row * self.size + col
                if self.white_bb & (1 << pos):
                    line.append("W")
                elif self.black_bb & (1 << pos):
                    line.append("B")
                elif self.arrow_bb & (1 << pos):
                    line.append("X")
                else:
                    line.append(".")
            board_array.append(line)
        return board_array

    def calculate_territory_scores(self) -> Tuple[int, int]:
        occupied = self.occupied()

        def get_reachable_territory(queens_bb: int) -> int:
            reachable = 0
            frontier = queens_bb
            while frontier:
                reachable |= frontier
                new_frontier = 0
                temp_frontier = frontier
                while temp_frontier:
                    lsb = temp_frontier & -temp_frontier
                    pos = lsb.bit_length() - 1
                    temp_frontier &= temp_frontier - 1
                    row = pos // self.size
                    col = pos % self.size
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue
                            next_row = row + dr
                            next_col = col + dc
                            if 0 <= next_row < self.size and 0 <= next_col < self.size:
                                next_pos = next_row * self.size + next_col
                                if not (occupied & (1 << next_pos)) and not (reachable & (1 << next_pos)):
                                    new_frontier |= 1 << next_pos
                frontier = new_frontier
            return reachable & ~queens_bb

        white_t = get_reachable_territory(self.white_bb)
        black_t = get_reachable_territory(self.black_bb)
        return white_t.bit_count(), black_t.bit_count()


# =====================================================================
# Evaluators & AI Engines
# =====================================================================

class Evaluator:
    @staticmethod
    def evaluate(board: Board, color: str, evaluator_type: str = "hybrid") -> float:
        if evaluator_type == "territory":
            w_score, b_score = board.calculate_territory_scores()
            return float(w_score - b_score if color == Color.W else b_score - w_score)

        if evaluator_type == "mobility":
            my_moves = sum(1 for _ in board.get_legal_moves(color))
            opp_color = Color.opponent(color)
            opp_moves = sum(1 for _ in board.get_legal_moves(opp_color))
            return float(my_moves - opp_moves)

        # Hybrid
        w_score, b_score = board.calculate_territory_scores()
        territory_diff = w_score - b_score if color == Color.W else b_score - w_score
        my_moves = sum(1 for _ in board.get_legal_moves(color))
        opp_color = Color.opponent(color)
        opp_moves = sum(1 for _ in board.get_legal_moves(opp_color))
        mobility_diff = my_moves - opp_moves
        return 0.7 * territory_diff + 0.3 * mobility_diff


class RandomEngine:
    def best_move(self, board: Board, color: str) -> Optional[Move]:
        legal_moves = list(board.get_legal_moves(color))
        if not legal_moves:
            return None
        return random.choice(legal_moves)


class MinimaxEngine:
    def __init__(self, depth: int = 2, evaluator: str = "hybrid", time_limit: Optional[float] = 1.5):
        self.depth = depth
        self.evaluator = evaluator
        self.time_limit = time_limit
        self.start_time = None

    def _time_exceeded(self) -> bool:
        return self.time_limit is not None and (time.time() - self.start_time >= self.time_limit)

    def best_move(self, board: Board, color: str) -> Optional[Move]:
        self.start_time = time.time()
        best_val = -math.inf
        chosen_move = None
        alpha = -math.inf
        beta = math.inf

        legal_moves = list(board.get_legal_moves(color))
        if not legal_moves:
            return None

        # Sort moves heuristically if many (e.g. center preference)
        center = board.size / 2.0
        legal_moves.sort(
            key=lambda m: (
                abs((m.end_pos // board.size) - center) + abs((m.end_pos % board.size) - center)
            )
        )

        for move in legal_moves:
            if self._time_exceeded():
                break

            board.make_move(move, color)
            val = self._min_value(board, Color.opponent(color), self.depth - 1, alpha, beta)
            board.undo_move(move, color)

            if val > best_val:
                best_val = val
                chosen_move = move

            alpha = max(alpha, best_val)
            if beta <= alpha:
                break

        return chosen_move if chosen_move is not None else (legal_moves[0] if legal_moves else None)

    def _min_value(self, board: Board, color: str, depth: int, alpha: float, beta: float) -> float:
        if self._time_exceeded() or depth <= 0 or not board.has_moves(color):
            return -Evaluator.evaluate(board, color, self.evaluator)

        min_val = math.inf
        for move in board.get_legal_moves(color):
            if self._time_exceeded():
                break
            board.make_move(move, color)
            val = self._max_value(board, Color.opponent(color), depth - 1, alpha, beta)
            board.undo_move(move, color)
            min_val = min(min_val, val)
            beta = min(beta, min_val)
            if beta <= alpha:
                break
        return min_val

    def _max_value(self, board: Board, color: str, depth: int, alpha: float, beta: float) -> float:
        if self._time_exceeded() or depth <= 0 or not board.has_moves(color):
            return Evaluator.evaluate(board, color, self.evaluator)

        max_val = -math.inf
        for move in board.get_legal_moves(color):
            if self._time_exceeded():
                break
            board.make_move(move, color)
            val = self._min_value(board, Color.opponent(color), depth - 1, alpha, beta)
            board.undo_move(move, color)
            max_val = max(max_val, val)
            alpha = max(alpha, max_val)
            if beta <= alpha:
                break
        return max_val


class MCTSNode:
    def __init__(self, board: Board, parent=None, move=None, color=None):
        self.parent = parent
        self.move = move
        self.color = color
        self.children = []
        self.visits = 0
        self.wins = 0
        self.untried_moves = list(board.get_legal_moves(color))
        random.shuffle(self.untried_moves)

    def uct_select_child(self):
        exploration_weight = 1.41
        return max(
            self.children,
            key=lambda child: ((child.visits - child.wins) / child.visits)
            + exploration_weight * math.sqrt(math.log(self.visits) / child.visits),
        )


class MCTSEngine:
    def __init__(self, time_limit: float = 1.5):
        self.time_limit = time_limit

    def best_move(self, board: Board, color: str) -> Optional[Move]:
        start_time = time.time()
        root = MCTSNode(board=board, color=color)
        if not root.untried_moves:
            return None

        while time.time() - start_time < self.time_limit:
            node = root
            sim_board = board.copy()

            # 1. Selection
            while not node.untried_moves and node.children:
                node = node.uct_select_child()
                sim_board.make_move(node.move, Color.opponent(node.color))

            # 2. Expansion
            if node.untried_moves:
                move = node.untried_moves.pop()
                sim_board.make_move(move, node.color)
                child_node = MCTSNode(
                    board=sim_board,
                    parent=node,
                    move=move,
                    color=Color.opponent(node.color),
                )
                node.children.append(child_node)
                node = child_node

            # 3. Simulation (Rollout)
            curr_color = node.color
            depth = 0
            max_sim_depth = 12
            while sim_board.has_moves(curr_color) and depth < max_sim_depth:
                moves = list(sim_board.get_legal_moves(curr_color))
                if not moves:
                    break
                sim_board.make_move(random.choice(moves), curr_color)
                curr_color = Color.opponent(curr_color)
                depth += 1

            winner = Color.opponent(curr_color) if not sim_board.has_moves(curr_color) else None
            if winner is None:
                w_t, b_t = sim_board.calculate_territory_scores()
                winner = Color.W if w_t >= b_t else Color.B

            # 4. Backpropagation
            while node is not None:
                node.visits += 1
                if node.color != winner:
                    node.wins += 1
                node = node.parent

        if not root.children:
            return root.untried_moves[0] if root.untried_moves else None

        best_child = max(root.children, key=lambda c: c.visits)
        return best_child.move


class IterativeDeepening:
    def __init__(self, evaluator: str = "hybrid", time_limit: float = 1.5):
        self.evaluator = evaluator
        self.time_limit = time_limit

    def best_move(self, board: Board, color: str) -> Optional[Move]:
        start_time = time.time()
        best_move = None
        for depth in range(1, 10):
            remaining = self.time_limit - (time.time() - start_time)
            if remaining <= 0.05:
                break
            engine = MinimaxEngine(depth=depth, evaluator=self.evaluator, time_limit=remaining)
            move = engine.best_move(board, color)
            if move is not None:
                best_move = move
            if engine._time_exceeded():
                break
        return best_move if best_move is not None else RandomEngine().best_move(board, color)


# =====================================================================
# High-Level Game Session Controller for Web (JSON-based)
# =====================================================================

class GameSession:
    def __init__(self, size: int = 6):
        self.size = size
        self.board = Board(size)
        self.current_player = Color.W
        self.history = []  # list of dicts {start, end, arrow, color}
        self.redo_stack = []

    def reset(self, size: int = 6):
        self.size = size
        self.board = Board(size)
        self.current_player = Color.W
        self.history = []
        self.redo_stack = []
        return self.get_state()

    def get_state(self) -> dict:
        w_t, b_t = self.board.calculate_territory_scores()
        w_has_moves = self.board.has_moves(Color.W)
        b_has_moves = self.board.has_moves(Color.B)
        game_over = False
        winner = None

        if self.current_player == Color.W and not w_has_moves:
            game_over = True
            winner = Color.B
        elif self.current_player == Color.B and not b_has_moves:
            game_over = True
            winner = Color.W

        return {
            "size": self.size,
            "grid": self.board.get_board_array(),
            "current_player": self.current_player,
            "white_territory": w_t,
            "black_territory": b_t,
            "game_over": game_over,
            "winner": winner,
            "history_count": len(self.history),
            "can_undo": len(self.history) > 0,
            "can_redo": len(self.redo_stack) > 0,
        }

    def get_queen_moves(self, start_pos: int) -> List[int]:
        return self.board.get_legal_queen_destinations(start_pos)

    def get_arrow_moves(self, end_pos: int, start_pos: int) -> List[int]:
        return self.board.get_legal_arrow_destinations(end_pos, start_pos)

    def play_move(self, start_pos: int, end_pos: int, arrow_pos: int) -> dict:
        move = Move(start_pos, end_pos, arrow_pos)
        if not self.board.is_valid_move(move, self.current_player):
            return {"success": False, "error": "Invalid move"}

        self.board.make_move(move, self.current_player)
        self.history.append({
            "start": start_pos,
            "end": end_pos,
            "arrow": arrow_pos,
            "color": self.current_player,
            "notation": move.to_dict(self.size)["notation"]
        })
        self.redo_stack.clear()
        self.current_player = Color.opponent(self.current_player)
        state = self.get_state()
        state["success"] = True
        state["last_move"] = move.to_dict(self.size)
        return state

    def undo(self) -> dict:
        if not self.history:
            return {"success": False, "error": "Nothing to undo"}

        last = self.history.pop()
        move = Move(last["start"], last["end"], last["arrow"])
        self.board.undo_move(move, last["color"])
        self.current_player = last["color"]
        self.redo_stack.append(last)
        state = self.get_state()
        state["success"] = True
        return state

    def redo(self) -> dict:
        if not self.redo_stack:
            return {"success": False, "error": "Nothing to redo"}

        nxt = self.redo_stack.pop()
        move = Move(nxt["start"], nxt["end"], nxt["arrow"])
        self.board.make_move(move, nxt["color"])
        self.history.append(nxt)
        self.current_player = Color.opponent(nxt["color"])
        state = self.get_state()
        state["success"] = True
        return state

    def compute_ai_move(self, ai_mode: str = "minimax", ai_time: float = 1.0, depth: int = 2, evaluator: str = "hybrid") -> dict:
        if ai_mode == "random":
            engine = RandomEngine()
        elif ai_mode == "mcts":
            engine = MCTSEngine(time_limit=ai_time)
        elif ai_mode == "iterative":
            engine = IterativeDeepening(evaluator=evaluator, time_limit=ai_time)
        else:
            engine = MinimaxEngine(depth=depth, evaluator=evaluator, time_limit=ai_time)

        move = engine.best_move(self.board, self.current_player)
        if move is None:
            return {"success": False, "error": "No legal move available"}

        return {
            "success": True,
            "move": move.to_dict(self.size)
        }


# Global session singleton for web interface
_SESSION = GameSession(6)

def web_reset(size=6):
    return json.dumps(_SESSION.reset(int(size)))

def web_get_state():
    return json.dumps(_SESSION.get_state())

def web_get_queen_moves(start_pos):
    return json.dumps(_SESSION.get_queen_moves(int(start_pos)))

def web_get_arrow_moves(end_pos, start_pos):
    return json.dumps(_SESSION.get_arrow_moves(int(end_pos), int(start_pos)))

def web_play_move(start_pos, end_pos, arrow_pos):
    return json.dumps(_SESSION.play_move(int(start_pos), int(end_pos), int(arrow_pos)))

def web_undo():
    return json.dumps(_SESSION.undo())

def web_redo():
    return json.dumps(_SESSION.redo())

def web_compute_ai_move(ai_mode="minimax", ai_time=1.0, depth=2, evaluator="hybrid"):
    return json.dumps(_SESSION.compute_ai_move(
        ai_mode=str(ai_mode),
        ai_time=float(ai_time),
        depth=int(depth),
        evaluator=str(evaluator)
    ))
