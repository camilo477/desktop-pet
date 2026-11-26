"""Shared, grounded body deformation and a small projected facial surface."""

import math

MAX_REACH = 78.0
FACE_RX, FACE_RY, FACE_DEPTH = 35, 28, 23
EAR_ANCHORS = {-1: (82, 57), 1: (125, 57)}


def face_depth(x, y):
    return FACE_DEPTH * math.sqrt(max(0.0, 1 - (x / FACE_RX) ** 2 - (y / FACE_RY) ** 2))


class BodyGeometry:
    def __init__(self, pose):
        self.lift = pose.lift
        self.x = pose.balance_x + pose.sway_x + pose.contact_side * pose.contact * .45
        contact_dip = pose.contact * (1.25 + max(0, pose.expression.opening - 1) * 2)
        self.y = (pose.balance_y + pose.sway_y + pose.relax * 1.2 - pose.breath * .55
                  + pose.pet * 1.1 + contact_dip)
        self.breadth = 1 + pose.breath * .002 + pose.contact * .003
        self.mouse_reach = pose.mouse
        self.shoulder_roll = pose.motion.shoulders

    def map(self, x, y):
        # Zero deformation at the floor: the haunches do not slide with the chest.
        weight = max(0.0, min(1.05, (153 - y) / 62))
        drop = self.y
        if self.shoulder_roll:
            drop += self.shoulder_roll * max(-1, min(1, (x - 104) / 18))
        return (104 + (x - 104) * (1 + (self.breadth - 1) * weight) + self.x * weight,
                y + drop * weight - self.lift)

    @property
    def hips(self):
        return self.map(104, 153)

    @property
    def chest(self):
        return self.map(104, 111)

    @property
    def neck(self):
        return self.map(103, 94)

    @property
    def head(self):
        return self.map(103, 76.5)

    @property
    def tail_base(self):
        return self.map(139, 145)

    def shoulder(self, side):
        slide = self.mouse_reach if side < 0 else 0
        return self.map((87 if side < 0 else 119) - 4 * slide, 115 + 4 * slide)

    def reachable(self, side, point):
        sx, sy = self.shoulder(side)
        dx, dy = point[0] - sx, point[1] - sy
        distance = math.hypot(dx, dy)
        if distance <= MAX_REACH:
            return point
        return sx + dx * MAX_REACH / distance, sy + dy * MAX_REACH / distance


class FaceGeometry:
    def __init__(self, pose, body=None):
        self.pose = pose
        body = body or BodyGeometry(pose)
        self.cx, self.cy = body.head
        # The neck stays anchored as the chin dips and the head settles to one side.
        self.cx += 3.8 * pose.sleep
        self.cy += 4.6 * pose.sleep + pose.pet * 2 + pose.groom * .8
        self.yaw = pose.head_x * .46 + .17 * pose.sleep + pose.motion.turn
        self.pitch = pose.head_y * .34 + pose.expression.pitch + pose.contact * .025 + .12 * pose.sleep + pose.motion.pitch
        self.roll = math.radians(pose.head_tilt + 14 * pose.sleep + pose.motion.tilt)
        self.cos_y, self.sin_y = math.cos(self.yaw), math.sin(self.yaw)
        self.cos_p, self.sin_p = math.cos(self.pitch), math.sin(self.pitch)
        self.cos_r, self.sin_r = math.cos(self.roll), math.sin(self.roll)

    def _screen(self, x, y):
        return (self.cx + .92 * (x * self.cos_r - y * self.sin_r),
                self.cy + .92 * (x * self.sin_r + y * self.cos_r))

    def point(self, x, y, depth=None):
        if depth is None:
            depth = face_depth(x, y)
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

    def ear_projection(self, side):
        anchor_x, anchor_y = EAR_ANCHORS[side]
        pose = self.pose
        angle = math.radians((pose.ear_left if side < 0 else pose.ear_right)
                             + side * pose.sleep * 20 + side * pose.pet * 13)
        cos, sin = math.cos(angle), math.sin(angle)

        def project(x, y):
            x, y = x - anchor_x, y - anchor_y
            return self.point(anchor_x - 101 + x * cos - y * sin,
                              anchor_y - 77 + x * sin + y * cos, -3)
        return project

    def ear_grooming_target(self, side, stroke):
        x, y = EAR_ANCHORS[side]
        return self.ear_projection(side)(x + side * 7, y + 4 + stroke)

    def grooming_target(self, kind, phase):
        if kind == 'lick':
            x, y = self.mouth
            return x - 2, y + 4 + math.sin(phase * math.tau * 4) * .55
        stroke = (phase * 2.2) % 1
        return self.point(-21 + math.sin(stroke * math.pi) * 3,
                          9 - math.sin(stroke * math.pi) * 27)
