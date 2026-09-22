.DEFAULT_GOAL := help
.PHONY: help check selftest e2e wheel site-check site serve

help:
	@echo "Targets:"
	@echo "  check       selftest + e2e + wheel + site-check (what CI runs)"
	@echo "  selftest    the engine's planted-fixture gate"
	@echo "  e2e         init · gate · scaffold · plugins · serve · annotate · export · drift · pin"
	@echo "  wheel       uv tool install this checkout, then init + gate a repo with the installed engine"
	@echo "  site-check  the content gate on this repo's own documentation (content/)"
	@echo "  site        export the documentation as a static site to _site/"
	@echo "  serve       serve the documentation on the port in kit.json (foreground)"

selftest:
	@./bin/ckit selftest

e2e:
	@bash tests/e2e.sh

wheel:
	@bash tests/wheel.sh

site-check:
	@./bin/ckit check

site:
	@./bin/ckit export --out _site

serve:
	@./bin/ckit serve

check: selftest e2e wheel site-check
	@echo "content-kit check ok"
