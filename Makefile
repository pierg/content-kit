.DEFAULT_GOAL := help
.PHONY: help check selftest e2e

help:
	@echo "Targets:"
	@echo "  check     selftest + an end-to-end install into a scratch repo (what CI runs)"
	@echo "  selftest  the engine's planted-fixture gate"
	@echo "  e2e       install · gate · scaffold · serve · annotate round-trip · drift · pin"

selftest:
	@./bin/ckit selftest

e2e:
	@bash tests/e2e.sh

check: selftest e2e
	@echo "content-kit check ok"
