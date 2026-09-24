/* ============================================================================
   annotate.js — session-free page annotations (content-kit)

   Loaded by lib.js only when the serving engine answers /__annotations/ping.
     reads   GET  <page>.annotations.json           a static sidecar, committed
     writes  POST /__annotations  {op, page, …}    the engine writes the sidecar

   Nothing here needs a session. The human annotates whenever; the file is the
   channel; any agent later runs `ckit annotations list` and the /address skill.
   Quotes are anchored by text (W3C TextQuoteSelector), never by CSS path, so an
   edited page keeps its notes and a rewritten passage is reported stale by the gate.

   Two kinds of thread meet here. A reader's QUESTION opens and waits: whoever
   acts on the page replies and keeps, addresses or declines it. An agent's FLAG
   rests as `noted`: a disclosure that a passage was written beyond the source,
   asking nothing until the reader keeps it or asks for a change. Both sides act
   from this panel; the CLI is never required. `#ann=<id>` in the URL opens the
   panel on that thread (the home page and the review page link this way).

   The passages a live thread quotes are marked from the moment the page loads,
   panel open or not — dotted amber for a question waiting, azure for a noted flag
   — and a click on one opens the panel on its thread. The marks are CSS highlights
   over ranges of the page's own text: nothing is inserted into <main>, so the text
   a reader sees, selects and quotes is the text the page carries. The panel takes
   the page rail's slot beside the reading column on a wide screen, and is a sheet
   along the bottom on a narrow one.
   ========================================================================== */

