import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { runInNewContext } from "node:vm";

const source = readFileSync(
    new URL("../../static/js/compare.js", import.meta.url),
    "utf8",
);

// Exercise the actual browser functions without requiring the rest of the UI.
function functionSource(name) {
    const start = source.indexOf(`function ${name}(`);
    assert.notEqual(start, -1);
    const end = source.indexOf("\n}", start) + 2;
    assert.ok(end > start);
    return source.slice(start, end);
}

function browserContext(imageUrls) {
    const textArea = {};
    const context = {
        URL,
        window: { location: { origin: "https://comps.example.test" } },
        document: { getElementById: () => textArea },
        imageUrls,
        imageNames: ["left.png", "right.png"],
        totalColumns: 2,
        totalRows: 1,
        textArea,
    };
    const functions = ["resolveImageUrl", "generateBBCode"].map(functionSource);
    runInNewContext(functions.join("\n"), context);
    return context;
}

function viewerContext(imageUrls) {
    const context = browserContext(imageUrls);
    const images = [];
    Object.assign(context, {
        images,
        isSolarized: true,
        solarizationInProgress: false,
        solarizationUnsupportedNotified: false,
        solarizedImageCache: new Map(),
        absoluteIndex: 0,
        imageSizes: [],
        currentImage: {
            style: {},
            removeAttribute(name) {
                delete this[name];
            },
        },
        currentImageInfoSpan: {},
        mobileCurrentImageInfoSpan: null,
        applyZoom: () => {},
        console: { error: () => {}, warn: () => {} },
        Image: class {
            constructor() {
                images.push(this);
            }
        },
    });
    context.document.createElement = () => ({ style: {}, remove: () => {} });
    context.document.body = { appendChild: () => {} };
    runInNewContext(functionSource("updateDisplay"), context);
    return context;
}

test("image URL resolution accepts legacy, app-relative, and public URLs", () => {
    const context = browserContext([]);
    for (const [input, expected] of [
        ["comparison/image.png", "/uploads/comparison/image.png"],
        ["/uploads/comparison/image.png", "/uploads/comparison/image.png"],
        [
            "https://images.example.test/image.png",
            "https://images.example.test/image.png",
        ],
        [
            "http://images.example.test/image.png",
            "http://images.example.test/image.png",
        ],
        [
            "HTTPS://images.example.test/image.png",
            "HTTPS://images.example.test/image.png",
        ],
    ]) {
        assert.equal(context.resolveImageUrl(input), expected);
    }
});

test("BBCode always includes absolute URLs for local and private S3 images", () => {
    const context = browserContext([
        "comparison/left.png",
        "/uploads/comparison/right.png",
    ]);
    context.generateBBCode();
    assert.equal(
        context.textArea.value,
        "[comparison=left, right]\n" +
            "https://comps.example.test/uploads/comparison/left.png\n" +
            "https://comps.example.test/uploads/comparison/right.png\n" +
            "[/comparison]",
    );
});

test("BBCode preserves public CDN URLs and encoded object keys", () => {
    const context = browserContext([
        "https://images.example.test/prefix/left%20%231.png",
        "https://images.example.test/prefix/right.png",
    ]);
    context.generateBBCode();
    assert.equal(
        context.textArea.value,
        "[comparison=left, right]\n" +
            "https://images.example.test/prefix/left%20%231.png\n" +
            "https://images.example.test/prefix/right.png\n" +
            "[/comparison]",
    );
});

test("failed cross-origin solarization restores the normal public image", () => {
    const imageUrl = "https://images.example.test/image.png";
    const context = viewerContext([imageUrl]);

    context.updateDisplay();
    assert.equal(context.solarizationInProgress, true);
    assert.equal(context.images[0].src, imageUrl);
    context.images[0].onerror();
    assert.equal(context.isSolarized, false);
    assert.equal(context.solarizationInProgress, false);
    assert.equal(context.currentImage.src, imageUrl);
});

for (const solarized of [false, true]) {
    test(`empty comparisons do not throw with solarization ${solarized}`, () => {
        const context = viewerContext([]);
        context.isSolarized = solarized;
        context.currentImage.src = "previous-image.png";
        context.updateDisplay();
        assert.equal(context.currentImage.src, undefined);
        assert.equal(context.images.length, 0);
    });
}

test("display clamps an out-of-range selection before resolving its URL", () => {
    const context = viewerContext(["/uploads/left.png", "/uploads/right.png"]);
    context.isSolarized = false;
    context.absoluteIndex = 10;
    context.updateDisplay();
    assert.equal(context.absoluteIndex, 1);
    assert.equal(context.currentImage.src, "/uploads/right.png");
});

test("a late solarization failure does not replace the newly selected image", () => {
    const context = viewerContext(["/uploads/left.png", "/uploads/right.png"]);
    context.updateDisplay();
    const pendingImage = context.images[0];
    context.isSolarized = false;
    context.absoluteIndex = 1;
    context.updateDisplay();
    pendingImage.onerror();
    assert.equal(context.currentImage.src, "/uploads/right.png");
    assert.equal(context.currentImageInfoSpan.textContent, "right.png []");
    assert.equal(context.solarizationInProgress, false);
});

test("a late solarization success does not overwrite a disabled/current selection", () => {
    const context = viewerContext(["/uploads/left.png", "/uploads/right.png"]);
    context.updateDisplay();
    const pendingImage = context.images[0];
    context.isSolarized = false;
    context.absoluteIndex = 1;
    context.updateDisplay();
    pendingImage.onload();
    assert.equal(context.currentImage.src, "/uploads/right.png");
    assert.equal(context.solarizedImageCache.size, 0);
    assert.equal(context.solarizationInProgress, false);
});

test("a late solarization load starts work for the latest selected image", () => {
    const context = viewerContext(["/uploads/left.png", "/uploads/right.png"]);
    context.updateDisplay();
    const pendingImage = context.images[0];
    context.absoluteIndex = 1;
    pendingImage.onload();
    assert.equal(context.images.length, 2);
    assert.equal(context.images[1].src, "/uploads/right.png");
    assert.equal(context.solarizationInProgress, true);
});
