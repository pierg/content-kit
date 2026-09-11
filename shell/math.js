/* ============================================================================
   Library — opt-in KaTeX loader
   Include on math-heavy pages with:
     <script src="/shell/math.js" defer></script>
   Then write LaTeX inline: $H(s) \wedge \neg H(s')$
   or display:              $$\forall s.\ H(s) \Rightarrow (H \circ T)(s)$$
   Also accepts \(...\)  and  \[...\]  delimiters.
   Renders locally from shell/vendor/katex — no CDN dependency.
   ========================================================================== */

(function () {
  "use strict";

  var VENDOR = "/shell/vendor/katex/";

  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = VENDOR + "katex.min.css";
  document.head.appendChild(css);

  var katex = document.createElement("script");
  katex.src = VENDOR + "katex.min.js";
  katex.async = false;
  katex.onload = function () {
    var auto = document.createElement("script");
    auto.src = VENDOR + "contrib/auto-render.min.js";
    auto.async = false;
    auto.onload = function () {
      var opts = {
        delimiters: [
          { left: "$$", right: "$$", display: true  },
          { left: "$",  right: "$",  display: false },
          { left: "\\(", right: "\\)", display: false },
          { left: "\\[", right: "\\]", display: true  }
        ],
        throwOnError: false,
        errorColor: "var(--leak)",
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
        ignoredClasses: ["defn-name"]
      };
      var run = function () { window.renderMathInElement(document.body, opts); };
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", run);
      } else {
        run();
      }
    };
    document.head.appendChild(auto);
  };
  document.head.appendChild(katex);
})();
