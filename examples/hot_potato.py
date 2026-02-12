#!/usr/bin/env python3
"""
Hot Potato - A party game for 3 Sifteo cubes!

One cube holds the "hot potato" and starts ticking down.
Touch it to another cube (neighbor) to pass the potato before it explodes!
The potato gets faster each round -- who will be left holding it?

How to play:
  - One cube glows RED -- that's the hot potato!
  - The other cubes are BLUE -- they're safe (for now).
  - Physically touch the hot cube to a cool cube to pass the potato.
  - The potato ticks faster each round. When time runs out, it EXPLODES!
  - The cube holding the potato when it explodes gets a point (bad!).
  - Lowest score wins. Press any button to start a new round.
  - Shake a cube to see the current scores.

Usage:
    sudo python3 examples/hot_potato.py
"""

# --- Imports ---

import sys
import os
import random
import time

# Make sure Python can find the sifteo library even if we run from the
# examples/ folder directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sifteo import BaseApp, Cube


# ============================================================================
#  GAME SETTINGS  -- tweak these to change the feel of the game!
# ============================================================================

STARTING_TIME = 8.0      # Seconds before the potato explodes (round 1)
MIN_TIME = 2.0            # Fastest the timer can get
SPEEDUP = 0.6             # Each round, multiply the time by this (gets faster)
FLASH_DURATION = 2.0      # How long the explosion animation plays (seconds)
FLASH_SPEED = 0.15        # How fast the explosion flashes (seconds per flash)

# Colors (R, G, B) -- feel free to change!
COLOR_COOL = (0, 80, 200)       # Safe cubes: calm blue
COLOR_HOT_START = (255, 200, 0) # Potato starts: warm yellow
COLOR_HOT_END = (255, 0, 0)     # Potato near explosion: angry red
COLOR_EXPLODED = (255, 255, 255)  # Flash color 1: white
COLOR_SCORE_BG = (20, 20, 40)   # Score display background: dark blue


# ============================================================================
#  HELPER FUNCTIONS
# ============================================================================

def mix_color(color_a, color_b, t):
    """Blend two RGB colors together.

    t=0.0 gives color_a, t=1.0 gives color_b, t=0.5 is halfway.
    This is called "linear interpolation" (lerp).
    """
    r = int(color_a[0] + (color_b[0] - color_a[0]) * t)
    g = int(color_a[1] + (color_b[1] - color_a[1]) * t)
    b = int(color_a[2] + (color_b[2] - color_a[2]) * t)
    return (r, g, b)


def clamp(value, low, high):
    """Keep a number between low and high."""
    return max(low, min(high, value))


# ============================================================================
#  THE GAME
# ============================================================================

