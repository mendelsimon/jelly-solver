from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

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
    def __init__(self, coords: list[Coord]) -> None:
        super().__init__(coords, Color.x, False)

class State:
    def __init__(self, movables: list[Movable], tile_locations: list[Coord], width: int = 14, height: int = 10) -> None:
        self.movables: list[Movable] = movables
        self.width: int = width
        self.height: int = height
        self.movable_idx_board: list[Optional[int]]
        self.tile_board: list[bool] = [False] * (width * height)
        for coord in tile_locations:
            self.tile_board[self._coord_to_index(coord)] = True
        self._rebuild_board()

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
        new_state: State = State([movable.clone() for movable in self.movables], [], self.width, self.height)
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
        return state

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
                new_movables_moved = movables_moved.copy()
                new_movables_moved.add(pushed_against_movable_idx)
                state = state._move_movable_in_direction(pushed_against_movable_idx, direction, new_movables_moved)
                if state is None:
                    return None
        state.movables[movable_idx].coords = [coord + direction for coord in state.movables[movable_idx].coords]
        state._rebuild_board()
        return state

    def _gravity(self) -> Optional[State]:
        direction = Direction.down
        movable_moved = True
        while movable_moved:
            movable_moved = False
            for idx, movable in enumerate(self.movables):
                can_fall = True
                for coord in movable.coords:
                    new_coord = coord + direction
                    on_movable = self.lookup_movable(new_coord)
                    if self.lookup_tile(new_coord) or (on_movable is not None and on_movable != idx):
                        # There's a tile there or There's a movable there that is not the current one
                        can_fall = False
                        break
                if can_fall:
                    movable_moved = True
                    movable.coords = [coord + direction for coord in movable.coords]
                    self._rebuild_board()

    def _fuse_movables(self) -> Optional[State]:
        idx = 0
        while idx < len(self.movables):
            movable = self.movables[idx]
            coord_idx = 0
            while coord_idx < len(movable.coords):
                for direction in Direction:
                    neighbor_idx = self.lookup_movable(movable.coords[coord_idx] + direction)
                    if (
                        neighbor_idx is not None 
                        and neighbor_idx != idx 
                        and movable.__class__ is Jelly 
                        and self.movables[neighbor_idx].color == movable.color
                    ):
                        movable.coords.extend(self.movables[neighbor_idx].coords)
                        movable.is_anchored = movable.is_anchored or self.movables[neighbor_idx].is_anchored
                        del self.movables[neighbor_idx]
                        self._rebuild_board()
                coord_idx += 1
            idx += 1        

    # def _fuse_popouts(self) -> Optional[State]:
    #     pass


def print_board(state: State):
    for i in range(state.width * state.height):
        if i % state.width == 0:
            print()

        if state.tile_board[i]:
            print('#', end='')
        elif state.movable_idx_board[i] is not None:
            # print(state.movables[state.movable_idx_board[i]].color.name[0], end='')
            print(state.movable_idx_board[i], end='')
        else:
            print(' ', end='')
    print(state.is_win_state())

def move(state: State, movable_idx: int, direction: Direction):
    new_state = state.move(movable_idx, direction)
    if (new_state):
        state = new_state
    print_board(state)
    return state

def parse_puzzle(raw_text: str) -> State:
    puzzle_string, movable_definition_strings = raw_text.split("\n\n")
    movable_definition_strings = movable_definition_strings.split("\n")
    width = len(puzzle_string.split("\n")[0])
    height = len(puzzle_string.split("\n"))
    flat_puzzle_string = puzzle_string.replace("\n", "")
    tile_locations = [Coord.from_2d(i, width) for i in range(len(flat_puzzle_string)) if flat_puzzle_string[i] == '#']
    movables = []
    for movable_definition in movable_definition_strings:
        if movable_definition == '':
            break
        num, _color, *_is_anchored = movable_definition.split(' ')
        coords = [Coord.from_2d(i, width) for i in range(len(flat_puzzle_string)) if flat_puzzle_string[i] == num]
        color = Color[_color]
        if color == Color.x:
            movables.append(Block(coords))
        else:
            movables.append(Jelly(coords, color, bool(_is_anchored)))

    return State(movables, tile_locations, width, height)

if __name__ == '__main__':
    # Test by inspecting printed contents
    with open('puzzles/steps.txt', 'r') as f:
        state = parse_puzzle(f.read())
    print_board(state)
    state = move(state, 0, Direction.right)
    state = move(state, 0, Direction.left)
    state = move(state, 0, Direction.left)
    state = move(state, 0, Direction.left)
    state = move(state, 0, Direction.left)
    state = move(state, 0, Direction.left)
    state = move(state, 0, Direction.left)
    
