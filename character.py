"""Original vector artwork, perspective-aware expressions and connected limbs."""

import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer

from animations import Pose, mix, smoothstep


def curve(points: list[tuple[float, float]]) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(*points[0])
    for index in range(1, len(points), 3):
        path.cubicTo(*points[index], *points[index + 1], *points[index + 2])
    path.closeSubpath()
    return path


def unit(x: float, y: float) -> tuple[float, float]:
    length = max(0.001, math.hypot(x, y))
    return x / length, y / length


class CatArt:
    LAYERS = ("body", "ear-left", "ear-right", "keyboard", "mouse", "paw", "muzzle")
    TAIL_WEIGHTS = (0, .24, .5, .65, .82, .94, 1, 1, 1, .98, .86, .78, .66, .48, .25, .03, 0, 0, 0)

    def __init__(self) -> None:
        path = Path(__file__).resolve().parent / "assets" / "cat" / "miga.svg"
        self.renderer = QSvgRenderer(str(path))
        if not self.renderer.isValid():
            raise RuntimeError("Could not load the character artwork.")
        elements = {node.get("id"): node for node in ET.parse(path).iter() if node.get("id")}

        def read_curve(name: str) -> list[tuple[float, float]]:
            data = elements[name].get("d", "")
            commands = re.findall(r"[A-Za-z]", data)
            values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", data)]
            count = (len(values) - 2) // 6
            if commands != ["M"] + ["C"] * count + ["Z"] or len(values) != 2 + count * 6:
                raise RuntimeError(f"Character curve {name} must use absolute M/C/Z commands.")
            return list(zip(values[::2], values[1::2]))

        self.heads = {name: read_curve(name) for name in (
            "head-shape", "head-left", "head-right", "head-up", "head-down",
        )}
        if len({len(points) for points in self.heads.values()}) != 1:
            raise RuntimeError("Head poses must have matching curve topology.")
        self.chin = read_curve("chin")
        self.tail = read_curve("tail")
        if len(self.tail) != len(self.TAIL_WEIGHTS):
            raise RuntimeError("Tail curvature and deformation weights do not match.")
        self.layers: dict[str, tuple[QPointF, QPixmap]] = {}
        self.cache_scale = 0.0
        self.head_color = QColor("#353e47")
        self.arm_color = QColor("#303a43")
        self.edge = QPen(QColor("#65717a"), 0.8)
        self.edge.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.eye_rim = QPen(QColor("#1d252c"), 1.1)
        self.lid_pen = QPen(QColor("#89979d"), 0.8)
        self.lid_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.whisker_pen = QPen(QColor("#7a858b"), 0.75)
        self.whisker_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    def cache(self, size: int, pixel_ratio: float) -> None:
        scale = math.ceil(size * pixel_ratio) / 200.0
        if scale == self.cache_scale:
            return
        self.cache_scale = scale
        for name in self.LAYERS:
            if not self.renderer.elementExists(name):
                raise RuntimeError(f"Missing character layer: {name}")
            bounds = self.renderer.boundsOnElement(name)
            left = math.floor((bounds.left() - 2) * scale)
            top = math.floor((bounds.top() - 2) * scale)
            width = math.ceil((bounds.right() + 2) * scale) - left
            height = math.ceil((bounds.bottom() + 2) * scale) - top
            origin = QPointF(left / scale, top / scale)
            pixmap = QPixmap(width, height)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.scale(scale, scale)
            painter.translate(-origin.x(), -origin.y())
            self.renderer.render(painter, name, bounds)
            painter.end()
            pixmap.setDevicePixelRatio(scale)
            self.layers[name] = origin, pixmap

    def layer(self, painter: QPainter, name: str) -> None:
        origin, pixmap = self.layers[name]
        painter.drawPixmap(origin, pixmap)

    def _tail(self, painter: QPainter, pose: Pose) -> None:
        points = []
        for (x, y), weight in zip(self.tail, self.TAIL_WEIGHTS):
            amplitude = pose.tail * weight * weight
            x += math.sin(pose.tail_phase - weight * 2.3) * amplitude * 4.0
            y += math.sin(pose.tail_phase - weight * 2.3 + .65) * amplitude * 2.6
            points.append((x + pose.lean, y - pose.breath * .1))
        painter.setPen(self.edge)
        painter.setBrush(QColor("#2c343c"))
        painter.drawPath(curve(points))

    def _body(self, painter: QPainter, pose: Pose) -> None:
        painter.save()
        painter.translate(94 + pose.lean, 162)
        painter.scale(1 + pose.breath * .006, 1 + pose.breath * .011)
        painter.translate(-94, -162)
        self.layer(painter, "body")
        painter.restore()

    @staticmethod
    def shoulder(side: int, pose: Pose) -> tuple[float, float]:
        x = 79.5 if side < 0 else 109.5 + smoothstep(pose.mouse) * 3.0
        return (94 + pose.lean + (x - 94) * (1 + pose.breath * .006),
                162 + (96 - 162) * (1 + pose.breath * .011))

    @staticmethod
    def elbow(shoulder: tuple[float, float], wrist: tuple[float, float],
              side: int, reach: float) -> tuple[float, float]:
        sx, sy = shoulder
        dx, dy = wrist[0] - sx, wrist[1] - sy
        distance = max(0.001, math.hypot(dx, dy))
        upper, lower = (28.0, 29.0) if side < 0 else (29 + 4 * reach, 30 + 5 * reach)
        # Keep a small bend at full reach and a fixed outward elbow preference.
        stretch = max(1.0, distance / ((upper + lower) * .97))
        upper, lower = upper * stretch, lower * stretch
        along = (upper * upper - lower * lower + distance * distance) / (2 * distance)
        height = min(9.0, math.sqrt(max(0.0, upper * upper - along * along)))
        sign = 1 if side < 0 else -1
        return (sx + dx / distance * along - dy / distance * height * sign,
                sy + dy / distance * along + dx / distance * height * sign)

    def _arm(self, painter: QPainter, pose: Pose, side: int) -> None:
        shoulder = self.shoulder(side, pose)
        wrist = (pose.left_x, pose.left_y) if side < 0 else (pose.right_x, pose.right_y)
        elbow = self.elbow(shoulder, wrist, side, smoothstep(pose.mouse))
        sx, sy = shoulder
        ex, ey = elbow
        wx, wy = wrist
        ax, ay = unit(ex - sx, ey - sy)
        bx, by = unit(wx - ex, wy - ey)
        tx, ty = unit(wx - sx, wy - sy)
        normals = ((-ay, ax), (-ty, tx), (-by, bx))
        widths = (6.6, 5.4, 4.0)
        outline = QPainterPath()
        edges = QPainterPath()
        for direction in (1, -1):
            snx, sny = (n * direction * widths[0] for n in normals[0])
            enx, eny = (n * direction * widths[1] for n in normals[1])
            wnx, wny = (n * direction * widths[2] for n in normals[2])
            if direction == 1:
                outline.moveTo(sx + snx, sy + sny)
                edges.moveTo(sx + snx, sy + sny)
                edges.cubicTo(sx + ax * 15 + snx, sy + ay * 15 + sny,
                              ex - tx * 6 + enx, ey - ty * 6 + eny, ex + enx, ey + eny)
                edges.cubicTo(ex + tx * 6 + enx, ey + ty * 6 + eny,
                              wx - bx * 9 + wnx, wy - by * 9 + wny, wx + wnx, wy + wny)
                outline.cubicTo(sx + ax * 15 + snx, sy + ay * 15 + sny,
                                ex - tx * 6 + enx, ey - ty * 6 + eny, ex + enx, ey + eny)
                outline.cubicTo(ex + tx * 6 + enx, ey + ty * 6 + eny,
                                wx - bx * 9 + wnx, wy - by * 9 + wny, wx + wnx, wy + wny)
            else:
                edges.moveTo(wx + wnx, wy + wny)
                edges.cubicTo(wx - bx * 9 + wnx, wy - by * 9 + wny,
                              ex + tx * 6 + enx, ey + ty * 6 + eny, ex + enx, ey + eny)
                edges.cubicTo(ex - tx * 6 + enx, ey - ty * 6 + eny,
                              sx + ax * 15 + snx, sy + ay * 15 + sny, sx + snx, sy + sny)
                outline.lineTo(wx + wnx, wy + wny)
                outline.cubicTo(wx - bx * 9 + wnx, wy - by * 9 + wny,
                                ex + tx * 6 + enx, ey + ty * 6 + eny, ex + enx, ey + eny)
                outline.cubicTo(ex - tx * 6 + enx, ey - ty * 6 + eny,
                                sx + ax * 15 + snx, sy + ay * 15 + sny, sx + snx, sy + sny)
        outline.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.arm_color)
        painter.drawPath(outline)
        painter.setPen(self.edge)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(edges)
        painter.save()
        painter.translate(wx, wy)
        lift = pose.left_paw if side < 0 else pose.right_paw
        painter.rotate((-2 + lift * 6) if side < 0 else (2 - smoothstep(pose.mouse) * 17 - lift * 4))
        painter.scale(1 + lift * .035, 1 - lift * .04)
        self.layer(painter, "paw")
        painter.restore()

    def _eye(self, painter: QPainter, pose: Pose, side: int) -> None:
        yaw, pitch = pose.head_x, pose.head_y
        width = 10 * (1 - max(0.0, side * yaw) * .26 + max(0.0, -side * yaw) * .025)
        cx = 94 + side * 14 * (1 - abs(yaw) * .13) + yaw * 7.0
        cy = 64 + pitch * 3.8 + side * yaw * .65
        top = mix(-10.0, 1.65, pose.blink)
        bottom = mix(10.0, 1.65, pose.blink)
        # The upper lid travels further than the lower lid; the aperture itself closes.
        aperture = QPainterPath()
        aperture.moveTo(cx - width, cy)
        aperture.cubicTo(cx - width * .65, cy + top, cx + width * .65, cy + top, cx + width, cy)
        aperture.cubicTo(cx + width * .65, cy + bottom, cx - width * .65, cy + bottom, cx - width, cy)
        aperture.closeSubpath()
        painter.setPen(self.eye_rim)
        painter.setBrush(QColor("#c2d196"))
        painter.drawPath(aperture)
        painter.save()
        painter.setClipPath(aperture)
        px = cx + (pose.gaze_x - yaw * .32) * 2.3
        py = cy + (pose.gaze_y - pitch * .3) * 1.5
        pupil = QPainterPath()
        pupil.moveTo(px, py - 8.0)
        pupil.cubicTo(px - 3.3, py - 4, px - 3.3, py + 4, px, py + 8)
        pupil.cubicTo(px + 3.3, py + 4, px + 3.3, py - 4, px, py - 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#131b21"))
        painter.drawPath(pupil)
        painter.setBrush(QColor("#f3f5e3"))
        painter.drawEllipse(QPointF(px - 3.1, py - 4.1), .85, 1.0)
        painter.restore()
        if pose.blink > .75:
            lid = QPainterPath()
            lid.moveTo(cx - width, cy)
            lid.cubicTo(cx - width * .65, cy + 1.65, cx + width * .65, cy + 1.65, cx + width, cy)
            painter.setPen(self.lid_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setOpacity((pose.blink - .75) * 4)
            painter.drawPath(lid)
            painter.setOpacity(1)

    def _head(self, painter: QPainter, pose: Pose) -> None:
        painter.save()
        painter.translate(9.4 + pose.lean * .45, -2 - pose.breath * .65)
        painter.scale(.9, .9)
        yaw, pitch = pose.head_x, pose.head_y
        for side, name, flick in ((-1, "ear-left", pose.ear_left), (1, "ear-right", pose.ear_right)):
            x, y = (73, 46) if side < 0 else (117, 46)
            painter.save()
            painter.translate(x - yaw * 3, y + pitch * 2)
            painter.scale(1 - max(0, side * yaw) * .3, 1 - pitch * .04)
            painter.rotate(flick - yaw * 4 + side * pitch * 2)
            painter.translate(-x, -y)
            self.layer(painter, name)
            painter.restore()
        front = self.heads["head-shape"]
        profile = self.heads["head-right" if yaw >= 0 else "head-left"]
        vertical = self.heads["head-down" if pitch >= 0 else "head-up"]
        points = [(mix(x, sx, abs(yaw)) + (vx - x) * abs(pitch),
                   mix(y, sy, abs(yaw)) + (vy - y) * abs(pitch))
                  for (x, y), (sx, sy), (vx, vy) in zip(front, profile, vertical)]
        silhouette = curve(points)
        painter.setPen(self.edge)
        painter.setBrush(self.head_color)
        painter.drawPath(silhouette)
        painter.save()
        painter.setClipPath(silhouette)
        if abs(yaw) > .01:
            width = abs(yaw) * 14
            side_plane = [(94, 32), (76, 37), (61, 49), (59, 67),
                          (56, 84), (69, 97), (95, 99),
                          (82 + width * .5, 96), (59 + width, 79), (61 + width, 63),
                          (62 + width, 49), (78 + width * .4, 40), (94, 32)]
            if yaw < 0:
                side_plane = [(188 - x, y) for x, y in side_plane]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2c343d"))
            painter.drawPath(curve(side_plane))
        chin = [(94 + (x - 94) * (1 - abs(yaw) * .1) + yaw * 8,
                 y + pitch * 3.5) for x, y in self.chin]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#414c55"))
        painter.drawPath(curve(chin))
        painter.restore()
        self._eye(painter, pose, -1)
        self._eye(painter, pose, 1)
        painter.save()
        painter.translate(94 + yaw * 9, 82 + pitch * 4.4)
        painter.scale(1 - abs(yaw) * .18, 1 - abs(pitch) * .06)
        painter.translate(-94, -82)
        self.layer(painter, "muzzle")
        painter.restore()
        painter.setPen(self.whisker_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for side in (-1, 1):
            length = 18 * (1 - max(0, side * yaw) * .45)
            root_x = 94 + side * 18 + yaw * 7
            root_y = 81 + pitch * 4 + side * yaw * .6
            whiskers = QPainterPath()
            whiskers.moveTo(root_x, root_y)
            whiskers.cubicTo(root_x + side * length * .4, root_y - 2,
                             root_x + side * length * .75, root_y - 3,
                             root_x + side * length, root_y - 2)
            whiskers.moveTo(root_x + side, root_y + 3)
            whiskers.cubicTo(root_x + side * length * .4, root_y + 3,
                             root_x + side * length * .75, root_y + 4,
                             root_x + side * length * .95, root_y + 6)
            painter.drawPath(whiskers)
        painter.restore()

    def draw(self, painter: QPainter, pose: Pose) -> None:
        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self._tail(painter, pose)
        self._body(painter, pose)
        self.layer(painter, "keyboard")
        painter.save()
        painter.translate(pose.mouse_dx, pose.mouse_dy + pose.click * .4)
        self.layer(painter, "mouse")
        painter.restore()
        self._arm(painter, pose, -1)
        self._arm(painter, pose, 1)
        self._head(painter, pose)
        painter.restore()
