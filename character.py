"""Minimal feline silhouettes and organic limbs, drawn on an invisible floor."""

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap, QRegion, QTransform
from PySide6.QtSvg import QSvgRenderer

from appearance import Appearance, COATS, EYES, NOSES
from coat_patterns import Markings, cubic_path as curve
from animations import Pose, mix, smoothstep
from anatomy import BodyGeometry, FaceGeometry, face_depth
from keyboard_layout import Keyboard, KEYBOARD_SCALE, KEY_TRAVEL
from personality import DROWSY

BODY_TONES = ('neck-shade', 'chest-volume', 'hip-left', 'hip-right')

# Sample the same cubic limb and taper at the same 15 material coordinates.
def arm_samples():
    for i in range(15):
        t = i / 14
        u = 1 - t
        radius = 3.0 + 4.5 * u ** .8 + math.sin(math.pi * t) ** 2 * .6
        yield t, u, u * u, u * t, t * t, radius


ARM_SAMPLES = tuple(arm_samples())


def polygon(points):
    path = QPainterPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.closeSubpath()
    return path


def rounded_polygon(points, radius):
    path = QPainterPath()
    for i, corner in enumerate(points):
        neighbors = (points[i - 1], points[(i + 1) % len(points)])
        edges = [QPointF(*(c + (n - c) * radius / math.dist(corner, neighbor)
                            for c, n in zip(corner, neighbor))) for neighbor in neighbors]
        if i == 0:
            path.moveTo(edges[0])
        else:
            path.lineTo(edges[0])
        path.quadTo(QPointF(*corner), edges[1])
    path.closeSubpath()
    return path


def cubic_points(node):
    data = node.get('d', '')
    values = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', data)]
    commands = re.findall('[A-Za-z]', data)
    count = (len(values) - 2) // 6
    if commands != ['M'] + ['C'] * count + ['Z'] or len(values) != 2 + count * 6:
        raise RuntimeError('Silhouettes must use absolute M/C/Z curves.')
    return list(zip(values[::2], values[1::2]))


