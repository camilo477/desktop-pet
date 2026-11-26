"""Small, transient expression choices driven only by aggregate physical activity."""

import math
import random
from typing import NamedTuple


class Expression(NamedTuple):
    opening: float = 1.0        # Eye aperture relative to the original almond.
    pupil: float = 2.3          # Width of the pupil's cubic handles, in face coordinates.
    slant: float = 0.0          # Lower the nasal end of the upper lid.
    ears: float = 0.0           # Degrees away from upright, around each ear root.
    lean: float = 0.0           # Vertical displacement of the chest.
    pitch: float = 0.0          # Additional face pitch, in radians.
    tilt: float = 0.0           # Roll toward the current target, in degrees.
    whiskers: float = 0.0       # Vertical deflection at the flexible ends.
    tail: float = 0.0           # Tip excursion, in logical pixels.
    tip_speed: float = 3.0      # Radians per second.

    def blend(self, other, weight):
        if weight <= 0 or self is other:
            return self
        if weight >= 1:
            return other
        return Expression(*(a + (b - a) * weight for a, b in zip(self, other)))


CALM = Expression()
FOCUSED = Expression(opening=.64, pupil=1.7, slant=.85, ears=-10, lean=1.9,
                     pitch=.10, whiskers=-.9, tail=1.15, tip_speed=4)
EXCITED = Expression(opening=1.22, pupil=4.7, ears=-17, lean=-1.7, pitch=-.06,
                     tilt=2, whiskers=-1.8, tail=4.6, tip_speed=5.8)
IMPATIENT = Expression(opening=.53, pupil=1.35, slant=3.7, ears=28, lean=3,
                       pitch=.12, whiskers=.9, tail=2.8, tip_speed=8.2)
SURPRISED = Expression(opening=1.48, pupil=6.6, ears=-24, lean=-3.6, pitch=-.14,
                       whiskers=-2.4, tail=1.6, tip_speed=5.4)
CURIOUS = Expression(opening=1.06, pupil=4.0, ears=-5, tilt=8.5, lean=-.7,
                     whiskers=-1.1, tail=1.4)
CONTENT = Expression(opening=.54, pupil=3, ears=5, lean=1.2, pitch=-.07,
                     whiskers=1.7, tail=2, tip_speed=2.5)
DROWSY = Expression(opening=.22, pupil=2.7, ears=17, lean=1.9, pitch=.13,
                    whiskers=2.1, tail=.4, tip_speed=1.7)


class Personality:
    def __init__(self, origin=CALM):
        self.rate = self.pointer_speed = self.scroll_rate = 0.0
        self.baseline = 0.0
        self.sampled = self.intense_since = None
        self.band = 0
        self.last_edge = self.quiet_until = -math.inf
        self.next_surprise = self.next_impatience = -math.inf
        self.next_choice = self.next_check = -math.inf
        self.state = CALM
        self.shape = self.origin = origin
        self.changed = None

    def _select(self, state, now):
        if self.state is not state:
            self.origin = self.shape
            self.state = state
            self.changed = now

    def _choose(self, now, pointer_recent, looking):
        # Schmitt thresholds let the smoothed cadence fluctuate between taps.
        enter, leave = (4.1, 7.0, 9.4), (3.35, 5.9, 8.0)
        while self.band < 3 and self.rate >= enter[self.band]:
            self.band += 1
        while self.band and self.rate < leave[self.band - 1]:
            self.band -= 1
        if self.band < 3:
            self.intense_since = None
        elif self.intense_since is None:
            self.intense_since = now

        if self.state is SURPRISED and now < self.next_choice:
            return
        typing = self.band > 0 and now - self.last_edge < .58
        if typing:
            compatible = (self.state in (CALM, FOCUSED) or
                          (self.state is EXCITED and self.band >= 2) or
                          (self.state is IMPATIENT and self.band == 3))
            if compatible and now < self.next_choice:
                return
            state = FOCUSED
            if self.band >= 2:
                roll = random.random()
                if (self.intense_since is not None and now - self.intense_since >= 1.8
                        and now >= self.next_impatience and roll < .24):
                    state = IMPATIENT
                    self.next_impatience = now + random.uniform(15, 23)
                elif roll < .60:
                    state = EXCITED
                elif roll > .94:
                    state = CALM
            self.next_choice = now + random.uniform(2.2, 4.8)
        elif looking or (pointer_recent and
                         (self.state is CURIOUS or self.pointer_speed > 95 or self.scroll_rate > 4)):
            state = CURIOUS
        else:
            state = CALM
            self.next_choice = now
        self._select(state, now)

    def update(self, dt, now, activity, prior_idle, looking, pet, relax):
        if self.changed is None:
            self.changed = now
        elapsed = max(.0001, dt if self.sampled is None else now - self.sampled)
        self.sampled = now
        # EMA of counts per second, independent of frame rate and event batching.
        alpha = -math.expm1(-elapsed / .95)
        self.rate += (activity.new_presses / elapsed - self.rate) * alpha
        self.baseline += (self.rate - self.baseline) * -math.expm1(-elapsed / 3.5)
        alpha = -math.expm1(-elapsed / .28)
        self.pointer_speed += (activity.pointer_distance / elapsed - self.pointer_speed) * alpha
        self.scroll_rate += (activity.wheel_distance / elapsed - self.scroll_rate) * alpha
        if activity.new_presses:
            self.last_edge = now
        if prior_idle >= 5:
            self.quiet_until = now + .45
        sudden = ((now < self.quiet_until and
                   (activity.new_presses or (activity.pointer_distance and self.pointer_speed > 330)))
                  or (activity.new_presses and self.rate >= 7 and self.rate - self.baseline > 4.3
                      and self.baseline < 4.5))
        if sudden and now >= self.next_surprise and pet < .05:
            self._select(SURPRISED, now)
            self.next_choice = now + .42
            self.next_surprise = now + random.uniform(9, 15)
        if now >= self.next_check:
            self.next_check = now + .14
            pointer_recent = now - max(activity.mouse, activity.scroll) < .50
            self._choose(now, pointer_recent, looking)

        duration = .11 if self.state is SURPRISED else .42
        t = min(1, (now - self.changed) / duration)
        self.shape = self.origin.blend(self.state, t * t * (3 - 2 * t))
        return self.shape.blend(DROWSY, relax).blend(CONTENT, pet)
