"""Minimal feline silhouettes and organic limbs, drawn on an invisible floor."""

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap
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
        for name in ('body', 'body-sleep', 'head-shape', 'head-sleep', 'tail', 'tail-sleep'):
            data = elements[name].get('d', '')
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
        for name in ('ear-left', 'ear-right', 'mouse', 'paw', 'hind-feet'):
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
        if scale >= .99 and label:
            font = QFont('sans-serif'); font.setPixelSize(4)
            p.setFont(font); p.setPen(QColor('#39454b'))
            bounds = self.key_paths[key.identifier].boundingRect()
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
        points = self.blended('body', 'body-sleep', sleep)
        warped = []
        for x, y in points:
            weight = max(0, min(1, (153 - y) / 65))
            warped.append((x + pose.balance_x * weight,
                           y + (pose.balance_y - pose.breath * .65 + pose.relax * 2) * weight))
        p.setBrush(self.fur); p.setPen(Qt.PenStyle.NoPen)
        if sleep > .999:
            p.save(); p.translate(92, 153); p.scale(1, 1 - pose.breath * .003)
            p.translate(-92, -153); p.drawPath(self.sleep_body); p.restore()
        else:
            body = curve(warped)
            if sleep < .99:
                gap = QPainterPath()
                middle = 101 + pose.balance_x * .2
                width = 5 * (1 - sleep)
                gap.moveTo(middle - width, 155)
                gap.cubicTo(middle - width * .2, 146, middle - width, 131, middle, 126)
                gap.cubicTo(middle + width, 131, middle + width * .2, 146, middle + width, 155)
                gap.closeSubpath()
                body = body.subtracted(gap)
            p.drawPath(body)

    def _tail(self, p, pose):
        sleep = smoothstep(pose.sleep)
        points = self.blended('tail', 'tail-sleep', sleep)
        warped = []
        count = len(points)
        for i, (x, y) in enumerate(points):
            weight = math.sin(math.pi * i / (count - 1)) ** 2
            amplitude = (pose.tail * 1.6 + abs(pose.balance_velocity) * .012) * (1 - sleep)
            warped.append((x + math.sin(pose.tail_phase - weight * 2) * amplitude * weight,
                           y + math.sin(pose.tail_phase - weight * 2 + .6) * amplitude * weight * .55))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.fur)
        p.drawPath(self.sleep_tail if sleep > .999 else curve(warped))

    @staticmethod
    def shoulder(side, pose):
        sleep = smoothstep(pose.sleep)
        return (mix(89 if side < 0 else 114, 90 if side < 0 else 119, sleep) + pose.balance_x * .8,
                mix(118, 139, sleep) + pose.balance_y * .8 - pose.breath * .4)

    @staticmethod
    def elbow(shoulder, wrist, side, reach=0):
        sx, sy = shoulder; dx, dy = wrist[0] - sx, wrist[1] - sy
        distance = max(.001, math.hypot(dx, dy))
        upper, lower = 25.0, 28.0
        stretch = max(1, distance / ((upper + lower) * .98))
        upper, lower = upper * stretch, lower * stretch
        along = (upper * upper - lower * lower + distance * distance) / (2 * distance)
        height = min(7.5, math.sqrt(max(0, upper * upper - along * along)))
        nx, ny = unit(side * max(.4, abs(dy / distance)), -.3 * dx / distance)
        return sx + dx / distance * along + nx * height, sy + dy / distance * along + ny * height

    def _arm(self, p, pose, side):
        sx, sy = self.shoulder(side, pose)
        wx, wy = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
        ex, ey = self.elbow((sx, sy), (wx, wy), side)
        ax, ay = unit(ex - sx, ey - sy); bx, by = unit(wx - ex, wy - ey); tx, ty = unit(wx - sx, wy - sy)
        normals = ((-ay, ax), (-ty, tx), (-by, bx)); widths = (5.2, 4, 2.9)
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
        path.closeSubpath(); p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.fur); p.drawPath(path)

    def _head(self, p, pose):
        s = smoothstep(pose.sleep)
        yaw, pitch = pose.head_x * (1 - s), pose.head_y * (1 - s)
        dx = pose.balance_x * .8; dy = pose.balance_y * .65 - pose.breath * .3 + pose.groom * 3
        points = self.blended('head-shape', 'head-sleep', s)
        points = [(mix(101, 109, s) + (x - mix(101, 109, s)) * (1 - abs(yaw) * .08) + yaw * 1.5 + dx,
                   y + pitch * 1.2 + dy) for x, y in points]
        for side, name, anchor in ((-1, 'ear-left', (82, 57)), (1, 'ear-right', (125, 57))):
            x = mix(anchor[0], 91 if side < 0 else 128, s)
            y = mix(anchor[1], 120, s)
            p.save(); p.translate(x + dx - yaw * 2, y + dy + pitch)
            p.rotate((pose.ear_left if side < 0 else pose.ear_right) + side * s * 27 - yaw * 3)
            p.scale(1 - max(0, side * yaw) * .22, 1 - s * .25)
            p.translate(-anchor[0], -anchor[1]); self.layer(p, name); p.restore()
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.fur); p.drawPath(curve(points))
        blink = max(pose.blink, smoothstep((s - .35) / .65), pose.yawn * .92,
                    pose.groom * (.65 if pose.action == 'wash' else .2))
        for side in (-1, 1):
            cx = mix(101 + side * 13.5, 110 + side * 10, s) + yaw * 5.5 + dx
            cy = mix(76, 131, s) + pitch * 3 + dy
            w = mix(8.5, 7.8, s) * (1 - max(0, side * yaw) * .25)
            top = mix(-9, 1.1, blink); bottom = mix(8, 1.1, blink)
            aperture = QPainterPath(); aperture.moveTo(cx - w, cy)
            aperture.cubicTo(cx - w * .65, cy + top, cx + w * .65, cy + top, cx + w, cy)
            aperture.cubicTo(cx + w * .65, cy + bottom, cx - w * .65, cy + bottom, cx - w, cy)
            aperture.closeSubpath(); p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.iris); p.drawPath(aperture)
            p.save(); p.setClipPath(aperture)
            px, py = cx + (pose.gaze_x - yaw * .25) * 1.9 * (1 - s), cy + pose.gaze_y * 1.25 * (1 - s)
            pupil = QPainterPath(); pupil.moveTo(px, py - 7)
            pupil.cubicTo(px - 2.7, py - 3, px - 2.7, py + 3, px, py + 7)
            pupil.cubicTo(px + 2.7, py + 3, px + 2.7, py - 3, px, py - 7)
            p.setBrush(self.pupil); p.drawPath(pupil); p.restore()
            if blink > .85:
                lid = QPainterPath(); lid.moveTo(cx - w, cy)
                lid.cubicTo(cx - w * .65, cy + 1.1, cx + w * .65, cy + 1.1, cx + w, cy)
                p.setPen(QPen(QColor('#788388'), .65)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(lid)
        if pose.yawn > .03 or pose.tongue > .03:
            mx, my = 102 + yaw * 6 + dx, 92 + pitch * 3 + dy
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.pupil)
            p.drawEllipse(QPointF(mx, my), 2.5 + pose.yawn * .8, .5 + pose.yawn * 6)
            if pose.tongue > .03:
                p.setBrush(QColor('#b87e86'))
                p.drawEllipse(QPointF(mx + .5, my + 2 + pose.tongue), 1.5, 1 + pose.tongue)

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
        if pose.sleep < .995:
            self._arm(p, pose, -1); self._arm(p, pose, 1)
        self._head(p, pose)
        for side in (-1, 1):
            x, y = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
            p.save(); p.translate(x, y); p.rotate(-pose.mouse * 12 if side > 0 else 0)
            self.layer(p, 'paw'); p.restore()
        self._zzz(p, pose); p.restore()