class CatArt:
    def __init__(self, keyboard=None, appearance=Appearance()):
        path = Path(__file__).resolve().parent / 'assets' / 'cat' / 'miga.svg'
        self.renderer = QSvgRenderer(str(path))
        if not self.renderer.isValid():
            raise RuntimeError('Could not load the character artwork.')
        self.wheel_center = self.renderer.boundsOnElement('mouse-wheel').center()
        elements = {node.get('id'): node for node in ET.parse(path).iter() if node.get('id')}
        self.shapes = {}
        names = ('body', 'head-shape', 'tail', 'tail-curled', 'ear-left', 'ear-right',
                 'ear-inner-left', 'ear-inner-right', 'face-volume') + BODY_TONES
        for name in names:
            node = elements[name]
            if node.tag.endswith('g'):
                node = next(iter(node))
            self.shapes[name] = cubic_points(node)
        self.body_controls = {name: BodyGeometry.bind(self.shapes[name])
                              for name in ('body', *BODY_TONES)}
        self.face_volume = [(x - 101, y - 77, face_depth(x - 101, y - 77))
                            for x, y in self.shapes['face-volume']]
        tail_count = len(self.shapes['tail'])
        self.tail_weights = tuple(math.sin(math.pi * i / (tail_count - 1)) ** 2
                                  for i in range(tail_count))
        self.hits = []
        self.head_hit_paths = []
        self.paw_path = curve(cubic_points(elements['paw'][0]))
        self.feet_path = QPainterPath()
        for node in elements['hind-feet']:
            self.feet_path.addPath(curve(cubic_points(node)))
        self.mouse_path = curve(cubic_points(elements['mouse'][0])).united(
            curve(cubic_points(elements['mouse'][1])))
        self.head_position = QPointF(103, 76.5)
        self.layers = {}
        self.cache_scale = 0.0
        self.pixel_aligned = True
        self.keyboard = QPixmap()
        self.sleep_face = None
        self.set_keyboard(keyboard or Keyboard())
        self.original = {key: QColor(elements[key].get('fill')) for key in
                         ('body', 'head-shape', 'tail', 'front-legs', 'eyes', 'pupils',
                          'ear-inner-left', 'face-volume', *BODY_TONES)}
        self.original['whiskers'] = QColor(elements['whiskers'].get('stroke'))
        self.original['closed-eyes'] = QColor(elements['closed-eyes'].get('stroke'))
        self.appearance = None
        self.set_appearance(appearance)
        font = QFont('sans-serif'); font.setPixelSize(9); font.setWeight(QFont.Weight.DemiBold)
        self.z_path = QPainterPath(); self.z_path.addText(QPointF(0, 0), font, 'Z')

    def set_appearance(self, appearance):
        if appearance == self.appearance:
            return
        coat = COATS[appearance.coat]
        if self.appearance is None or appearance.coat != self.appearance.coat:
            def color(swatch, element):
                return QColor(swatch) if swatch else self.original[element]

            self.fur = color(coat.base, 'body')
            self.head_fur = color(coat.base, 'head-shape')
            self.tail_fur = color(coat.tail or coat.light, 'tail')
            self.foreleg = color(coat.leg, 'front-legs')
            self.ears = tuple(map(QColor, coat.ears)) or (self.head_fur, self.head_fur)
            self.ear_inner = color(coat.inner, 'ear-inner-left')
            self.face_tone = color(coat.light, 'face-volume')
            self.whisker = color(coat.whisker, 'whiskers')
            self.lid_color = color(coat.lid, 'closed-eyes')
            self.pupil = self.original['pupils']
            self.body_tones = {k: color(c, k) for k, c in zip(BODY_TONES,
                               (coat.shade, coat.light, coat.light, coat.shade))}
            self.eye_edge = QPen(self.foreleg.darker(165), .90) if self.fur.lightness() > 105 else None
            self.fur_edge = QPen(self.fur.darker(114), .9) if self.fur.lightness() > 200 else None
            self.markings = Markings(coat) if coat.pattern else None
            self.coat_layers_dirty = True
        eye = coat.eyes if appearance.eyes == 'auto' else appearance.eyes
        eye_pair = ('blue', 'green') if eye == 'odd' else (eye, eye)
        self.irises = tuple(self.original['eyes'] if key == 'gold' else QColor(EYES[key][1])
                            for key in eye_pair)
        self.iris = self.irises[0]
        nose = NOSES[appearance.nose][1] or coat.nose
        self.nose = QColor(nose) if nose else self.pupil
        self.nose_edge = None
        if nose and min(abs(self.nose.lightness() - c.lightness()) for c in
                        (self.face_tone, self.head_fur)) < 50:
            edge = self.nose.darker(150) if self.nose.lightness() > 100 else self.nose.lighter(185)
            self.nose_edge = QPen(edge, .5)
        self.appearance = appearance
        self.sleep_face = None

    def set_keyboard(self, keyboard):
        self.model = keyboard
        self.key_paths = {key.identifier: polygon(key.polygon) for key in keyboard.by_id.values()}
        self.board_top = polygon(keyboard.board)
        self.board_path = self.board_top.united(self.board_top.translated(0, 2 * KEYBOARD_SCALE))
        self.touchpad_path = rounded_polygon(keyboard.touchpad, .8) if keyboard.touchpad else QPainterPath()
        self.keyboard_cache = None

    def cache(self, size, pixel_ratio):
        extent = size * pixel_ratio
        scale = math.ceil(extent) / 200
        aligned = extent == round(extent)
        resized = scale != self.cache_scale or aligned != self.pixel_aligned
        self.pixel_aligned = aligned
        keyboard_cache = (scale, aligned, self.model.layout)
        if self.keyboard_cache != keyboard_cache:
            self._cache_keyboard(scale)
            self.keyboard_cache = keyboard_cache
        if resized:
            self.cache_scale = scale
            self._cache_layer('mouse', scale)
        if resized or self.coat_layers_dirty:
            coat = COATS[self.appearance.coat]
            toes = coat.toes or (coat.leg, coat.leg)
            feet = coat.feet or (coat.shade, coat.shade)
            self._cache_layer('paw', scale, toes[:1])
            if toes[0] == toes[1]:
                self.layers['paw-right'] = self.layers['paw']
            else:
                self._cache_layer('paw', scale, toes[1:], 'paw-right')
            self._cache_layer('hind-feet', scale, feet)
            self.coat_layers_dirty = False
        if resized:
            self.sleep_face = None

    def _cache_sleep_face(self):
        scale = self.cache_scale
        image = QPixmap(math.ceil(200 * scale), math.ceil(200 * scale))
        image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(scale, scale)
        resting = Pose(sleep=1, relax=1, blink=1, expression=DROWSY)
        face = FaceGeometry(resting)
        self._draw_face(p, resting, face)
        p.end()
        origin = QPointF()
        if self.pixel_aligned:
            bounds = QRegion(image.mask()).boundingRect().adjusted(-2, -2, 2, 2).intersected(image.rect())
            image = image.copy(bounds)
            origin = QPointF(bounds.topLeft()) / scale
        image.setDevicePixelRatio(scale)
        self.sleep_face = image, origin, QPointF(face.cx, face.cy), self.head_hit_paths[:]

    def _cache_layer(self, name, scale, colors=(), target=None):
        bounds = self.renderer.boundsOnElement(name)
        left, top = math.floor((bounds.left() - 1) * scale), math.floor((bounds.top() - 1) * scale)
        width = math.ceil((bounds.right() + 1) * scale) - left
        height = math.ceil((bounds.bottom() + 1) * scale) - top
        origin = QPointF(left / scale, top / scale)
        image = QPixmap(width, height); image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(scale, scale); p.translate(-origin.x(), -origin.y())
        self.renderer.render(p, name, bounds)
        if colors and colors[0]:
            # Tint the SVG's existing coverage, including the antialiased toe edges.
            p.resetTransform()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            if len(colors) == 2 and colors[0] != colors[1]:
                half = width // 2
                p.fillRect(0, 0, half, height, QColor(colors[0]))
                p.fillRect(half, 0, width - half, height, QColor(colors[1]))
            else:
                p.fillRect(image.rect(), QColor(colors[0]))
        p.end(); image.setDevicePixelRatio(scale)
        self.layers[target or name] = origin, image

    def _cache_keyboard(self, scale):
        self.keyboard = QPixmap(math.ceil(200 * scale), math.ceil(200 * scale))
        self.keyboard.fill(Qt.GlobalColor.transparent)
        p = QPainter(self.keyboard); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(scale, scale)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#647078'))
        p.save(); p.translate(0, 2 * KEYBOARD_SCALE); p.drawPath(self.board_top); p.restore()
        p.setBrush(QColor('#929ea2')); p.drawPath(self.board_top)
        if self.model.touchpad:
            p.setPen(QPen(QColor('#647078'), .65))
            p.setBrush(QColor('#bac5c6')); p.drawPath(self.touchpad_path)
            p.setPen(Qt.PenStyle.NoPen)
        self.legends = {}
        font = QFont('sans-serif')
        font.setPixelSize(16)
        cap_height = QFontMetricsF(font).capHeight()
        for key in self.model.by_id.values():
            label = self.model.label(key.identifier)
            if scale >= 1 and label:
                glyph = QPainterPath()
                glyph.addText(0, 0, font, label)
                box = glyph.boundingRect()
                fit = min(3.2 / cap_height, (key.width * 5.2 - .5) / max(1, box.width()),
                          3.65 / max(1, box.height()))
                if fit * cap_height * scale * KEYBOARD_SCALE >= 1.9:
                    x, y, ux, uy, vx, vy = key.label_basis
                    transform = QTransform(ux, uy, vx, vy, x, y)
                    transform.scale(fit, fit)
                    transform.translate(-box.center().x(), -box.center().y())
                    self.legends[key.identifier] = transform.map(glyph)
            self.draw_key(p, key, False)
        p.end()
        # At fractional physical extents preserve Qt's full-image sampling origin.
        self.keyboard_origin = QPointF()
        if self.pixel_aligned:
            bounds = QTransform.fromScale(scale, scale).mapRect(self.board_path.boundingRect())
            pixels = bounds.toAlignedRect().adjusted(-2, -2, 2, 2).intersected(self.keyboard.rect())
            self.keyboard = self.keyboard.copy(pixels)
            self.keyboard_origin = QPointF(pixels.topLeft()) / scale
        self.keyboard.setDevicePixelRatio(scale)

    def draw_key(self, p, key, down, pressure=0.0):
        p.save(); p.translate(0, (KEY_TRAVEL if down else 0) + pressure * .45 * KEYBOARD_SCALE)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#829294' if down else '#ccd2ce'))
        p.drawPath(self.key_paths[key.identifier])
        legend = self.legends.get(key.identifier)
        if legend is not None:
            p.fillPath(legend, QColor('#39454b'))
        p.restore()

    def layer(self, p, name):
        origin, image = self.layers[name]; p.drawPixmap(origin, image)

    def _body(self, p, body):
        p.setBrush(self.fur); p.setPen(Qt.PenStyle.NoPen)
        outline = curve(body.deform(self.body_controls['body']))
        self.hits.append(('torso', outline))
        p.drawPath(outline)
        p.save(); p.setClipPath(outline, Qt.ClipOperation.IntersectClip)
        for name, color in self.body_tones.items():
            p.setBrush(color); p.drawPath(curve(body.deform(self.body_controls[name])))
        if self.markings:
            self.markings.draw_body(p, body)
        if self.fur_edge:
            p.strokePath(outline, self.fur_edge)
        p.restore()

    def _tail(self, p, pose, body):
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.tail_fur)
        points = self.shapes['tail']
        curled = self.shapes['tail-curled']
        warped = []
        amplitude = (pose.tail * 2.4 + pose.pet * .8 + abs(pose.balance_velocity) * .012) * (1 - pose.sleep)
        for i, (x, y) in enumerate(points):
            if pose.motion.curl:
                x = mix(x, curled[i][0], pose.motion.curl)
                y = mix(y, curled[i][1], pose.motion.curl)
            weight = self.tail_weights[i]
            x += math.sin(pose.tail_phase - weight * 2) * amplitude * weight
            y += math.sin(pose.tail_phase - weight * 2 + .6) * amplitude * weight * .55
            y += (pose.tail_tip + pose.motion.tip) * weight * weight
            if pose.tail_touch:
                # The bend travels around the curl, with the strongest lift at its tip.
                phase = max(0, min(1, (pose.tail_touch - .17 * weight) / .83))
                bend = math.sin(math.pi * phase) ** 2 * weight
                x -= 4.4 * bend
                y -= (5 + 2 * math.sin(math.tau * phase)) * bend
            if pose.lift or pose.sway_x or pose.sway_y or pose.tail_sway:
                x += mix(pose.sway_x * .65, pose.tail_sway * .95, weight) * weight
                y += (pose.sway_y * .8 - pose.lift * .38) * weight
            warped.append(body.map(x, y))
        outline = curve(warped)
        self.hits.append(('tail', outline))
        p.drawPath(outline)
        if self.markings:
            self.markings.draw_tail(p, outline, warped)

    @staticmethod
    def shoulder(side, pose):
        return BodyGeometry(pose).shoulder(side)

    def _arm(self, p, pose, side, body):
        sx, sy = body.shoulder(side)
        wx, wy = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
        dx, dy = wx - sx, wy - sy
        distance = math.hypot(dx, dy)
        bend = max(4, 12 - distance * .09)
        if side == pose.action_side:
            bend += 11 * pose.motion.rub
        cx = (sx + wx) * .5 + side * bend
        cy = (sy + wy) * .5 + min(9, abs(dx) * .12)
        reach = body.mouse_reach if side < 0 else 0
        # These cubic handles reproduce the usual quadratic exactly at rest.
        ax, ay = mix(sx, cx, 2 / 3), mix(sy, cy, 2 / 3)
        bx, by = mix(wx, cx, 2 / 3), mix(wy, cy, 2 / 3)
        if reach:
            # A shallow bow beside the shoulder–wrist chord. The elbow opens
            # as the paw reaches outward, without folding the wrist back.
            bend = mix(7.5, 4.5, smoothstep((distance - 32) / 25))
            nx, ny = dy / max(1, distance), -dx / max(1, distance)
            ax = mix(ax, sx + dx * .32 + nx * bend, reach)
            ay = mix(ay, sy + dy * .32 + ny * bend, reach)
            bx = mix(bx, sx + dx * .70 + nx * bend * .55, reach)
            by = mix(by, sy + dy * .70 + ny * bend * .55, reach)
        left, right = [], []
        for t, u, uu, ut, tt, base_radius in ARM_SAMPLES:
            x = uu * u * sx + 3 * ut * (u * ax + t * bx) + tt * t * wx
            y = uu * u * sy + 3 * ut * (u * ay + t * by) + tt * t * wy
            tx = uu * (ax - sx) + 2 * ut * (bx - ax) + tt * (wx - bx)
            ty = uu * (ay - sy) + 2 * ut * (by - ay) + tt * (wy - by)
            length = max(.001, math.hypot(tx, ty))
            tx, ty = tx / length, ty / length
            radius = base_radius + reach * u * u
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
        self.hits.append(('paw', path))
        p.drawPath(path)
        if self.markings:
            self.markings.draw_arm(p, side, path, left, right)

    def region_at(self, point):
        return next((region for region, path in reversed(self.hits) if path.contains(point)), None)

    def head_hit(self, point):
        if self.region_at(point) != 'head':
            return None
        return max(-1, min(1, (point.x() - self.head_position.x()) / 30))

    def _head(self, p, pose, body):
        face = FaceGeometry(pose, body)
        self.head_position = QPointF(face.cx, face.cy)
        if pose.sleep == 1 and pose.blink == 1:
            if self.sleep_face is None:
                self._cache_sleep_face()
            image, origin, anchor, paths = self.sleep_face
            offset = self.head_position - anchor
            transform = QTransform.fromTranslate(offset.x(), offset.y())
            p.drawPixmap(offset + origin, image)
            self.head_hit_paths = [transform.map(path) for path in paths]
        else:
            self._draw_face(p, pose, face)

    def _draw_face(self, p, pose, face):
        self.head_hit_paths = []
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.head_fur)
        for side, name in ((-1, 'ear-left'), (1, 'ear-right')):
            ear_point = face.ear_projection(side)
            path = curve([ear_point(x, y) for x, y in self.shapes[name]])
            p.setBrush(self.ears[int(side > 0)]); p.drawPath(path)
            self.head_hit_paths.append(path)
            inner = self.shapes['ear-inner-left' if side < 0 else 'ear-inner-right']
            p.save(); p.setClipPath(path, Qt.ClipOperation.IntersectClip); p.setBrush(self.ear_inner)
            p.drawPath(curve([ear_point(x, y) for x, y in inner])); p.restore()
        p.setBrush(self.head_fur)
        shape = curve([face.outline(x - 101, y - 77) for x, y in self.shapes['head-shape']])
        p.drawPath(shape); self.head_hit_paths.append(shape)
        blink = max(pose.blink, pose.yawn * .92,
                    pose.groom * (.65 if pose.action == 'wash' else .2))
        p.save(); p.setClipPath(shape, Qt.ClipOperation.IntersectClip)
        p.setBrush(self.face_tone)
        p.drawPath(curve([face.point(*point) for point in self.face_volume]))
        if self.markings:
            self.markings.draw_face(p, face, shape)
        if self.fur_edge:
            p.strokePath(shape, self.fur_edge)
        for side in (-1, 1):
            ex, ey = side * 13.7, -1.15
            width = 8.45
            opening = pose.expression.opening
            if pose.dizzy:
                opening *= 1 + side * (.21 + .13 * pose.gaze_x) * pose.dizzy
            top = mix(-9.6 * opening, 1.1, blink)
            bottom = mix(8.1 * (.4 + .6 * opening), 1.1, blink)
            slope = side * pose.expression.slant * (1 - blink)
            left, right = face.point(ex - width, ey + slope * .55), face.point(ex + width, ey - slope * .55)
            aperture = curve([left, face.point(ex - width * .65, ey + top + slope),
                              face.point(ex + width * .65, ey + top - slope), right,
                              face.point(ex + width * .65, ey + bottom - slope * .3),
                              face.point(ex - width * .65, ey + bottom + slope * .3), left])
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.irises[int(side > 0)]); p.drawPath(aperture)
            p.save(); p.setClipPath(aperture, Qt.ClipOperation.IntersectClip)
            if self.eye_edge and blink < .85:
                p.strokePath(aperture, self.eye_edge)
            px = ex + (pose.gaze_x - pose.head_x * .35) * 2.5
            py = ey + pose.gaze_y * 2.0
            radius = pose.expression.pupil
            height = 7 + max(0, opening - 1) * 4
            pupil = curve([face.point(px, py - height), face.point(px - radius, py - 3),
                           face.point(px - radius, py + 3), face.point(px, py + height),
                           face.point(px + radius, py + 3), face.point(px + radius, py - 3),
                           face.point(px, py - height)])
            p.setBrush(self.pupil); p.drawPath(pupil); p.restore()
            if blink > .85:
                lid = QPainterPath(); lid.moveTo(*face.point(ex - width, ey))
                lid.cubicTo(*face.point(ex - width * .65, ey + 1.1),
                            *face.point(ex + width * .65, ey + 1.1), *face.point(ex + width, ey))
                p.setPen(QPen(self.lid_color, .65)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(lid)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(self.nose)
        nose = polygon([face.point(-1.2, 10), face.point(1.2, 10), face.point(0, 11.3)])
        p.drawPath(nose)
        if self.nose_edge:
            p.save()
            p.setClipPath(nose, Qt.ClipOperation.IntersectClip)
            p.strokePath(nose, self.nose_edge)
            p.restore()
        if pose.yawn > .03 or pose.tongue > .03:
            p.setBrush(self.pupil)
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
            flex = (pose.pet * math.sin(pose.time * 7) * .6 + pose.groom * .5
                    + pose.balance_velocity * .006 + pose.expression.whiskers + pose.motion.whiskers)
            p.setPen(QPen(self.whisker, .65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for level in (-1, 1):
                whisker = QPainterPath(); whisker.moveTo(*face.point(side * 22, 10 + level * 1.4))
                whisker.cubicTo(*face.point(side * 27, 10 + level * 1.8, 12),
                                *face.point(side * 33, 10 + level * 3 + flex, 8),
                                *face.point(side * 37, 10 + level * 3.2 + flex, 6))
                p.drawPath(whisker)

    def _zzz(self, p, pose):
        if pose.zzz < .01:
            return
        for index in range(3):
            phase = (pose.time * .31 + index / 3) % 1
            p.save(); p.translate(self.head_position + QPointF(44 + phase * 17, -17 - phase * 30))
            size = .76 + phase * .34
            p.scale(size, size)
            p.setOpacity(pose.zzz * smoothstep(phase / .13) * smoothstep((1 - phase) / .22))
            p.strokePath(self.z_path, QPen(QColor('#f0f2ed'), 1.4))
            p.fillPath(self.z_path, QColor('#526168')); p.restore()

    def _paw(self, p, pose, side, body):
        x, y = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
        reach = body.mouse_reach if side < 0 else 0
        transform = QTransform.fromTranslate(x, y)
        transform.rotate(-14 * reach)
        pressure = pose.left_pressure if side < 0 else pose.right_pressure
        transform.scale(1 + pressure * .035, 1 - pressure * .10)
        if pose.motion.content and not pose.pressed and pose.mouse < .01:
            planted = pose.motion.content * smoothstep((y - 153) / 4)
            transform.scale(1 + .16 * planted, 1 - .13 * planted)
        transform.translate(-reach, mix(-3.5, 0, reach))
        self.hits.append(('paw', transform.map(self.paw_path)))
        p.save(); p.setTransform(transform, True)
        self.layer(p, 'paw' if side < 0 else 'paw-right'); p.restore()

    def draw(self, p, pose):
        p.save(); p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        body = BodyGeometry(pose)
        self.hits.clear()
        self._tail(p, pose, body)
        if self.model.pointer == 'mouse':
            mouse_x = self.model.mouse_offset + pose.mouse_dx
            p.save(); p.translate(mouse_x, pose.mouse_dy + pose.click * .4); self.layer(p, 'mouse')
            if pose.scroll > .01:
                p.translate(self.wheel_center); p.rotate(-77)
                p.setPen(QPen(QColor('#c2cecc'), .7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                step = math.sin(pose.time * 28) * pose.scroll_direction * pose.scroll
                p.drawLine(QPointF(step, -.6), QPointF(step, .6))
            p.restore()
            self.hits.append(('mouse', self.mouse_path.translated(mouse_x, pose.mouse_dy + pose.click * .4)))
        p.save(); p.translate(0, -pose.lift)
        self.layer(p, 'hind-feet'); p.restore()
        self.hits.append(('paw', self.feet_path.translated(0, -pose.lift)))
        self._body(p, body)
        p.drawPixmap(self.keyboard_origin, self.keyboard)
        self.hits.append(('keyboard', self.board_path))
        if self.model.touchpad:
            self.hits.append(('touchpad', self.touchpad_path))
            if pose.click > .01 and pose.mouse > .5:
                p.fillPath(self.touchpad_path, QColor(68, 86, 94, round(pose.click * 45)))
        pressures = dict(pose.contacts)
        for identifier in pose.pressed | pressures.keys():
            key = self.model.by_id[identifier]
            self.draw_key(p, key, identifier in pose.pressed, pressures.get(identifier, 0))
        washing_face = pose.action == 'wash' and pose.groom > .01
        # The typing foreleg crosses in front of the paw planted on the touchpad.
        pad_paw_behind = pose.touchpad and pose.mouse > .01 and not washing_face
        if not washing_face:
            self._arm(p, pose, -1, body)
        if pad_paw_behind:
            self._paw(p, pose, -1, body)
        self._arm(p, pose, 1, body)
        self._head(p, pose, body)
        self.hits.extend(zip(('ear-left', 'ear-right', 'head'), self.head_hit_paths))
        if washing_face:
            self._arm(p, pose, -1, body)
        if not pad_paw_behind:
            self._paw(p, pose, -1, body)
        self._paw(p, pose, 1, body)
        self._zzz(p, pose); p.restore()
