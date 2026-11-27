"""Original fur markings in facial, trunk and limb surface coordinates."""

from dataclasses import dataclass
import math

from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainterPath, QRadialGradient, QTransform
from PySide6.QtCore import Qt

from anatomy import FACE_RX, FACE_RY, FACE_DEPTH, FACE_CAMERA_DISTANCE, BodyGeometry, face_depth


FACE_RADII = (FACE_RX, FACE_RY, FACE_DEPTH)
FACE_SAMPLE_STEP = .65


def smooth_loop(points):
    """Make a closed cubic through a small set of hand-placed landmarks."""
    result = [points[0]]
    for i, a in enumerate(points):
        before, b, after = points[i - 1], points[(i + 1) % len(points)], points[(i + 2) % len(points)]
        result.extend(
            (
                tuple(a[k] + (b[k] - before[k]) * 0.14 for k in (0, 1)),
                tuple(b[k] - (after[k] - a[k]) * 0.14 for k in (0, 1)),
                b,
            )
        )
    return result


def cubic_path(points):
    path = QPainterPath()
    path.moveTo(*points[0])
    for i in range(1, len(points), 3):
        path.cubicTo(*points[i], *points[i + 1], *points[i + 2])
    path.closeSubpath()
    return path


def surface(x, y):
    return (x, y, face_depth(x, y))


class FacePatch:
    def __init__(self, points):
        loop = smooth_loop(points)
        # Keep the same sampled boundary on both sides of the horizon. Switching
        # from projected cubic controls to a coarse polygon made markings pop.
        contour = []
        for i in range(0, len(loop) - 1, 3):
            length = sum(math.dist(loop[i + j], loop[i + j + 1]) for j in range(3))
            steps = max(8, math.ceil(length / FACE_SAMPLE_STEP))
            for step in range(steps):
                t = step / steps
                u = 1 - t
                weights = (u**3, 3 * u * u * t, 3 * u * t * t, t**3)
                contour.append(
                    surface(*(sum(loop[i + j][k] * w for j, w in enumerate(weights)) for k in (0, 1)))
                )
        self.contour = contour

    def project(self, face):
        nx, ny, nz = -face.sin_y * face.cos_p, -face.sin_p, face.cos_y * face.cos_p
        nx, ny, nz = nx / FACE_RX**2, ny / FACE_RY**2, nz / FACE_DEPTH**2
        # The perspective camera's tangent plane is offset from the origin.
        # In unit-sphere coordinates its intersection is a small circle.
        offset = face.cos_p / FACE_CAMERA_DISTANCE
        normal = (nx * FACE_RX, ny * FACE_RY, nz * FACE_DEPTH)
        length2 = sum(value * value for value in normal)
        center = tuple(value * offset / length2 for value in normal)
        radius = math.sqrt(1 - offset * offset / length2)
        dots = [nx * x + ny * y + nz * z - offset for x, y, z in self.contour]
        path = QPainterPath()
        start = next((i for i, dot in enumerate(dots) if dot >= 0), None)
        if start is None:
            return path
        previous, prior = self.contour[start], dots[start]
        path.moveTo(*face.point(*previous))
        horizon_start = None
        for index in range(start + 1, start + len(self.contour) + 1):
            point, dot = self.contour[index % len(self.contour)], dots[index % len(dots)]
            if (prior < 0) != (dot < 0):
                t = prior / (prior - dot)
                unit = [(a + (b - a) * t) / scale - c
                        for a, b, scale, c in zip(previous, point, FACE_RADII, center)]
                norm = math.hypot(*unit)
                unit = [value / norm for value in unit]
                if dot < 0:
                    horizon_start = unit
                else:
                    # The hidden part ends on a curved horizon, not the chord
                    # between its two crossings through the visible forehead.
                    cosine = sum(a * b for a, b in zip(horizon_start, unit))
                    angle = math.acos(max(-1., min(1., cosine)))
                    steps = max(1, math.ceil(angle * radius * max(FACE_RADII) / FACE_SAMPLE_STEP))
                    for step in range(1, steps):
                        fraction = step / steps
                        middle = [a + (b - a) * fraction for a, b in zip(horizon_start, unit)]
                        length = math.hypot(*middle)
                        edge = ((c + value / length * radius) * scale
                                for value, c, scale in zip(middle, center, FACE_RADII))
                        path.lineTo(*face.point(*edge))
                edge = ((c + value * radius) * scale for value, c, scale in zip(unit, center, FACE_RADII))
                path.lineTo(*face.point(*edge))
            if dot >= 0:
                path.lineTo(*face.point(*point))
            previous, prior = point, dot
        path.closeSubpath()
        return path


@dataclass(frozen=True)
class Pattern:
    face: tuple = ()
    body: tuple = ()
    # Leg bands span samples on the two edges of the live shoulder-to-wrist curve.
    legs: tuple = ((), ())
    # Paired tail contours run from base (0) through the bend (1) to the tip (3).
    tail: tuple = ()


def cheeks(side, y):
    return [(side*x, y+dy) for x,dy in ((20, 0),(27,-2.5),(32,-4.2),(29,-1.3),(24,.7))]


