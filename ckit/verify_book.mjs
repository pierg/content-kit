/* verify_book.mjs — page checker for a Library book
     1. tag balance for structural tags
     2. every inline <script> parses AND runs against a DOM stub
     3. local hrefs/anchors resolve across the chapter set
   Run from repo root:
     node engine/verify_book.mjs
     node engine/verify_book.mjs content/books/proofs-forever
*/
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname, resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const ENGINE = dirname(fileURLToPath(import.meta.url));

/* Resolve the lab root the same way engine/paths.py does, or a vendored kit looks for
   the book inside itself. The kit lives at <lab>/kit/, so ENGINE/.. is the KIT root,
   not the lab root. Order: $LAB_ROOT, then the nearest ancestor holding lab.json, then
   the kit root's parent when the kit root is named "kit", then the kit root itself. */
function labRoot() {
  if (process.env.LAB_ROOT) return resolve(process.env.LAB_ROOT);
  let dir = resolve(ENGINE, "..");
  const kitRoot = dir;
  for (let d = dir; ; d = dirname(d)) {
    if (existsSync(join(d, "lab.json"))) return d;
    if (dirname(d) === d) break;
  }
  return basename(kitRoot) === "kit" ? dirname(kitRoot) : kitRoot;
}
const LIB_ROOT = labRoot();
const bookArg = process.argv[2] || "content/books/proofs-forever";
const BOOK = resolve(LIB_ROOT, bookArg);
if (!existsSync(BOOK)) {
  console.error(`book not found: ${BOOK}`);
  process.exit(1);
}
process.chdir(BOOK);

const labsNanolab = join(BOOK, "labs/nanolab.js");
const labsRotlab = join(BOOK, "labs/rotlab.js");
const recordJs = join(BOOK, "assets/record.js");
if (existsSync(labsNanolab)) await import(labsNanolab);
if (existsSync(labsRotlab)) await import(labsRotlab);

globalThis.window = globalThis;
if (existsSync(recordJs)) {
  vm.runInThisContext(readFileSync(recordJs, "utf8"), { filename: "assets/record.js" });
}

const files = process.argv.length > 3
  ? process.argv.slice(3)
  : readdirSync(".").filter(f => f.endsWith(".html"));

let problems = 0;
const say = (f, msg) => { problems++; console.error(`✗ ${f}: ${msg}`); };

function makeEl() {
  const el = {
    innerHTML: "", textContent: "", value: "0", disabled: false,
    dataset: new Proxy({}, { get: () => "0" }),
    style: {}, classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    setAttribute() {}, getAttribute() { return ""; },
    addEventListener() {}, appendChild() {}, insertBefore() {},
    querySelector() { return makeEl(); },
    querySelectorAll() { const a = []; a.forEach = () => {}; return a; },
    closest() { return null; }
  };
  return el;
}
function runScripts(file, html) {
  const scripts = [...html.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  scripts.forEach((src, i) => {
    const sandbox = {
      window: globalThis, NANOLAB: globalThis.NANOLAB, ROTLAB: globalThis.ROTLAB,
      RECORD: globalThis.RECORD, console,
      hbStepper: cfg => { cfg.render(0); return { go() {}, get: () => 0 }; },
      document: {
        getElementById: () => makeEl(),
        querySelector: () => makeEl(),
        querySelectorAll: () => { const a = []; a.forEach = () => {}; return a; },
        addEventListener: (ev, fn) => { if (ev === "DOMContentLoaded") fn(); },
        createElement: () => makeEl(),
        body: makeEl()
      }
    };
    sandbox.window.hbStepper = sandbox.hbStepper;
    try {
      vm.runInNewContext(src, sandbox, { filename: `${file}#script${i + 1}`, timeout: 30000 });
    } catch (e) {
      say(file, `inline script ${i + 1} failed: ${e.message}`);
    }
  });
  return scripts.length;
}

function tagBalance(file, html) {
  for (const tag of ["section", "table", "figure", "svg", "details", "blockquote", "script", "div"]) {
    const open = (html.match(new RegExp(`<${tag}(\\s|>)`, "g")) || []).length;
    const close = (html.match(new RegExp(`</${tag}>`, "g")) || []).length;
    if (open !== close) say(file, `<${tag}> open ${open} ≠ close ${close}`);
  }
}

const ids = {}, links = [];
for (const f of files) {
  const html = readFileSync(f, "utf8");
  ids[f] = new Set([...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]));
  for (const m of html.matchAll(/href="([^"#:]*)(#[^"]*)?"/g)) {
    if (m[1].startsWith("http") || m[1].startsWith("mailto") || m[1].startsWith("/")) continue;
    links.push({ from: f, file: m[1] || f, anchor: m[2] ? m[2].slice(1) : null });
  }
}
for (const f of files) {
  const html = readFileSync(f, "utf8");
  tagBalance(f, html);
  const n = runScripts(f, html);
  console.log(`· ${f}: ${n} inline scripts ran`);
}
for (const l of links) {
  if (!(l.file in ids)) {
    try { readFileSync(l.file); } catch { say(l.from, `broken link → ${l.file}`); }
    continue;
  }
  if (l.anchor && !ids[l.file].has(l.anchor)) say(l.from, `broken anchor → ${l.file}#${l.anchor}`);
}

console.log(problems ? `\n${problems} problem(s)` : "\nall pages clean");
if (problems) process.exit(1);