class HotPotato(BaseApp):
    """Main game class. Inherits from BaseApp which handles all the
    cube communication for us. We just override the methods we need.
    """

    def setup(self):
        """Called once when the game starts. Set up all our game state."""

        # --- Game state ---
        self.scores = {}          # cube_id -> number of times caught
        self.hot_cube_id = None   # which cube holds the potato (None = no game)
        self.timer = 0.0          # seconds remaining before explosion
        self.round_time = STARTING_TIME  # how long this round lasts
        self.round_number = 0     # current round

        # --- Animation state ---
        self.exploding = False    # are we playing the explosion animation?
        self.explode_timer = 0.0  # time left in explosion animation
        self.game_active = False  # is a round in progress?

        # Initialize each connected cube
        for cube in self.cubes:
            self.scores[cube.id] = 0

        # Show a welcome message in the terminal
        print("=== HOT POTATO ===")
        print(f"  {len(self.cubes)} cube(s) connected")
        print("  Press any button to start a round!")
        print()

        # Paint all cubes blue to start
        for cube in self.cubes:
            self._paint_cool(cube)

    # ------------------------------------------------------------------
    #  DRAWING HELPERS -- these paint the cubes in different states
    # ------------------------------------------------------------------

    def _paint_cool(self, cube):
        """Paint a cube as 'cool' (safe, not holding the potato)."""
        r, g, b = COLOR_COOL
        cube.fill(r, g, b)

        # Draw a small snowflake-like pattern in the center to look nice.
        # It's just a plus sign (+) made of rectangles.
        cx, cy = 64, 64    # center of the 128x128 screen
        cube.rect(cx - 2, cy - 16, 4, 32, 100, 180, 255)   # vertical bar
        cube.rect(cx - 16, cy - 2, 32, 4, 100, 180, 255)   # horizontal bar

    def _paint_hot(self, cube, urgency):
        """Paint a cube as 'hot' (holding the potato).

        urgency: 0.0 = just got it (yellow), 1.0 = about to explode (red)
        """
        # Blend from yellow to red based on how close to explosion
        r, g, b = mix_color(COLOR_HOT_START, COLOR_HOT_END, urgency)
        cube.fill(r, g, b)

        # Draw a "flame" in the center -- bigger as urgency increases
        flame_size = int(20 + urgency * 30)  # grows from 20 to 50 pixels
        half = flame_size // 2
        cx, cy = 64, 64
        # Outer flame (darker)
        cube.rect(cx - half, cy - half, flame_size, flame_size, 200, 60, 0)
        # Inner flame (brighter)
        inner = max(4, flame_size // 2)
        cube.rect(cx - inner // 2, cy - inner // 2, inner, inner, 255, 255, 100)

    def _paint_exploded(self, cube, flash_on):
        """Paint the explosion animation.

        flash_on: True = white flash, False = red
        """
        if flash_on:
            cube.fill(*COLOR_EXPLODED)
        else:
            cube.fill(255, 0, 0)

    def _paint_score(self, cube):
        """Show this cube's score on screen.

        Uses rectangles to create a simple bar graph.
        """
        cube.fill(*COLOR_SCORE_BG)
        score = self.scores.get(cube.id, 0)

        # Draw one red square for each point (max 10 visible)
        for i in range(min(score, 10)):
            x = 10 + (i % 5) * 22
            y = 40 + (i // 5) * 28
            cube.rect(x, y, 18, 22, 255, 60, 60)

        # If score is 0, draw a green check-like pattern (doing great!)
        if score == 0:
            cube.rect(30, 50, 8, 30, 0, 255, 100)    # left part of check
            cube.rect(38, 72, 40, 8, 0, 255, 100)     # right part of check

    # ------------------------------------------------------------------
    #  GAME LOGIC
    # ------------------------------------------------------------------

    def _start_round(self):
        """Begin a new round: pick a random cube to hold the potato."""
        self.round_number += 1
        self.game_active = True
        self.exploding = False

        # Make the timer shorter each round (but not below MIN_TIME)
        if self.round_number == 1:
            self.round_time = STARTING_TIME
        else:
            self.round_time = max(MIN_TIME, self.round_time * SPEEDUP)

        self.timer = self.round_time

        # Pick a random cube to be "it"
        if self.cubes:
            hot_cube = random.choice(self.cubes)
            self.hot_cube_id = hot_cube.id

        print(f"Round {self.round_number}! "
              f"Cube {self.hot_cube_id} has the potato! "
              f"({self.round_time:.1f}s)")

        # Repaint all cubes
        self._repaint_all()

    def _pass_potato(self, from_cube, to_cube):
        """Pass the potato from one cube to another."""
        # Only pass if from_cube is actually holding the potato
        if from_cube.id != self.hot_cube_id:
            return

        # Don't pass to ourselves!
        if from_cube.id == to_cube.id:
            return

        # Transfer the potato
        self.hot_cube_id = to_cube.id
        print(f"  Passed! Cube {to_cube.id} now has the potato "
              f"({self.timer:.1f}s left)")

        # Repaint both cubes to reflect the change
        self._repaint_all()

    def _explode(self):
        """The potato exploded! The cube holding it loses."""
        self.game_active = False
        self.exploding = True
        self.explode_timer = FLASH_DURATION

        # Add a point to the unlucky cube's score
        loser_id = self.hot_cube_id
        self.scores[loser_id] = self.scores.get(loser_id, 0) + 1

        print(f"  BOOM! Cube {loser_id} exploded! "
              f"(score: {self.scores[loser_id]})")
        print("  Press any button for next round.")

    def _repaint_all(self):
        """Repaint every cube based on current game state."""
        for cube in self.cubes:
            if self.exploding and cube.id == self.hot_cube_id:
                # Don't repaint the exploding cube here; tick() handles it
                pass
            elif cube.id == self.hot_cube_id and self.game_active:
                urgency = 1.0 - (self.timer / self.round_time)
                urgency = clamp(urgency, 0.0, 1.0)
                self._paint_hot(cube, urgency)
            else:
                self._paint_cool(cube)

    # ------------------------------------------------------------------
    #  TICK -- called every frame (~30 times per second)
    # ------------------------------------------------------------------

    def tick(self, dt):
        """Update game logic each frame. dt = time since last frame."""

        if self.game_active:
            # Count down the timer
            self.timer -= dt

            # Update the hot cube's color to show increasing urgency
            hot_cube = self._get_cube_by_id(self.hot_cube_id)
            if hot_cube:
                urgency = 1.0 - (self.timer / self.round_time)
                urgency = clamp(urgency, 0.0, 1.0)
                self._paint_hot(hot_cube, urgency)

            # Check if time ran out
            if self.timer <= 0:
                self._explode()

        elif self.exploding:
            # Play the explosion flash animation
            self.explode_timer -= dt

            # Alternate between white and red every FLASH_SPEED seconds
            flash_on = (int(self.explode_timer / FLASH_SPEED) % 2) == 0
            hot_cube = self._get_cube_by_id(self.hot_cube_id)
            if hot_cube:
                self._paint_exploded(hot_cube, flash_on)

            # When the animation is done, go back to idle
            if self.explode_timer <= 0:
                self.exploding = False
                for cube in self.cubes:
                    self._paint_cool(cube)
                print()

    def _get_cube_by_id(self, cube_id):
        """Find a cube object by its ID. Returns None if not found."""
        for cube in self.cubes:
            if cube.id == cube_id:
                return cube
        return None

    # ------------------------------------------------------------------
    #  EVENT HANDLERS -- respond to what players do with the cubes
    # ------------------------------------------------------------------

    def on_new_cube(self, cube):
        """A new cube just connected! Welcome it to the game."""
        print(f"Cube {cube.id} joined the game!")
        self.scores[cube.id] = 0
        self._paint_cool(cube)

    def on_neighbor_add(self, cube, side, neighbor, neighbor_side):
        """Two cubes were placed next to each other!

        This is how you pass the potato -- touch the hot cube to a cool one.
        side/neighbor_side tell us which edges are touching (0=top, 1=left,
        2=bottom, 3=right), but we don't need that for this game.
        """
        if not self.game_active:
            return

        # Try to pass in both directions (whichever one is holding it)
        self._pass_potato(cube, neighbor)
        self._pass_potato(neighbor, cube)

    def on_button(self, cube, pressed):
        """A button was pressed on a cube.

        We use this to start new rounds.
        """
        if not pressed:
            return  # We only care about the press, not the release

        # Start a new round if we're not currently playing
        if not self.game_active and not self.exploding:
            self._start_round()

    def on_shake(self, cube):
        """A cube was shaken! Show the scores for a moment."""
        if self.game_active:
            return  # Don't interrupt active gameplay

        print("Scores:")
        for cid, score in sorted(self.scores.items()):
            print(f"  Cube {cid}: {score} point(s)")
        print()

        # Show scores on all cubes briefly
        for c in self.cubes:
            self._paint_score(c)

    def on_flip(self, cube, face_down):
        """A cube was flipped upside down.

        Flip all cubes face-down to reset the scores!
        """
        if face_down:
            # Check if ALL cubes are face-down
            all_down = all(c.face_down for c in self.cubes)
            if all_down and not self.game_active:
                # Reset all scores!
                for cid in self.scores:
                    self.scores[cid] = 0
                print("All cubes flipped! Scores reset to 0.")
                self.round_number = 0
                self.round_time = STARTING_TIME
        else:
            # Cube flipped back up -- repaint it
            if not self.game_active and not self.exploding:
                self._paint_cool(cube)


# ============================================================================
#  START THE GAME
# ============================================================================

if __name__ == "__main__":
    print()
    print("  ____________________________")
    print(" |                            |")
    print(" |   HOT POTATO!              |")
    print(" |   A Sifteo party game      |")
    print(" |____________________________|")
    print()
    print("  Connect 3 cubes, then press any button to start.")
    print("  Touch cubes together to pass the potato!")
    print("  Shake a cube to see scores.")
    print("  Flip ALL cubes face-down to reset scores.")
    print()

    HotPotato().run()