TABBY_FACE = (
    ('accent', [(-12,10),(-5,8),(0,9),(5,8),(12,10),(9,14),(3,15),(0,14),(-4,15),(-10,14)]),
    # Paired, tapering brow strokes grow together towards the bridge.
    *(('ink', [(side*x,y) for x,y in ((2,-27),(5,-25),(6,-19),(6.5,-15),
                                        (9,-19),(13,-21),(11,-17),(6,-12),(4.5,-15),(4,-21))])
      for side in (-1,1)),
    *(('ink', cheeks(s,y)) for s in (-1,1) for y in (6,11)),
)
TABBY_BODY = tuple(('ink', [(x,y),(x+side*9,y+3),(x+side*18,y+9),
                            (x+side*9,y+5.8),(x-side*1,y+2.8)])
                   for side,x in ((-1,78),(1,130)) for y in (110,121,133))
TABBY_LEGS = (('ink', 6, 7.1), ('ink', 9, 10.2))
TABBY = Pattern(TABBY_FACE, TABBY_BODY, (TABBY_LEGS, TABBY_LEGS),
                (('ink',.30,.38),('ink',.57,.65),('ink',.84,.94),('ink',1.25,1.47),('ink',2.38,3.0)))

BIB = Pattern(
    face=(('ink', [(-13,12),(-6,9),(-2,8),(1,4),(4,9),(12,11),(11,16),(6,20),(0,22),(-8,19)]),),
    body=(('ink', [(87,92),(101,96),(120,91),(119,103),(115,111),(110,117),(106,126),
                   (100,121),(96,116),(91,113),(89,106)]),),
    legs=((('ink',11.9,14),),(('ink',12.5,14),)),
)
PIEBALD = Pattern(
    face=(('ink',[(-30,-17),(-14,-29),(-3,-27),(2,-21),(-3,-13),(-7,-7),
                  (-10,1),(-17,5),(-26,2),(-32,-4)]),
          ('ink',[(9,-24),(22,-23),(31,-16),(30,-9),(25,-6),(19,-10),(16,-16)])),
    body=(('ink',[(91,91),(115,87),(132,99),(135,113),(130,119),(115,116),
                  (108,111),(101,112),(94,106)]),
          ('ink',[(61,125),(72,119),(78,120),(82,129),(78,137),(81,145),
                  (72,153),(62,148)])),
    legs=((),(('ink',6.7,14),)),
)
POINT = Pattern()  # The seal points use feathered color on face and forelegs.
PATCHES = Pattern(
    face=(('ink',[(-31,-14),(-20,-25),(-7,-27),(-3,-21),(-7,-15),(-6,-9),(-12,1),
                  (-21,6),(-29,1)]),
          ('accent',[(3,-26),(18,-25),(31,-16),(33,-6),(26,-1),(21,-3),(16,-10),
                     (9,-11),(7,-18)])),
    body=(('accent',[(89,90),(104,89),(109,101),(105,111),(100,116),(90,114),
                     (84,119),(76,113),(78,102)]),
          ('ink',[(122,104),(133,111),(141,123),(146,140),(137,146),(125,141),
                  (124,134),(114,129),(115,119)]),
          ('accent',[(65,139),(77,137),(85,146),(87,156),(73,160),(63,154)])),
    legs=((('accent',2.5,7.6),),(('ink',5.4,10),)),
    tail=(('ink',.28,.88),('ink',1.72,3.0)),
)
BRINDLE = Pattern(
    face=(('ink',[(-11,-26),(-4,-25),(0,-18),(-2,-11),(2,-4),(1,8),(-5,5),
                  (-7,-3),(-13,-8),(-10,-16)]),
          ('accent',[(14,-20),(25,-17),(27,-11),(19,-8),(13,-11)]),
          ('ink',[(17,7),(29,2),(28,8),(20,13),(12,13)])),
    body=(('ink',[(77,101),(86,96),(95,99),(92,108),(96,114),(88,120),(79,117)]),
          ('accent',[(101,120),(113,112),(119,116),(115,124),(118,129),(110,139),(100,136)]),
          ('ink',[(126,132),(137,125),(143,133),(141,140),(130,148),(127,145)])),
    legs=((('ink',8.5,14),),(('accent',3.5,6.5),)),
    tail=(('accent',.28,.6),('ink',.92,1.42),('accent',2.6,3.0)),
)

PATTERNS = {'tabby': TABBY, 'bib': BIB, 'piebald': PIEBALD, 'point': POINT,
            'patches': PATCHES, 'brindle': BRINDLE}


def tail_weights(start, stop):
    # Each strip samples matching cubic rails from the actual SVG outline.
    # Segment 0 mates with reversed segment 5, 1 with 4, and 2 with 3.
    count = math.ceil((stop - start) * 7)
    rails = [[], []]
    for i in range(count + 1):
        position = start + (stop - start) * i / count
        segment = min(2, int(position))
        t = position - segment
        u = 1 - t
        weights = (u**3, 3 * u * u * t, 3 * u * t * t, t**3)
        for side, first, step in ((0, segment * 3, 1), (1, (6 - segment) * 3, -1)):
            rails[side].append(tuple((first + step * j, w) for j, w in enumerate(weights)))
    return rails[0] + rails[1][::-1]


