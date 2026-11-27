"""Two paw goals and independent channels for a coordinated feline body."""

from dataclasses import dataclass
import math
import random

from activity import Activity, KeyHint
from drag_motion import DragMotion
from keyboard_layout import Keyboard, KEY_TRAVEL, REST
from anatomy import BodyGeometry, FaceGeometry
from idle_motion import DURATIONS, QUIET, STILL, IdleMotion, sample, smoothstep
from personality import CALM, CONTENT, CURIOUS, SURPRISED, Expression, Personality

MOUSE_PAW = 0  # Screen left is the cat's anatomical right.
MOUSE_HOLD = .5
CURSOR_TRAVEL_TO_EDGE = 400.0  # Screen pixels from the center to one edge of either device.
IDLE_ACTION_AFTER = 15.0
RELAX_AFTER = 60.0
SLEEP_AFTER = 180.0
IDLE_ACTION_GAP = (12.0, 27.0)
UNSTEADY = Expression(opening=.70, pupil=4.1, ears=19, whiskers=1.8)


def approach(value, target, speed, dt):
    result = value + (target - value) * (1 - math.exp(-speed * dt))
    return target if abs(result - target) < .0001 else result


def mix(start, end, amount):
    return start + (end - start) * amount


def spring(value, velocity, target, speed, dt):
    decay = math.exp(-speed * dt)
    change = value - target
    temporary = (velocity + speed * change) * dt
    return target + (change + temporary) * decay, (velocity - speed * temporary) * decay


@dataclass
class Pose:
    time: float = 0.0
    breath: float = 0.0
    blink: float = 0.0
    tail: float = 0.0
    tail_phase: float = 0.0
    tail_tip: float = 0.0
    tail_touch: float = 0.0
    expression: Expression = CALM
    gaze_x: float = 0.0
    gaze_y: float = 0.0
    head_x: float = 0.0
    head_y: float = 0.0
    head_tilt: float = 0.0
    focus: float = 0.0
    pet: float = 0.0
    pet_side: float = 0.0
    ear_left: float = 0.0
    ear_right: float = 0.0
    balance_x: float = 0.0
    balance_y: float = 0.0
    balance_velocity: float = 0.0
    lift: float = 0.0
    sway_x: float = 0.0
    sway_y: float = 0.0
    tail_sway: float = 0.0
    dizzy: float = 0.0
    left_x: float = REST[0][0]
    left_y: float = REST[0][1]
    right_x: float = REST[1][0]
    right_y: float = REST[1][1]
    left_key: str | None = None
    right_key: str | None = None
    pressed: frozenset[str] = frozenset()
    mouse: float = 0.0
    touchpad: bool = False
    mouse_dx: float = 0.0
    mouse_dy: float = 0.0
    click: float = 0.0
    scroll: float = 0.0
    scroll_direction: float = 0.0
    sleep: float = 0.0
    relax: float = 0.0
    zzz: float = 0.0
    groom: float = 0.0
    tongue: float = 0.0
    yawn: float = 0.0
    action: str | None = None
    motion: IdleMotion = STILL
    action_side: int = -1
    contact: float = 0.0
    contact_side: float = 0.0
    contacts: tuple[tuple[str, float], ...] = ()
    left_pressure: float = 0.0
    right_pressure: float = 0.0


@dataclass
class Paw:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    key: str | None = None
    stamp: float = -math.inf
    motion_stamp: float = -math.inf
    until: float = -math.inf
    goal: str = 'rest'
    target: tuple[float, float] | None = None
    age: float = 1.0
    duration: float = .18
    arc: float = 0.0
    response: float = 25.0
    landed: bool = False
    pressure: float = 0.0
    distance: float = 0.0
    ready: tuple[float, float] | None = None
    ready_until: float = -math.inf

    def aim(self, goal, point, stamp=0.0, interval=.33, keystroke=False):
        if self.goal != goal or self.motion_stamp != stamp:
            distance = math.hypot(point[0] - self.x, point[1] - self.y)
            if keystroke:
                travel = max(.042, min(.12, interval * .12 + distance / 1450))
                self.response = 4.3 / travel
                tempo = max(0, min(1, (.33 - interval) / .26))
                self.duration = mix(.093, .055, tempo)
                self.arc = mix(3.4, 1.8, tempo) * min(1.0, .75 + distance / 60)
            else:
                self.response = 25 if goal == 'mouse' else 21
                self.duration = .22
                self.arc = min(3, distance * .06) if goal in ('groom', 'mouse') else 0
            self.age = 0.0
            self.goal, self.motion_stamp = goal, stamp
            self.landed = False
            self.distance = distance
        self.target = point

    def advance(self, dt):
        if self.target is None:
            return
        self.age += dt
        lift = math.sin(math.pi * min(1, self.age / self.duration)) * self.arc
        self.x, self.vx = spring(self.x, self.vx, self.target[0], self.response, dt)
        self.y, self.vy = spring(self.y, self.vy, self.target[1] - lift, self.response, dt)
        self.pressure = approach(self.pressure, 0, 22, dt)


