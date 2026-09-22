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

  function positionDefnPop(anchor) {
    var pop = ensureDefnPop();
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
    var pop = ensureDefnPop();
    pop.innerHTML = '<span class="defn-pop-name muted">Loading…</span>';
    positionDefnPop(anchor);
    defnFetch(url).then(function (blockHtml) {
      if (defnAnchor !== anchor) return;
      if (!blockHtml) {
        pop.innerHTML = '<span class="defn-pop-name muted">No definition of record found at ' +
          escapeHtml(url) + '</span>';
      } else {
        pop.innerHTML = blockHtml;
      }
      positionDefnPop(anchor);
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

  /* Backlinks: any <ul data-backlinks> gets populated from
     /content/backlinks.json keyed by the page's site path. */
  function initBacklinks() {
    var lists = document.querySelectorAll("ul[data-backlinks]");
    if (!lists.length) return;
    var here = sitePath();
    if (here.endsWith("/index.html")) here = here.slice(0, -"index.html".length);
    fetchJson("/content/backlinks.json").then(function (data) {
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
        var s = document.createElement("script");
        s.src = hbUrl("/shell/annotate.js");
        s.defer = true;
        document.head.appendChild(s);
      })
      .catch(function () {});
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

  /* Reference links: ids matching a kit.json `refs` pattern become links, e.g.
       "refs": [{"pattern": "Q-\\d+", "href": "/shell/record.html?p=QUESTIONS.md#{id}"}]
     Text inside inline <code> is linked; <pre> blocks, existing links, headings, scripts
     and styles are left alone, and so is a qualified id (`other:Q-3`, another repo's), and
     anything inside an element marked data-norefs (a shell page's own rendered lists).
     Idempotent — a second pass skips ids already inside an <a>. Runs on content pages, and
     through hbLinkRefs() on anything a shell page renders later (the record viewer). */
  var REF_SKIP = { A: 1, PRE: 1, SCRIPT: 1, STYLE: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1 };
  var catalogCache = null;
  function catalogPromise() {  /* one fetch of the catalog per page, shared by every caller */
    if (!catalogCache) catalogCache = fetchJson("/content/catalog.json").catch(function () { return null; });
    return catalogCache;
  }
  window.hbCatalog = catalogPromise;

  function compileRefs(refs) {
    var out = [];
    (refs || []).forEach(function (r) {
      try {
        out.push({ re: new RegExp("^(?:" + r.pattern + ")$"), src: r.pattern, href: r.href });
      } catch (e) { /* ckit check reports a bad pattern; the shell just skips it */ }
    });
    return out;
  }

  function linkRefs(root, refs) {
    if (!root || !refs.length || typeof document.createTreeWalker !== "function") return;
    var any = new RegExp("\\b(" + refs.map(function (r) { return "(?:" + r.src + ")"; }).join("|") + ")\\b", "g");
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var v = node.nodeValue;
        if (!v) return NodeFilter.FILTER_REJECT;
        for (var p = node.parentNode; p && p !== root; p = p.parentNode) {
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
  window.hbLinkRefs = function (root) {
    return window.hbRefs().then(function (refs) { linkRefs(root, refs); });
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

  function fetchJson(url) {
    return fetch(hbUrl(url), { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }

  function pageToc() {
    var main = document.querySelector("main");
    if (!main) return [];
    var out = [];
    main.querySelectorAll("h2[id]").forEach(function (h) {
      out.push({
        id: h.id,
        text: (h.textContent || "").replace(/\s+/g, " ").trim()
      });
    });
    return out;
  }

  function injectFoot(chapters) {
    var cur = hereFile();
    var i = chapters.findIndex(function (c) { return c.file === cur; });
    if (i < 0) return;
    var prev = null, next = null;
    for (var p = i - 1; p >= 0; p--) if (chapters[p].status === "landed") { prev = chapters[p]; break; }
    for (var n = i + 1; n < chapters.length; n++) if (chapters[n].status === "landed") { next = chapters[n]; break; }
    var main = document.querySelector("main");
    if (!main) return;
    var foot = document.createElement("div");
    foot.className = "hb-foot";
    foot.innerHTML =
      (prev ? '<a href="' + prev.file + '">◀ ' + prev.title + "</a>" : "<span></span>") +
      (next ? '<a href="' + next.file + '">' + next.title + " ▶</a>" : "<span></span>");
    main.appendChild(foot);
  }

  function injectTopNav(book) {
    if (!book || !book.chapters) return;
    var cur = hereFile();
    var nav = document.createElement("nav");
    nav.className = "hb-nav";
    nav.setAttribute("aria-label", "Chapters");
    var bits = [
      '<a class="hb-home" href="' + escapeAttr(book.homeHref || "index.html") + '">' +
        escapeHtml(book.homeLabel || "Book") + "</a><span class=\"sep\">·</span>"
    ];
    book.chapters.forEach(function (c) {
      if (c.file === "index.html") return;
      if (c.status === "planned" && c.file !== cur) {
        bits.push(
          '<a class="muted" title="' + escapeAttr(c.title) + ' (planned)" ' +
          'style="opacity:.45;cursor:default" onclick="return false" href="#">' +
          escapeHtml(c.label) + "</a>"
        );
      } else {
        bits.push(
          '<a href="' + escapeAttr(c.file) + '"' +
          (c.file === cur ? ' class="here" aria-current="page"' : "") +
          ' title="' + escapeAttr(c.title) + '">' + escapeHtml(c.label) + "</a>"
        );
      }
    });
    nav.innerHTML = bits.join(" ");

    var toc = pageToc();
    var tocEl = null;
    if (toc.length) {
      tocEl = document.createElement("nav");
      tocEl.className = "hb-toc";
      tocEl.setAttribute("aria-label", "On this page");
      tocEl.innerHTML =
        '<span class="hb-toc-label">On this page</span>' +
        toc.map(function (t) {
          return '<a href="#' + escapeAttr(t.id) + '">' + escapeHtml(t.text) + "</a>";
        }).join(" ");
    }

    var stage = document.querySelector(".hb-stage");
    var main = document.querySelector("main");
    var anchor = stage || document.body;
    if (main && main.parentNode === anchor) {
      anchor.insertBefore(nav, main);
      if (tocEl) anchor.insertBefore(tocEl, main);
    } else {
      anchor.insertBefore(nav, anchor.firstChild);
      if (tocEl) anchor.insertBefore(tocEl, nav.nextSibling);
    }
  }

  function catalogBlock(catalog, bookSlug) {
    if (!catalog) return "";
    var here = sitePath();
    var extra = (catalog.links || []).map(function (l) {
      return '<a class="hb-side-lib" href="' + escapeAttr(hbUrl(l.href)) + '"' +
        (l.title ? ' title="' + escapeAttr(l.title) + '"' : "") +
        (here === l.href ? ' aria-current="page"' : "") + ">" + escapeHtml(l.label) + "</a> ";
    }).join("");
    var bits = [
      '<div class="hb-side-section">' +
        extra +
        '<a class="hb-side-lib" href="' + hbUrl("/") + '">Library</a> ' +
        '<a class="hb-side-search" href="' + hbUrl("/shell/search.html") + '" title="Search all content">Search</a>' +
        ((catalog.record && catalog.record.length) ? ' <a class="hb-side-search" href="' + hbUrl("/shell/chronicle.html") + '" title="The record as a timeline">Chronicle</a>' : '') +
      '</div>'
    ];

    function list(label, items, isHere) {
      if (!items || !items.length) return;
      bits.push(
        '<div class="hb-side-section"><div class="hb-side-label">' + escapeHtml(label) +
        '</div><ul class="hb-side-list">'
      );
      items.forEach(function (item) {
        bits.push(
          "<li><a href=\"" + escapeAttr(hbUrl(item.href)) + "\"" +
          (isHere(item) ? ' class="here" aria-current="page"' : "") + ">" +
          escapeHtml(item.title) + "</a></li>"
        );
      });
      bits.push("</ul></div>");
    }

    (catalog.groups || []).forEach(function (g) {
      list(g.label, catalog[g.key], g.kind === "book" || g.key === "books"
        ? function (b) { return bookSlug && b.slug === bookSlug; }
        : function (p) { return here === p.href; });
    });
    list("Record", catalog.record, function (r) {
      return here === "/shell/record.html" && location.search === "?p=" + r.path;
    });

    return bits.join("");
  }

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

  function mountShell(opts) {
    var catalog = opts.catalog;
    var book = opts.book;
    var root = opts.bookRoot;
    var bookSlug = root ? root.replace(/^\/content\/books\//, "").replace(/\/$/, "") : null;
    var main = document.querySelector("main");
    if (!main) return;

    document.body.classList.add("hb-has-shell");

    var stage = document.createElement("div");
    stage.className = "hb-stage";
    main.parentNode.insertBefore(stage, main);
    stage.appendChild(main);

    var catalogHtml = catalogBlock(catalog, bookSlug);
    if (catalogHtml) {
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "hb-side-toggle";
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-controls", "hb-side");
      toggle.textContent = "Library";

      var aside = document.createElement("aside");
      aside.id = "hb-side";
      aside.className = "hb-side";
      aside.setAttribute("aria-label", "Library");
      aside.innerHTML = catalogHtml;

      var backdrop = document.createElement("div");
      backdrop.className = "hb-side-backdrop";

      function setOpen(open) {
        document.body.classList.toggle("hb-side-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      }
      toggle.addEventListener("click", function () {
        setOpen(!document.body.classList.contains("hb-side-open"));
      });
      backdrop.addEventListener("click", function () { setOpen(false); });
      aside.addEventListener("click", function (e) {
        if (e.target.closest("a")) setOpen(false);
      });

      /* Only aside + stage are layout children; toggle/backdrop are fixed overlays. */
      document.body.insertBefore(aside, stage);
      stage.insertBefore(backdrop, stage.firstChild);
      stage.insertBefore(toggle, stage.firstChild);
    } else {
      document.body.classList.add("hb-no-side");
    }

    if (book && book.chapters) {
      injectTopNav(book);
      injectFoot(book.chapters);
    }
  }

  var manualBook = null;

  /** Optional manual API — rare full chapter list without nav.json. */
  window.libBook = function (cfg) {
    manualBook = cfg || {};
  };

  document.addEventListener("DOMContentLoaded", function () {
    var root = bookRoot();
    var catalogP = catalogPromise();
    var bookP = manualBook
      ? Promise.resolve(manualBook)
      : root
        ? fetchJson(root + "nav.json").catch(function () { return null; })
        : Promise.resolve(null);

    Promise.all([catalogP, bookP]).then(function (pair) {
      var catalog = pair[0];
      var book = pair[1];
      if (catalog || book) mountShell({ catalog: catalog, book: book, bookRoot: root });
      initTabs();
      initDefnLinks();
      initBacklinks();
      initAnnotate();
      linkRefs(document.querySelector("main"), compileRefs(catalog && catalog.refs));
    });
  });
})();
