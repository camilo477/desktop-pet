"""Elapsed-time movement, with independent expression and activity channels."""

from dataclasses import dataclass
import math
import random

from activity import Activity

LEFT_REST = (78.0, 153.0)
RIGHT_REST = (108.0, 154.0)
MOUSE_REST = (157.0, 155.0)
MOUSE_HOLD = 0.5


def approach(value: float, target: float, speed: float, dt: float) -> float:
    result = value + (target - value) * (1.0 - math.exp(-speed * dt))
    return target if abs(result - target) < 0.0001 else result


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def mix(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


@dataclass
class Pose:
    breath: float = 0.0
    blink: float = 0.0
    tail: float = 0.0
    tail_phase: float = 0.0
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    head_x: float = 0.0
    head_y: float = 0.0
    ear_left: float = 0.0
    ear_right: float = 0.0
    lean: float = 0.0
    typing: float = 0.0
    left_paw: float = 0.0
    right_paw: float = 0.0
    left_x: float = LEFT_REST[0]
    left_y: float = LEFT_REST[1]
    right_x: float = RIGHT_REST[0]
    right_y: float = RIGHT_REST[1]
    mouse: float = 0.0
    mouse_dx: float = 0.0
    mouse_dy: float = 0.0
    click: float = 0.0


class Animations:
    def __init__(self) -> None:
        self.pose = Pose()
        self.time = 0.0
        self.next_blink = random.uniform(1.8, 4.5)
        self.blink_start = -10.0
        self.next_tail = random.uniform(4.5, 10.0)
        self.tail_start = -10.0
        self.next_ear = random.uniform(8.0, 17.0)
        self.ear_start = -10.0
        self.ear_side = 1
        self.mouse_goal = 0.0
        self.typing_phase = 0.0
        self.frequency = 3.0
        self.left_goal = LEFT_REST
        self.right_goal = RIGHT_REST
        self.left_key = list(LEFT_REST)
        self.right_key = list(RIGHT_REST)

    def pet(self) -> None:
        self.blink_start = self.time
        self.next_blink = self.time + random.uniform(3.0, 6.0)
        self.tail_start = self.time
        self.next_tail = self.time + random.uniform(9.0, 18.0)

    def advance(
        self, dt: float, now: float = 0.0, activity: Activity = Activity(),
        gaze: tuple[float, float] = (0.0, 0.0),
    ) -> Pose:
        self.time += dt
        t, pose = self.time, self.pose
        pose.breath = math.sin(t * math.tau / 4.2) + 0.12 * math.sin(t * math.tau / 6.7)
        if t >= self.next_blink:
            self.blink_start = t
            self.next_blink = t + (0.38 if random.random() < 0.12 else random.uniform(3.0, 6.8))
        age = t - self.blink_start
        if 0 <= age < 0.075:
            pose.blink = smoothstep(age / 0.075)
        elif 0.075 <= age < 0.105:
            pose.blink = 1.0
        elif 0.105 <= age < 0.27:
            pose.blink = 1.0 - smoothstep((age - 0.105) / 0.165)
        else:
            pose.blink = 0.0
        if t >= self.next_tail:
            self.tail_start = t
            self.next_tail = t + random.uniform(9.0, 19.0)
        age = t - self.tail_start
        pose.tail = math.sin(math.pi * age / 2.8) ** 2 if 0 <= age < 2.8 else 0.0
        pose.tail_phase = age * 4.3
        if t >= self.next_ear:
            self.ear_start = t
            self.ear_side = random.choice((-1, 1))
            self.next_ear = t + random.uniform(10.0, 23.0)
        age = t - self.ear_start
        flick = math.sin(math.pi * age / 0.55) ** 2 * 5.0 if 0 <= age < 0.55 else 0.0
        pose.ear_left = flick if self.ear_side < 0 else 0.0
        pose.ear_right = -flick if self.ear_side > 0 else 0.0

        keyboard_active = now - activity.keyboard < 0.38
        mouse_active = now - activity.mouse < MOUSE_HOLD
        pose.typing = approach(pose.typing, float(keyboard_active), 12.0 if keyboard_active else 6.0, dt)
        # Two filters give the transfer a soft start and finish, including on interruption.
        self.mouse_goal = approach(self.mouse_goal, float(mouse_active), 10.0, dt)
        pose.mouse = approach(pose.mouse, self.mouse_goal, 11.0, dt)
        reach = smoothstep(pose.mouse)
        pose.mouse_dx = approach(pose.mouse_dx, activity.motion_x * reach if mouse_active else 0.0, 6.0, dt)
        pose.mouse_dy = approach(pose.mouse_dy, activity.motion_y * reach * 0.65 if mouse_active else 0.0, 6.0, dt)
        click_age = now - activity.click
        pose.click = math.sin(math.pi * click_age / 0.18) if 0 <= click_age < 0.18 else 0.0

        frequency = max(2.0, min(6.5, 0.5 / activity.key_interval))
        self.frequency = approach(self.frequency, frequency, 5.0, dt)
        old_half = int(self.typing_phase / math.pi)
        self.typing_phase = (self.typing_phase + dt * self.frequency * math.tau) % math.tau
        half = int(self.typing_phase / math.pi)
        if half != old_half and keyboard_active:
            base = LEFT_REST if half == 0 else RIGHT_REST
            goal = (base[0] + random.uniform(-3.8, 3.8), base[1] + random.uniform(-1.5, 1.0))
            if half == 0:
                self.left_goal = goal
            else:
                self.right_goal = goal
        pose.left_paw = pose.typing * max(0.0, math.sin(self.typing_phase)) ** 1.4
        pose.right_paw = pose.typing * max(0.0, -math.sin(self.typing_phase)) ** 1.4 * (1.0 - reach)
        for key, goal, rest in ((self.left_key, self.left_goal, LEFT_REST),
                                (self.right_key, self.right_goal, RIGHT_REST)):
            for axis in (0, 1):
                target = mix(rest[axis], goal[axis], pose.typing)
                key[axis] = approach(key[axis], target, 14.0, dt)
        pose.left_x = self.left_key[0]
        pose.left_y = self.left_key[1] - pose.left_paw * 3.2
        pose.right_x = mix(self.right_key[0], MOUSE_REST[0] + pose.mouse_dx, reach)
        pose.right_y = (mix(self.right_key[1] - pose.right_paw * 3.2,
                            MOUSE_REST[1] + pose.mouse_dy + pose.click * 0.55, reach)
                        - math.sin(math.pi * reach) * 7.0)
        pose.gaze_x = approach(pose.gaze_x, max(-1.0, min(1.0, gaze[0])), 13.0, dt)
        pose.gaze_y = approach(pose.gaze_y, max(-1.0, min(1.0, gaze[1])), 13.0, dt)
        pose.head_x = approach(pose.head_x, pose.gaze_x, 4.0, dt)
        pose.head_y = approach(pose.head_y, pose.gaze_y, 3.5, dt)
        pose.lean = approach(pose.lean, reach * 1.5 + pose.head_x * 0.6, 4.0, dt)
        return pose
