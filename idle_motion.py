"""Offsets for one seated idle action, sampled by the existing animation clock."""

from dataclasses import dataclass
import math

# Ranges are seconds. The quiet choices also weight the ordinary idle repertoire.
DURATIONS = {'look': (2.8, 4.2), 'shift': (2.4, 3.6), 'lick': (4.5, 4.5),
             'wash': (4.6, 4.6), 'yawn': (3.5, 3.5), 'stretch': (3.4, 4.8),
             'ear_rub': (2.8, 4.0), 'knead': (3.4, 4.8), 'shake': (1.1, 1.6),
             'tail': (3.0, 4.6)}
QUIET = ('look', 'shift', 'tail', 'yawn')


@dataclass(frozen=True, slots=True)
class IdleMotion:
    lean: float = 0.0
    drop: float = 0.0
    shoulders: float = 0.0
    pitch: float = 0.0
    turn: float = 0.0
    tilt: float = 0.0
    lids: float = 0.0
    ears: float = 0.0
    swivel: float = 0.0
    whiskers: float = 0.0
    curl: float = 0.0
    tip: float = 0.0
    content: float = 0.0
    # Forepaw offsets on the free strip of floor just behind the keyboard.
    left: tuple[float, float] | None = None
    right: tuple[float, float] | None = None
    rub: float = 0.0
    stroke: float = 0.0


STILL = IdleMotion()


def smoothstep(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def sample(kind, phase, weight, side, strength):
    if not kind or not weight or not 0 < phase < 1:
        return STILL
    envelope = math.sin(math.pi * phase) ** 2 * weight * strength
    if kind == 'stretch':
        # Plant one paw first, lower the chest between the planted forelegs, then release.
        plant = smoothstep(phase / .30) * smoothstep((1 - phase) / .36) * weight * strength
        follow = smoothstep((phase - .07) / .30) * smoothstep((1 - phase) / .30) * weight * strength
        lead = (side * 31 * plant, -.4 * plant)
        trail = (side * 15 * follow, -1.6 * follow)
        left, right = (lead, trail) if side < 0 else (trail, lead)
        return IdleMotion(lean=side * 4 * envelope, drop=13 * envelope,
                          shoulders=-side * 2 * envelope, pitch=.26 * envelope,
                          turn=side * .22 * envelope, tilt=side * 4 * envelope,
                          lids=.61 * envelope, ears=6 * envelope, whiskers=1.3 * envelope,
                          curl=.48 * plant, left=left, right=right)
    if kind == 'ear_rub':
        reach = smoothstep(phase / .26) * smoothstep((1 - phase) / .27) * weight
        beat = math.sin(phase * math.tau * 4.3) * envelope
        return IdleMotion(lean=-side * 3 * envelope, drop=2 * envelope,
                          shoulders=-side * 2 * envelope, tilt=side * 12 * envelope,
                          turn=side * .09 * envelope, lids=.54 * envelope,
                          swivel=side * 5 * beat, rub=reach, stroke=3 * beat)
    if kind == 'knead':
        beat = math.sin(phase * math.tau * 4 + .45 * math.sin(phase * math.tau)) * side
        left_lift = envelope * (1 + beat) * .5
        right_lift = envelope * (1 - beat) * .5
        return IdleMotion(lean=1.7 * beat * envelope, drop=1.8 * envelope,
                          shoulders=-2.4 * beat * envelope, pitch=.06 * envelope,
                          content=.72 * envelope, curl=.42 * envelope,
                          left=(-2 * envelope, -9 * left_lift), right=(2 * envelope, -9 * right_lift))
    if kind == 'shake':
        beat = math.sin(phase * math.tau * 2.5) * envelope * (1 - phase) * side
        return IdleMotion(lean=1.8 * beat, turn=.62 * beat, tilt=14 * beat,
                          shoulders=1.8 * beat, swivel=-16 * beat, lids=.72 * envelope,
                          whiskers=-5 * beat)
    if kind == 'shift':
        foot = (side * 5 * envelope, -3 * envelope)
        return IdleMotion(lean=side * 4 * envelope, drop=-2.2 * envelope,
                          shoulders=side * 2 * envelope, tilt=-side * 3 * envelope,
                          left=foot if side < 0 else None, right=foot if side > 0 else None)
    if kind == 'tail':
        return IdleMotion(curl=envelope, tip=2.8 * envelope * math.sin(phase * math.tau * 2),
                          lean=-1.2 * envelope)
    return STILL
