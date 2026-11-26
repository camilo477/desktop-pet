"""Pace visible animation on the panel's display; use Qt for sleep and hidden windows."""

import time
import weakref

import AppKit
import objc
from Foundation import NSObject, NSNotificationCenter, NSRunLoop, NSRunLoopCommonModes
from PySide6.QtCore import QTimer


class FrameTarget(NSObject):
    @objc.typedSelector(b'v@:@')
    def frame_(self, link):
        clock = self.clock()
        if clock is not None and clock.using_display:
            # An input notification can draw just before this display callback.
            if time.monotonic() - clock.parent().last_frame >= .016:
                clock.timeout.emit()


class MacFrameTimer(QTimer):
    def __init__(self, parent):
        super().__init__(parent)
        self.running = self.using_display = False
        self.panel = self.link = self.observer = None
        self.target = FrameTarget.alloc().init()
        self.target.clock = weakref.ref(self)

    def attach(self, panel):
        if panel == self.panel:
            return
        self.detach()
        self.panel = panel
        link = panel.displayLinkWithTarget_selector_(self.target, b'frame:')
        if link is not None and link.respondsToSelector_(b'setPreferredFrameRateRange:'):
            link.setPaused_(True)
            link.setPreferredFrameRateRange_((30., 30., 30.))
            link.addToRunLoop_forMode_(NSRunLoop.mainRunLoop(), NSRunLoopCommonModes)
            self.link = link
            self.observer = NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                AppKit.NSWindowDidChangeOcclusionStateNotification, panel, None,
                lambda note: self.schedule())
        elif link is not None:
            link.invalidate()
        self.schedule()

    def schedule(self):
        visible = (self.link is not None and self.running and self.interval() == 34
                   and self.panel.occlusionState() & AppKit.NSWindowOcclusionStateVisible)
        self.using_display = bool(visible)
        if self.link is not None:
            self.link.setPaused_(not self.using_display)
        if self.running and not self.using_display:
            super().start()
        else:
            super().stop()

    def setInterval(self, ms):
        super().setInterval(ms)
        self.schedule()

    def start(self, ms=None):
        if ms is not None and ms != self.interval():
            super().setInterval(ms)
        self.running = True
        self.schedule()

    def stop(self):
        self.running = False
        self.schedule()

    def isActive(self):
        return self.using_display or super().isActive()

    def detach(self):
        if self.observer is not None:
            NSNotificationCenter.defaultCenter().removeObserver_(self.observer)
            self.observer = None
        self.using_display = False
        if self.link is not None:
            self.link.invalidate()
        self.link = self.panel = None
