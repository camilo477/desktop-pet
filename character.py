"""Minimal feline silhouettes and organic limbs, drawn on an invisible floor."""

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtSvg import QSvgRenderer

from animations import Pose, mix, smoothstep
from keyboard_layout import BOARD, KEYS, LABELS


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


def unit(x, y):
    length = max(.001, math.hypot(x, y))
    return x / length, y / length


class CatArt:
    def __init__(self):
        path = Path(__file__).resolve().parent / 'assets' / 'cat' / 'miga.svg'
        self.renderer = QSvgRenderer(str(path))
        if not self.renderer.isValid():
            raise RuntimeError('Could not load the character artwork.')
        elements = {node.get('id'): node for node in ET.parse(path).iter() if node.get('id')}
        self.shapes = {}
        for name in ('body', 'body-sleep', 'head-shape', 'head-sleep', 'tail', 'tail-sleep', 'ear-left', 'ear-right'):
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
        for a, b in (('body', 'body-sleep'), ('head-shape', 'head-sleep'), ('tail', 'tail-sleep')):
            if len(self.shapes[a]) != len(self.shapes[b]):
                raise RuntimeError('Resting silhouettes must retain their curve topology.')
        self.sleep_body = curve(self.shapes['body-sleep'])
        self.sleep_head = curve(self.shapes['head-sleep'])
        self.sleep_tail = curve(self.shapes['tail-sleep'])
        self.ears = {name: curve(self.shapes[name]) for name in ('ear-left', 'ear-right')}
        self.head_hit_paths = []
        self.head_inverse = QTransform()
        self.head_center = 101.0
        self.layers = {}
        self.cache_scale = 0.0
        self.layout = 'us'
        self.keyboard = QPixmap()
        self.key_paths = {key.identifier: polygon(key.polygon) for key in KEYS}
        self.fur = QColor('#30363b')
        self.iris = QColor('#d2cc91')
        self.pupil = QColor('#151a1e')
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

    def draw_key(self, p, key, down, scale):
        p.save(); p.translate(0, .65 if down else 0)
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

    def _body(self, p, pose):
        sleep = smoothstep(pose.sleep)
        p.setBrush(self.fur); p.setPen(Qt.PenStyle.NoPen)
        if sleep > .999:
            p.save(); p.translate(92, 153); p.scale(1, 1 - pose.breath * .003)
            p.translate(-92, -153); p.drawPath(self.sleep_body); p.restore()
            return
        points = self.blended('body', 'body-sleep', sleep)
        warped = []
        for x, y in points:
            weight = max(0, min(1, (153 - y) / 65))
            warped.append((x + pose.balance_x * weight,
                           y + (pose.balance_y - pose.breath * .65 + pose.relax * 2) * weight))
        body = curve(warped)
        if sleep < .99:
            gap = QPainterPath()
            middle = 103 + pose.balance_x * .2
            width = 6 * (1 - sleep)
            gap.moveTo(middle - width, 155)
            gap.cubicTo(middle - width * .3, 145, middle - width * .6, 129, middle, 123)
            gap.cubicTo(middle + width * .7, 130, middle + width * .5, 146, middle + width, 155)
            gap.closeSubpath()
            body = body.subtracted(gap)
        p.drawPath(body)

    def _tail(self, p, pose):
        sleep = smoothstep(pose.sleep)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.fur)
        if sleep > .999:
            p.drawPath(self.sleep_tail)
            return
        points = self.blended('tail', 'tail-sleep', sleep)
        warped = []
        count = len(points)
        for i, (x, y) in enumerate(points):
            weight = math.sin(math.pi * i / (count - 1)) ** 2
            amplitude = (pose.tail * 2.4 + pose.pet * .8 + abs(pose.balance_velocity) * .012) * (1 - sleep)
            warped.append((x + math.sin(pose.tail_phase - weight * 2) * amplitude * weight,
                           y + math.sin(pose.tail_phase - weight * 2 + .6) * amplitude * weight * .55))
        p.drawPath(curve(warped))

    @staticmethod
    def shoulder(side, pose):
        sleep = smoothstep(pose.sleep)
        mouse = pose.mouse if side < 0 else 0
        return (mix(91 if side < 0 else 115, 90 if side < 0 else 119, sleep) + pose.balance_x * .8 - mouse * 3,
                mix(120, 139, sleep) + pose.balance_y * .8 - pose.breath * .4 + mouse * 4)

    @staticmethod
    def elbow(shoulder, wrist, side):
        sx, sy = shoulder; dx, dy = wrist[0] - sx, wrist[1] - sy
        distance = max(.001, math.hypot(dx, dy))
        upper, lower = 27.0, 30.0
        stretch = max(1, distance / ((upper + lower) * .98))
        upper, lower = upper * stretch, lower * stretch
        along = (upper * upper - lower * lower + distance * distance) / (2 * distance)
        height = min(9, math.sqrt(max(0, upper * upper - along * along)))
        nx, ny = unit(side * max(.4, abs(dy / distance)), -.3 * dx / distance)
        return sx + dx / distance * along + nx * height, sy + dy / distance * along + ny * height

    def _arm(self, p, pose, side):
        sx, sy = self.shoulder(side, pose)
        wx, wy = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
        ex, ey = self.elbow((sx, sy), (wx, wy), side)
        ax, ay = unit(ex - sx, ey - sy); bx, by = unit(wx - ex, wy - ey); tx, ty = unit(wx - sx, wy - sy)
        normals = ((-ay, ax), (-ty, tx), (-by, bx)); widths = (7.0, 5.0, 3.0)
        path = QPainterPath()
        for sign in (1, -1):
            snx, sny = (v * sign * widths[0] for v in normals[0])
            enx, eny = (v * sign * widths[1] for v in normals[1])
            wnx, wny = (v * sign * widths[2] for v in normals[2])
            if sign == 1:
                path.moveTo(sx + snx, sy + sny)
                path.cubicTo(sx + ax * 9 + snx, sy + ay * 9 + sny,
                             ex - tx * 4 + enx, ey - ty * 4 + eny, ex + enx, ey + eny)
                path.cubicTo(ex + tx * 4 + enx, ey + ty * 4 + eny,
                             wx - bx * 6 + wnx, wy - by * 6 + wny, wx + wnx, wy + wny)
            else:
                path.lineTo(wx + wnx, wy + wny)
                path.cubicTo(wx - bx * 6 + wnx, wy - by * 6 + wny,
                             ex + tx * 4 + enx, ey + ty * 4 + eny, ex + enx, ey + eny)
                path.cubicTo(ex - tx * 4 + enx, ey - ty * 4 + eny,
                             sx + ax * 9 + snx, sy + ay * 9 + sny, sx + snx, sy + sny)
        nx, ny = normals[0]
        path.cubicTo(sx - ax * 5 - nx * widths[0], sy - ay * 5 - ny * widths[0],
                     sx - ax * 5 + nx * widths[0], sy - ay * 5 + ny * widths[0],
                     sx + nx * widths[0], sy + ny * widths[0])
        path.closeSubpath(); p.setPen(Qt.PenStyle.NoPen)
        # A slight flat tone keeps a raised leg readable against its chest.
        tone = round(pose.groom * 6) if side < 0 else 0
        p.setBrush(QColor(48 + tone, 54 + tone, 59 + tone) if tone else self.fur)
        p.drawPath(path)

    def head_hit(self, point):
        if not any(path.contains(point) for path in self.head_hit_paths):
            return None
        local = self.head_inverse.map(point)
        return max(-1, min(1, (local.x() - self.head_center) / 30))

    def _head(self, p, pose):
        s = smoothstep(pose.sleep)
        yaw, pitch = pose.head_x * (1 - s), pose.head_y * (1 - s)
        cx, cy = mix(101, 110, s), mix(77, 131, s)
        dx = pose.balance_x * .8
        dy = (pose.balance_y * .45 - pose.breath * .3 + pose.groom * 2.5
              + pitch * (6 if pitch > 0 else 4) + pose.pet * 3)
        transform = QTransform()
        transform.translate(cx + dx, cy + dy - 4 * (1 - s))
        transform.rotate(pose.head_tilt * (1 - s))
        transform.scale(mix(.90, 1, s), mix(.90, 1, s))
        transform.translate(-cx, -cy)
        self.head_inverse = transform.inverted()[0]
        self.head_center = cx
        p.save(); p.setTransform(transform, True)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.fur)
        self.head_hit_paths = []
        for side, name, anchor in ((-1, 'ear-left', (82, 57)), (1, 'ear-right', (125, 57))):
            ear = QTransform()
            ear.translate(mix(anchor[0], 91 if side < 0 else 128, s) - yaw * 2,
                          mix(anchor[1], 120, s) + pitch * 2)
            ear.rotate((pose.ear_left if side < 0 else pose.ear_right) + side * s * 27
                       - yaw * 5 + side * pose.pet * 13)
            ear.scale(1 - max(0, side * yaw) * .25, 1 - s * .25 - max(0, pitch) * .05)
            ear.translate(-anchor[0], -anchor[1])
            path = ear.map(self.ears[name]); p.drawPath(path)
            self.head_hit_paths.append(transform.map(path))
        if s > .999:
            shape = self.sleep_head
        else:
            points = self.blended('head-shape', 'head-sleep', s)
            points = [(cx + (x - cx) * (1 - abs(yaw) * .11) + yaw * 2.8,
                       cy + (y - cy) * (1 - max(0, pitch) * .10 - pose.pet * .025)) for x, y in points]
            shape = curve(points)
        p.drawPath(shape); self.head_hit_paths.append(transform.map(shape))
        blink = max(pose.blink, smoothstep((s - .35) / .65), pose.yawn * .92,
                    pose.groom * (.65 if pose.action == 'wash' else .2))
        for side in (-1, 1):
            ex = mix(101 + side * 13.5, 110 + side * 10, s) + yaw * 7
            ey = mix(76, 131, s) + pitch * 3.4
            width = mix(8.5, 7.8, s) * (1 - max(0, side * yaw) * .28)
            top = mix(-9, 1.1, blink) * (1 - abs(pitch) * .12)
            bottom = mix(8, 1.1, blink)
            aperture = QPainterPath(); aperture.moveTo(ex - width, ey)
            aperture.cubicTo(ex - width * .65, ey + top, ex + width * .65, ey + top, ex + width, ey)
            aperture.cubicTo(ex + width * .65, ey + bottom, ex - width * .65, ey + bottom, ex - width, ey)
            aperture.closeSubpath(); p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.iris); p.drawPath(aperture)
            p.save(); p.setClipPath(aperture)
            px = ex + (pose.gaze_x - yaw * .25) * 2.3 * (1 - s)
            py = ey + pose.gaze_y * 2.2 * (1 - s)
            pupil = QPainterPath(); pupil.moveTo(px, py - 7)
            pupil.cubicTo(px - 2.7, py - 3, px - 2.7, py + 3, px, py + 7)
            pupil.cubicTo(px + 2.7, py + 3, px + 2.7, py - 3, px, py - 7)
            p.setBrush(self.pupil); p.drawPath(pupil); p.restore()
            if blink > .85:
                lid = QPainterPath(); lid.moveTo(ex - width, ey)
                lid.cubicTo(ex - width * .65, ey + 1.1, ex + width * .65, ey + 1.1, ex + width, ey)
                p.setPen(QPen(QColor('#788388'), .65)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(lid)
        for side in (-1, 1):
            root_x = cx + side * mix(22, 16, s) + yaw * 7
            root_y = mix(87, 137, s) + pitch * 3
            length = mix(15, 12, s) * (1 - max(0, side * yaw) * .3)
            flex = pose.pet * math.sin(pose.time * 7) * .6 + pose.groom * .5 + pose.balance_velocity * .008
            p.setPen(QPen(QColor('#7e898c'), .65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for level in (-1, 1):
                whisker = QPainterPath(); whisker.moveTo(root_x, root_y + level * 1.4)
                whisker.cubicTo(root_x + side * length * .4, root_y + level * 1.8,
                                root_x + side * length * .8, root_y + level * 3 + flex,
                                root_x + side * length, root_y + level * 3.2 + flex)
                p.drawPath(whisker)
        if pose.yawn > .03 or pose.tongue > .03:
            mx, my = 102 + yaw * 7, 92 + pitch * 3
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.pupil)
            p.drawEllipse(QPointF(mx, my), 2.5 + pose.yawn * .8, .5 + pose.yawn * 6)
            if pose.tongue > .03:
                p.setBrush(QColor('#b87e86'))
                p.drawEllipse(QPointF(mx + .5, my + 2 + pose.tongue), 1.5, 1 + pose.tongue)
        p.restore()

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
        self._tail(p, pose); self.layer(p, 'hind-feet'); self._body(p, pose)
        p.drawPixmap(0, 0, self.keyboard)
        for key in KEYS:
            if key.identifier in pose.pressed:
                self.draw_key(p, key, True, self.cache_scale)
        p.save(); p.translate(pose.mouse_dx, pose.mouse_dy + pose.click * .4); self.layer(p, 'mouse'); p.restore()
        if pose.scroll > .01:
            p.setPen(QPen(QColor('#586970'), 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            x, y = 21 + pose.mouse_dx, 162 + pose.mouse_dy
            step = math.sin(pose.time * 28) * pose.scroll_direction * pose.scroll
            p.drawLine(QPointF(x - 1, y + 3 + step), QPointF(x, y + 5 + step))
        washing_face = pose.action == 'wash' and pose.groom > .01
        if pose.sleep < .995:
            if not washing_face:
                self._arm(p, pose, -1)
            self._arm(p, pose, 1)
        self._head(p, pose)
        if washing_face:
            self._arm(p, pose, -1)
        for side in (-1, 1):
            x, y = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
            p.save(); p.translate(x, y); p.rotate(pose.mouse * 12 if side < 0 else 0)
            self.layer(p, 'paw'); p.restore()
        self._zzz(p, pose); p.restore()
