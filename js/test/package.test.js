const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const pkg = require("../src/index.js");
const SPEC = path.resolve(__dirname, "..", "..", "spec");

test("version is set", () => {
  assert.ok(pkg.version);
});

test("shared spec is reachable", () => {
  const walk = (dir) =>
    fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
      d.isDirectory() ? walk(path.join(dir, d.name)) : d.name.endsWith(".yaml") ? [d.name] : []
    );
  assert.ok(walk(path.join(SPEC, "fixtures")).length > 0, "the shared fixture corpus in spec/fixtures is missing");
});