class Markings:
    def __init__(self, coat):
        pattern = PATTERNS[coat.pattern]
        colors = {'ink': QColor(coat.ink), 'accent': QColor(coat.accent or coat.ink)}
        self.point_brush = None
        if pattern is POINT:
            gradient = QRadialGradient(0, 0, 1)
            for t, alpha in ((0, 255), (0.45, 250), (0.70, 204), (0.88, 84), (1, 0)):
                tint = QColor(colors['ink'])
                tint.setAlpha(alpha)
                gradient.setColorAt(t, tint)
            self.point_brush = QBrush(gradient)
            self.point_color = colors['ink']
        self.face = [(colors[c], FacePatch(points)) for c, points in pattern.face]
        self.body = [(colors[c], BodyGeometry.bind(smooth_loop(points))) for c, points in pattern.body]
        self.legs = [[(colors[c], start, stop) for c, start, stop in bands] for bands in pattern.legs]
        self.tail = [(colors[c], tail_weights(start, stop)) for c, start, stop in pattern.tail]

    def draw_face(self, p, face, shape):
        if self.point_brush is not None:
            # Local tangent axes turn, pitch and roll with the muzzle.
            for cx, cy, rx, ry in ((0, -2, 30, 16), (-0.7, 7.5, 19, 14)):
                x, y = face.point(cx, cy)
                l, r = face.point(cx - rx, cy), face.point(cx + rx, cy)
                top, bottom = face.point(cx, cy - ry), face.point(cx, cy + ry)
                self.point_brush.setTransform(
                    QTransform(
                        (r[0] - l[0]) * 0.5,
                        (r[1] - l[1]) * 0.5,
                        (bottom[0] - top[0]) * 0.5,
                        (bottom[1] - top[1]) * 0.5,
                        x,
                        y,
                    )
                )
                p.fillPath(shape, self.point_brush)
        for color, patch in self.face:
            p.fillPath(patch.project(face), color)

    def draw_body(self, p, body):
        p.save()
        p.setOpacity(p.opacity() * 0.94)
        for color, controls in self.body:
            p.fillPath(cubic_path(body.deform(controls)), color)
        p.restore()

    def draw_tail(self, p, outline, warped):
        if not self.tail:
            return
        p.save()
        p.setClipPath(outline, Qt.ClipOperation.IntersectClip)
        for color, samples in self.tail:
            path = QPainterPath()
            for weights in samples:
                x = y = 0.0
                for i, w in weights:
                    x += warped[i][0] * w
                    y += warped[i][1] * w
                if path.elementCount():
                    path.lineTo(x, y)
                else:
                    path.moveTo(x, y)
            path.closeSubpath()
            p.fillPath(path, color)
        p.restore()

    def draw_arm(self, p, side, outline, left, right):
        if self.point_brush is not None:

            def middle(i):
                return ((left[i][0] + right[i][0]) * 0.5, (left[i][1] + right[i][1]) * 0.5)

            gradient = QLinearGradient(*middle(4), *middle(13))
            clear = QColor(self.point_color)
            clear.setAlpha(0)
            gradient.setColorAt(0, clear)
            gradient.setColorAt(1, self.point_color)
            p.fillPath(outline, gradient)
            return
        bands = self.legs[int(side > 0)]
        if not bands:
            return
        p.save()
        p.setClipPath(outline, Qt.ClipOperation.IntersectClip)

        def edge(rail, t):
            i = min(int(t), len(rail) - 2)
            a, b = rail[i : i + 2]
            return (a[0] + (b[0] - a[0]) * (t - i), a[1] + (b[1] - a[1]) * (t - i))

        for color, start, stop in bands:
            # A slightly diagonal cuff follows both changing edges of the foreleg.
            path = QPainterPath()
            path.moveTo(*edge(left, start))
            for i in range(math.ceil(start), math.ceil(stop)):
                path.lineTo(*left[i])
            path.lineTo(*edge(left, stop))
            end = stop if stop == 14 else stop + 0.40
            a, b = edge(left, stop), edge(right, end)
            dx, dy = right[0][0] - left[0][0], right[0][1] - left[0][1]
            path.quadTo((a[0] + b[0]) * 0.5 - dy * 0.11, (a[1] + b[1]) * 0.5 + dx * 0.11, *b)
            for i in range(int(end), math.ceil(start + 0.6) - 1, -1):
                path.lineTo(*right[i])
            path.lineTo(*edge(right, start + 0.6))
            a, b = edge(right, start + 0.6), edge(left, start)
            path.cubicTo(
                a[0] - (a[0] - b[0]) * 0.35 + dy * 0.16,
                a[1] - (a[1] - b[1]) * 0.35 - dx * 0.16,
                b[0] + (a[0] - b[0]) * 0.35 - dy * 0.08,
                b[1] + (a[1] - b[1]) * 0.35 + dx * 0.08,
                *b
            )
            path.closeSubpath()
            p.fillPath(path, color)
        p.restore()
