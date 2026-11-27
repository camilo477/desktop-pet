// Only the Miga toplevel owned by this process is ever read or changed.
let pet = null;
let adjusting = false;
let previous = null;
let lastPointerReport = -Infinity;

function reportPointer() {
    if (!config.input) return;
    const now = Date.now();
    if (now - lastPointerReport < 16) return;
    lastPointerReport = now;
    const p = workspace.cursorPos;
    callDBus(config.service, '/Placement', config.interface, 'pointerMoved', JSON.stringify({
        generation: config.generation, x: p.x, y: p.y
    }));
}

function frame() {
    // QJSEngine exposes a live QRectF property reference; retain plain numbers
    // when comparing a later resize with the previous frame.
    const r = pet.frameGeometry;
    return {x: r.x, y: r.y, width: r.width, height: r.height};
}

function outputNamed(name) {
    return workspace.screens.find(output => output.name === name);
}

function report(released, done) {
    if (!pet || !pet.output) return;
    const r = frame();
    const area = workspace.clientArea(KWin.MaximizeArea, pet);
    callDBus(config.service, '/Placement', config.interface, 'report', JSON.stringify({
        generation: config.generation, x: r.x, y: r.y, width: r.width, height: r.height,
        above: pet.keepAbove,
        screen: pet.output.name, offsetX: r.x - area.x, offsetY: r.y - area.y,
        released: !!released
    }), function () { if (done) done(); });
}

function place(output, x, y) {
    if (!pet || !output || adjusting) return;
    adjusting = true;
    try {
        if (pet.output !== output) workspace.sendClientToScreen(pet, output);
        const area = workspace.clientArea(KWin.MaximizeArea, output, workspace.currentDesktop);
        const r = frame();
        pet.frameGeometry = {
            x: Math.max(area.x, Math.min(x, area.x + area.width - r.width)),
            y: Math.max(area.y, Math.min(y, area.y + area.height - r.height)),
            width: r.width, height: r.height
        };
        previous = frame();
    } finally {
        adjusting = false;
    }
    report(false);
}

function recover() {
    if (!pet || pet.move) return;
    const output = outputNamed(pet.output ? pet.output.name : '') ||
                   outputNamed(config.primary) || workspace.screens[0];
    const r = frame();
    place(output, r.x, r.y);
}

function attach(window) {
    if (pet || window.pid !== config.pid || window.transient ||
        (window.caption !== 'Miga' && window.captionNormal !== 'Miga')) return;
    pet = window;
    pet.keepAbove = config.above;
    previous = frame();
    if (config.action === 'restore' || config.action === 'screen') {
        const output = outputNamed(config.screen) || outputNamed(config.primary) || pet.output;
        const area = workspace.clientArea(KWin.MaximizeArea, output, workspace.currentDesktop);
        const r = frame();
        const saved = config.action === 'restore' && output.name === config.screen && config.position;
        place(output,
              area.x + (saved ? saved[0] : area.width - r.width - 24),
              area.y + (saved ? saved[1] : area.height - r.height - 12));
    } else {
        recover();
    }
    pet.frameGeometryChanged.connect(function () {
        if (adjusting) return;
        const r = frame();
        if (previous && !pet.move && (r.width !== previous.width || r.height !== previous.height)) {
            const anchor = previous;
            previous = r;
            // KWin may still be committing the Wayland resize while this signal
            // runs. Reposition on the D-Bus reply, after that commit finishes.
            report(false, function () {
                if (!pet || pet.move) return;
                const current = frame();
                place(pet.output, anchor.x + (anchor.width - current.width) / 2,
                      anchor.y + anchor.height - current.height);
            });
        } else {
            previous = r;
            report(false);
        }
    });
    pet.interactiveMoveResizeFinished.connect(function () {
        recover();
        report(true);
    });
    report(false);
}

workspace.windowAdded.connect(attach);
workspace.windowRemoved.connect(function (window) {
    if (window === pet) { pet = null; previous = null; }
});
workspace.screensChanged.connect(recover);
workspace.virtualScreenGeometryChanged.connect(recover);
workspace.cursorPosChanged.connect(reportPointer);
workspace.windowList().forEach(attach);
reportPointer();
