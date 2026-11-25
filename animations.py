"""Independent, elapsed-time animation channels in the character's coordinates."""

from dataclasses import dataclass
import math
import random


def approach(value: float, target: float, speed: float, dt: float) -> float:
    return value + (target - value) * (1.0 - math.exp(-speed * dt))


@dataclass
class Pose:
    breath: float = 0.0
    blink: float = 0.0
    tail: float = 0.0
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    typing: float = 0.0
    left_paw: float = 0.0
    right_paw: float = 0.0
    mouse: float = 0.0
    click: float = 0.0


class Animations:
    def __init__(self) -> None:
        self.pose = Pose()
        self.time = 0.0
        self.next_blink = random.uniform(2.0, 5.5)
        self.blink_start = -10.0
        self.next_tail = random.uniform(5.0, 12.0)
        self.tail_start = -10.0

    def pet(self) -> None:
        self.blink_start = self.time
        self.tail_start = self.time

    def advance(self, dt: float) -> Pose:
        self.time += dt
        t = self.time
        self.pose.breath = math.sin(t * math.tau / 3.8) * 0.65
        if t >= self.next_blink:
            self.blink_start = t
            self.next_blink = t + random.uniform(3.0, 7.0)
        blink_time = t - self.blink_start
        self.pose.blink = (
            math.sin(math.pi * blink_time / 0.29) ** 2
            if 0.0 <= blink_time < 0.29 else 0.0
        )
        if t >= self.next_tail:
            self.tail_start = t
            self.next_tail = t + random.uniform(8.0, 18.0)
        tail_time = t - self.tail_start
        self.pose.tail = (
            math.sin(tail_time * math.tau / 1.5)
            * math.sin(math.pi * tail_time / 3.0) ** 2 * 9.0
            if 0.0 <= tail_time < 3.0 else 0.0
        )
        return self.pose
