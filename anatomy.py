"""Shared, grounded body deformation and a small projected facial surface."""

import math

MAX_REACH = 78.0


def mix(a, b, t):
    return a + (b - a) * t


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


class BodyGeometry:
    def __init__(self, pose):
        self.sleep = smooth(pose.sleep)
        self.x = pose.balance_x + pose.contact_side * pose.contact * .45
        contact_dip = pose.contact * (1.25 + max(0, pose.expression.opening - 1) * 2)
        self.y = (pose.balance_y + pose.relax * 1.2 - pose.breath * .55
                  + pose.pet * 1.1 + contact_dip)
        self.breadth = 1 + pose.breath * .002 + pose.contact * .003
        self.mouse_reach = pose.mouse * (1 - self.sleep)

    def map(self, x, y):
        # Zero deformation at the floor: the haunches do not slide with the chest.
        weight = max(0.0, min(1.05, (153 - y) / 62))
        return (104 + (x - 104) * (1 + (self.breadth - 1) * weight) + self.x * weight,
                y + self.y * weight)

    @property
    def hips(self):
        return self.map(104, 153)

    @property
    def chest(self):
        return self.map(104, mix(111, 134, self.sleep))

    @property
    def neck(self):
        return self.map(mix(103, 110, self.sleep), mix(94, 129, self.sleep))

    @property
    def head(self):
        return self.map(mix(103, 110, self.sleep), mix(76.5, 131, self.sleep))

    @property
    def tail_base(self):
        return self.map(139, 145)

    def shoulder(self, side):
        slide = self.mouse_reach if side < 0 else 0
        return self.map(mix(87 if side < 0 else 119, 90 if side < 0 else 119, self.sleep) - 4 * slide,
                        mix(115, 139, self.sleep) + 4 * slide)

    def reachable(self, side, point):
        sx, sy = self.shoulder(side)
        dx, dy = point[0] - sx, point[1] - sy
        distance = math.hypot(dx, dy)
        if distance <= MAX_REACH:
            return point
        return sx + dx * MAX_REACH / distance, sy + dy * MAX_REACH / distance


class FaceGeometry:
    def __init__(self, pose, body=None):
        body = body or BodyGeometry(pose)
        self.sleep = body.sleep
        self.cx, self.cy = body.head
        awake = 1 - self.sleep
        self.yaw = pose.head_x * .46 * awake
        self.pitch = (pose.head_y * .34 + pose.expression.pitch + pose.contact * .025) * awake
        self.roll = math.radians(pose.head_tilt * awake)
        self.cy += pose.pet * 2 + pose.groom * .8
        self.scale = mix(.92, 1.0, self.sleep)
        self.cos_y, self.sin_y = math.cos(self.yaw), math.sin(self.yaw)
        self.cos_p, self.sin_p = math.cos(self.pitch), math.sin(self.pitch)
        self.cos_r, self.sin_r = math.cos(self.roll), math.sin(self.roll)

    def _screen(self, x, y):
        return (self.cx + self.scale * (x * self.cos_r - y * self.sin_r),
                self.cy + self.scale * (x * self.sin_r + y * self.cos_r))

    def point(self, x, y, depth=None):
        if depth is None:
            depth = 23 * math.sqrt(max(0.0, 1 - (x / 35) ** 2 - (y / 28) ** 2))
        horizontal = x * self.cos_y + depth * self.sin_y
        forward = depth * self.cos_y - x * self.sin_y
        vertical = y * self.cos_p + forward * self.sin_p
        perspective = 1 / (1 - forward / 240)
        return self._screen(horizontal * perspective, vertical * perspective)

    def outline(self, x, y):
        # Ellipsoid support widths preserve volume as the facial surface turns.
        width = math.hypot(self.cos_y, .72 * self.sin_y)
        height = math.hypot(self.cos_p, .82 * self.sin_p)
        return self._screen(x * width, y * height)

    @property
    def mouth(self):
        return self.point(0, 15)

    def grooming_target(self, kind, phase):
        if kind == 'lick':
            x, y = self.mouth
            return x - 2, y + 4 + math.sin(phase * math.tau * 4) * .55
        stroke = (phase * 2.2) % 1
        return self.point(-21 + math.sin(stroke * math.pi) * 3,
                          9 - math.sin(stroke * math.pi) * 27)
