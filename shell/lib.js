/* ============================================================================
   Library — shared chrome helpers
   Every page includes:  <link rel="stylesheet" href="/shell/lib.css">
                         <script src="/shell/lib.js" defer></script>
   Book chapter order is discovered into nav.json (`ckit nav`; lint does it too).
   Optional thin overrides live in that book's book.json.
   Agents edit content pages; this file changes rarely and deliberately.

   Every URL the shell builds is root-absolute (/content/…, /shell/…) and goes through
   hbUrl(), which prefixes the site's base path — "/" under `ckit serve`, "/<repo>/" on a
   project site written by `ckit export --base /<repo>/`. The base is read from this
   script's own URL, so nothing needs configuring.

   The chrome — the library rail, the top bar, the page rail, the palette, link peeks — is
   built from /content/catalog.json and inserted OUTSIDE <main>. <main> is the page as its
   author wrote it: the annotation layer anchors quotes in its text, and nothing here
   changes that text (the status pill is a class on the author's own <b>, heading ids are
   attributes). The catalog is cached per site, so the chrome paints with the page and a
   fresh copy replaces it quietly when the library has changed.
   ========================================================================== */

(function () {
  "use strict";

  var BASE = (function () {
    var s = document.currentScript;
    if (!s || !s.src) return "/";
    try {
      return new URL(s.src, location.href).pathname.replace(/shell\/lib\.js$/, "") || "/";
    } catch (e) { return "/"; }
  })();

  function hbUrl(href) {
    if (typeof href !== "string" || href.charAt(0) !== "/" || href.charAt(1) === "/") return href;
    return BASE + href.slice(1);
  }

  /* The site-relative path of this page ("/content/x/"), whatever the base. */
  function sitePath() {
    var p = location.pathname;
    return p.indexOf(BASE) === 0 ? "/" + p.slice(BASE.length) : p;
  }

  window.hbBase = BASE;
  window.hbUrl = hbUrl;

  /* ------------------------------------------------------------ preferences
     Theme (auto · light · dark) and reading face (serif · sans), kept in this browser.
     Applied first, before anything paints that depends on them. */
  var store = {
    get: function (k) { try { return localStorage.getItem("ckit:" + k); } catch (e) { return null; } },
    set: function (k, v) { try { if (v == null) localStorage.removeItem("ckit:" + k); else localStorage.setItem("ckit:" + k, v); } catch (e) {} }
  };
  var root = document.documentElement;
  function applyPrefs() {
    var t = store.get("theme");
    if (t === "light" || t === "dark") root.setAttribute("data-theme", t); else root.removeAttribute("data-theme");
    if (store.get("font") === "sans") root.setAttribute("data-font", "sans"); else root.removeAttribute("data-font");
  }
  applyPrefs();

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function fetchJson(url) {
    return fetch(hbUrl(url), { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }

  /* a JSON object as a map with no prototype: a topic or tag called "constructor" is a key */
  function own(obj) {
    var out = Object.create(null);
    if (obj && typeof obj === "object") Object.keys(obj).forEach(function (k) { out[k] = obj[k]; });
    return out;
  }

  function slugify(t) {
    return String(t).toLowerCase().replace(/<[^>]*>/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
  }

  function titleCase(slug) {
    return String(slug).replace(/[-_]+/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  /* An href (relative, absolute, or root-absolute) as a site path ("/content/x/"), or null
     when it leaves this site. index.html folds into its folder, as every index keys it. */
  function canon(href) {
    try {
      var u = new URL(href, location.href);
      if (u.origin !== location.origin) return null;
      var p = u.pathname;
      if (p.indexOf(BASE) === 0) p = "/" + p.slice(BASE.length);
      return p.replace(/\/index\.html$/, "/");
    } catch (e) { return null; }
  }

  function fmtDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!m) return "";
    try {
      return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    } catch (e) { return iso; }
  }

  var ICONS = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/>',
    browse: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    link: '<path d="M9.5 14.5 14.5 9.5"/><path d="M11 6.5 12.5 5a4 4 0 0 1 5.7 5.7L16.7 12.2"/><path d="M13 17.5 11.5 19a4 4 0 0 1-5.7-5.7L7.3 11.8"/>',
    ext: '<path d="M7 17 17 7"/><path d="M8 7h9v9"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/>',
    auto: '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17" /><path d="M12 3.5a8.5 8.5 0 0 1 0 17Z" fill="currentColor" stroke="none"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    list: '<path d="M9 7h11M9 12h11M9 17h11M4.5 7h.01M4.5 12h.01M4.5 17h.01"/>',
    record: '<path d="M6 3.5h9l3.5 3.5v13.5H6z"/><path d="M14.5 3.5V7.5H18.5"/><path d="M9 12h6M9 15.5h6"/>',
    review: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4h-1A2.5 2.5 0 0 1 4 13.5z"/><path d="m8.5 9.5 2.5 2.5 4.5-4.5"/>'
  };
  function icon(name) {
    return '<svg class="hb-ico" viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[name] || ICONS.link) + "</svg>";
  }

  /* Tab groups: <section data-hbtabs data-active="a">
                   <button class="tbtn" data-tab="a">…</button> …
                   <div data-pane="a">…</div> …
     Panes whose data-pane ≠ data-active are hidden. */
  function initTabs() {
    document.querySelectorAll("[data-hbtabs]").forEach(function (w) {
      function render() {
        var act = w.dataset.active;
        w.querySelectorAll("[data-tab]").forEach(function (b) {
          b.classList.toggle("active", b.dataset.tab === act);
        });
        w.querySelectorAll("[data-pane]").forEach(function (p) {
          p.style.display = p.dataset.pane === act ? "" : "none";
        });
      }
      w.addEventListener("click", function (e) {
        var b = e.target.closest("[data-tab]");
        if (!b || !w.contains(b)) return;
        w.dataset.active = b.dataset.tab;
        render();
      });
      render();
    });
  }

  /* Concept popover: <a class="defn-link" href="/content/concepts/SLUG/">TERM</a>
     shows the target's first <blockquote class="defn"> on hover / focus.
     Click still navigates. Fetches are cached per URL for the session. */
  var defnCache = Object.create(null);
  var defnPop = null;
  var defnHoverTimer = null;
  var defnHideTimer = null;
  var defnAnchor = null;

  function defnFetch(url) {
    if (defnCache[url]) return defnCache[url];
    defnCache[url] = fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) return null;
        var m = html.match(/<blockquote[^>]*class="[^"]*\bdefn\b[^"]*"[\s\S]*?<\/blockquote>/i);
        return m ? m[0] : null;
      })
      .catch(function () { return null; });
    return defnCache[url];
  }

  function ensureDefnPop() {
    if (defnPop) return defnPop;
    defnPop = document.createElement("div");
    defnPop.className = "defn-pop";
    defnPop.setAttribute("role", "tooltip");
    defnPop.hidden = true;
    defnPop.addEventListener("pointerenter", function () {
      if (defnHideTimer) { clearTimeout(defnHideTimer); defnHideTimer = null; }
    });
    defnPop.addEventListener("pointerleave", scheduleDefnHide);
    document.body.appendChild(defnPop);
    return defnPop;
  }

  function placePop(pop, anchor) {
    var rect = anchor.getBoundingClientRect();
    var margin = 8;
    /* Fall back to a sensible viewport if the browser reports 0 (headless / detached). */
    var vw = window.innerWidth || document.documentElement.clientWidth || 1024;
    var vh = window.innerHeight || document.documentElement.clientHeight || 768;
    var maxW = Math.max(240, Math.min(420, vw - 2 * margin));
    pop.style.maxWidth = maxW + "px";
    pop.style.visibility = "hidden";
    pop.hidden = false;
    var pw = pop.offsetWidth;
    var ph = pop.offsetHeight;
    var left = rect.left + window.scrollX;
    var minLeft = margin + window.scrollX;
    var maxLeft = window.scrollX + Math.max(vw - pw - margin, minLeft);
    left = Math.min(Math.max(minLeft, left), maxLeft);
    var top = rect.bottom + window.scrollY + 6;
    if (top + ph > window.scrollY + vh - margin && rect.top - ph - 6 > margin) {
      top = rect.top + window.scrollY - ph - 6;
    }
    pop.style.left = left + "px";
    pop.style.top = top + "px";
    pop.style.visibility = "";
  }

  function showDefnFor(anchor) {
    defnAnchor = anchor;
    var url = anchor.getAttribute("href");
    if (!url) return;
    hidePeek();
    var pop = ensureDefnPop();
    pop.innerHTML = '<span class="defn-pop-name muted">Loading…</span>';
    placePop(pop, anchor);
    defnFetch(url).then(function (blockHtml) {
      if (defnAnchor !== anchor) return;
      if (!blockHtml) {
        pop.innerHTML = '<span class="defn-pop-name muted">No definition of record found at ' +
          escapeHtml(url) + '</span>';
      } else {
        pop.innerHTML = blockHtml;
      }
      placePop(pop, anchor);
    });
  }

  function scheduleDefnHide() {
    if (defnHideTimer) clearTimeout(defnHideTimer);
    defnHideTimer = setTimeout(function () {
      if (!defnPop) return;
      defnPop.hidden = true;
      defnAnchor = null;
    }, 180);
  }

  function initDefnLinks() {
    document.addEventListener("pointerover", function (e) {
      var a = e.target.closest && e.target.closest("a.defn-link");
      if (!a) return;
      if (defnHideTimer) { clearTimeout(defnHideTimer); defnHideTimer = null; }
      if (defnHoverTimer) clearTimeout(defnHoverTimer);
      defnHoverTimer = setTimeout(function () { showDefnFor(a); }, 120);
    });
    document.addEventListener("pointerout", function (e) {
      var a = e.target.closest && e.target.closest("a.defn-link");
      if (!a) return;
      if (defnHoverTimer) { clearTimeout(defnHoverTimer); defnHoverTimer = null; }
      var to = e.relatedTarget;
      if (defnPop && to && (defnPop.contains(to) || defnPop === to)) return;
      scheduleDefnHide();
    });
    document.addEventListener("focusin", function (e) {
      var a = e.target.closest && e.target.closest("a.defn-link");
      if (a) showDefnFor(a);
    });
    document.addEventListener("focusout", function (e) {
      var a = e.target.closest && e.target.closest("a.defn-link");
      if (a) scheduleDefnHide();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && defnPop && !defnPop.hidden) {
        defnPop.hidden = true;
        defnAnchor = null;
      }
    });
  }

  /* ----------------------------------------------------------------- indices
     The catalog drives the chrome; the search index (titles, summaries, headings, tags) and
     the backlinks are fetched only when something needs them, once per page. */
  var catalogCache = null;
  function catalogPromise() {  /* one fetch of the catalog per page, shared by every caller */
    if (!catalogCache) {
      catalogCache = fetch(hbUrl("/content/catalog.json"), { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.text() : null; })
        .then(function (txt) {
          if (!txt) return null;
          store.set("catalog:" + BASE, txt);
          return JSON.parse(txt);
        })
        .catch(function () { return null; });
    }
    return catalogCache;
  }
  window.hbCatalog = catalogPromise;

  function cachedCatalog() {
    var txt = store.get("catalog:" + BASE);
    if (!txt) return null;
    try { return JSON.parse(txt); } catch (e) { return null; }
  }

  var searchCache = null;
  function searchIndex() {
    if (!searchCache) searchCache = fetchJson("/content/search-index.json").catch(function () { return []; });
    return searchCache;
  }
  var backlinksCache = null;
  function backlinksIndex() {
    if (!backlinksCache) backlinksCache = fetchJson("/content/backlinks.json").catch(function () { return {}; });
    return backlinksCache;
  }

  /* Backlinks: any <ul data-backlinks> gets populated from
     /content/backlinks.json keyed by the page's site path. */
  function initBacklinks() {
    var lists = document.querySelectorAll("ul[data-backlinks]");
    if (!lists.length) return;
    var here = sitePath();
    if (here.endsWith("/index.html")) here = here.slice(0, -"index.html".length);
    backlinksIndex().then(function (data) {
      var hits = (data && data[here]) || [];
      lists.forEach(function (ul) {
        if (!hits.length) {
          ul.innerHTML = '<li class="muted">No inbound links yet.</li>';
          return;
        }
        ul.innerHTML = hits.map(function (b) {
          return '<li><span class="hb-kind hb-kind-' + escapeAttr(b.kind) + '">' +
            escapeHtml(b.kind) + '</span> ' +
            '<a href="' + escapeAttr(hbUrl(b.href)) + '">' + escapeHtml(b.title) + '</a></li>';
        }).join("");
      });
    }).catch(function () {
      lists.forEach(function (ul) {
        ul.innerHTML = '<li class="muted">Backlink index unavailable.</li>';
      });
    });
  }

  /* Annotation layer: loaded only when the serving engine answers the ping, so a page on a
     static host never grows the affordance and stays portable. See shell/annotate.js. */
  function initAnnotate() {
    if (!document.querySelector("main")) return;
    fetch(hbUrl("/__annotations/ping"), { credentials: "same-origin", cache: "no-store" })
      .then(function (r) {
        if (!r.ok) return;
        window.hbEngine = true;
        addReviewLink();
        var s = document.createElement("script");
        s.src = hbUrl("/shell/annotate.js");
        s.defer = true;
        document.head.appendChild(s);
      })
      .catch(function () {});
  }

  /* Review — every annotation thread in the library — is a shell page only the engine can feed
     (the index it reads stays home with the sidecars), so its rail item arrives with the ping
     rather than with the catalog, once the library has any thread at all. Whichever finishes
     first, the ping or the chrome, adds it: navHtml when the chrome comes second, this when it
     came first. */
  function addReviewLink() {
    catalogPromise().then(function (cat) {
      var t = cat && cat.threads;
      if (!t || !t.total) return;
      var nav = document.querySelector(".hb-side-nav");
      if (!nav || nav.querySelector("[data-hb-review]")) return;
      var here = sitePath() === "/shell/review.html";
      var li = document.createElement("li");
      li.innerHTML = '<a href="' + escapeAttr(hbUrl("/shell/review.html")) + '" data-hb-review' + (here ? ' class="here" aria-current="page"' : "") +
        ' title="' + t.open + " waiting · " + t.noted + ' noted">' + icon("review") + "<span>Review</span>" +
        (t.open ? '<span class="hb-ext">' + t.open + "</span>" : "") + "</a>";
      // beside Chronicle, where navHtml puts it: after the last of the shell's own items
      var core = [hbUrl("/"), hbUrl("/shell/search.html"), hbUrl("/shell/chronicle.html")];
      var after = null;
      Array.prototype.forEach.call(nav.children, function (item) {
        var a = item.querySelector("a");
        if (a && core.indexOf(a.getAttribute("href")) !== -1) after = item;
      });
      if (after && after.nextSibling) nav.insertBefore(li, after.nextSibling); else nav.appendChild(li);
    });
  }

  /* Reference links: ids matching a kit.json `refs` pattern become links, e.g.
       "refs": [{"pattern": "Q-\\d+", "href": "/shell/record.html?p=QUESTIONS.md#{id}"}]
     Text inside inline <code> is linked; <pre> blocks, existing links, headings, scripts
     and styles are left alone, and so is a qualified id (`other:Q-3`, another repo's), and
     anything inside an element marked data-norefs (a shell page's own rendered lists).
     Idempotent — a second pass skips ids already inside an <a>. Runs on content pages, and
     through hbLinkRefs() on anything a shell page renders later (the record viewer). */
  var REF_SKIP = { A: 1, PRE: 1, SCRIPT: 1, STYLE: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1 };

  function compileRefs(refs) {
    var out = [];
    (refs || []).forEach(function (r) {
      try {
        out.push({ re: new RegExp("^(?:" + r.pattern + ")$"), src: r.pattern, href: r.href });
      } catch (e) { /* ckit check reports a bad pattern; the shell just skips it */ }
    });
    return out;
  }

  function linkRefs(rootEl, refs) {
    if (!rootEl || !refs.length || typeof document.createTreeWalker !== "function") return;
    var any = new RegExp("\\b(" + refs.map(function (r) { return "(?:" + r.src + ")"; }).join("|") + ")\\b", "g");
    var walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var v = node.nodeValue;
        if (!v) return NodeFilter.FILTER_REJECT;
        for (var p = node.parentNode; p && p !== rootEl; p = p.parentNode) {
          if (p.nodeType === 1 && (REF_SKIP[p.tagName] || p.hasAttribute("data-norefs"))) return NodeFilter.FILTER_REJECT;
        }
        any.lastIndex = 0;
        return any.test(v) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    var targets = [];
    var node;
    while ((node = walker.nextNode())) targets.push(node);
    targets.forEach(function (t) {
      var text = t.nodeValue;
      var frag = document.createDocumentFragment();
      var last = 0, m;
      any.lastIndex = 0;
      while ((m = any.exec(text))) {
        var idx = m.index;
        if (idx > 0 && text.charAt(idx - 1) === ":") continue; /* qualified: another repo's id */
        var ref = null;
        for (var i = 0; i < refs.length; i++) if (refs[i].re.test(m[1])) { ref = refs[i]; break; }
        if (!ref) continue;
        if (idx > last) frag.appendChild(document.createTextNode(text.slice(last, idx)));
        var a = document.createElement("a");
        a.className = "rec-ref";
        a.setAttribute("href", hbUrl(ref.href.split("{id}").join(m[1])));
        a.textContent = m[1];
        frag.appendChild(a);
        last = idx + m[1].length;
      }
      if (last === 0) return;
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      t.parentNode.replaceChild(frag, t);
    });
  }

  /* hbLinkRefs(root) — for shell pages that render content after load. hbRefs() resolves to
     the compiled refs, so a page can also use them (the record viewer anchors headings on them). */
  window.hbRefs = function () {
    return catalogPromise().then(function (c) { return compileRefs(c && c.refs); });
  };
  window.hbLinkRefs = function (rootEl) {
    return window.hbRefs().then(function (refs) { linkRefs(rootEl, refs); });
  };
  window.hbLinkRecordIds = window.hbLinkRefs;  /* the 0.3 name, kept for one minor version */

  /* Generic stepper: hbStepper({el, count, render}) wires ⟲/◀/▶ buttons marked
     data-step="reset|prev|next" inside el, calls render(i) on every change. */
  window.hbStepper = function (cfg) {
    var i = 0;
    function go(n) {
      i = Math.max(0, Math.min(cfg.count - 1, n));
      cfg.el.querySelectorAll("[data-step]").forEach(function (b) {
        if (b.dataset.step === "prev") b.disabled = i === 0;
        if (b.dataset.step === "next") b.disabled = i === cfg.count - 1;
      });
      cfg.render(i);
    }
    cfg.el.addEventListener("click", function (e) {
      var b = e.target.closest("[data-step]");
      if (!b) return;
      if (b.dataset.step === "reset") go(0);
      if (b.dataset.step === "prev") go(i - 1);
      if (b.dataset.step === "next") go(i + 1);
    });
    go(0);
    return { go: go, get: function () { return i; } };
  };

  function hereFile() {
    return location.pathname.split("/").pop() || "index.html";
  }

  function bookRoot() {
    var m = sitePath().match(/^(\/content\/books\/[^/]+)\//);
    return m ? m[1] + "/" : null;
  }

  /* ------------------------------------------------------------ the library
     The catalog as a model: every page with its group, kind and topic; the topics with
     their labels and hubs. */
  function model(cat) {
    var groups = (cat && cat.groups) || [];
    var pages = [];
    var byHref = Object.create(null);
    var byKey = Object.create(null);
    groups.forEach(function (g) {
      byKey[g.key] = g;
      (cat[g.key] || []).forEach(function (it) {
        var p = { title: it.title, href: it.href, slug: it.slug, topic: it.topic || null, tags: it.tags || [],
                  updated: it.updated || null, created: it.created || null, group: g, kind: g.kind };
        pages.push(p);
        byHref[p.href] = p;
      });
    });
    var labels = own((cat && cat.topics) || {});
    var order = Object.keys(labels);
    pages.forEach(function (p) { if (p.topic && order.indexOf(p.topic) === -1) order.push(p.topic); });
    var topics = order.map(function (slug) {
      var ps = pages.filter(function (p) { return p.topic === slug; });
      var hub = null;
      ps.forEach(function (p) { if (!hub && p.kind === "hub") hub = p; });
      return { slug: slug, label: labels[slug] || titleCase(slug), pages: ps, hub: hub };
    }).filter(function (t) { return t.pages.length; });
    return { cat: cat || {}, groups: groups, pages: pages, byHref: byHref, byKey: byKey, topics: topics,
             site: (cat && cat.site) || {} };
  }

  /* where this page sits: its catalog entry (a chapter answers with its book), its group */
  function locate(lib) {
    var here = canon(location.href) || sitePath();
    var m = here.match(/^\/content\/([^/]+)\//);
    var group = m ? lib.byKey[m[1]] || null : null;
    var page = lib.byHref[here] || null;
    var book = null;
    var root = bookRoot();
    if (root) book = lib.byHref[root] || null;
    return { href: here, group: group, page: page || book, book: book, chapter: !!(root && here !== root) };
  }

  /* ----------------------------------------------------------- chrome: rail */
  var openState = (function () {
    try { return own(JSON.parse(store.get("open:" + BASE) || "{}")); } catch (e) { return Object.create(null); }
  })();
  function isOpen(key, fallback) { return Object.prototype.hasOwnProperty.call(openState, key) ? !!openState[key] : fallback; }

  function linkItem(p, where, extraClass) {
    var here = where.href === p.href || (where.book && where.book.href === p.href);
    return '<li><a href="' + escapeAttr(hbUrl(p.href)) + '"' +
      (here ? ' class="here' + (extraClass ? " " + extraClass : "") + '" aria-current="page"' : (extraClass ? ' class="' + extraClass + '"' : "")) +
      ' title="' + escapeAttr(p.title) + '">' + escapeHtml(p.title) + "</a></li>";
  }

  function disclosure(key, label, count, openByDefault, inner, cls) {
    return '<li><details data-key="' + escapeAttr(key) + '"' + (cls ? ' class="' + cls + '"' : "") +
      (isOpen(key, openByDefault) ? " open" : "") + '><summary><span class="hb-t-name">' + escapeHtml(label) +
      '</span><span class="hb-count">' + count + "</span></summary><ul>" + inner + "</ul></details></li>";
  }

  function treeHtml(lib, where) {
    var out = [];
    if (lib.topics.length) {
      var single = lib.topics.length === 1;
      out.push('<div class="hb-side-label">Topics</div><ul class="hb-tree">');
      lib.topics.forEach(function (t) {
        var mine = where.page && where.page.topic === t.slug;
        var inner = [];
        if (t.hub) inner.push(linkItem({ title: "Overview", href: t.hub.href }, where, "hb-t-hub"));
        lib.groups.forEach(function (g) {
          var ps = t.pages.filter(function (p) { return p.group === g && p !== t.hub; });
          if (!ps.length) return;
          var here = where.group === g && mine;
          inner.push(disclosure("t:" + t.slug + ":" + g.key, g.label, ps.length, here || ps.length <= 4,
            ps.map(function (p) { return linkItem(p, where); }).join("")));
        });
        out.push(disclosure("t:" + t.slug, t.label, t.pages.length, mine || single, inner.join(""), "hb-t-topic"));
      });
      out.push("</ul>");
      var loose = lib.pages.filter(function (p) { return !p.topic; });
      if (loose.length) {
        out.push('<div class="hb-side-label">Not on a topic</div><ul class="hb-tree">');
        lib.groups.forEach(function (g) {
          var ps = loose.filter(function (p) { return p.group === g; });
          if (ps.length) out.push(disclosure("g:" + g.key, g.label, ps.length, where.group === g,
            ps.map(function (p) { return linkItem(p, where); }).join("")));
        });
        out.push("</ul>");
      }
    } else {
      out.push('<div class="hb-side-label">Library</div><ul class="hb-tree">');
      lib.groups.forEach(function (g) {
        var ps = lib.pages.filter(function (p) { return p.group === g; });
        if (ps.length) out.push(disclosure("g:" + g.key, g.label, ps.length, where.group === g || ps.length <= 6,
          ps.map(function (p) { return linkItem(p, where); }).join("")));
      });
      out.push("</ul>");
    }
    var rec = lib.cat.record || [];
    if (rec.length) {
      var onRecord = sitePath() === "/shell/record.html";
      var files = rec.map(function (r) {
        var here = onRecord && location.search === "?p=" + r.path;
        var name = String(r.title || r.path).replace(/\s+[—–-]\s+(LIVE|HISTORICAL|PARKED|RETIRED|FROZEN|DRAFT)\s*$/, "");
        return '<li><a href="' + escapeAttr(hbUrl(r.href)) + '"' + (here ? ' class="here" aria-current="page"' : "") +
          ' title="' + escapeAttr(r.path) + '">' + escapeHtml(name) + "</a></li>";
      }).join("");
      out.push('<div class="hb-side-label">Record</div><ul class="hb-tree">');
      out.push(rec.length <= 4 ? files : disclosure("record", "Files", rec.length, onRecord, files));
      out.push("</ul>");
    }
    return out.join("");
  }

  function navHtml(lib) {
    var here = sitePath();
    var items = [{ label: "Home", href: "/", icon: "home" },
                 { label: "Browse", href: "/shell/search.html", icon: "browse" }];
    if ((lib.cat.record || []).length) items.push({ label: "Chronicle", href: "/shell/chronicle.html", icon: "clock" });
    var th = lib.cat.threads;
    if (window.hbEngine && th && th.total) {  // the ping answered before the chrome was built
      items.push({ label: "Review", href: "/shell/review.html", icon: "review", review: true,
                   title: th.open + " waiting · " + th.noted + " noted" });
    }
    (lib.cat.links || []).forEach(function (l) { items.push({ label: l.label, href: l.href, title: l.title, icon: "link" }); });
    return '<ul class="hb-side-nav">' + items.map(function (it) {
      var ext = /^[a-z]+:\/\//i.test(it.href);
      var cur = !ext && (here === it.href || (it.href === "/" && here === "/index.html"));
      return '<li><a href="' + escapeAttr(ext ? it.href : hbUrl(it.href)) + '"' + (cur ? ' class="here" aria-current="page"' : "") +
        (it.review ? " data-hb-review" : "") +
        (it.title ? ' title="' + escapeAttr(it.title) + '"' : "") + ">" + icon(ext ? "link" : it.icon) +
        "<span>" + escapeHtml(it.label) + "</span>" + (ext ? '<span class="hb-ext">↗</span>' : "") + "</a></li>";
    }).join("") + "</ul>";
  }

  var THEMES = ["auto", "light", "dark"];
  function themeButton() {
    var t = store.get("theme") || "auto";
    var ic = t === "dark" ? "moon" : t === "light" ? "sun" : "auto";
    return '<button type="button" class="hb-iconbtn" data-hb-theme title="Theme: ' + t + ' (click to change)">' + icon(ic) + "</button>";
  }
  function fontButton() {
    var f = store.get("font") === "sans" ? "sans" : "serif";
    return '<button type="button" class="hb-iconbtn" data-hb-font title="Reading face: ' + f + ' (click to change)">' +
      '<span style="font:600 13px/1 ' + (f === "sans" ? "var(--font-serif)" : "var(--font-sans)") + '">Aa</span></button>';
  }

  function sideHtml(lib, where) {
    var name = lib.site.name || "Library";
    var mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
    return '<div class="hb-side-scroll">' +
      '<div class="hb-side-head"><a class="hb-side-lib" href="' + hbUrl("/") + '" title="' + escapeAttr(name) + '">' + escapeHtml(name) + "</a></div>" +
      '<button type="button" class="hb-find" data-hb-palette>' + icon("search") + '<span class="hb-find-label">Search</span>' +
      '<span class="hb-kbd">' + (mac ? "⌘" : "Ctrl") + " K</span></button>" +
      navHtml(lib) + treeHtml(lib, where) +
      "</div>" +
      '<div class="hb-side-foot">' + themeButton() + fontButton() + '<span class="hb-spacer"></span></div>';
  }

  /* only what the reader opens or closes is remembered — a group the tree opens by default
     (the current page's) fires "toggle" too, and must not become sticky */
  function wireTree(aside) {
    aside.addEventListener("click", function (e) {
      var sm = e.target.closest && e.target.closest("summary");
      var d = sm && sm.parentNode;
      if (!d || d.tagName !== "DETAILS" || !d.dataset.key || !aside.contains(d)) return;
      openState[d.dataset.key] = !d.open;  /* the state the click is about to give it */
      store.set("open:" + BASE, JSON.stringify(openState));
    });
  }

  /* --------------------------------------------------------- chrome: top bar */
  function crumbsHtml(lib, where) {
    var bits = ['<a href="' + hbUrl("/") + '">' + escapeHtml(lib.site.name || "Home") + "</a>"];
    var sep = '<span class="hb-sep">/</span>';
    var p = where.page;
    if (p && p.topic) {
      var t = null;
      lib.topics.forEach(function (x) { if (x.slug === p.topic) t = x; });
      if (t) bits.push(t.hub && t.hub !== p ? '<a href="' + escapeAttr(hbUrl(t.hub.href)) + '">' + escapeHtml(t.label) + "</a>"
                                           : "<span>" + escapeHtml(t.label) + "</span>");
    }
    if (where.group && !(p && p.kind === "hub")) {
      bits.push('<a href="' + escapeAttr(hbUrl("/shell/search.html?kind=" + encodeURIComponent(where.group.kind))) + '">' +
        escapeHtml(where.group.label) + "</a>");
    } else if (!where.group && sitePath().indexOf("/shell/") === 0) {
      bits.push('<span class="hb-crumb-here">' + escapeHtml((document.title || "").split(" — ")[0]) + "</span>");
    }
    return '<nav class="hb-crumbs" aria-label="Breadcrumbs">' + bits.join(sep) + "</nav>";
  }

  function bookHtml(book) {
    var cur = hereFile();
    var bits = ['<a class="hb-book-home' + (cur === "index.html" ? " here" : "") + '" href="' + escapeAttr(book.homeHref || "index.html") + '">' +
      escapeHtml(book.homeLabel || "Book") + "</a>"];
    (book.chapters || []).forEach(function (c) {
      if (c.file === "index.html") return;
      if (c.status === "planned" && c.file !== cur) {
        bits.push('<a class="hb-planned" title="' + escapeAttr(c.title) + ' (planned)" onclick="return false" href="#">' + escapeHtml(c.label) + "</a>");
      } else {
        bits.push('<a href="' + escapeAttr(c.file) + '"' + (c.file === cur ? ' class="here" aria-current="page"' : "") +
          ' title="' + escapeAttr(c.title) + '">' + escapeHtml(c.label) + "</a>");
      }
    });
    return '<nav class="hb-book" aria-label="Chapters">' + bits.join("") + "</nav>";
  }

  function readingMinutes(main) {  /* the prose, not a widget's script or style */
    var words = 0, w = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) { return /^(SCRIPT|STYLE|TEMPLATE)$/.test(n.parentNode.nodeName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; }
    }), n;
    while ((n = w.nextNode())) words += n.nodeValue.split(/\s+/).filter(Boolean).length;
    return Math.max(1, Math.round(words / 230));
  }

  /* ------------------------------------------------------ chrome: page rail */
  function headings(main) {
    var used = Object.create(null);
    document.querySelectorAll("[id]").forEach(function (el) { used[el.id] = 1; });
    var out = [];
    main.querySelectorAll("h2, h3").forEach(function (h) {
      if (h.closest("figure, table, details, .hb-ann-ui, [data-hbtabs]")) return;
      var text = (h.textContent || "").replace(/\s+/g, " ").trim();
      if (!text) return;
      if (!h.id) {  /* an attribute, never text: annotations anchor in the text */
        var base = slugify(text) || "section", id = base, n = 2;
        while (used[id]) id = base + "-" + n++;
        h.id = id;
        used[id] = 1;
      }
      if (h.id === "backlinks") return;
      out.push({ id: h.id, text: text, level: h.tagName === "H3" ? 3 : 2 });
    });
    if (!out.some(function (h) { return h.level === 2; })) out.forEach(function (h) { h.level = 2; });
    return out;
  }

  function tocHtml(hs) {
    return '<ul class="hb-toc-list">' + hs.map(function (h) {
      return '<li><a href="#' + escapeAttr(h.id) + '"' + (h.level === 3 ? ' class="hb-l3"' : "") + ">" + escapeHtml(h.text) + "</a></li>";
    }).join("") + "</ul>";
  }

  function factsHtml(lib, where, minutes) {
    var p = where.page;
    var bits = [];
    var kind = where.chapter ? "chapter" : (where.group ? where.group.kind : "page");
    var badge = '<span class="hb-kind hb-kind-' + escapeAttr(where.chapter ? "book" : kind) + '">' + escapeHtml(kind) + "</span>";
    if (where.group) badge = '<a href="' + escapeAttr(hbUrl("/shell/search.html?kind=" + encodeURIComponent(where.group.kind))) + '" title="Every ' +
      escapeAttr(where.group.label.toLowerCase()) + '">' + badge + "</a>";
    var topic = (document.querySelector('meta[name="topic"]') || {}).content || (p && p.topic);
    var on = "";
    if (topic) {
      var t = null;
      lib.topics.forEach(function (x) { if (x.slug === topic) t = x; });
      var label = t ? t.label : titleCase(topic);
      var href = t && t.hub ? t.hub.href : "/shell/search.html?topic=" + encodeURIComponent(topic);
      on = '<span>on <a href="' + escapeAttr(hbUrl(href)) + '">' + escapeHtml(label) + "</a></span>";
    }
    bits.push('<div class="hb-fact">' + badge + on + "</div>");
    var when = p && (p.updated || p.created);
    bits.push('<div class="hb-fact">' + icon("clock") + "<span>" + (when ? "Updated " + escapeHtml(fmtDate(when)) + " · " : "") +
      minutes + " min read</span></div>");
    var tags = ((document.querySelector('meta[name="tags"]') || {}).content || "").split(",")
      .map(function (s) { return s.trim(); }).filter(Boolean);
    if (tags.length) {
      bits.push('<div class="hb-tags">' + tags.map(function (tg) {
        return '<a class="hb-chip" href="' + escapeAttr(hbUrl("/shell/search.html?tag=" + encodeURIComponent(tg))) + '">#' + escapeHtml(tg) + "</a>";
      }).join("") + "</div>");
    }
    return '<div class="hb-facts">' + bits.join("") + "</div>";
  }

  function linksHtml(hits) {
    return '<ul class="hb-links">' + hits.map(function (b) {
      return '<li><a href="' + escapeAttr(hbUrl(b.href)) + '"><span class="hb-kind hb-kind-' + escapeAttr(b.kind) + '">' +
        escapeHtml(b.kind) + "</span>" + escapeHtml(b.title) + "</a></li>";
    }).join("") + "</ul>";
  }

  function scrollSpy(toc, hs) {
    if (!("IntersectionObserver" in window) || !hs.length) return;
    var links = Object.create(null);
    toc.querySelectorAll("a[href^='#']").forEach(function (a) { links[a.getAttribute("href").slice(1)] = a; });
    var visible = Object.create(null);
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
      var first = null;
      for (var i = 0; i < hs.length; i++) if (visible[hs[i].id]) { first = hs[i].id; break; }
      if (!first) return;
      Object.keys(links).forEach(function (id) { links[id].classList.toggle("on", id === first); });
    }, { rootMargin: "0px 0px -65% 0px" });
    hs.forEach(function (h) { var el = document.getElementById(h.id); if (el) io.observe(el); });
  }

  /* the opening line's <b>Status: X</b> becomes a pill — a class, so the text is untouched */
  function markStatus(main) {
    var sub = main.querySelector("p.sub");
    if (!sub) return;
    var b = sub.firstElementChild;
    if (!b || !/^(B|STRONG)$/.test(b.tagName)) return;
    var m = /^\s*Status:\s*([A-Za-z]+)/.exec(b.textContent || "");
    if (!m) return;
    b.classList.add("hb-status");
    b.setAttribute("data-status", m[1].toLowerCase());
  }

  /* ----------------------------------------------------------- the mount */
  var mounted = null;

  function isApp(main) {
    var body = document.body;
    return !!(body.hasAttribute("data-hb-app") || sitePath().indexOf("/shell/") === 0 || main.classList.contains("hb-home"));
  }

  function metaText(where, minutes) {
    var when = where.page && (where.page.updated || where.page.created);
    return (when ? "Updated " + escapeHtml(fmtDate(when)) + " · " : "") + minutes + " min read";
  }

  function mountShell(opts) {
    var main = document.querySelector("main");
    if (!main) return;
    var cat = opts.catalog;
    var lib = model(cat);
    var where = locate(lib);
    if (mounted) {  /* a fresher catalog: repaint what it drives, keep the rest */
      refresh(lib, where);
      if (opts.book) applyBook(opts.book);
      return;
    }
    var body = document.body;
    var app = isApp(main);

    body.classList.add("hb-has-shell", "hb-has-top");
    if (app) body.classList.add("hb-app");

    var stage = document.createElement("div");
    stage.className = "hb-stage";
    main.parentNode.insertBefore(stage, main);
    stage.appendChild(main);
    /* the chrome is fixed or absolutely placed: it goes first in <body>, wherever <main> lives */
    var first = body.firstChild;

    /* the library rail */
    var aside = null;
    if (cat && (cat.groups || []).length) {
      aside = document.createElement("aside");
      aside.id = "hb-side";
      aside.className = "hb-side";
      aside.setAttribute("aria-label", "Library");
      aside.innerHTML = sideHtml(lib, where);
      wireTree(aside);
      var backdrop = document.createElement("div");
      backdrop.className = "hb-side-backdrop";
      backdrop.addEventListener("click", function () { setDrawer(false); });
      body.insertBefore(aside, first);
      body.insertBefore(backdrop, first);
      aside.addEventListener("click", function (e) {
        if (e.target.closest("a")) setDrawer(false);
        var tb = e.target.closest("[data-hb-theme]");
        if (tb) {
          var t = store.get("theme") || "auto";
          var nx = THEMES[(THEMES.indexOf(t) + 1) % THEMES.length];
          store.set("theme", nx === "auto" ? null : nx);
          applyPrefs();
          tb.outerHTML = themeButton();
        }
        var fb = e.target.closest("[data-hb-font]");
        if (fb) {
          store.set("font", store.get("font") === "sans" ? null : "sans");
          applyPrefs();
          fb.outerHTML = fontButton();
        }
      });
      /* keep the current page in view in a long tree */
      var here = aside.querySelector(".hb-tree a.here");
      if (here) {
        var sc = aside.querySelector(".hb-side-scroll");
        if (here.offsetTop > sc.clientHeight - 80) sc.scrollTop = here.offsetTop - sc.clientHeight / 2;
      }
    } else {
      body.classList.add("hb-no-side");
    }

    /* the top bar */
    var hs = app ? [] : headings(main);
    var minutes = readingMinutes(main);
    var top = document.createElement("div");
    top.className = "hb-top";
    top.innerHTML =
      (aside ? '<button type="button" class="hb-iconbtn hb-only-narrow" data-hb-drawer aria-label="Library" aria-controls="hb-side" aria-expanded="false">' + icon("menu") + "</button>" : "") +
      crumbsHtml(lib, where) +
      '<div class="hb-top-meta">' +
      (!app && !bookRoot() ? '<span class="hb-only-wide hb-norail">' + metaText(where, minutes) + "</span>" : "") +
      (!app && hs.length > 1 ? '<span class="hb-contents"><button type="button" class="hb-iconbtn" data-hb-contents aria-expanded="false">' + icon("list") +
        '<span class="hb-only-wide">Contents</span></button><div class="hb-contents-panel" hidden>' + tocHtml(hs) + "</div></span>" : "") +
      '<button type="button" class="hb-iconbtn hb-only-narrow" data-hb-palette aria-label="Search">' + icon("search") + "</button>" +
      "</div>";
    body.insertBefore(top, first);
    top.addEventListener("click", function (e) {
      if (e.target.closest("[data-hb-drawer]")) setDrawer(!body.classList.contains("hb-side-open"));
      var cb = e.target.closest("[data-hb-contents]");
      if (cb) {
        var panel = top.querySelector(".hb-contents-panel");
        panel.hidden = !panel.hidden;
        cb.setAttribute("aria-expanded", panel.hidden ? "false" : "true");
      } else if (e.target.closest(".hb-contents-panel a")) {
        top.querySelector(".hb-contents-panel").hidden = true;
      }
    });

    /* the page rail, and what it holds when the screen is too narrow for it */
    var rail = null;
    if (!app) {
      body.classList.add("hb-has-rail");
      rail = document.createElement("aside");
      rail.className = "hb-rail";
      rail.setAttribute("aria-label", "About this page");
      rail.innerHTML = (hs.length > 1 ? '<div class="hb-rail-sec"><div class="hb-rail-label">On this page</div>' + tocHtml(hs) + "</div>" : "") +
        '<div class="hb-rail-sec"><div class="hb-rail-label">Page</div><div data-hb-facts>' + factsHtml(lib, where, minutes) + "</div></div>" +
        '<div class="hb-rail-sec" data-hb-linked hidden></div>';
      body.appendChild(rail);
      scrollSpy(rail, hs);
      if (!main.querySelector("ul[data-backlinks]")) {
        backlinksIndex().then(function (data) {
          var hits = (data && Object.prototype.hasOwnProperty.call(data, where.href) && data[where.href]) || [];
          if (!hits.length || !Array.isArray(hits)) return;
          var sec = rail.querySelector("[data-hb-linked]");
          sec.innerHTML = '<div class="hb-rail-label">Linked from · ' + hits.length + "</div>" + linksHtml(hits);
          sec.hidden = false;
          var after = document.createElement("div");
          after.className = "hb-after";
          after.innerHTML = '<div class="hb-rail-label">Linked from · ' + hits.length + "</div>" + linksHtml(hits);
          main.insertAdjacentElement("afterend", after);
        });
      }
    }

    mounted = { aside: aside, lib: lib, where: where, top: top, rail: rail, main: main, book: null, foot: null, minutes: minutes };
    if (opts.book) applyBook(opts.book);
  }

  /* a fresher catalog than the cached one the page painted with: the library rail, the crumbs,
     the top bar's date and the page's facts follow it */
  function refresh(lib, where) {
    mounted.lib = lib;
    mounted.where = where;
    if (mounted.aside) {
      var sc0 = mounted.aside.querySelector(".hb-side-scroll");
      var keep = sc0 ? sc0.scrollTop : 0;
      mounted.aside.innerHTML = sideHtml(lib, where);
      var sc1 = mounted.aside.querySelector(".hb-side-scroll");
      if (sc1) sc1.scrollTop = keep;
    }
    if (!mounted.book) {
      var crumbs = mounted.top.querySelector(".hb-crumbs");
      if (crumbs) crumbs.outerHTML = crumbsHtml(lib, where);
    }
    var meta = mounted.top.querySelector(".hb-norail");
    if (meta) meta.innerHTML = metaText(where, mounted.minutes);
    var facts = mounted.rail && mounted.rail.querySelector("[data-hb-facts]");
    if (facts) facts.innerHTML = factsHtml(lib, where, mounted.minutes);
  }

  /* a book's chapters: in the top bar in place of the crumbs, and prev / next below the page —
     both outside the reading column, so they can arrive after the page has painted, and be
     replaced when a fresher nav.json (or a libBook() call) arrives */
  function applyBook(book) {
    if (!mounted || !book || !book.chapters) return;
    if (mounted.book && JSON.stringify(mounted.book) === JSON.stringify(book)) return;
    mounted.book = book;
    var strip = mounted.top.querySelector(".hb-crumbs, .hb-book");
    if (strip) strip.outerHTML = bookHtml(book);
    if (mounted.foot && mounted.foot.parentNode) mounted.foot.parentNode.removeChild(mounted.foot);
    mounted.foot = injectFoot(book.chapters, mounted.main);
  }

  function setDrawer(open) {
    document.body.classList.toggle("hb-side-open", open);
    var b = document.querySelector("[data-hb-drawer]");
    if (b) b.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function injectFoot(chapters, main) {
    var cur = hereFile();
    var i = chapters.findIndex(function (c) { return c.file === cur; });
    if (i < 0) return null;
    var prev = null, next = null;
    for (var p = i - 1; p >= 0; p--) if (chapters[p].status === "landed") { prev = chapters[p]; break; }
    for (var n = i + 1; n < chapters.length; n++) if (chapters[n].status === "landed") { next = chapters[n]; break; }
    if (!prev && !next) return null;
    var foot = document.createElement("nav");
    foot.className = "hb-foot";
    foot.setAttribute("aria-label", "Previous and next");
    foot.innerHTML =
      (prev ? '<a class="hb-prev" href="' + escapeAttr(prev.file) + '"><small>← Previous</small>' + escapeHtml(prev.title) + "</a>" : "") +
      (next ? '<a class="hb-next" href="' + escapeAttr(next.file) + '"><small>Next →</small>' + escapeHtml(next.title) + "</a>" : "");
    main.insertAdjacentElement("afterend", foot);
    return foot;
  }

  var manualBook = null;

  /** Optional manual API — rare full chapter list without nav.json. Callable any time,
      including from the page's own DOMContentLoaded handler; it replaces nav.json's chapters. */
  window.libBook = function (cfg) {
    manualBook = cfg || {};
    if (mounted) applyBook(manualBook);
  };

  /* ------------------------------------------------------------ the palette
     ⌘K / Ctrl-K / "/" anywhere: pages by title, topics, tags, the shell's own pages, and —
     when the site carries a Pagefind index (/pagefind/, built by `ckit serve` or `ckit export`
     where pagefind is installed) — the full text. */
  var pal = null;

  function tokens(q) { return q.toLowerCase().split(/\s+/).filter(Boolean); }

  function scoreRec(r, toks, topicLabel) {
    var title = (r.title || "").toLowerCase();
    var fields = [
      [title, 10], [(r.tags || []).join(" ").toLowerCase(), 5], [topicLabel.toLowerCase(), 4],
      [(r.headings || []).join(" ").toLowerCase(), 3], [(r.sub || "").toLowerCase(), 2], [(r.defn || "").toLowerCase(), 1]
    ];
    var total = 0;
    for (var i = 0; i < toks.length; i++) {
      var tk = toks[i], best = 0;
      for (var j = 0; j < fields.length; j++) {
        var f = fields[j][0];
        if (!f) continue;
        var at = f.indexOf(tk);
        if (at === -1) continue;
        var wordStart = at === 0 || /[^a-z0-9]/.test(f.charAt(at - 1));
        var s = fields[j][1] * (wordStart ? 1 : 0.5);
        if (s > best) best = s;
      }
      if (!best) return 0;  /* every word must land somewhere */
      total += best;
    }
    if (title.indexOf(toks.join(" ")) === 0) total += 8;
    return total;
  }

  window.hbScore = function (r, q, topicLabel) { return scoreRec(r, tokens(q), topicLabel || ""); };
  window.hbCleanSub = function (sub) { return cleanSub(sub); };

  function highlight(text, toks) {  /* marks on the raw text, then escapes every piece */
    var s = String(text == null ? "" : text);
    var ws = toks.filter(function (t) { return t.length >= 2; })
      .map(function (t) { return t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); });
    if (!ws.length) return escapeHtml(s);
    var re = new RegExp(ws.join("|"), "ig"), out = "", last = 0, m;
    while ((m = re.exec(s))) {
      if (!m[0]) { re.lastIndex++; continue; }
      out += escapeHtml(s.slice(last, m.index)) + "<mark>" + escapeHtml(m[0]) + "</mark>";
      last = m.index + m[0].length;
    }
    return out + escapeHtml(s.slice(last));
  }
  window.hbHighlight = function (text, q) { return highlight(text, tokens(String(q || ""))); };

  function cleanSub(sub) {
    return String(sub || "").replace(/^\s*Status:\s*[A-Z]+\s*[—–-]\s*/, "");
  }

  function recentPages() {
    try { var r = JSON.parse(store.get("recent:" + BASE) || "[]"); return Array.isArray(r) ? r : []; } catch (e) { return []; }
  }
  function remember(title, href) {
    if (!title || !href) return;
    var list = recentPages().filter(function (r) { return r.href !== href; });
    list.unshift({ title: title, href: href });
    store.set("recent:" + BASE, JSON.stringify(list.slice(0, 12)));
  }

  var pagefindP = null;
  function pagefind() {
    if (pagefindP) return pagefindP;
    pagefindP = fetch(hbUrl("/shell/pagefind.json"), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!(j && j.available)) { pagefindP = null; return null; }  /* ask again next time: it may be building */
        return import(hbUrl("/pagefind/pagefind.js")).then(function (pf) {
          return Promise.resolve(pf.options ? pf.options({ baseUrl: BASE }) : null).then(function () { return pf; });
        });
      })
      .catch(function () { return null; });
    return pagefindP;
  }
  window.hbPagefind = pagefind;

  function ensurePalette() {
    if (pal) return pal;
    var d = document.createElement("dialog");
    d.className = "hb-pal";
    d.setAttribute("aria-label", "Search");
    d.innerHTML = '<div class="hb-pal-in">' + icon("search") +
      '<input type="search" placeholder="Search pages, topics, tags…" autocomplete="off" spellcheck="false" aria-label="Search">' +
      '<span class="hb-kbd">esc</span></div><ul class="hb-pal-list" role="listbox"></ul>' +
      '<div class="hb-pal-foot"><span>↑↓ move</span><span>↵ open</span><span>⌘↵ new tab</span></div>';
    document.body.appendChild(d);
    var input = d.querySelector("input");
    var list = d.querySelector(".hb-pal-list");
    var state = { items: [], sel: 0, seq: 0 };

    function render(groups, keepUrl) {
      state.items = [];
      groups.forEach(function (g) { g.items.forEach(function (it) { state.items.push(it); }); });
      if (keepUrl) {  /* late results must not move the highlight onto another row */
        var at = -1;
        state.items.forEach(function (it, i) { if (at < 0 && it.url === keepUrl) at = i; });
        state.sel = at < 0 ? 0 : at;
      }
      var html = [];
      var n = 0;
      groups.forEach(function (g) {
        if (!g.items.length) return;
        html.push('<li class="hb-pal-group">' + escapeHtml(g.label) + "</li>");
        g.items.forEach(function (it) {
          var i = n++;
          html.push('<li class="hb-pal-item' + (i === state.sel ? " sel" : "") + '" data-i="' + i + '" role="option"><a href="' +
            escapeAttr(it.url) + '"' + (it.ext ? ' target="_blank" rel="noopener"' : "") + '><span class="hb-pal-t">' + it.titleHtml + "</span>" +
            (it.meta ? '<span class="hb-pal-m">' + it.meta + "</span>" : "") +
            (it.sub ? '<div class="hb-pal-s">' + it.sub + "</div>" : "") + "</a></li>");
        });
      });
      list.innerHTML = html.length ? html.join("") : '<li class="hb-pal-empty">Nothing matches — try fewer words.</li>';
    }

    function move(delta) {
      if (!state.items.length) return;
      state.sel = (state.sel + delta + state.items.length) % state.items.length;
      list.querySelectorAll(".hb-pal-item").forEach(function (li) { li.classList.toggle("sel", +li.dataset.i === state.sel); });
      var cur = list.querySelector(".hb-pal-item.sel");
      if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" });
    }

    function run() {
      var q = input.value.trim();
      var seq = ++state.seq;
      state.sel = 0;
      Promise.all([catalogPromise().then(function (c) { return c || cachedCatalog(); }), searchIndex()]).then(function (res) {
        if (seq !== state.seq) return;
        var lib = model(res[0]);
        var idx = res[1] || [];
        var labels = Object.create(null);
        lib.topics.forEach(function (t) { labels[t.slug] = t.label; });
        var groups = [];
        if (!q) {
          groups.push({ label: "Recently opened", items: recentPages().slice(0, 6).map(function (r) {
            return { url: hbUrl(r.href), titleHtml: escapeHtml(r.title) };
          }) });
          groups.push({ label: "Topics", items: lib.topics.map(function (t) {
            return { url: hbUrl(t.hub ? t.hub.href : "/shell/search.html?topic=" + encodeURIComponent(t.slug)),
                     titleHtml: escapeHtml(t.label), meta: t.pages.length + " pages" };
          }) });
        } else {
          var toks = tokens(q);
          var hits = idx.map(function (r) { return { r: r, s: scoreRec(r, toks, String(labels[r.topic] || r.topic || "")) }; })
            .filter(function (x) { return x.s > 0; })
            .sort(function (a, b) { return b.s - a.s; })
            .slice(0, 12);
          groups.push({ label: "Pages", items: hits.map(function (x) {
            var r = x.r;
            return { url: hbUrl(r.href), titleHtml: highlight(r.title || r.href, toks),
                     meta: '<span class="hb-kind hb-kind-' + escapeAttr(r.kind) + '">' + escapeHtml(r.kind) + "</span>" +
                       (r.topic ? escapeHtml(labels[r.topic] || titleCase(r.topic)) : ""),
                     sub: highlight(cleanSub(r.sub).slice(0, 180), toks) };
          }) });
          var tl = lib.topics.filter(function (t) { return toks.every(function (tk) { return t.label.toLowerCase().indexOf(tk) !== -1; }); });
          groups.push({ label: "Topics", items: tl.map(function (t) {
            return { url: hbUrl(t.hub ? t.hub.href : "/shell/search.html?topic=" + encodeURIComponent(t.slug)), titleHtml: highlight(t.label, toks), meta: t.pages.length + " pages" };
          }) });
          var tagSet = Object.create(null);
          idx.forEach(function (r) { (r.tags || []).forEach(function (tg) { tagSet[tg] = (tagSet[tg] || 0) + 1; }); });
          var tags = Object.keys(tagSet).filter(function (tg) { return toks.every(function (tk) { return tg.toLowerCase().indexOf(tk) !== -1; }); }).slice(0, 5);
          groups.push({ label: "Tags", items: tags.map(function (tg) {
            return { url: hbUrl("/shell/search.html?tag=" + encodeURIComponent(tg)), titleHtml: "#" + highlight(tg, toks), meta: tagSet[tg] + " pages" };
          }) });
        }
        var cmds = [{ label: "Home", href: "/" }, { label: "Browse everything", href: "/shell/search.html" }];
        if ((lib.cat.record || []).length) cmds.push({ label: "Chronicle", href: "/shell/chronicle.html" });
        if (window.hbEngine && lib.cat.threads && lib.cat.threads.total) cmds.push({ label: "Review the annotation threads", href: "/shell/review.html" });
        (lib.cat.links || []).forEach(function (l) { cmds.push({ label: l.label, href: l.href }); });
        var qt = tokens(q);
        groups.push({ label: "Go to", items: cmds.filter(function (c) {
          return !qt.length || qt.every(function (tk) { return c.label.toLowerCase().indexOf(tk) !== -1; });
        }).map(function (c) {
          var ext = /^[a-z]+:\/\//i.test(c.href);
          return { url: ext ? c.href : hbUrl(c.href), ext: ext, titleHtml: escapeHtml(c.label) };
        }) });
        render(groups);
        if (q.length >= 3) {
          pagefind().then(function (pf) {
            if (!pf || seq !== state.seq) return;
            return pf.debouncedSearch ? pf.debouncedSearch(q, {}, 180) : pf.search(q);
          }).then(function (s) {
            if (!s || seq !== state.seq) return;
            return Promise.all(s.results.slice(0, 6).map(function (x) { return x.data(); }));
          }).then(function (docs) {
            if (!docs || seq !== state.seq || !docs.length) return;
            var shown = Object.create(null);
            state.items.forEach(function (it) { shown[canon(it.url)] = 1; });
            var items = docs.filter(function (d) { return !shown[canon(d.url)]; }).map(function (d) {
              return { url: d.url, titleHtml: escapeHtml((d.meta && d.meta.title) || d.url), sub: d.excerpt };
            });
            if (!items.length) return;
            var keep = state.items[state.sel] && state.items[state.sel].url;
            groups.splice(1, 0, { label: "In the text", items: items });
            render(groups, keep);
          }).catch(function () {});
        }
      });
    }

    input.addEventListener("input", run);
    d.addEventListener("keydown", function (e) {
      if (e.isComposing || e.keyCode === 229) return;
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") {
        var it = state.items[state.sel];
        if (!it) return;
        e.preventDefault();
        if (e.metaKey || e.ctrlKey || it.ext) window.open(it.url, "_blank", "noopener"); else location.href = it.url;
      }
    });
    list.addEventListener("pointermove", function (e) {
      var li = e.target.closest(".hb-pal-item");
      if (!li || +li.dataset.i === state.sel) return;
      state.sel = +li.dataset.i;
      list.querySelectorAll(".hb-pal-item").forEach(function (x) { x.classList.toggle("sel", x === li); });
    });
    d.addEventListener("click", function (e) { if (e.target === d) d.close(); });
    pal = { dialog: d, input: input, run: run };
    return pal;
  }

  function openPalette(q) {
    var p = ensurePalette();
    if (!p.dialog.open) {
      if (p.dialog.showModal) p.dialog.showModal(); else p.dialog.setAttribute("open", "");
    }
    p.input.value = q || "";
    p.input.focus();
    p.run();
  }
  window.hbPalette = openPalette;

  function typing(e) {
    var t = e.target;
    return t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
  }

  function initPalette() {
    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === "k" || e.key === "K")) {
        if (typing(e) && !(pal && pal.dialog.contains(e.target))) return;
        e.preventDefault();
        if (pal && pal.dialog.open) pal.dialog.close(); else openPalette();
      } else if (e.key === "/" && !e.metaKey && !e.ctrlKey && !typing(e)) {
        e.preventDefault();
        openPalette();
      } else if (e.key === "Escape") {
        setDrawer(false);
      }
    });
    document.addEventListener("click", function (e) {
      var t = e.target.closest && e.target.closest("[data-hb-palette]");
      if (!t || e.metaKey || e.ctrlKey || e.shiftKey || e.button > 0) return;
      e.preventDefault();
      openPalette();
    });
  }

  /* ------------------------------------------------------------- link peeks
     Hovering an internal link shows what is behind it — its kind, title and the page's own
     opening line — from the search index. Concept links keep their definition popover. */
  var peek = null, peekTimer = null, peekHide = null, peekAnchor = null;

  function hidePeek() {
    if (peekTimer) { clearTimeout(peekTimer); peekTimer = null; }
    if (peek) peek.hidden = true;
    peekAnchor = null;
  }

  function showPeek(a) {
    var target = canon(a.href);
    if (!target) return;
    searchIndex().then(function (idx) {
      if (peekAnchor !== a) return;
      var rec = null;
      for (var i = 0; i < idx.length; i++) if (idx[i].href === target) { rec = idx[i]; break; }
      if (!rec) return;
      if (!peek) {
        peek = document.createElement("div");
        peek.className = "hb-peek";
        peek.setAttribute("role", "tooltip");
        peek.addEventListener("pointerenter", function () { if (peekHide) { clearTimeout(peekHide); peekHide = null; } });
        peek.addEventListener("pointerleave", function () { hidePeek(); });
        document.body.appendChild(peek);
      }
      var lib = mounted ? mounted.lib : model(cachedCatalog());
      var label = "";
      lib.topics.forEach(function (t) { if (t.slug === rec.topic) label = t.label; });
      peek.innerHTML = '<div class="hb-peek-head"><span class="hb-kind hb-kind-' + escapeAttr(rec.kind) + '">' + escapeHtml(rec.kind) + "</span>" +
        escapeHtml(label || (rec.topic ? titleCase(rec.topic) : "")) + "</div>" +
        '<div class="hb-peek-title">' + escapeHtml(rec.title || target) + "</div>" +
        (rec.sub ? '<div class="hb-peek-sub">' + escapeHtml(cleanSub(rec.sub)) + "</div>" : "");
      placePop(peek, a);
    });
  }

  function initPeeks() {
    if (window.matchMedia && window.matchMedia("(hover: none)").matches) return;
    document.addEventListener("pointerover", function (e) {
      var a = e.target.closest && e.target.closest("main a[href], .hb-rail a[href], .hb-after a[href]");
      if (!a || a.classList.contains("defn-link") || a.closest(".hb-ann-ui, .hb-toc-list")) return;
      var target = canon(a.href);
      if (!target || target.indexOf("/content/") !== 0 || target === (canon(location.href) || "")) return;
      if (peekHide) { clearTimeout(peekHide); peekHide = null; }
      if (peekTimer) clearTimeout(peekTimer);
      peekAnchor = a;
      peekTimer = setTimeout(function () { showPeek(a); }, 380);
    });
    document.addEventListener("pointerout", function (e) {
      var a = e.target.closest && e.target.closest("a[href]");
      if (!a || a !== peekAnchor) return;
      if (peekTimer) { clearTimeout(peekTimer); peekTimer = null; }
      var to = e.relatedTarget;
      if (peek && to && peek.contains(to)) return;
      peekHide = setTimeout(hidePeek, 160);
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") hidePeek(); });
    window.addEventListener("scroll", function () { if (peek && !peek.hidden) hidePeek(); }, { passive: true });
  }

  /* ------------------------------------------ moving between pages, quickly
     Where the browser supports speculation rules, a link hovered for a moment is fetched
     before it is clicked. Elsewhere this does nothing at all. */
  function initPrefetch() {
    try {
      if (!(HTMLScriptElement.supports && HTMLScriptElement.supports("speculationrules"))) return;
      var s = document.createElement("script");
      s.type = "speculationrules";
      s.textContent = JSON.stringify({ prefetch: [{ where: { and: [
        { href_matches: BASE + "*" }, { not: { href_matches: BASE + "__*" } }
      ] }, eagerness: "moderate" }] });
      document.head.appendChild(s);
    } catch (e) {}
  }

  /* ------------------------------------------------------------- start
     lib.js is deferred, so the document is parsed when this runs. The chrome mounts now —
     from the cached catalog when there is one, so it paints with the page — and a fresh
     catalog repaints the library rail only if the library changed since. */
  /* a tab icon, unless the page names its own — and no request for a /favicon.ico that is not there */
  function initIcon() {
    if (document.querySelector('link[rel~="icon"]')) return;
    var l = document.createElement("link");
    l.rel = "icon";
    l.href = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">' +
      '<rect width="32" height="32" rx="8" fill="#4a3aa7"/><path d="M9 8.5h8.5a5.5 5.5 0 0 1 5.5 5.5v9.5h-8.5A5.5 5.5 0 0 1 9 18z" fill="#fff"/></svg>');
    document.head.appendChild(l);
  }

  function safely(fn) {
    try { fn(); } catch (e) { if (window.console && console.error) console.error("ckit shell:", e); }
  }

  function start(viaLoaded) {
    safely(initIcon);
    var root = bookRoot();
    var bookKey = root ? "nav:" + BASE + root : null;
    var cachedBook = null;
    if (bookKey) { try { cachedBook = JSON.parse(store.get(bookKey) || "null"); } catch (e) { cachedBook = null; } }
    var cached = cachedCatalog();
    var bookP = root ? fetch(hbUrl(root + "nav.json"), { credentials: "same-origin" })
          .then(function (r) { return r.ok ? r.text() : null; })
          .then(function (t) { if (!t) return null; store.set(bookKey, t); return JSON.parse(t); })
          .catch(function () { return null; })
      : Promise.resolve(null);

    var main = document.querySelector("main");
    if (main) safely(function () { markStatus(main); });  /* before the first paint: the pill must not reflow the page later */
    if (cached) safely(function () { mountShell({ catalog: cached, book: manualBook || cachedBook }); });

    Promise.all([catalogPromise(), bookP]).then(function (pair) {
      var catalog = pair[0];
      var book = pair[1];
      safely(function () {
        if (!mounted && (catalog || book || manualBook)) mountShell({ catalog: catalog, book: manualBook || book });
        else if (mounted && catalog && JSON.stringify(catalog) !== JSON.stringify(cached)) mountShell({ catalog: catalog });
        if (!mounted) document.body.classList.add("hb-no-side");
        else if (!manualBook && book) applyBook(book);
      });
      safely(function () { linkRefs(main, compileRefs(catalog && catalog.refs)); });
    });

    /* everything a page's own script may build on runs after the page's DOMContentLoaded
       handlers, as in 0.4: tabs, popovers and backlink lists that a page creates are wired */
    function late() {
      [initTabs, initDefnLinks, initBacklinks, initAnnotate, initPalette, initPeeks, initPrefetch].forEach(safely);
      safely(function () {
        var h1 = document.querySelector("main h1");
        var here = canon(location.href);
        if (h1 && here && here.indexOf("/content/") === 0) remember((h1.textContent || "").replace(/\s+/g, " ").trim(), here);
      });
    }
    if (viaLoaded || document.readyState === "complete") late();
    else document.addEventListener("DOMContentLoaded", late);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { start(true); });
  else start(false);
})();
