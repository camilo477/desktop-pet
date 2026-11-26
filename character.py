"""Minimal feline silhouettes and organic limbs, drawn on an invisible floor."""

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtSvg import QSvgRenderer

from animations import Pose, mix, smoothstep
from anatomy import BodyGeometry, FaceGeometry
from keyboard_layout import BOARD, KEYS, LABELS

BODY_TONES = ('neck-shade', 'chest-volume', 'hip-left', 'hip-right')


def curve(points):
    path = QPainterPath()
    path.moveTo(*points[0])
    for i in range(1, len(points), 3):
        path.cubicTo(*points[i], *points[i + 1], *points[i + 2])
    path.closeSubpath()
    return path


def polygon(points):
    path = QPainterPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.closeSubpath()
    return path


class CatArt:
    def __init__(self):
        path = Path(__file__).resolve().parent / 'assets' / 'cat' / 'miga.svg'
        self.renderer = QSvgRenderer(str(path))
        if not self.renderer.isValid():
            raise RuntimeError('Could not load the character artwork.')
        self.wheel_center = self.renderer.boundsOnElement('mouse-wheel').center()
        elements = {node.get('id'): node for node in ET.parse(path).iter() if node.get('id')}
        self.shapes = {}
        names = ('body', 'body-sleep', 'head-shape', 'head-sleep', 'tail', 'tail-sleep',
                 'ear-left', 'ear-right', 'ear-inner-left', 'ear-inner-right', 'face-volume')
        names += tuple(name + suffix for name in BODY_TONES for suffix in ('', '-sleep'))
        for name in names:
            node = elements[name]
            if node.tag.endswith('g'):
                node = next(iter(node))
            data = node.get('d', '')
            values = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', data)]
            commands = re.findall('[A-Za-z]', data)
            count = (len(values) - 2) // 6
            if commands != ['M'] + ['C'] * count + ['Z'] or len(values) != 2 + count * 6:
                raise RuntimeError('Silhouettes must use matching absolute M/C/Z curves.')
            self.shapes[name] = list(zip(values[::2], values[1::2]))
        pairs = (('body', 'body-sleep'), ('head-shape', 'head-sleep'), ('tail', 'tail-sleep'))
        for a, b in pairs + tuple((name, name + '-sleep') for name in BODY_TONES):
            if len(self.shapes[a]) != len(self.shapes[b]):
                raise RuntimeError('Resting silhouettes must retain their curve topology.')
        self.sleep_body = curve(self.shapes['body-sleep'])
        self.sleep_head = curve(self.shapes['head-sleep'])
        self.sleep_tail = curve(self.shapes['tail-sleep'])
        self.ears = {name: curve(self.shapes[name]) for name in ('ear-left', 'ear-right')}
        self.head_hit_paths = []
        self.head_center = 101.0
        self.head_position = QPointF(103, 76.5)
        self.layers = {}
        self.cache_scale = 0.0
        self.layout = 'us'
        self.keyboard = QPixmap()
        self.sleep_face = None
        self.keys = {key.identifier: key for key in KEYS}
        self.key_paths = {key.identifier: polygon(key.polygon) for key in KEYS}
        # SVG colors are shared by cached artwork and procedural surfaces.
        self.fur = QColor(elements['body'].get('fill'))
        self.head_fur = QColor(elements['head-shape'].get('fill'))
        self.tail_fur = QColor(elements['tail'].get('fill'))
        self.foreleg = QColor(elements['front-legs'].get('fill'))
        self.iris = QColor(elements['eyes'].get('fill'))
        self.pupil = QColor(elements['pupils'].get('fill'))
        self.whisker = QColor(elements['whiskers'].get('stroke'))
        self.ear_inner = QColor(elements['ear-inner-left'].get('fill'))
        self.face_tone = QColor(elements['face-volume'].get('fill'))
        self.lid_color = QColor(elements['closed-eyes'].get('stroke'))
        self.body_tones = {name: QColor(elements[name].get('fill')) for name in BODY_TONES}
        self.sleep_tones = [(curve(self.shapes[name + '-sleep']), color)
                            for name, color in self.body_tones.items()]
        font = QFont('sans-serif'); font.setPixelSize(8)
        self.z_path = QPainterPath(); self.z_path.addText(QPointF(0, 0), font, 'z')

    def set_layout(self, layout):
        layout = layout if layout in LABELS else 'us'
        if layout != self.layout:
            self.layout = layout
            self.cache_scale = 0

    def cache(self, size, pixel_ratio):
        scale = math.ceil(size * pixel_ratio) / 200
        if scale == self.cache_scale:
            return
        self.cache_scale = scale
        for name in ('mouse', 'paw', 'hind-feet'):
            bounds = self.renderer.boundsOnElement(name)
            left, top = math.floor((bounds.left() - 1) * scale), math.floor((bounds.top() - 1) * scale)
            width = math.ceil((bounds.right() + 1) * scale) - left
            height = math.ceil((bounds.bottom() + 1) * scale) - top
            origin = QPointF(left / scale, top / scale)
            image = QPixmap(width, height); image.fill(Qt.GlobalColor.transparent)
            p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.scale(scale, scale); p.translate(-origin.x(), -origin.y())
            self.renderer.render(p, name, bounds); p.end(); image.setDevicePixelRatio(scale)
            self.layers[name] = origin, image
        self.keyboard = QPixmap(math.ceil(200 * scale), math.ceil(200 * scale))
        self.keyboard.fill(Qt.GlobalColor.transparent)
        p = QPainter(self.keyboard); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(scale, scale)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#647078'))
        p.save(); p.translate(0, 2); p.drawPath(polygon(BOARD)); p.restore()
        p.setBrush(QColor('#929ea2')); p.drawPath(polygon(BOARD))
        for key in KEYS:
            self.draw_key(p, key, False, scale)
        p.end(); self.keyboard.setDevicePixelRatio(scale)
        self.sleep_face = None
        image = QPixmap(math.ceil(200 * scale), math.ceil(200 * scale))
        image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(scale, scale)
        resting = Pose(sleep=1, blink=1)
        self._head(p, resting, BodyGeometry(resting)); p.end(); image.setDevicePixelRatio(scale)
        self.sleep_face = image, self.head_hit_paths[:]

    def draw_key(self, p, key, down, scale, pressure=0.0):
        p.save(); p.translate(0, (.35 if down else 0) + pressure * .45)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#829294' if down else '#ccd2ce'))
        p.drawPath(self.key_paths[key.identifier])
        label = LABELS.get(self.layout, {}).get(key.identifier, key.label)
        if scale >= 1.4 and label:
            font = QFont('sans-serif'); font.setPixelSize(3)
            p.setFont(font); p.setPen(QColor('#39454b'))
            x, y, ux, uy, vx, vy = key.label_basis
            p.setTransform(QTransform(ux, uy, vx, vy, x, y), True)
            bounds = QRectF(-key.width * 2.5 + .3, -2.5, key.width * 5 - .6, 5)
            metrics = QFontMetricsF(font)
            if metrics.horizontalAdvance(label) < bounds.width() - .4:
                p.drawText(bounds, Qt.AlignmentFlag.AlignCenter, label)
        p.restore()

    def layer(self, p, name):
        origin, image = self.layers[name]; p.drawPixmap(origin, image)

    def blended(self, a, b, sleep):
        return [(mix(x, sx, sleep), mix(y, sy, sleep))
                for (x, y), (sx, sy) in zip(self.shapes[a], self.shapes[b])]

    def _body(self, p, pose, body):
        sleep = body.sleep
        p.setBrush(self.fur); p.setPen(Qt.PenStyle.NoPen)
        if sleep > .999:
            p.save(); p.translate(104, 153); p.scale(1, 1 - pose.breath * .003)
            p.translate(-104, -153); p.drawPath(self.sleep_body)
            p.setClipPath(self.sleep_body)
            for path, color in self.sleep_tones:
                p.setBrush(color); p.drawPath(path)
            p.restore()
            return
        points = self.blended('body', 'body-sleep', sleep)
        outline = curve([body.map(x, y) for x, y in points])
        p.drawPath(outline)
        p.save(); p.setClipPath(outline)
        for name, color in self.body_tones.items():
            points = self.blended(name, name + '-sleep', sleep)
            p.setBrush(color); p.drawPath(curve([body.map(x, y) for x, y in points]))
        p.restore()

    def _tail(self, p, pose, body):
        sleep = body.sleep
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.tail_fur)
        if sleep > .999:
            p.drawPath(self.sleep_tail)
            return
        points = self.blended('tail', 'tail-sleep', sleep)
        warped = []
        for i, (x, y) in enumerate(points):
            weight = math.sin(math.pi * i / (len(points) - 1)) ** 2
            amplitude = (pose.tail * 2.4 + pose.pet * .8 + abs(pose.balance_velocity) * .012) * (1 - sleep)
            x += math.sin(pose.tail_phase - weight * 2) * amplitude * weight
            y += math.sin(pose.tail_phase - weight * 2 + .6) * amplitude * weight * .55
            warped.append(body.map(x, y))
        p.drawPath(curve(warped))

    @staticmethod
    def shoulder(side, pose):
        return BodyGeometry(pose).shoulder(side)

    def _arm(self, p, pose, side, body):
        sx, sy = body.shoulder(side)
        wx, wy = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
        dx, dy = wx - sx, wy - sy
        distance = math.hypot(dx, dy)
        bend = max(4, 12 - distance * .09)
        cx = (sx + wx) * .5 + side * bend
        cy = (sy + wy) * .5 + min(9, abs(dx) * .12)
        reach = body.mouse_reach if side < 0 else 0
        # These cubic handles reproduce the usual quadratic exactly at rest.
        ax, ay = mix(sx, cx, 2 / 3), mix(sy, cy, 2 / 3)
        bx, by = mix(wx, cx, 2 / 3), mix(wy, cy, 2 / 3)
        if reach:
            # The elbow folds below the chest. At full extension the wrist
            # still approaches the top of the shell almost parallel to the floor.
            fold = 1 - smoothstep((distance - 30) / 40)
            ax = mix(ax, sx + dx * .12 + 3 + 7 * fold, reach)
            ay = mix(ay, sy + dy * .62 + 7, reach)
            bx = mix(bx, wx - dx * .38, reach)
            by = mix(by, wy - dy * .04 + 3 * fold, reach)
        left, right = [], []
        for i in range(15):
            t = i / 14; u = 1 - t
            uu, ut, tt = u * u, u * t, t * t
            x = uu * u * sx + 3 * ut * (u * ax + t * bx) + tt * t * wx
            y = uu * u * sy + 3 * ut * (u * ay + t * by) + tt * t * wy
            tx = uu * (ax - sx) + 2 * ut * (bx - ax) + tt * (wx - bx)
            ty = uu * (ay - sy) + 2 * ut * (by - ay) + tt * (wy - by)
            length = max(.001, math.hypot(tx, ty))
            tx, ty = tx / length, ty / length
            radius = 3.0 + 4.5 * u ** .8 + math.sin(math.pi * t) ** 2 * (.6 + reach * u)
            left.append((x - ty * radius, y + tx * radius))
            right.append((x + ty * radius, y - tx * radius))
        cap = [(wx + (tx * math.sin(a) - ty * math.cos(a)) * 3,
                wy + (ty * math.sin(a) + tx * math.cos(a)) * 3)
               for a in (math.pi / 4, math.pi / 2, math.pi * .75)]
        points = left + cap + list(reversed(right)) + [(sx - dx / max(1, distance) * 5, sy - dy / max(1, distance) * 5)]
        path = QPainterPath()
        path.moveTo((points[-1][0] + points[0][0]) * .5, (points[-1][1] + points[0][1]) * .5)
        for i, (x, y) in enumerate(points):
            following = points[(i + 1) % len(points)]
            path.quadTo(x, y, (x + following[0]) * .5, (y + following[1]) * .5)
        path.closeSubpath(); p.setPen(Qt.PenStyle.NoPen)
        tone = round(pose.groom * 20) if side < 0 else 0
        p.setBrush(self.foreleg.lighter(100 + tone) if tone else self.foreleg)
        p.drawPath(path)

    def head_hit(self, point):
        if not any(path.contains(point) for path in self.head_hit_paths):
            return None
        return max(-1, min(1, (point.x() - self.head_center) / 30))

    def _head(self, p, pose, body):
        face = FaceGeometry(pose, body)
        self.head_position = QPointF(face.cx, face.cy)
        s = body.sleep
        if s > .999 and self.sleep_face is not None:
            image, paths = self.sleep_face
            transform = QTransform.fromTranslate(face.cx - 110, face.cy - 131)
            p.drawPixmap(QPointF(face.cx - 110, face.cy - 131), image)
            self.head_hit_paths = [transform.map(path) for path in paths]
            self.head_center = face.cx
            return
        cx, cy = mix(101, 110, s), mix(77, 131, s)
        self.head_center = face.cx
        self.head_hit_paths = []
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.head_fur)
        for side, name, anchor in ((-1, 'ear-left', (82, 57)), (1, 'ear-right', (125, 57))):
            angle = math.radians((pose.ear_left if side < 0 else pose.ear_right)
                                 + side * s * 27 + side * pose.pet * 13)
            cos, sin = math.cos(angle), math.sin(angle)
            ax, ay = mix(anchor[0], 91 if side < 0 else 128, s), mix(anchor[1], 120, s)
            points = []
            for x, y in self.shapes[name]:
                x, y = (x - anchor[0]) * (1 - s * .25), (y - anchor[1]) * (1 - s * .25)
                points.append(face.point(ax + x * cos - y * sin - cx,
                                         ay + x * sin + y * cos - cy, -3))
            path = curve(points); p.setBrush(self.head_fur); p.drawPath(path)
            self.head_hit_paths.append(path)
            inner = []
            for x, y in self.shapes['ear-inner-left' if side < 0 else 'ear-inner-right']:
                x, y = (x - anchor[0]) * (1 - s * .25), (y - anchor[1]) * (1 - s * .25)
                inner.append(face.point(ax + x * cos - y * sin - cx,
                                        ay + x * sin + y * cos - cy, -3))
            p.save(); p.setClipPath(path); p.setBrush(self.ear_inner)
            p.drawPath(curve(inner)); p.restore()
        p.setBrush(self.head_fur)
        points = self.blended('head-shape', 'head-sleep', s)
        shape = curve([face.outline(x - cx, y - cy) for x, y in points])
        p.drawPath(shape); self.head_hit_paths.append(shape)
        blink = max(pose.blink, smoothstep((s - .35) / .65), pose.yawn * .92,
                    pose.groom * (.65 if pose.action == 'wash' else .2))
        p.save(); p.setClipPath(shape)
        face_points = [(mix(x - 101, (x - 101) * .76, s),
                        mix(y - 77, (y - 77) * .60, s)) for x, y in self.shapes['face-volume']]
        p.setBrush(self.face_tone)
        p.drawPath(curve([face.point(x, y) for x, y in face_points]))
        for side in (-1, 1):
            ex, ey = side * mix(13.7, 10, s), -1.15
            width = mix(8.45, 7.8, s)
            top, bottom = mix(-9.6, 1.1, blink), mix(8.1, 1.1, blink)
            aperture = curve([face.point(ex - width, ey), face.point(ex - width * .65, ey + top),
                              face.point(ex + width * .65, ey + top), face.point(ex + width, ey),
                              face.point(ex + width * .65, ey + bottom), face.point(ex - width * .65, ey + bottom),
                              face.point(ex - width, ey)])
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.iris); p.drawPath(aperture)
            p.save(); p.setClipPath(aperture, Qt.ClipOperation.IntersectClip)
            px = ex + (pose.gaze_x - pose.head_x * .35) * 2.5 * (1 - s)
            py = ey + pose.gaze_y * 2.0 * (1 - s)
            pupil = curve([face.point(px, py - 7), face.point(px - 2.3, py - 3),
                           face.point(px - 2.3, py + 3), face.point(px, py + 7),
                           face.point(px + 2.3, py + 3), face.point(px + 2.3, py - 3), face.point(px, py - 7)])
            p.setBrush(self.pupil); p.drawPath(pupil); p.restore()
            if blink > .85:
                lid = QPainterPath(); lid.moveTo(*face.point(ex - width, ey))
                lid.cubicTo(*face.point(ex - width * .65, ey + 1.1),
                            *face.point(ex + width * .65, ey + 1.1), *face.point(ex + width, ey))
                p.setPen(QPen(self.lid_color, .65)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(lid)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.pupil)
        p.drawPath(polygon([face.point(-1.2, 10), face.point(1.2, 10), face.point(0, 11.3)]))
        if pose.yawn > .03 or pose.tongue > .03:
            mouth = []
            for i in range(16):
                angle = i * math.tau / 16
                mouth.append(face.point(math.cos(angle) * (2.5 + pose.yawn * .8),
                                        15 + math.sin(angle) * (.5 + pose.yawn * 6)))
            p.drawPath(polygon(mouth))
            if pose.tongue > .03:
                tongue = polygon([face.point(-1, 16), face.point(1.5, 16),
                                  face.point(1.0, 18 + pose.tongue), face.point(-.5, 18 + pose.tongue)])
                p.setBrush(QColor('#b87e86')); p.drawPath(tongue)
        p.restore()
        for side in (-1, 1):
            flex = pose.pet * math.sin(pose.time * 7) * .6 + pose.groom * .5 + pose.balance_velocity * .006
            p.setPen(QPen(self.whisker, .65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for level in (-1, 1):
                whisker = QPainterPath(); whisker.moveTo(*face.point(side * mix(22, 16, s), 10 + level * 1.4))
                whisker.cubicTo(*face.point(side * mix(27, 20, s), 10 + level * 1.8, 12),
                                *face.point(side * mix(33, 26, s), 10 + level * 3 + flex, 8),
                                *face.point(side * mix(37, 29, s), 10 + level * 3.2 + flex, 6))
                p.drawPath(whisker)

    def _zzz(self, p, pose):
        if pose.zzz < .01:
            return
        for index in range(3):
            phase = (pose.time * .38 + index / 3) % 1
            p.save(); p.translate(130 + phase * 4, 116 - phase * 13)
            p.scale(.65 + phase * .25, .65 + phase * .25)
            p.setOpacity(pose.zzz * math.sin(math.pi * phase))
            p.setPen(QPen(QColor('#eef0e8'), 1.1)); p.setBrush(QColor('#5b686f'))
            p.drawPath(self.z_path); p.restore()

    def draw(self, p, pose):
        p.save(); p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        body = BodyGeometry(pose)
        self._tail(p, pose, body)
        p.save(); p.translate(104, 153); p.scale(mix(1, .82, body.sleep), mix(1, .65, body.sleep))
        p.translate(-104, -153); self.layer(p, 'hind-feet'); p.restore()
        self._body(p, pose, body)
        p.drawPixmap(0, 0, self.keyboard)
        pressures = dict(pose.contacts)
        for identifier in pose.pressed | pressures.keys():
            key = self.keys[identifier]
            self.draw_key(p, key, identifier in pose.pressed, self.cache_scale, pressures.get(identifier, 0))
        p.save(); p.translate(pose.mouse_dx, pose.mouse_dy + pose.click * .4); self.layer(p, 'mouse')
        if pose.scroll > .01:
            p.translate(self.wheel_center); p.rotate(-14)
            p.setPen(QPen(QColor('#c2cecc'), .7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            step = math.sin(pose.time * 28) * pose.scroll_direction * pose.scroll
            p.drawLine(QPointF(step, -.6), QPointF(step, .6))
        p.restore()
        washing_face = pose.action == 'wash' and pose.groom > .01
        if pose.sleep < .995:
            if not washing_face:
                self._arm(p, pose, -1, body)
            self._arm(p, pose, 1, body)
        self._head(p, pose, body)
        if washing_face:
            self._arm(p, pose, -1, body)
        for side in (-1, 1):
            x, y = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
            reach = body.mouse_reach if side < 0 else 0
            p.save(); p.translate(x, y); p.rotate(-14 * reach)
            pressure = pose.left_pressure if side < 0 else pose.right_pressure
            p.scale(1 + pressure * .035, 1 - pressure * .10)
            p.translate(-reach, mix(-3.5, 0, reach))
            self.layer(p, 'paw'); p.restore()
        self._zzz(p, pose); p.restore()
