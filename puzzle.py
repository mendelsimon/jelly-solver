from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from collections import deque
from copy import deepcopy
import colorama

class Color(Enum):
    red = 1
    green = 2
    blue = 3
    yellow = 4
    x = 5 # Block

class Direction(Enum):
    up = (0, -1)
    right = (1, 0)
    down = (0, 1)
    left = (-1, 0)

@dataclass
class Coord:
    x: int
    y: int

    @classmethod
    def from_2d(cls, idx: int, width: int):
        return cls(idx % width, idx // width)

    def __add__(self, addend):
        if addend.__class__ is Direction:
            return Coord(self.x + addend.value[0], self.y + addend.value[1])

class Entity:
    pass

class Tile(Entity):
    pass

class Movable(Entity):
    def __init__(self, coords: list[Coord], color: Color, is_anchored: bool) -> None:
        self.coords: list[Coord] = coords
        self.color: Color = color
        self.is_anchored: bool = is_anchored

    def clone(self):
        return self.__class__(self.coords.copy(), self.color, self.is_anchored)

class Jelly(Movable):
    pass

class Block(Movable):
    def __init__(self, coords: list[Coord], _=None, __=None) -> None:
        super().__init__(coords, Color.x, False)

@dataclass
class StateTransition:
    state: State
    movable_idx: int
    direction: Direction

class State:
    def __init__(self, movables: list[Movable], tile_locations: list[Coord], width: int = 14, height: int = 10, attached_movables = None) -> None:
        self.movables: list[Movable] = movables
        self.width: int = width
        self.height: int = height
        self.movable_idx_board: list[Optional[int]] = []
        self.tile_board: list[bool] = [False] * (width * height)
        self.attached_movables: dict[int, set[int]] = attached_movables if attached_movables is not None else {}
        self.attached_chunks: list[list[int]]
        self._rebuild_attached_chunks()
        for coord in tile_locations:
            self.tile_board[self._coord_to_index(coord)] = True
        self._rebuild_board()

    def __hash__(self) -> int:
        hash_list = []
        for idx in self.movable_idx_board:
            if idx is None:
                hash_list.append(None)
            else:
                hash_list.append((idx, self.movables[idx].color))
        return hash(tuple(hash_list))

    def __eq__(self, other: object) -> bool:
        return other.__class__ is self.__class__ and self.movable_idx_board == other.movable_idx_board

    def _coord_to_index(self, coord: Coord):
        return coord.x + coord.y * self.width

    def is_win_state(self):
        colors = set()
        for movable in self.movables:
            if movable.__class__ is Jelly and movable.color in colors:
                return False
            colors.add(movable.color)
        return True

    def lookup_tile(self, coord: Coord) -> bool:
        return self.tile_board[self._coord_to_index(coord)]

    def lookup_movable(self, coord: Coord) -> Optional[int]:
        return self.movable_idx_board[self._coord_to_index(coord)]

    def clone(self) -> State:
        new_state: State = State([movable.clone() for movable in self.movables], [], self.width, self.height, deepcopy(self.attached_movables))
        new_state.tile_board = self.tile_board
        new_state.movable_idx_board = self.movable_idx_board
        return new_state

    def _rebuild_board(self):
        self.movable_idx_board = [None] * (self.width * self.height)
        for idx, movable in enumerate(self.movables):
            for coord in movable.coords:
                self.movable_idx_board[coord.x + self.width * coord.y] = idx

    def move(self, movable_idx: int, direction: Direction) -> Optional[State]:
        if direction not in (Direction.left, Direction.right):
            return None
        state = self._move_movable_in_direction(movable_idx, direction, {movable_idx})
        if state is None:
            return None
        state._gravity()
        state._fuse_movables()
        state._rebuild_board()
        return state

    def get_all_state_transitions(self) -> list[StateTransition]:
        state_transitions = []
        for movable_idx in range(len(self.movables)):
            new_state = self.move(movable_idx, Direction.left)
            if new_state:
                state_transitions.append(StateTransition(new_state, movable_idx, Direction.left))
            new_state = self.move(movable_idx, Direction.right)
            if new_state:
                state_transitions.append(StateTransition(new_state, movable_idx, Direction.right))
        return state_transitions

    def _move_movable_in_direction(self, movable_idx: int, direction: Direction, movables_moved: set[int]) -> Optional[State]:
        if self.movables[movable_idx].is_anchored:
            return None

        state = self.clone()
        for coord in self.movables[movable_idx].coords:
            new_coord = coord + direction
            if state.lookup_tile(new_coord):
                return None
            pushed_against_movable_idx = state.lookup_movable(new_coord)
            if pushed_against_movable_idx is not None and pushed_against_movable_idx not in movables_moved:
                # We're pushing against a new movable
                movables_moved.add(pushed_against_movable_idx)
                state = state._move_movable_in_direction(pushed_against_movable_idx, direction, movables_moved.copy())
                if state is None:
                    return None
        for attached_movable_idx in state.attached_movables.get(movable_idx, []):
            if attached_movable_idx not in movables_moved:
                movables_moved.add(attached_movable_idx)
                state = state._move_movable_in_direction(attached_movable_idx, direction, movables_moved.copy())
                if state is None:
                    return None

        state.movables[movable_idx].coords = [coord + direction for coord in state.movables[movable_idx].coords]
        state._rebuild_board()
        return state

    def _rebuild_attached_chunks(self):
        seen = set()
        chunks = []
        for start_movable_idx in range(len(self.movables)):
            if start_movable_idx in seen:
                continue
            seen.add(start_movable_idx)
            chunk = [start_movable_idx]
            to_explore = deque(self.attached_movables.get(start_movable_idx, ()))
            while to_explore:
                idx = to_explore.popleft()
                if idx in seen:
                    continue
                seen.add(idx)
                chunk.append(idx)
                to_explore.extend(self.attached_movables[idx])
            chunks.append(chunk)
        self.attached_chunks = chunks

    def _gravity(self) -> Optional[State]:
        direction = Direction.down
        movable_moved = True
        while movable_moved:
            movable_moved = False
            for chunk in self.attached_chunks:
                can_fall = True
                for movable_idx in chunk:
                    movable = self.movables[movable_idx]
                    if movable.is_anchored:
                        can_fall = False
                        break
                    for coord in movable.coords:
                        new_coord = coord + direction
                        on_movable = self.lookup_movable(new_coord)
                        if self.lookup_tile(new_coord) or (on_movable is not None and on_movable != movable_idx and on_movable not in self.attached_movables.get(movable_idx, ())):
                            # There's a tile there or There's a movable there that is not the current one and not attached
                            can_fall = False
                            break
                    if not can_fall:
                        break
                if can_fall:
                    movable_moved = True
                    for movable_idx in chunk:
                        self.movables[movable_idx].coords = [coord + direction for coord in self.movables[movable_idx].coords]
                        self._rebuild_board()

    def _fuse_movables(self) -> Optional[State]:
        movable_idx = 0
        while movable_idx < len(self.movables):
            movable = self.movables[movable_idx]
            coord_idx = 0
            while coord_idx < len(movable.coords):
                for direction in Direction:
                    neighbor_idx = self.lookup_movable(movable.coords[coord_idx] + direction)
                    if (
                        neighbor_idx is not None
                        and neighbor_idx != movable_idx
                        and movable.__class__ is Jelly
                        and self.movables[neighbor_idx].color == movable.color
                    ):
                        movable.coords.extend(self.movables[neighbor_idx].coords)
                        movable.is_anchored = movable.is_anchored or self.movables[neighbor_idx].is_anchored
                        del self.movables[neighbor_idx]
                        self._rebuild_board()
                        self._adjust_attached_after_fusing(movable_idx, neighbor_idx)
                coord_idx += 1
            movable_idx += 1

    def _adjust_attached_after_fusing(self, fused_to_idx, fused_from_idx):
        new_attached_movables = {}
        new_fused_attached = set()
        # First handle the union-ed sets of the fused from/to movables
        if fused_to_idx in self.attached_movables:
            new_fused_attached = new_fused_attached.union(self.attached_movables[fused_to_idx])
            del self.attached_movables[fused_to_idx]
        if fused_from_idx in self.attached_movables:
            new_fused_attached = new_fused_attached.union(self.attached_movables[fused_from_idx])
            del self.attached_movables[fused_from_idx]
        if new_fused_attached:
            new_attached_movables[fused_to_idx] = {
                attached_idx - 1 if attached_idx > fused_from_idx else attached_idx
                for attached_idx in new_fused_attached
            }
        for idx, values in self.attached_movables.items():
            if idx > fused_from_idx:
                idx -= 1
            new_attached_for_idx = set()
            for attached_idx in values:
                if attached_idx == fused_from_idx:
                    new_attached_for_idx.add(fused_to_idx)
                elif attached_idx > fused_from_idx:
                    new_attached_for_idx.add(attached_idx - 1)
                else:
                    new_attached_for_idx.add(attached_idx)
            new_attached_movables[idx] = new_attached_for_idx
        self.attached_movables = new_attached_movables
        self._rebuild_attached_chunks()

def print_state(state: State):
    color_lookup = {
        Color.red: colorama.Fore.RED,
        Color.green: colorama.Fore.GREEN,
        Color.blue: colorama.Fore.BLUE,
        Color.yellow: colorama.Fore.YELLOW,
        Color.x: colorama.Fore.MAGENTA,
    }
    out = ''
    for i in range(state.width * state.height):
        if i % state.width == 0 and i > 0:
            out += '\n'
        if state.tile_board[i]:
            out += '#'
        elif state.movable_idx_board[i] is not None:
            color = state.movables[state.movable_idx_board[i]].color
            out += color_lookup[color] + str(state.movable_idx_board[i]) + colorama.Style.RESET_ALL
        else:
            out += ' '

    out += "\n"
    for color in Color:
        out += color.name + "(" + ' '.join(str(i) for i, m in enumerate(state.movables) if m.color == color) + ") "
    out += "\n"

    print(out)
    return out

def print_transition(transition: StateTransition, print_idx_and_dir=True):
    color_lookup = {
        Color.red: colorama.Fore.RED,
        Color.green: colorama.Fore.GREEN,
        Color.blue: colorama.Fore.BLUE,
        Color.yellow: colorama.Fore.YELLOW,
        Color.x: colorama.Fore.MAGENTA,
    }
    if print_idx_and_dir:
        print(transition.movable_idx, transition.direction.name)
    print_state(transition.state)

def move(state: State, movable_idx: int, direction: Direction):
    new_state = state.move(movable_idx, direction)
    if (new_state):
        state = new_state
    print_transition(StateTransition(state, movable_idx, direction))
    return state

def parse_puzzle(raw_text: str) -> State:
    puzzle_string, definition_strings = raw_text.split("\n\n")
    definition_strings = definition_strings.split("\n")
    width = len(puzzle_string.split("\n")[0])
    height = len(puzzle_string.split("\n"))
    flat_puzzle_string = puzzle_string.replace("\n", "")
    tile_locations = [Coord.from_2d(i, width) for i in range(len(flat_puzzle_string)) if flat_puzzle_string[i] == '#']
    movables = []
    attachments = {}

    movable_indices = {}
    for definition in definition_strings:
        if definition == '':
            break

        if definition.startswith('@'):
            src, *attached = definition[1:].split(' ')
            attachments[movable_indices[src]] = set([movable_indices[_id] for _id in attached])
        else:
            _id, _color, *_is_anchored = definition.split(' ')
            coords = [Coord.from_2d(i, width) for i in range(len(flat_puzzle_string)) if flat_puzzle_string[i] == _id]
            color = Color[_color]
            if color == Color.x:
                movables.append(Block(coords))
            else:
                movables.append(Jelly(coords, color, bool(_is_anchored)))
            movable_indices[_id] = len(movables) - 1

    return State(movables, tile_locations, width, height, attachments)


def solve(puzzle: State) -> list[StateTransition]:
    if puzzle.is_win_state():
        return [puzzle]
    seen_states: set = {puzzle}
    state_transition_tree: deque[tuple[int, StateTransition]] = []
    states_to_explore: deque[State] = deque()

    for transition in puzzle.get_all_state_transitions():
        if transition.state not in seen_states:
            if transition.state.is_win_state():
                return [transition]
            state_transition_tree.append((-1, transition))
            states_to_explore.append(transition.state)
            seen_states.add(transition.state)

    state_idx = 0
    while len(states_to_explore) > 0:
        # We're popping #state_idx, i.e. state_idx is the parent idx of any new state transitions
        state = states_to_explore.popleft() # breadth-first search
        for transition in state.get_all_state_transitions():
            if transition.state not in seen_states:
                if transition.state.is_win_state():
                    winning_moves = deque([transition])
                    parent_idx = state_idx
                    while parent_idx != -1:
                        parent_idx, transition = state_transition_tree[parent_idx]
                        winning_moves.appendleft(transition)
                    return list(winning_moves)
                state_transition_tree.append((state_idx, transition))
                states_to_explore.append(transition.state)
                seen_states.add(transition.state)
        state_idx += 1
    raise Exception("No more states to explore")

if __name__ == '__main__':
    # Test by inspecting printed contents
    colorama.init() # Enable color printing
    with open('puzzles/real_levels/09.txt', 'r') as f:
        state = parse_puzzle(f.read())
    print_state(state)
    solution = solve(state)
    for transition in solution:
        print_transition(transition)