(function () {
  "use strict";

  var main = document.querySelector("main");
  if (!main || document.body.dataset.hbAnnotate === "on") return;
  document.body.dataset.hbAnnotate = "on";

  var PAGE = location.pathname.replace(/index\.html$/, "");
  var SIDECAR = PAGE.slice(-1) === "/"
    ? PAGE + "index.annotations.json"
    : PAGE.replace(/\.html$/, ".annotations.json");
  var CONTEXT = 32;
  var CLIP = 160;
  var STATES = ["open", "noted", "addressed", "declined"];

  var state = { on: false, threads: [], stale: {}, marks: [], focus: null, scrollTo: null, pending: "", expanded: {} };

  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = window.hbUrl ? window.hbUrl("/shell/annotate.css") : "/shell/annotate.css";
  document.head.appendChild(css);

  var toggle = el("button", "hb-ann-toggle hb-ann-ui", "✎ Annotate");
  toggle.type = "button";
  toggle.title = "Mark up this page; an agent picks the notes up later";
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "hb-ann-panel");
  document.body.appendChild(toggle);

  var panel = el("aside", "hb-ann-panel hb-ann-ui");
  panel.id = "hb-ann-panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", "Annotations");
  var inner = el("div", "hb-ann-in");
  var live = el("div", "hb-ann-sr");  // what changed, said to a screen reader
  live.setAttribute("role", "status");
  panel.appendChild(inner);
  panel.appendChild(live);
  document.body.appendChild(panel);

  var bubble = el("button", "hb-ann-bubble hb-ann-ui", "＋ Comment on selection");
  bubble.type = "button";
  bubble.hidden = true;
  document.body.appendChild(bubble);

  /* ------------------------------------------------------------------ helpers */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function norm(s) { return String(s).replace(/\s+/g, " ").trim(); }
  function reEsc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  function me() { return localStorage.getItem("ckit.author") || ""; }
  function author() {
    var a = me();
    if (!a) {
      a = window.prompt("Your name for annotations (kept in this browser):", "") || "";
      a = a.trim();
      if (a) localStorage.setItem("ckit.author", a);
    }
    return a;
  }
  function kindOf(t) { return t.kind || "question"; }
  function isLive(t) { return t.state === "open" || t.state === "noted"; }
  function say(text) { live.textContent = ""; setTimeout(function () { live.textContent = text; }, 60); }
  function post(req) {
    return fetch("/__annotations", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req)
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok || !j.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
  }
  function hashThread() {
    var m = /(?:^#|[#&])ann=([^&]+)/.exec(location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }

  /* ----------------------------------------------------- the page's text model
     The same model the engine uses: text nodes under <main>, minus script/style and
     our own chrome, concatenated. Quotes are located whitespace-flexibly. */
  function textNodes() {
    var out = [];
    var walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        for (var p = n.parentNode; p && p !== main; p = p.parentNode) {
          var t = p.nodeName;
          if (t === "SCRIPT" || t === "STYLE" || t === "NOSCRIPT" || t === "TEMPLATE") return NodeFilter.FILTER_REJECT;
          if (p.classList && p.classList.contains("hb-ann-ui")) return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = walker.nextNode())) out.push(n);
    return out;
  }
  function model() {
    var full = "", spans = [];
    textNodes().forEach(function (n) {
      spans.push({ node: n, start: full.length, end: full.length + n.nodeValue.length });
      full += n.nodeValue;
    });
    return { full: full, spans: spans };
  }
  function find(m, exact) {
    var q = norm(exact);
    if (!q) return null;
    var re = new RegExp(q.split(" ").map(reEsc).join("\\s+"));
    var hit = re.exec(m.full);
    return hit ? [hit.index, hit.index + hit[0].length] : null;
  }
  function context(m, se) {
    return {
      prefix: norm(m.full.slice(Math.max(0, se[0] - CONTEXT * 3), se[0])).slice(-CONTEXT),
      suffix: norm(m.full.slice(se[1], se[1] + CONTEXT * 3)).slice(0, CONTEXT)
    };
  }
  function toRange(m, se) {  // [start, end) of the model as a DOM range over the page's own text nodes
    var r = document.createRange(), i, sp;
    for (i = 0; i < m.spans.length; i++) { sp = m.spans[i]; if (se[0] < sp.end) { r.setStart(sp.node, se[0] - sp.start); break; } }
    for (i = 0; i < m.spans.length; i++) { sp = m.spans[i]; if (se[1] <= sp.end) { r.setEnd(sp.node, se[1] - sp.start); break; } }
    return r;
  }

  /* ------------------------------------------------------------------- marks
     One CSS highlight per state (hb-ann-open, hb-ann-noted, …) over the quoted ranges,
     and hb-ann-focus over the thread in hand. With the panel closed only the live
     threads are marked; open, the settled ones show too. Where the browser has no
     highlights, the ranges still anchor clicks, jumps and the stale chips. */
  var HL = !!(window.CSS && CSS.highlights && typeof window.Highlight === "function");
  function paint() {
    var m = model();
    state.stale = {};
    state.marks = [];
    state.threads.forEach(function (t) {
      if (!t.target || t.state === "withdrawn") return;
      var se = find(m, t.target.exact);
      if (!se) { state.stale[t.id] = true; return; }
      state.marks.push({ id: t.id, state: t.state, range: toRange(m, se) });
    });
    if (!HL) return;
    STATES.concat("focus").forEach(function (k) { CSS.highlights.delete("hb-ann-" + k); });
    var hl = {};
    shown().forEach(function (x) {
      (hl[x.state] = hl[x.state] || new Highlight()).add(x.range);
      if (x.id === state.focus && state.on) CSS.highlights.set("hb-ann-focus", new Highlight(x.range));
    });
    Object.keys(hl).forEach(function (k) { CSS.highlights.set("hb-ann-" + k, hl[k]); });
  }
  function shown() {
    return state.marks.filter(function (x) { return state.on || x.state === "open" || x.state === "noted"; });
  }
  function markAt(x, y) {  // the thread whose marked passage is under this point, if any
    var node = null, off = 0, hit = null;
    if (document.caretPositionFromPoint) {
      var cp = document.caretPositionFromPoint(x, y);
      if (cp) { node = cp.offsetNode; off = cp.offset; }
    } else if (document.caretRangeFromPoint) {
      var cr = document.caretRangeFromPoint(x, y);
      if (cr) { node = cr.startContainer; off = cr.startOffset; }
    }
    if (!node || !main.contains(node)) return null;
    shown().forEach(function (mk) {
      if (hit) return;
      try { if (!mk.range.isPointInRange(node, off)) return; } catch (e) { return; }
      Array.prototype.forEach.call(mk.range.getClientRects(), function (q) {
        if (x >= q.left && x <= q.right && y >= q.top && y <= q.bottom) hit = mk.id;
      });
    });
    return hit;
  }
  function onText(e) {  // a click or a move over the page's text, not over a control in it
    return !e.target.closest("a, button, input, textarea, select, summary, label, [contenteditable], .hb-ann-ui");
  }
  main.addEventListener("click", function (e) {
    if (e.button || e.defaultPrevented || !onText(e)) return;
    var sel = window.getSelection();
    if (sel && !sel.isCollapsed) return;
    var id = markAt(e.clientX, e.clientY);
    if (id) openOn(id);
  });
  var hoverPending = false;
  main.addEventListener("mousemove", function (e) {
    if (hoverPending) return;
    hoverPending = true;
    requestAnimationFrame(function () {
      hoverPending = false;
      main.classList.toggle("hb-ann-over", onText(e) && !!markAt(e.clientX, e.clientY));
    });
  });

  /* --------------------------------------------------------------- lifecycle */
  toggle.addEventListener("click", function () { setOn(!state.on, true); });
  function place() {  // the page rail's slot when the shell built one, else the page's edge
    var slot = document.querySelector(".hb-stage") || document.body;
    if (panel.parentNode !== slot) slot.appendChild(panel);
  }
  function setOn(on, byKey) {
    var had = panel.contains(document.activeElement);
    state.on = on;
    document.body.classList.toggle("hb-ann-on", on);
    toggle.classList.toggle("on", on);
    toggle.setAttribute("aria-expanded", on ? "true" : "false");
    place();
    panel.hidden = !on;
    bubble.hidden = true;
    if (on) {
      load(byKey);
    } else {
      paint();
      if (had) toggle.focus();
    }
  }
  function load(focusPanel) {
    return fetch(SIDECAR, { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : { threads: [] }; })
      .catch(function () { return { threads: [] }; })
      .then(function (d) {
        state.threads = d.threads || [];
        paint();
        if (!state.on) return;
        render();
        if (focusPanel) inner.querySelector(".hb-ann-head h2").focus();
      });
  }
  function openOn(id) {  // a deep link, or a click on a marked passage: the panel on, this thread in view
    if (!id) return;
    state.focus = id;
    state.scrollTo = id;
    if (state.on) { paint(); render(); } else setOn(true);
  }
  if (hashThread()) openOn(hashThread()); else load();
  window.addEventListener("hashchange", function () { openOn(hashThread()); });
  window.addEventListener("load", paint);  // math or a widget may have rebuilt the text since

  /* ------------------------------------------------------------- selection */
  var bubbleTimer = null;
  document.addEventListener("selectionchange", function () {
    if (!state.on) return;
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(placeBubble, 160);
  });
  function placeBubble() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || !main.contains(sel.anchorNode) || !main.contains(sel.focusNode)) {
      bubble.hidden = true; return;
    }
    var text = norm(sel.toString());
    if (!text) { bubble.hidden = true; return; }
    var rect = sel.getRangeAt(0).getBoundingClientRect();
    bubble.style.top = (window.scrollY + rect.bottom + 6) + "px";
    bubble.style.left = (window.scrollX + Math.max(8, rect.left)) + "px";
    bubble.hidden = false;
    state.pending = text;
  }
  bubble.addEventListener("mousedown", function (e) { e.preventDefault(); });
  bubble.addEventListener("click", function () {
    var q = state.pending;
    bubble.hidden = true;
    if (q) compose(q);
  });

  /* ------------------------------------------------- composer: a new question */
  function compose(quote) {
    var m = model();
    var se = quote ? find(m, quote) : null;
    if (quote && !se) { alert("Could not locate that selection in the page text."); return; }
    var ctx = se ? context(m, se) : null;
    var form = el("div", "hb-ann-form hb-ann-ui");
    form.innerHTML =
      (quote ? '<div class="hb-ann-quote">' + esc(quote.length > CLIP ? quote.slice(0, CLIP) + "…" : quote) + "</div>"
             : '<div class="hb-ann-meta">Page-level note</div>') +
      '<textarea aria-label="Your note" placeholder="What should change, and why?"></textarea>' +
      '<div class="hb-ann-err" role="alert" hidden></div>' +
      '<div class="hb-ann-actions"><button type="button" class="hb-ann-btn primary" data-act="save">Save</button>' +
      '<button type="button" class="hb-ann-btn" data-act="cancel">Cancel</button></div>';
    var slot = panel.querySelector("[data-composer]");
    slot.innerHTML = "";
    slot.appendChild(form);
    var ta = form.querySelector("textarea");
    ta.focus();
    function cancel() { slot.innerHTML = ""; panel.querySelector("[data-act=note]").focus(); }
    form.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "cancel") { cancel(); return; }
      var body = ta.value.trim();
      var err = form.querySelector(".hb-ann-err");
      if (!body) { err.textContent = "Say something first."; err.hidden = false; return; }
      var who = author();
      if (!who) { err.textContent = "A name is needed so the thread has an author."; err.hidden = false; return; }
      b.disabled = true;
      post({ op: "add", page: PAGE, author: who, body: body,
             target: quote ? { type: "TextQuoteSelector", exact: quote, prefix: ctx.prefix, suffix: ctx.suffix } : null })
        .then(function (j) {
          slot.innerHTML = "";
          if (j.thread) state.focus = j.thread.id;
          say("Note saved.");
          return load();
        })
        .catch(function (ex) { err.textContent = ex.message; err.hidden = false; b.disabled = false; });
    });
    ta.addEventListener("keydown", function (e) { if (e.key === "Escape") { e.stopPropagation(); cancel(); } });
  }

  /* ------------------------------------------ a reply, a change request, a decline
     One inline form under the thread. `mode` says what saving means:
       reply    — a reply in the thread, state unchanged
       change   — the reader asks for a change: the thread becomes (or stays) open, waiting
       decline  — whoever acts on the page declines, with the reason the gate requires */
  var PROMPTS = {
    reply: "Reply in this thread.",
    change: "What should change, and why? The thread opens and waits for the agent.",
    decline: "Why not? A declined thread needs its reason."
  };
  var SAID = { reply: "Reply saved.", change: "Change asked for; the thread is waiting.", decline: "Declined." };
  function replyForm(item, t, mode, opener) {
    var old = item.querySelector(".hb-ann-form");
    if (old) old.remove();
    var form = el("div", "hb-ann-form inline hb-ann-ui");
    form.innerHTML =
      '<textarea aria-label="' + esc(PROMPTS[mode]) + '" placeholder="' + esc(PROMPTS[mode]) + '"></textarea>' +
      '<div class="hb-ann-err" role="alert" hidden></div>' +
      '<div class="hb-ann-actions"><button type="button" class="hb-ann-btn primary" data-act="save">' +
      (mode === "decline" ? "Decline" : mode === "change" ? "Ask for the change" : "Reply") + "</button>" +
      '<button type="button" class="hb-ann-btn" data-act="cancel">Cancel</button></div>';
    item.querySelector(".hb-ann-actions").insertAdjacentElement("beforebegin", form);
    var ta = form.querySelector("textarea");
    ta.focus();
    function cancel() { form.remove(); if (opener) opener.focus(); }
    form.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "cancel") { cancel(); return; }
      var body = ta.value.trim();
      var err = form.querySelector(".hb-ann-err");
      if (!body) { err.textContent = mode === "reply" ? "Say something first." : "Say why."; err.hidden = false; return; }
      var who = author();
      if (!who) { err.textContent = "A name is needed so the reply has an author."; err.hidden = false; return; }
      b.disabled = true;
      var req = { op: "reply", page: PAGE, id: t.id, author: who, body: body };
      if (mode === "decline") req.state = "declined";
      if (mode === "change") req.state = "open";
      post(req).then(function () { say(SAID[mode]); return load(); })
        .catch(function (ex) { err.textContent = ex.message; err.hidden = false; b.disabled = false; });
    });
    ta.addEventListener("keydown", function (e) { if (e.key === "Escape") { e.stopPropagation(); cancel(); } });
  }

  /* ------------------------------------------------------------------ render */
  function chips(t, stale) {
    var out = '<span class="hb-ann-chip ' + esc(t.state) + '">' + esc(t.state) + "</span>";
    if (kindOf(t) === "flag") out += '<span class="hb-ann-chip flag" title="An agent wrote this passage beyond its source">flag</span>';
    if (t.label) out += '<span class="hb-ann-chip label">' + esc(t.label) + "</span>";
    if (stale) out += '<span class="hb-ann-chip stale" title="The quoted passage is no longer on the page">stale anchor</span>';
    return out;
  }
  function actions(t) {
    var mine = me() && t.author === me();
    var b = [];
    if (t.state === "open") {
      b.push('<button type="button" class="hb-ann-btn" data-form="reply" data-id="' + esc(t.id) + '">Reply</button>');
      b.push('<button type="button" class="hb-ann-btn primary" data-keep="' + esc(t.id) + '" title="Close the thread as accepted">Keep</button>');
      b.push('<button type="button" class="hb-ann-btn" data-form="decline" data-id="' + esc(t.id) + '">Decline</button>');
    } else if (t.state === "noted") {
      b.push('<button type="button" class="hb-ann-btn primary" data-keep="' + esc(t.id) + '" title="Accept the passage as written">Keep</button>');
      b.push('<button type="button" class="hb-ann-btn" data-form="change" data-id="' + esc(t.id) + '">Ask for a change</button>');
    } else {
      b.push('<button type="button" class="hb-ann-btn" data-state="open" data-id="' + esc(t.id) + '">Reopen</button>');
    }
    if (isLive(t) && mine) {
      b.push('<button type="button" class="hb-ann-btn" data-state="withdrawn" data-id="' + esc(t.id) + '">Withdraw</button>');
    }
    return b.join("");
  }
  function bodyHtml(t) {
    var collapsed = t.state === "noted" && t.body.length > CLIP && !state.expanded[t.id];
    if (!collapsed) return '<div class="hb-ann-body">' + esc(t.body) + "</div>";
    return '<div class="hb-ann-body">' + esc(t.body.slice(0, CLIP)) + '… <button type="button" class="hb-ann-more" data-more="' +
      esc(t.id) + '">more</button></div>';
  }
  function render() {
    var open = 0, noted = 0;
    state.threads.forEach(function (t) {
      if (t.state === "open") open++;
      if (t.state === "noted") noted++;
    });

    var html = [
      '<div class="hb-ann-head"><h2 tabindex="-1">Annotations</h2>',
      '<span><button type="button" class="hb-ann-btn primary" data-act="note">＋ Page note</button> ',
      '<button type="button" class="hb-ann-btn" data-act="close" aria-label="Close annotations">Close</button></span>',
      '<div class="hb-ann-meta">' + open + " waiting · " + noted + " noted · " + state.threads.length +
        " total · select prose to comment on it</div></div>",
      '<div data-composer></div>'
    ];
    if (!state.threads.length) {
      html.push('<div class="hb-ann-empty">No annotations yet. Select some prose, or add a page note.</div>');
    }
    state.threads.slice().reverse().forEach(function (t) {
      var stale = state.stale[t.id];
      html.push('<div class="hb-ann-item hb-ann-' + esc(t.state) + (kindOf(t) === "flag" ? " hb-ann-flag" : "") +
        '" data-id="' + esc(t.id) + '">');
      html.push('<div class="hb-ann-top">' + chips(t, stale) +
        '<span class="hb-ann-meta">' + esc(t.author) + " · " + esc(String(t.created || "").slice(0, 10)) + "</span></div>");
      if (t.target) {
        var q = t.target.exact || "";
        html.push('<button type="button" class="hb-ann-quote" data-goto="' + esc(t.id) + '" title="Jump to the passage">' +
          esc(q.length > 140 ? q.slice(0, 140) + "…" : q) + "</button>");
      }
      html.push(bodyHtml(t));
      (t.replies || []).forEach(function (r) {
        html.push('<div class="hb-ann-reply"><span class="hb-ann-meta">' + esc(r.author || "") + " · " +
          esc(String(r.created || "").slice(0, 10)) + (r.state ? " → " + esc(r.state) : "") + "</span>" +
          '<div class="hb-ann-body">' + esc(r.body || "") + "</div></div>");
      });
      html.push('<div class="hb-ann-actions">' + actions(t) + "</div></div>");
    });
    inner.innerHTML = html.join("");
    if (state.scrollTo) { var id = state.scrollTo; state.scrollTo = null; focusThread(id, true); }
    else if (state.focus) focusThread(state.focus, false);
  }

  panel.addEventListener("click", function (e) {
    var act = e.target.closest("[data-act]");
    if (act && !act.closest(".hb-ann-form")) {
      if (act.dataset.act === "close") setOn(false);
      if (act.dataset.act === "note") compose(null);
      return;
    }
    var go = e.target.closest("[data-goto]");
    if (go) { focusThread(go.dataset.goto, true); return; }
    var more = e.target.closest("[data-more]");
    if (more) { state.expanded[more.dataset.more] = true; state.focus = more.dataset.more; render(); return; }
    var fm = e.target.closest("[data-form]");
    if (fm) {
      var item = fm.closest(".hb-ann-item");
      var t = state.threads.filter(function (x) { return x.id === fm.dataset.id; })[0];
      if (item && t) { state.focus = t.id; replyForm(item, t, fm.dataset.form, fm); }
      return;
    }
    var keep = e.target.closest("[data-keep]");
    if (keep) {
      var who = author();
      if (!who) return;
      keep.disabled = true;
      post({ op: "reply", page: PAGE, id: keep.dataset.keep, author: who, body: "Kept.", state: "addressed" })
        .then(function () { say("Kept."); return load(); })
        .catch(function (ex) { alert(ex.message); keep.disabled = false; });
      return;
    }
    var st = e.target.closest("[data-state]");
    if (st) {
      var name = author();
      if (!name) return;
      st.disabled = true;
      post({ op: "state", page: PAGE, id: st.dataset.id, state: st.dataset.state, author: name })
        .then(function () { say(st.dataset.state === "open" ? "Reopened; the thread is waiting." : "Withdrawn."); return load(); })
        .catch(function (ex) { alert(ex.message); st.disabled = false; });
    }
  });

  function focusThread(id, scroll) {
    state.focus = id;
    panel.querySelectorAll(".hb-ann-item.focus").forEach(function (x) { x.classList.remove("focus"); });
    var item = panel.querySelector('.hb-ann-item[data-id="' + id + '"]');
    if (item) item.classList.add("focus");
    paint();
    if (!scroll) return;
    if (item) {  // the thread in view in the panel's own list — never by scrolling the page
      var ir = inner.getBoundingClientRect(), jr = item.getBoundingClientRect();
      if (jr.top < ir.top || jr.bottom > ir.bottom) inner.scrollTop += jr.top - ir.top - 12;
    }
    var mk = state.marks.filter(function (x) { return x.id === id; })[0];
    if (mk) {  // the passage near the top: clear of a bottom sheet, and of the top bar on a phone
      var r = mk.range.getBoundingClientRect();
      window.scrollTo({ top: window.scrollY + r.top - Math.min(160, window.innerHeight / 4), behavior: "smooth" });
    }
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && state.on && !panel.querySelector(".hb-ann-form textarea")) setOn(false);
  });
})();