class Animations:
    def __init__(self, keyboard=None):
        self.keyboard = keyboard or Keyboard()
        self.pose = Pose(left_x=self.keyboard.rest[0][0], left_y=self.keyboard.rest[0][1],
                         right_x=self.keyboard.rest[1][0], right_y=self.keyboard.rest[1][1],
                         touchpad=self.keyboard.pointer == 'touchpad')
        self.personality = Personality()
        self.tip_phase = 0.0
        self.breath_phase = 0.0
        self.time = 0.0
        self.paws = [Paw(*point) for point in self.keyboard.rest]
        self.last_activity = None
        self.touch_pending = False
        self.last_hint = -math.inf
        self.next_blink = random.uniform(2, 5)
        self.blink_start = -10.0
        self.next_tail = random.uniform(5, 12)
        self.tail_start = -10.0
        self.next_ear = random.uniform(9, 19)
        self.ear_start = -10.0
        self.ear_side = 1
        self.mouse_goal = 0.0
        self.mouse_target = [0.0, 0.0]
        self.mouse_velocity = [0.0, 0.0]
        self.mouse_contact = False
        self.focus_point = [105.0, 160.0]
        self.head_velocity = [0.0, 0.0, 0.0]
        self.pet_start = -10.0
        self.pet_held = False
        self.pet_release = None
        self.pet_release_level = 0.0
        self.pet_fade = .60
        self.ear_touches = [-math.inf, -math.inf]
        self.tail_touch_start = -math.inf
        self.near_face = False
        self.drag = None
        self.release_dizzy = 0.
        self.lift_start = self.release_stamp = -math.inf
        self.lift_velocity = self.sway_vx = self.sway_vy = 0.0
        self.sleep_goal = 0.0
        self.next_idle = IDLE_ACTION_AFTER + random.uniform(1, 8)
        self.action_kind = None
        self.action_start = 0.0
        self.action_duration = 4.0
        self.action_weight = 0.0
        self.look_side = 1
        self.look_height = 0.0
        self.action_strength = 1.0
        self.last_idle = None
        self.last_wake = -math.inf

    @property
    def sleeping(self):
        return self.pose.sleep > .99 and self.sleep_goal > .99

    @property
    def carried(self):
        return self.drag is not None

    def interact(self):
        self.touch_pending = True
        if self.release_dizzy:
            self.release_dizzy = self.pose.dizzy = 0.

    def pet(self, side=0.0, held=False):
        self.interact()
        self.pet_start = self.time
        self.pet_held = held
        self.pet_release = None
        self.pose.pet_side = max(-1, min(1, side))
        self.blink_start = self.time
        self.next_blink = self.time + random.uniform(3, 6)
        self.tail_start = self.time
        self.next_tail = self.time + random.uniform(10, 20)

    def release_pet(self, quick=False):
        self.pet_held = False
        self.pet_release = self.time + (0 if quick else .10)
        self.pet_release_level = self.pose.pet
        self.pet_fade = .16 if quick else .60

    def touch(self, region):
        self.interact()
        if region in ('ear-left', 'ear-right'):
            index = int(region == 'ear-right')
            if self.time - self.ear_touches[index] >= .43:
                self.ear_touches[index] = self.time
        elif region == 'tail' and self.time - self.tail_touch_start >= .58:
            self.tail_touch_start = self.time

    def lift(self, now=None):
        self.interact()
        self.drag = DragMotion(now)
        self.lift_start = self.time
        if self.pet_held or self.pose.pet or self.time - self.pet_start < .78:
            self.release_pet(quick=True)
        self.mouse_target[:] = (self.pose.mouse_dx, self.pose.mouse_dy)
        self.mouse_velocity[:] = (0.0, 0.0)
        self.mouse_contact = False
        for paw in self.paws:
            paw.key = paw.ready = None

    def put_down(self, now):
        self.drag = None
        self.release_stamp = self.last_hint = now
        # A small compression proportional to how far the haunches actually rose.
        self.lift_velocity = -26 * max(0, self.pose.lift)
        self.interact()
        self.release_dizzy = self.pose.dizzy

    def _suspension(self, dt, now, delta):
        pose = self.pose
        if not (self.carried or pose.lift or pose.sway_x or pose.sway_y or pose.tail_sway):
            return
        horizontal = vertical = 0.0
        if self.carried:
            if delta is not None:
                self.drag.observe(*delta, now)
            horizontal, vertical, intensity = self.drag.targets(now, dt)
            pose.dizzy = approach(pose.dizzy, intensity, 5, dt)
        pose.lift, self.lift_velocity = spring(pose.lift, self.lift_velocity,
                                               6.5 if self.carried else 0, 13, dt)
        pose.sway_x, self.sway_vx = spring(pose.sway_x, self.sway_vx, horizontal, 16, dt)
        pose.sway_y, self.sway_vy = spring(pose.sway_y, self.sway_vy, vertical, 16, dt)
        pose.tail_sway = approach(pose.tail_sway, pose.sway_x, 10, dt)
        if not self.carried and max(abs(pose.lift), abs(pose.sway_x), abs(pose.sway_y), abs(pose.tail_sway)) < .005:
            pose.lift = pose.sway_x = pose.sway_y = pose.tail_sway = 0.0
            self.lift_velocity = self.sway_vx = self.sway_vy = 0.0

    def set_keyboard(self, keyboard, held):
        old = self.keyboard
        self.keyboard = keyboard
        pose = self.pose
        pose.pressed = held
        pose.touchpad = keyboard.pointer == 'touchpad'
        if old.pointer != keyboard.pointer:
            pose.mouse_dx = pose.mouse_dy = 0
        pose.contacts = ()
        pose.contact = pose.left_pressure = pose.right_pressure = 0
        self.mouse_contact = False
        self.mouse_target[:] = (pose.mouse_dx, pose.mouse_dy)
        self.mouse_velocity[:] = (0, 0)
        for index, paw in enumerate(self.paws):
            if paw.goal == 'rest' and math.dist((paw.x, paw.y), old.rest[index]) < .1:
                paw.x, paw.y = keyboard.rest[index]
            if paw.key not in held:
                paw.key = None
                paw.until = -math.inf
            if paw.goal in old.by_id or paw.goal == 'ready':
                paw.goal = 'redirect'
                paw.target = None
            paw.ready = None
            paw.pressure = 0
        pose.left_key, pose.right_key = (paw.key for paw in self.paws)
        pose.left_x, pose.left_y = self.paws[0].x, self.paws[0].y
        pose.right_x, pose.right_y = self.paws[1].x, self.paws[1].y

    def clear_input(self):
        # Clear the input estimates immediately, keeping the painted pose for the transition.
        self.personality = Personality(self.personality.shape)
        self.pose.pressed = frozenset()
        self.pose.left_key = self.pose.right_key = None
        self.pose.scroll = self.pose.contact = 0.0
        self.pose.contacts = ()
        self.pose.left_pressure = self.pose.right_pressure = 0.0
        self.last_hint = -math.inf
        self.mouse_contact = False
        self.mouse_target[:] = (self.pose.mouse_dx, self.pose.mouse_dy)
        self.mouse_velocity[:] = (0.0, 0.0)
        for paw in self.paws:
            paw.key = None; paw.stamp = -math.inf; paw.until = -math.inf
            paw.goal = 'cleared'; paw.motion_stamp = -math.inf
            paw.landed = False; paw.pressure = 0.0; paw.ready = None
        self.interact()

    def start_idle(self, kind):
        if kind not in DURATIONS:
            return
        self.action_kind = self.last_idle = kind
        self.action_start = self.time
        self.action_duration = random.uniform(*DURATIONS[kind])
        self.look_side = random.choice((-1, 1))
        self.look_height = random.uniform(-.75, .15)
        self.action_strength = random.uniform(.84, 1)
        self.next_idle = self.time + self.action_duration + random.uniform(*IDLE_ACTION_GAP)

    def _assign(self, now, activity, mouse):
        available = [1 - MOUSE_PAW] if mouse else [0, 1]
        for index, paw in enumerate(self.paws):
            if index not in available or (paw.key not in activity.held and now > paw.until):
                paw.key = None
        hints = {hint.identifier: hint for hint in (*activity.hints, activity.latest)
                 if hint.identifier in self.keyboard.by_id and hint.stamp > self.last_hint}
        for hint in sorted(hints.values(), key=lambda value: value.stamp):
            key = self.keyboard.by_id[hint.identifier]
            existing = next((i for i in available if self.paws[i].key == key.identifier), None)
            if existing is None:
                preferred = key.preferred_paw
                def score(index):
                    paw = self.paws[index]
                    held = paw.key in activity.held
                    modifier = held and self.keyboard.by_id[paw.key].modifier
                    return (50 if modifier else 28 if held else 0) + (0 if index == preferred else 5) + math.hypot(paw.x - key.contact[0], paw.y - key.contact[1]) * .1
                existing = min(available, key=score)
                if len(available) == 1 and key.modifier and self.paws[existing].key in activity.held:
                    self.last_hint = max(self.last_hint, hint.stamp)
                    continue
            paw = self.paws[existing]
            paw.key = key.identifier
            paw.stamp = hint.stamp
            contact = max(.075, min(.18, activity.key_interval * .55))
            paw.until = max(hint.stamp + contact, now + .04)
            self.last_hint = max(self.last_hint, hint.stamp)
        if activity.held:
            candidates = (activity.held & self.keyboard.ids) - {self.paws[i].key for i in available}
            free = [i for i in available if self.paws[i].key is None]
            # A still-held key may reappear after changing boards, without a new press.
            while free and candidates:
                def rank(pair):
                    i, identifier = pair
                    key = self.keyboard.by_id[identifier]
                    dist = math.dist((self.paws[i].x, self.paws[i].y), key.contact)
                    return (key.modifier, i != key.preferred_paw, dist, identifier)
                i, identifier = min(((i, key) for i in free for key in candidates), key=rank)
                self.paws[i].key, self.paws[i].stamp = identifier, 0.0
                free.remove(i)
                candidates = candidates - {identifier}

    def _expressions(self, dt, idle, active):
        t, pose = self.time, self.pose
        age = t - self.pet_start
        if self.pet_release is not None:
            elapsed = t - self.pet_release
            pose.pet = self.pet_release_level * (1 - smoothstep(elapsed / self.pet_fade))
            if elapsed >= self.pet_fade:
                self.pet_release = None
                self.pet_start = -10.0
        elif self.pet_held:
            pose.pet = smoothstep(age / .22) * (.94 + .055 * math.sin(age * 1.8))
        else:
            pose.pet = (smoothstep(age / .14) if 0 <= age < .14 else
                        1.0 if .14 <= age < .30 else
                        1 - smoothstep((age - .30) / .48) if .30 <= age < .78 else 0.0)
        if t >= self.next_blink:
            self.blink_start = t
            self.next_blink = t + (.38 if random.random() < .1 else random.uniform(3, 7))
        age = t - self.blink_start
        pose.blink = (smoothstep(age / .075) if 0 <= age < .075 else
                      1.0 if .075 <= age < .105 else
                      1 - smoothstep((age - .105) / .165) if .105 <= age < .27 else 0.0)
        pose.blink = max(pose.blink, pose.pet * .98)
        if t >= self.next_tail:
            self.tail_start = t; self.next_tail = t + random.uniform(9, 20)
        age = t - self.tail_start
        pose.tail = math.sin(math.pi * age / 2.8) ** 2 if 0 <= age < 2.8 else 0.0
        pose.tail_phase = age * 4.0
        if t >= self.next_ear:
            self.ear_start = t; self.ear_side = random.choice((-1, 1))
            self.next_ear = t + random.uniform(11, 24)
        age = t - self.ear_start
        flick = 0
        if 0 <= age < .65:
            progress = age / .65
            flick = (math.sin(math.pi * progress) ** 2 * math.sin(math.tau * progress) *
                     12 * (1 - .85 * pose.relax) * (1 - pose.sleep))
        pose.ear_left = flick if self.ear_side < 0 else 0
        pose.ear_right = -flick if self.ear_side > 0 else 0
        allowed = idle >= IDLE_ACTION_AFTER and idle < SLEEP_AFTER and not active
        if allowed and self.action_kind is None and t >= self.next_idle:
            choices = QUIET
            if idle < RELAX_AFTER:
                choices += tuple(DURATIONS)
                if t - self.last_wake < 30:
                    choices += ('stretch',)
            elif idle < RELAX_AFTER + 55:
                choices += ('stretch', 'knead', 'lick')
            self.start_idle(random.choice([kind for kind in choices if kind != self.last_idle]))
        phase = (t - self.action_start) / self.action_duration
        playing = self.action_kind is not None and phase < 1 and allowed
        self.action_weight = approach(self.action_weight, float(playing), 7 if playing else 14, dt)
        if not playing and self.action_weight < .001:
            self.action_kind = None
        pose.action = self.action_kind
        pose.action_side = self.look_side
        pose.motion = sample(self.action_kind, phase, self.action_weight, self.look_side, self.action_strength)
        envelope = math.sin(math.pi * max(0, min(1, phase))) ** 2 * self.action_weight
        pose.groom = envelope if self.action_kind in ('lick', 'wash') else 0
        pose.tongue = pose.groom * max(0, math.sin(phase * math.tau * 4)) if self.action_kind == 'lick' else 0
        pose.yawn = envelope if self.action_kind == 'yawn' else 0
        return phase, envelope, playing

    def _mouse_motion(self, dt, activity, active):
        pose = self.pose
        if not active:
            self.mouse_contact = False
        positions = [pose.mouse_dx, pose.mouse_dy]
        moving = active and (activity.motion_x != 0 or activity.motion_y != 0)
        # Turn screen motion into the cat's peripheral plane on both axes.
        for axis, (motion, limit) in enumerate(zip(
                (activity.motion_x, activity.motion_y), self.keyboard.pointer_limits)):
            position = positions[axis]
            target, velocity = self.mouse_target[axis], self.mouse_velocity[axis]
            delta = -motion * limit / CURSOR_TRAVEL_TO_EDGE if active else 0
            if delta:
                # A reversal starts from the painted object, not an unfinished reach.
                if delta * (target - position) < 0:
                    target = position
                if delta * velocity < 0:
                    velocity = 0
                target = max(-limit, min(limit, target + delta))
            elif moving:
                target, velocity = position, 0
            self.mouse_target[axis] = target
            # Wait for contact, then slide the mouse or glide over the fixed pad.
            if self.mouse_contact or not active:
                following, velocity = spring(position, velocity, target, 21, dt)
                bounded = max(min(position, target), min(max(position, target), following))
                bounded = max(-limit, min(limit, bounded))
                if bounded != following:
                    velocity = 0
                positions[axis] = bounded
            self.mouse_velocity[axis] = velocity
        pose.mouse_dx, pose.mouse_dy = positions

    def advance(self, dt, now=0.0, activity=Activity(), gaze=(0.0, 0.0), face_offset=None,
                drag_delta=None, desktop_idle=None):
        pose = self.pose
        if self.carried:
            self.interact()
        self._suspension(dt, now, drag_delta)
        observed = max(activity.keyboard, activity.mouse, activity.click, activity.scroll)
        if self.release_dizzy:
            if activity.any_held or activity.held or observed > self.release_stamp:
                self.release_dizzy = pose.dizzy = 0.
            else:
                duration = .8 + 3.5 * self.release_dizzy
                pose.dizzy = self.release_dizzy * smoothstep(1 - (now - self.release_stamp) / duration)
                if not pose.dizzy:
                    self.release_dizzy = 0.
        if self.last_activity is None:
            self.last_activity = now
        prior_idle = now - self.last_activity
        active = activity.any_held or bool(activity.held) or observed > self.last_activity or self.touch_pending
        if self.sleeping and active:
            self.last_wake = self.time
            dt = min(dt, 1 / 30)  # Restore fluid wake frames after the low-rate sleeping tick.
            self.blink_start = -10.0
            self.next_blink = self.time + random.uniform(1.2, 2.5)
        self.time += dt; pose.time = self.time
        if self.touch_pending or activity.any_held or activity.held:
            self.last_activity = now
        else:
            self.last_activity = max(self.last_activity, observed)
        self.touch_pending = False
        if desktop_idle is not None:
            # Before the idle edge we only know the seat was active within 15s.
            # Keep that bound for fallback without synthesizing input or cadence.
            self.last_activity = max(self.last_activity, now - max(IDLE_ACTION_AFTER, desktop_idle))
        idle = max(0, now - self.last_activity)
        if desktop_idle is not None:
            idle = min(idle, desktop_idle)
        phase, action, playing = self._expressions(dt, idle, active)
        relaxing = max(0, min(1, (idle - RELAX_AFTER) / (SLEEP_AFTER - RELAX_AFTER)))
        pose.relax = approach(pose.relax, relaxing, .8 if relaxing > pose.relax else 6, dt)
        distance = math.hypot(face_offset[0] / 49, face_offset[1] / 42) if face_offset else math.inf
        self.near_face = distance < (1.22 if self.near_face else 1)
        curious = (self.near_face and not activity.any_held and not activity.held
                   and now - max(activity.keyboard, activity.scroll) > .65 and not pose.pet)
        expression = self.personality.update(dt, now, activity, prior_idle,
                                             curious or (playing and self.action_kind == 'look'),
                                             pose.pet, pose.relax)
        motion = pose.motion
        expression = expression.blend(CONTENT, motion.content * (1 - pose.pet))
        ear_lean = 0.0
        for i, start in enumerate(self.ear_touches):
            ear_phase = (self.time - start) / .43
            if 0 < ear_phase < 1:
                side = 2 * i - 1
                flex = math.sin(math.pi * ear_phase) ** 2 * math.sin(math.tau * ear_phase + .6)
                if i == 0:
                    pose.ear_left -= 16 * flex
                else:
                    pose.ear_right += 16 * flex
                ear_lean += side * math.sin(math.pi * ear_phase) ** 2
        tail_phase = (self.time - self.tail_touch_start) / .58
        pose.tail_touch = tail_phase if 0 < tail_phase < 1 else 0
        if pose.tail_touch:
            expression = expression.blend(SURPRISED, .35 * math.sin(math.pi * tail_phase) ** 2)
        expression = expression.blend(CURIOUS, abs(ear_lean) * .6)
        if self.carried or pose.lift > .01:
            age = self.time - self.lift_start
            surprise = smoothstep(age / .10) * (1 - smoothstep((age - .14) / .38))
            if not self.carried:
                surprise *= min(1, pose.lift / 6.5)
            expression = expression.blend(SURPRISED, .65 * surprise)
        roll = nod = 0.
        if pose.dizzy:
            phase = (self.time - self.lift_start) * 6.6
            roll = pose.dizzy * math.sin(phase)
            nod = pose.dizzy * math.cos(phase)
            expression = expression.blend(UNSTEADY, pose.dizzy)
        pose.expression = expression
        sleep_target = float(idle >= SLEEP_AFTER)
        self.sleep_goal = approach(self.sleep_goal, sleep_target, 1.6 if sleep_target else 10, dt)
        pose.sleep = approach(pose.sleep, self.sleep_goal, 2.4 if sleep_target else 12, dt)
        # The eyelids can open while the head is still tilted.
        pose.blink = max(pose.blink, motion.lids, .64 * pose.relax, smoothstep((self.sleep_goal - .35) / .65))
        pose.zzz = approach(pose.zzz, smoothstep((pose.sleep - .78) / .22) if sleep_target else 0, 8, dt)
        drift = math.sin(self.time * .24) * (1 - pose.sleep)
        period = mix(4.2 + .27 * drift, 6.2, pose.sleep)
        self.breath_phase = (self.breath_phase + dt * math.tau / period) % math.tau
        pose.breath = math.sin(self.breath_phase) * mix(1 + .065 * drift, .4, pose.sleep)
        if self.sleeping and sleep_target and not active:
            pose.blink = 1.0; pose.tail = 0.0
            pose.tail_tip = 0.0
            pose.ear_left = pose.ear_right = 0.0
            pose.gaze_x = pose.gaze_y = pose.head_x = pose.head_y = pose.head_tilt = 0.0
            self.head_velocity[:] = (0.0, 0.0, 0.0)
            pose.pressed = frozenset()
            return pose
        self.tip_phase = (self.tip_phase + expression.tip_speed * dt) % (3 * math.tau)
        # A flexible tip moves in bouts; the root stays planted.
        bout = (.5 - .5 * math.cos(self.tip_phase / 3))
        pose.tail_tip = expression.tail * math.sin(self.tip_phase) * bout * (1 - pose.sleep)
        pose.tail_tip -= 3.6 * roll
        mouse_active = not self.carried and now - max(activity.mouse, activity.scroll) < MOUSE_HOLD
        self.mouse_goal = approach(self.mouse_goal, float(mouse_active), 10, dt)
        pose.mouse = approach(pose.mouse, self.mouse_goal, 12, dt)
        self._mouse_motion(dt, activity, mouse_active)
        age = now - activity.click
        pose.click = math.sin(math.pi * age / .18) if not self.carried and 0 <= age < .18 else 0
        if activity.scroll_x or activity.scroll_y:
            pose.scroll_direction = math.copysign(1, activity.scroll_y or activity.scroll_x)
            pose.scroll = min(1, pose.scroll + abs(activity.scroll_y or activity.scroll_x) * .4)
        else:
            pose.scroll = approach(pose.scroll, 0, 9, dt)
        pose.contact = approach(pose.contact, 0, 17, dt)
        pose.contacts = tuple((key, pressure * math.exp(-dt * 24)) for key, pressure in pose.contacts
                              if pressure * math.exp(-dt * 24) > .025)
        pose.pressed = activity.pressed & self.keyboard.ids
        if not self.carried:
            self._assign(now, activity, mouse_active)
        goals = [self.keyboard.by_id[paw.key].contact for paw in self.paws if paw.key in self.keyboard.by_id]
        key_point = goals[-1] if goals else None
        if (not self.carried and activity.latest.identifier in self.keyboard.by_id
                and activity.latest.stamp > self.release_stamp):
            key_point = self.keyboard.by_id[activity.latest.identifier].contact
        if key_point:
            points = [self.keyboard.by_id[hint.identifier].contact for hint in activity.hints
                      if hint.identifier in self.keyboard.by_id and hint.stamp > self.release_stamp and now - hint.stamp < .16]
            self.focus_point[:] = tuple(sum(point[axis] for point in points) / len(points) for axis in (0, 1)) if points else key_point
        pose.focus = approach(pose.focus, (0.2 if mouse_active else 1) if key_point else 0, 12, dt)
        moving = now - activity.mouse < .60
        scrolling = now - activity.scroll < MOUSE_HOLD
        if self.carried:
            look = (pose.sway_x * .045, .16 + pose.sway_y * .04)
        elif curious:
            look = (face_offset[0] / 48, face_offset[1] / 43)
        elif self.near_face and key_point and activity.keyboard >= max(activity.mouse, activity.scroll):
            look = ((self.focus_point[0] - 116) / 72, .95)
        elif moving and (not scrolling or now - activity.mouse < .18):
            look = gaze
            if key_point and activity.held:
                look = (gaze[0] * .9 + (self.focus_point[0] - 118) / 70 * .1, gaze[1] * .9 + .07)
        elif scrolling:
            look_x = ((self.keyboard.mouse_rest[0] + pose.mouse_dx - 116) / 100 if pose.touchpad
                      else -.72 + (self.keyboard.mouse_offset + pose.mouse_dx) / 120)
            look = (look_x, .78)
        elif key_point:
            look = ((self.focus_point[0] - 116) / 72, .95)
        elif playing and self.action_kind == 'look':
            look = (self.look_side * .68 * action, self.look_height * action)
        elif playing and self.action_kind == 'ear_rub':
            look = (self.look_side * .30 * action, -.14 * action)
        elif pose.groom > .02:
            look = (-.13, .38)
        elif pose.yawn > .02:
            look = (0, -pose.yawn * .2)
        else:
            look = (0, .10)
        if pose.dizzy:
            look = (look[0] - .72 * nod, look[1] + .40 * roll)
        look = (mix(look[0], pose.pet_side * .32, pose.pet), mix(look[1], .3, pose.pet))
        if sleep_target:
            look = (look[0] * (1 - pose.sleep), look[1] * (1 - pose.sleep))
        look = tuple(max(-1, min(1, value)) for value in look)
        # All three channels receive attention directly, rather than filtering each other.
        # The eyes briefly counter-roll as the head tries to level itself.
        eye_x = max(-1., min(1., look[0] - .46 * roll)) if pose.dizzy else look[0]
        pose.gaze_x = approach(pose.gaze_x, eye_x, 24, dt)
        pose.gaze_y = approach(pose.gaze_y, look[1], 24, dt)
        head_speed = 13 if key_point else 11
        if not key_point and not mouse_active:
            head_speed *= 1 - .35 * pose.relax
        pose.head_x, self.head_velocity[0] = spring(pose.head_x, self.head_velocity[0], look[0], head_speed, dt)
        pose.head_y, self.head_velocity[1] = spring(pose.head_y, self.head_velocity[1], look[1], head_speed, dt)
        toward = max(-1, min(1, look[0] * 1.8))
        tilt = look[0] * 3.5 + toward * expression.tilt + pose.pet_side * pose.pet * 8
        tilt += ear_lean * 3 + pose.sway_x * .82 + 12 * roll
        if playing and self.action_kind == 'look':
            tilt += self.look_side * action * 2
        pose.head_tilt, self.head_velocity[2] = spring(pose.head_tilt, self.head_velocity[2], tilt, 14, dt)
        if key_point:
            target_x = max(-18, min(21, (self.focus_point[0] - 116) * .29))
            target_y = max(7, min(20, 8 + (self.focus_point[1] - 151) * .36))
        else:
            target_x, target_y = look[0] * 1.2, 0
        if mouse_active:
            # Follow the planted paw with the chest; the opposite paw can still type.
            mouse_lean = -15 + (self.keyboard.mouse_offset + pose.mouse_dx) * .55
            if pose.touchpad:
                mouse_lean = (self.keyboard.mouse_rest[0] + pose.mouse_dx - 104) * .29
            target_x = mix(mouse_lean, target_x, .18) if key_point else mouse_lean
            target_y = max(target_y, (7 if pose.touchpad else 10) + pose.mouse_dy * .32)
        target_x += motion.lean - 4.2 * roll
        target_y += motion.drop + 1.5 * nod
        if pose.groom > 0:
            target_x -= pose.groom * 1.6
            target_y += pose.groom * 1.8
        target_y += pose.relax * 1.2 - pose.yawn * .6 + expression.lean
        old_balance = pose.balance_x
        rest_weight = 1 - pose.sleep if sleep_target else 1
        pose.balance_x = approach(pose.balance_x, target_x * rest_weight, 10, dt)
        pose.balance_y = approach(pose.balance_y, target_y * rest_weight, 10, dt)
        pose.balance_velocity = (pose.balance_x - old_balance) / max(.001, dt)
        swivel = toward * expression.tilt * .6
        spread = expression.ears + motion.ears
        pose.ear_left += (swivel - spread) * (1 - pose.sleep) + pose.balance_velocity * .013
        pose.ear_right += (swivel + spread) * (1 - pose.sleep) + pose.balance_velocity * .009
        pose.ear_left += motion.swivel * (.2 if motion.rub and pose.action_side > 0 else 1) + pose.sway_x * .8
        pose.ear_right += motion.swivel * (.2 if motion.rub and pose.action_side < 0 else 1) + pose.sway_x * .7
        ear_flex = (pose.sway_x - pose.tail_sway) * 1.3 + 3 * nod
        pose.ear_left += ear_flex
        pose.ear_right += ear_flex
        body = BodyGeometry(pose)
        pointer_x = self.keyboard.mouse_rest[0] + pose.mouse_dx
        pointer_y = self.keyboard.mouse_rest[1] + pose.mouse_dy + pose.click * .4
        if pose.touchpad:
            pointer_y += math.sin(pose.time * 14) * pose.scroll_direction * pose.scroll * .6
        for index, paw in enumerate(self.paws):
            rest = self.keyboard.rest[index]
            side = -1 if index == 0 else 1
            offset = motion.left if index == 0 else motion.right
            if self.carried:
                sx, sy = body.shoulder(side)
                paw.aim('lift', (sx - side * 6 + pose.sway_x * .57,
                                 sy + 25 + index * 2 + pose.sway_y * .32))
            elif index == MOUSE_PAW and mouse_active:
                paw.aim('mouse', (pointer_x, pointer_y))
            elif paw.key in self.keyboard.by_id:
                point = self.keyboard.by_id[paw.key].contact
                paw.aim(paw.key, (point[0], point[1] + KEY_TRAVEL), paw.stamp, activity.key_interval, keystroke=True)
                paw.ready = (mix(rest[0], point[0], .4), min(161, point[1] - 5))
                paw.ready_until = now + .6
            elif playing and self.action_kind in ('lick', 'wash') and index == 0:
                paw.aim('groom', FaceGeometry(pose, body).grooming_target(self.action_kind, phase))
            elif playing and motion.rub and side == pose.action_side:
                x, y = FaceGeometry(pose, body).ear_grooming_target(side, motion.stroke)
                paw.aim('ear_rub', (mix(rest[0], x, motion.rub), mix(rest[1], y + 3.5, motion.rub)))
            elif playing and offset is not None:
                paw.aim(self.action_kind, (rest[0] + offset[0], rest[1] + offset[1]))
            elif pose.dizzy:
                paw.aim('brace', (rest[0] + side * 3 * pose.dizzy, rest[1] - max(0., side * roll) * 2.6))
            elif paw.ready is not None and now < paw.ready_until:
                paw.aim('ready', paw.ready)
            else:
                paw.aim('rest', rest)
            paw.advance(dt)
            paw.x, paw.y = body.reachable(-1 if index == 0 else 1, (paw.x, paw.y))
            if index == MOUSE_PAW and mouse_active:
                x, y = pointer_x, pointer_y
                reachable = math.dist(body.reachable(-1, (x, y)), (x, y)) < .01
                if reachable and (self.mouse_contact or math.hypot(paw.x - x, paw.y - y) < 1.5):
                    self.mouse_contact = True
                    paw.x, paw.y = x, y
                    paw.vx, paw.vy = self.mouse_velocity
            if paw.goal in self.keyboard.by_id and not paw.landed and paw.age >= paw.duration * .55:
                contact = self.keyboard.by_id[paw.goal].contact
                if math.hypot(paw.x - contact[0], paw.y - contact[1] - KEY_TRAVEL) < 1.05:
                    paw.landed = True
                    strength = min(.7, .22 + paw.distance / 120 + math.hypot(paw.vx, paw.vy) / 900)
                    paw.pressure = strength
                    pose.contact = min(.9, pose.contact + strength * .6)
                    pose.contact_side = -1 if index == 0 else 1
                    pressures = dict(pose.contacts)
                    pressures[paw.goal] = strength
                    pose.contacts = tuple(pressures.items())[-2:]
        pose.left_x, pose.left_y = self.paws[0].x, self.paws[0].y
        pose.right_x, pose.right_y = self.paws[1].x, self.paws[1].y
        pose.left_key, pose.right_key = self.paws[0].key, self.paws[1].key
        pose.left_pressure, pose.right_pressure = self.paws[0].pressure, self.paws[1].pressure
        if pose.touchpad and self.mouse_contact:
            pose.left_pressure = max(pose.left_pressure, pose.click * .8)
        return pose
