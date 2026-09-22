.DEFAULT_GOAL := help
.PHONY: help check selftest e2e wheel

help:
	@echo "Targets:"
	@echo "  check     selftest + an end-to-end install into a scratch repo (what CI runs)"
	@echo "  selftest  the engine's planted-fixture gate"
	@echo "  e2e       init · gate · scaffold · plugins · serve · annotate · export · drift · pin"
	@echo "  wheel     uv tool install this checkout, then init + gate a repo with the installed engine"

selftest:
	@./bin/ckit selftest

e2e:
	@bash tests/e2e.sh

wheel:
	@bash tests/wheel.sh

check: selftest e2e wheel
	@echo "content-kit check ok"
