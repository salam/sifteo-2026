#!/usr/bin/env python3
"""
Hello World - Sifteo V1 Example Game.

Each cube displays a solid color. Press the button to change color.
Tilt a cube to shift the color. Neighbor two cubes to sync their colors.

Usage:
    python3 -m examples.hello_world
    # or, if sifteo is installed:
    python3 examples/hello_world.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sifteo import BaseApp, Cube

# A palette of distinct colors (R, G, B)
COLORS = [
    (255, 0, 0),      # Red
    (0, 255, 0),      # Green
    (0, 0, 255),      # Blue
    (255, 255, 0),    # Yellow
    (255, 0, 255),    # Magenta
    (0, 255, 255),    # Cyan
    (255, 128, 0),    # Orange
    (255, 255, 255),  # White
]


class HelloWorld(BaseApp):

    def setup(self):
        self.color_index = {}
        for cube in self.cubes:
            self._init_cube(cube)

    def _init_cube(self, cube):
        self.color_index[cube.id] = 0
        self._paint_cube(cube)

    def _paint_cube(self, cube):
        idx = self.color_index.get(cube.id, 0)
        r, g, b = COLORS[idx % len(COLORS)]
        cube.fill(r, g, b)

    def on_new_cube(self, cube):
        print(f"Welcome cube {cube.id}!")
        self._init_cube(cube)

    def on_button(self, cube, pressed):
        if pressed:
            # Cycle to next color
            idx = self.color_index.get(cube.id, 0)
            self.color_index[cube.id] = (idx + 1) % len(COLORS)
            self._paint_cube(cube)
            print(f"Cube {cube.id}: color -> {COLORS[self.color_index[cube.id]]}")

    def on_tilt(self, cube, x, y, z):
        # Shift color index based on tilt direction
        idx = self.color_index.get(cube.id, 0)
        if x == 0:
            self.color_index[cube.id] = (idx - 1) % len(COLORS)
            self._paint_cube(cube)
        elif x == 2:
            self.color_index[cube.id] = (idx + 1) % len(COLORS)
            self._paint_cube(cube)

    def on_shake(self, cube):
        # Random color on shake
        import random
        self.color_index[cube.id] = random.randint(0, len(COLORS) - 1)
        self._paint_cube(cube)
        print(f"Cube {cube.id}: shaken! -> {COLORS[self.color_index[cube.id]]}")

    def on_neighbor_add(self, cube, side, neighbor, neighbor_side):
        # Sync colors when cubes touch
        self.color_index[neighbor.id] = self.color_index.get(cube.id, 0)
        self._paint_cube(neighbor)
        print(f"Cube {cube.id} <-> Cube {neighbor.id}: colors synced!")

    def on_flip(self, cube, face_down):
        if face_down:
            cube.fill(0, 0, 0)  # Black when face down
            print(f"Cube {cube.id}: face down")
        else:
            self._paint_cube(cube)
            print(f"Cube {cube.id}: face up")


if __name__ == "__main__":
    print("Sifteo V1 - Hello World")
    print("Press button to change color, tilt to shift, shake for random")
    print()
    HelloWorld().run()
