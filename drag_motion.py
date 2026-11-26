"""Transient motion of an explicitly lifted pet, in Qt logical pixels."""

import math

MIN_EXCURSION = 24.   # Logical pixels of net travel, not cumulative jitter.
MIN_SPEED = 220.      # Logical pixels per second.
TURN_COSINE = math.cos(math.radians(100))
DIZZY_THRESHOLD = .68


class DragMotion:
    def __init__(self, now=None):
        self.turn_charge = 0.
        self.last_turn = -math.inf
        self.rebase(now)

    def rebase(self, now):
        """A new coordinate space or gap has no measurable velocity across it."""
        self.frame_time = self.leg_start = self.last_move = now
        self.dx = self.dy = self.leg_x = self.leg_y = 0.
        self.filtered_x = self.filtered_y = 0.
        self.heading = None
        self.last_fast = -math.inf

    def charge(self, now):
        return max(0., self.turn_charge - .34 * (now - self.last_turn))

    def observe(self, dx, dy, now):
        if not (dx or dy):
            return
        gap = now - self.last_move if self.last_move is not None else 0.
        if gap < 0 or gap > .25 or math.hypot(dx, dy) > max(150., 4800 * gap):
            self.rebase(now)
            return
        self.last_move = now
        self.dx += dx
        self.dy += dy
        self.leg_x += dx
        self.leg_y += dy
        distance = math.hypot(self.leg_x, self.leg_y)
        if distance < MIN_EXCURSION:
            return

        # Compare directions of substantial excursions. Retain the reference
        # through smaller bends so a circular shake can complete a turn.
        elapsed = now - self.leg_start if self.leg_start is not None else 0.
        speed = distance / max(1 / 240, elapsed)
        direction = (self.leg_x / distance, self.leg_y / distance)
        self.leg_x = self.leg_y = 0.
        self.leg_start = now
        if speed < MIN_SPEED:
            return
        if self.heading is None or now - self.last_fast > .34:
            self.heading = direction
        elif (now - self.last_turn >= .09
              and self.heading[0] * direction[0] + self.heading[1] * direction[1] <= TURN_COSINE):
            gain = .30 + .20 * min(1., (speed - MIN_SPEED) / 600)
            self.turn_charge = min(DIZZY_THRESHOLD + 1., self.charge(now) + gain)
            self.last_turn = now
            self.heading = direction
        self.last_fast = now

    def targets(self, now, dt):
        elapsed = dt if self.frame_time is None else now - self.frame_time
        self.frame_time = now
        if elapsed > .25 or elapsed < 0:
            self.rebase(now)
        interval = max(1 / 240, elapsed)
        vx, vy = self.dx / interval, self.dy / interval
        self.dx = self.dy = 0.
        # A change relative to the recent velocity gives a bounded braking
        # response. At constant velocity only the ordinary lean remains.
        horizontal = -8.7 * math.tanh((vx + .95 * (vx - self.filtered_x)) / 690)
        vertical = -4.6 * math.tanh((vy + .85 * (vy - self.filtered_y)) / 690)
        follow = -math.expm1(-interval * 13)
        self.filtered_x += (vx - self.filtered_x) * follow
        self.filtered_y += (vy - self.filtered_y) * follow
        return horizontal, vertical, max(0., self.charge(now) - DIZZY_THRESHOLD)
