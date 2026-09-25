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

/* Resolve the repo root the same way ckit/paths.py does, or a vendored kit looks for
   the book inside itself. Order: $CKIT_ROOT (or its old name $LAB_ROOT), then the nearest
   ancestor holding kit.json (or the deprecated lab.json), then the kit root's parent when
   the kit root is named "kit", then the kit root itself. */
function repoRoot() {
  const env = process.env.CKIT_ROOT || process.env.LAB_ROOT;
  if (env) return resolve(env);
  let dir = resolve(ENGINE, "..");
  const kitRoot = dir;
  for (let d = dir; ; d = dirname(d)) {
    if (existsSync(join(d, "kit.json")) || existsSync(join(d, "lab.json"))) return d;
    if (dirname(d) === d) break;
  }
  return basename(kitRoot) === "kit" ? dirname(kitRoot) : kitRoot;
}
const LIB_ROOT = repoRoot();
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

/* The stand-in DOM a chapter's inline scripts run against. It answers what a widget builds
   with — elements (HTML and SVG), text nodes, fragments, classes, attributes, styles, events,
   observers, timers — with inert stand-ins, so a script that works in a browser runs here too.
   An element answers any method or property it does not know with another inert stand-in, so a
   widget is never failed for reaching a corner of the DOM this file does not model. What still
   fails: a syntax error, a name that is not defined, and an exception the page's own logic
   throws. */
function inert() {
  const handler = {
    get(target, key) {
      if (key === Symbol.iterator) return function* () {};
      if (key === Symbol.toPrimitive) return () => 0;
      if (key === "length") return 0;
      if (key === "then") return undefined;  // never mistaken for a promise
      if (typeof key === "symbol") return undefined;
      return inert();
    },
    apply() { return inert(); },
    construct() { return inert(); },
    set() { return true; }
  };
  return new Proxy(function () {}, handler);
}
function makeEl() {
  const el = {
    innerHTML: "", textContent: "", value: "0", disabled: false, hidden: false, checked: false,
    dataset: new Proxy({}, { get: (o, k) => (k in o ? o[k] : "0") }),
    style: { setProperty() {}, removeProperty() {}, getPropertyValue() { return ""; } },
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; }, replace() {} },
    children: [], childNodes: [],  // parentNode, firstChild, … answer with an inert stand-in
    setAttribute() {}, getAttribute() { return ""; }, removeAttribute() {}, hasAttribute() { return false; },
    addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; },
    appendChild(c) { return c; }, insertBefore(c) { return c; }, removeChild(c) { return c; }, replaceChild(c) { return c; },
    append() {}, prepend() {}, remove() {}, replaceChildren() {}, before() {}, after() {},
    insertAdjacentElement(_, c) { return c; }, insertAdjacentHTML() {}, cloneNode() { return makeEl(); },
    querySelector() { return makeEl(); },
    querySelectorAll() { return []; },
    getElementsByTagName() { return []; }, getElementsByClassName() { return []; },
    closest() { return null; }, matches() { return false; }, contains() { return false; },
    focus() {}, blur() {}, click() {}, scrollIntoView() {}, scrollTo() {},
    getBoundingClientRect() { return { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 }; },
    getBBox() { return { x: 0, y: 0, width: 0, height: 0 }; }, getTotalLength() { return 0; },
    getPointAtLength() { return { x: 0, y: 0 }; },
    offsetWidth: 0, offsetHeight: 0, clientWidth: 0, clientHeight: 0, scrollWidth: 0, scrollHeight: 0, scrollTop: 0
  };
  return new Proxy(el, { get: (o, k) => (k in o || typeof k === "symbol" ? o[k] : inert()) });
}
function runScripts(file, html) {
  const scripts = [...html.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  scripts.forEach((src, i) => {
    const Observer = function () { return { observe() {}, unobserve() {}, disconnect() {}, takeRecords() { return []; } }; };
    const Event = function (type, init) { return { type, detail: init && init.detail, preventDefault() {}, stopPropagation() {} }; };
    const sandbox = {
      NANOLAB: globalThis.NANOLAB, ROTLAB: globalThis.ROTLAB, RECORD: globalThis.RECORD, console,
      hbStepper: cfg => { cfg.render(0); return { go() {}, get: () => 0 }; },
      document: {
        readyState: "loading",
        getElementById: () => makeEl(),
        querySelector: () => makeEl(),
        querySelectorAll: () => [],
        getElementsByTagName: () => [], getElementsByClassName: () => [],
        addEventListener: (ev, fn) => { if (ev === "DOMContentLoaded") fn(); },
        removeEventListener() {}, dispatchEvent() { return true; },
        createElement: () => makeEl(),
        createElementNS: () => makeEl(),
        createTextNode: () => makeEl(),
        createDocumentFragment: () => makeEl(),
        createRange: () => makeEl(),
        body: makeEl(), head: makeEl(), documentElement: makeEl(), activeElement: null
      },
      setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
      requestAnimationFrame: () => 0, cancelAnimationFrame() {},
      matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
      getComputedStyle: () => ({ getPropertyValue() { return ""; } }),
      IntersectionObserver: Observer, ResizeObserver: Observer, MutationObserver: Observer,
      CustomEvent: Event, Event, KeyboardEvent: Event,
      addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; },
      localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
      location: { href: "http://localhost/", pathname: "/", hash: "", search: "" },
      navigator: { userAgent: "verify_book", platform: "" },
      innerWidth: 1280, innerHeight: 800, scrollX: 0, scrollY: 0, scrollTo() {}, devicePixelRatio: 1,
      performance: { now: () => 0 }
    };
    sandbox.window = sandbox;
    sandbox.self = sandbox;
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
