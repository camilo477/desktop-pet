"""Two paw goals and independent channels for a coordinated feline body."""

from dataclasses import dataclass
import math
import random

from activity import Activity, KeyHint
from keyboard_layout import BY_ID, KEY_TRAVEL
from anatomy import BodyGeometry, FaceGeometry

LEFT_REST = (91.0, 157.0)
RIGHT_REST = (115.0, 157.0)
MOUSE_REST = (42.0, 157.0)  # Paw contact on the palm end of the shell.
MOUSE_PAW = 0  # Screen left is the cat's anatomical right.
MOUSE_HOLD = .5
IDLE_ACTION_AFTER = 15.0
RELAX_AFTER = 60.0
SLEEP_AFTER = 180.0
IDLE_ACTION_GAP = (12.0, 27.0)


def approach(value, target, speed, dt):
    result = value + (target - value) * (1 - math.exp(-speed * dt))
    return target if abs(result - target) < .0001 else result


def mix(start, end, amount):
    return start + (end - start) * amount


def smoothstep(value):
    value = max(0, min(1, value))
    return value * value * (3 - 2 * value)


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
    left_x: float = LEFT_REST[0]
    left_y: float = LEFT_REST[1]
    right_x: float = RIGHT_REST[0]
    right_y: float = RIGHT_REST[1]
    left_key: str | None = None
    right_key: str | None = None
    pressed: frozenset[str] = frozenset()
    mouse: float = 0.0
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

    def aim(self, goal, point, stamp=0.0, interval=.33):
        if self.goal != goal or self.motion_stamp != stamp:
            distance = math.hypot(point[0] - self.x, point[1] - self.y)
            if goal in BY_ID:
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
    def __init__(self):
        self.pose = Pose()
        self.time = 0.0
        self.paws = [Paw(*LEFT_REST), Paw(*RIGHT_REST)]
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
        self.sleep_goal = 0.0
        self.next_idle = IDLE_ACTION_AFTER + random.uniform(1, 8)
        self.action_kind = None
        self.action_start = 0.0
        self.action_duration = 4.0
        self.action_weight = 0.0
        self.look_side = 1

    @property
    def sleeping(self):
        return self.pose.sleep > .99 and self.sleep_goal > .99

    def interact(self):
        self.touch_pending = True

    def pet(self, side=0.0):
        self.interact()
        self.pet_start = self.time
        self.pose.pet_side = max(-1, min(1, side))
        self.blink_start = self.time
        self.next_blink = self.time + random.uniform(3, 6)
        self.tail_start = self.time
        self.next_tail = self.time + random.uniform(10, 20)

    def clear_input(self):
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
            paw.landed = False; paw.pressure = 0.0
        self.interact()

    def start_idle(self, kind):
        if kind not in ('look', 'shift', 'lick', 'wash', 'yawn'):
            return
        self.action_kind = kind
        self.action_start = self.time
        self.action_duration = {'look': 3.8, 'shift': 3.3, 'lick': 4.5, 'wash': 4.6, 'yawn': 3.5}[kind]
        self.look_side = random.choice((-1, 1))
        self.next_idle = self.time + self.action_duration + random.uniform(*IDLE_ACTION_GAP)

    def _assign(self, now, activity, mouse):
        available = [1 - MOUSE_PAW] if mouse else [0, 1]
        for index, paw in enumerate(self.paws):
            if index not in available or (paw.key not in activity.held and now > paw.until):
                paw.key = None
        hints = {hint.identifier: hint for hint in (*activity.hints, activity.latest)
                 if hint.identifier in BY_ID and hint.stamp > self.last_hint}
        for hint in sorted(hints.values(), key=lambda value: value.stamp):
            key = BY_ID[hint.identifier]
            existing = next((i for i in available if self.paws[i].key == key.identifier), None)
            if existing is None:
                preferred = key.preferred_paw
                def score(index):
                    paw = self.paws[index]
                    held = paw.key in activity.held
                    modifier = held and BY_ID[paw.key].modifier
                    return (50 if modifier else 28 if held else 0) + (0 if index == preferred else 5) + math.hypot(paw.x - key.contact[0], paw.y - key.contact[1]) * .1
                existing = min(available, key=score)
                if len(available) == 1 and key.modifier and self.paws[existing].key in activity.held:
                    self.last_hint = max(self.last_hint, hint.stamp)
                    continue
            paw = self.paws[existing]
            paw.key = key.identifier
            paw.stamp = hint.stamp
            contact = max(.075, min(.18, activity.key_interval * .55))
            paw.until = max(hint.stamp + contact, now + (.45 if self.pose.sleep > .2 else .04))
            self.last_hint = max(self.last_hint, hint.stamp)
        assigned = {self.paws[i].key for i in available if self.paws[i].key}
        for index in available:
            paw = self.paws[index]
            if paw.key is None:
                candidates = activity.held - assigned
                if candidates:
                    paw.key = min(candidates, key=lambda identifier: (BY_ID[identifier].modifier,
                                   math.hypot(BY_ID[identifier].contact[0] - paw.x, BY_ID[identifier].contact[1] - paw.y)))
                    paw.stamp = 0.0; assigned.add(paw.key)

    def _expressions(self, dt, idle, active):
        t, pose = self.time, self.pose
        age = t - self.pet_start
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
        flick = math.sin(math.pi * age / .55) ** 2 * 4 if 0 <= age < .55 else 0
        pose.ear_left = flick if self.ear_side < 0 else 0
        pose.ear_right = -flick if self.ear_side > 0 else 0
        allowed = idle >= IDLE_ACTION_AFTER and idle < SLEEP_AFTER and not active
        if allowed and self.action_kind is None and t >= self.next_idle:
            choices = ('look', 'shift', 'yawn') if idle > RELAX_AFTER else ('look', 'shift', 'lick', 'wash', 'yawn')
            self.start_idle(random.choice(choices))
        phase = (t - self.action_start) / self.action_duration
        playing = self.action_kind is not None and phase < 1 and allowed
        self.action_weight = approach(self.action_weight, float(playing), 7 if playing else 14, dt)
        if not playing and self.action_weight < .001:
            self.action_kind = None
        pose.action = self.action_kind
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
        for axis, (motion, gain, limit) in enumerate(((activity.motion_x, -.11, 12), (activity.motion_y, -.10, 10))):
            position = positions[axis]
            target, velocity = self.mouse_target[axis], self.mouse_velocity[axis]
            delta = motion * gain if active else 0
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
            # Wait for the paw, then move the object and its contact together.
            if self.mouse_contact or not active:
                following, velocity = spring(position, velocity, target, 21, dt)
                bounded = max(min(position, target), min(max(position, target), following))
                bounded = max(-limit, min(limit, bounded))
                if bounded != following:
                    velocity = 0
                positions[axis] = bounded
            self.mouse_velocity[axis] = velocity
        pose.mouse_dx, pose.mouse_dy = positions

    def advance(self, dt, now=0.0, activity=Activity(), gaze=(0.0, 0.0)):
        pose = self.pose
        observed = max(activity.keyboard, activity.mouse, activity.click, activity.scroll)
        if self.last_activity is None:
            self.last_activity = now
        active = activity.any_held or bool(activity.held) or observed > self.last_activity or self.touch_pending
        if self.sleeping and active:
            dt = min(dt, 1 / 30)  # Restore fluid wake frames after the low-rate sleeping tick.
            self.blink_start = -10.0
            self.next_blink = self.time + random.uniform(1.2, 2.5)
        self.time += dt; pose.time = self.time
        if self.touch_pending or activity.any_held or activity.held:
            self.last_activity = now
        else:
            self.last_activity = max(self.last_activity, observed)
        self.touch_pending = False
        idle = max(0, now - self.last_activity)
        phase, action, playing = self._expressions(dt, idle, active)
        relaxing = max(0, min(1, (idle - RELAX_AFTER) / (SLEEP_AFTER - RELAX_AFTER)))
        pose.relax = approach(pose.relax, relaxing, .8 if relaxing > pose.relax else 6, dt)
        sleep_target = float(idle >= SLEEP_AFTER)
        self.sleep_goal = approach(self.sleep_goal, sleep_target, 1.6 if sleep_target else 10, dt)
        pose.sleep = approach(pose.sleep, self.sleep_goal, 2.4 if sleep_target else 12, dt)
        pose.zzz = approach(pose.zzz, smoothstep((pose.sleep - .78) / .22) if sleep_target else 0, 8, dt)
        pose.breath = math.sin(self.time * math.tau / mix(4.2, 6.2, pose.sleep)) * mix(1, .4, pose.sleep)
        if self.sleeping and sleep_target and not active:
            pose.blink = 1.0; pose.tail = 0.0
            pose.ear_left = pose.ear_right = 0.0
            pose.gaze_x = pose.gaze_y = pose.head_x = pose.head_y = 0.0
            self.head_velocity[:] = (0.0, 0.0, 0.0)
            pose.pressed = frozenset()
            return pose
        mouse_active = now - max(activity.mouse, activity.scroll) < MOUSE_HOLD
        self.mouse_goal = approach(self.mouse_goal, float(mouse_active), 10, dt)
        pose.mouse = approach(pose.mouse, self.mouse_goal, 12, dt)
        self._mouse_motion(dt, activity, mouse_active)
        age = now - activity.click
        pose.click = math.sin(math.pi * age / .18) if 0 <= age < .18 else 0
        if activity.scroll_x or activity.scroll_y:
            pose.scroll_direction = math.copysign(1, activity.scroll_y or activity.scroll_x)
            pose.scroll = min(1, pose.scroll + abs(activity.scroll_y or activity.scroll_x) * .4)
        else:
            pose.scroll = approach(pose.scroll, 0, 9, dt)
        pose.contact = approach(pose.contact, 0, 17, dt)
        pose.contacts = tuple((key, pressure * math.exp(-dt * 24)) for key, pressure in pose.contacts
                              if pressure * math.exp(-dt * 24) > .025)
        pose.pressed = activity.pressed
        self._assign(now, activity, mouse_active)
        goals = [BY_ID[paw.key].contact for paw in self.paws if paw.key in BY_ID]
        key_point = BY_ID[activity.latest.identifier].contact if activity.latest.identifier in BY_ID else (goals[-1] if goals else None)
        if key_point:
            points = [BY_ID[hint.identifier].contact for hint in activity.hints
                      if hint.identifier in BY_ID and now - hint.stamp < .16]
            self.focus_point[:] = tuple(sum(point[axis] for point in points) / len(points) for axis in (0, 1)) if points else key_point
        pose.focus = approach(pose.focus, (0.2 if mouse_active else 1) if key_point else 0, 12, dt)
        moving = now - activity.mouse < .60
        scrolling = now - activity.scroll < MOUSE_HOLD
        if moving and (not scrolling or now - activity.mouse < .18):
            look = gaze
            if key_point and activity.held:
                look = (gaze[0] * .9 + (self.focus_point[0] - 118) / 70 * .1, gaze[1] * .9 + .07)
        elif scrolling:
            look = (-.72 + pose.mouse_dx / 120, .78)
        elif key_point:
            look = ((self.focus_point[0] - 116) / 72, .95)
        elif playing and self.action_kind == 'look':
            look = (self.look_side * .55 * action, -.05)
        elif pose.groom > .02:
            look = (-.13, .38)
        elif pose.yawn > .02:
            look = (0, -pose.yawn * .2)
        else:
            look = (0, .10)
        look = (mix(look[0], pose.pet_side * .32, pose.pet), mix(look[1], .3, pose.pet))
        if pose.sleep > .4:
            look = (look[0] * (1 - pose.sleep), look[1] * (1 - pose.sleep))
        look = tuple(max(-1, min(1, value)) for value in look)
        # All three channels receive attention directly, rather than filtering each other.
        pose.gaze_x = approach(pose.gaze_x, look[0], 24, dt)
        pose.gaze_y = approach(pose.gaze_y, look[1], 24, dt)
        head_speed = 13 if key_point else 11
        pose.head_x, self.head_velocity[0] = spring(pose.head_x, self.head_velocity[0], look[0], head_speed, dt)
        pose.head_y, self.head_velocity[1] = spring(pose.head_y, self.head_velocity[1], look[1], head_speed, dt)
        tilt = look[0] * 3.5 + pose.pet_side * pose.pet * 8
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
            mouse_lean = -15 + pose.mouse_dx * .55
            target_x = mix(mouse_lean, target_x, .18) if key_point else mouse_lean
            target_y = max(target_y, 10 + pose.mouse_dy * .32)
        if playing and self.action_kind == 'shift':
            target_x += self.look_side * action * 2
        if pose.groom > 0:
            target_x -= pose.groom * 1.6
            target_y += pose.groom * 1.8
        target_y += pose.relax * 1.2 - pose.yawn * .6
        old_balance = pose.balance_x
        pose.balance_x = approach(pose.balance_x, target_x * (1 - pose.sleep), 10, dt)
        pose.balance_y = approach(pose.balance_y, target_y * (1 - pose.sleep), 10, dt)
        pose.balance_velocity = (pose.balance_x - old_balance) / max(.001, dt)
        pose.ear_left += pose.balance_velocity * .013
        pose.ear_right += pose.balance_velocity * .009
        body = BodyGeometry(pose)
        face = FaceGeometry(pose, body)
        for index, paw in enumerate(self.paws):
            rest = LEFT_REST if index == 0 else RIGHT_REST
            if pose.sleep > .08 and not active and sleep_target:
                paw.aim('tuck', (90 if index == 0 else 118, 144))
            elif playing and self.action_kind in ('lick', 'wash') and index == 0:
                paw.aim('groom', face.grooming_target(self.action_kind, phase))
            elif index == MOUSE_PAW and mouse_active:
                paw.aim('mouse', (MOUSE_REST[0] + pose.mouse_dx, MOUSE_REST[1] + pose.mouse_dy + pose.click * .4))
            elif paw.key in BY_ID:
                point = BY_ID[paw.key].contact
                paw.aim(paw.key, (point[0], point[1] + KEY_TRAVEL), paw.stamp, activity.key_interval)
                paw.ready = (mix(rest[0], point[0], .4), min(161, point[1] - 5))
            elif now - activity.keyboard < .70 and paw.ready is not None:
                paw.aim('ready', paw.ready)
            else:
                paw.aim('rest', rest)
            paw.advance(dt)
            paw.x, paw.y = body.reachable(-1 if index == 0 else 1, (paw.x, paw.y))
            if index == MOUSE_PAW and mouse_active:
                x, y = MOUSE_REST[0] + pose.mouse_dx, MOUSE_REST[1] + pose.mouse_dy + pose.click * .4
                reachable = math.dist(body.reachable(-1, (x, y)), (x, y)) < .01
                if reachable and (self.mouse_contact or math.hypot(paw.x - x, paw.y - y) < 1.5):
                    self.mouse_contact = True
                    paw.x, paw.y = x, y
                    paw.vx, paw.vy = self.mouse_velocity
            if paw.goal in BY_ID and not paw.landed and paw.age >= paw.duration * .55:
                contact = BY_ID[paw.goal].contact
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
        return pose
