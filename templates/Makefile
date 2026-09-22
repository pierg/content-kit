# Content repo Makefile — the kit's targets; add whatever is local below.
.DEFAULT_GOAL := help
.PHONY: help check docs serve down status site kit-verify kit-sync

HOST ?=
PORT ?=

help:
	@echo "Targets:"
	@echo "  check       The content gate: version pin · shell · form · genre · annotations · books"
	@echo "  docs        Serve the pages on this repo's port (background); ✎ Annotate appears bottom-right"
	@echo "  down        Stop the server"
	@echo "  status      Is the server up?"
	@echo "  site        Write the pages as a static site to dist/ (BASE=/repo/ for a project site)"
	@echo "  kit-verify  Confirm the vendored kit/ matches its pin"
	@echo "  kit-sync    Re-vendor kit/ from its pinned sources (deliberate)"
	@echo
	@echo "Override host/port:  make docs PORT=8080"

check: kit-verify
	@ckit check

docs:
	@HOST=$(HOST) PORT=$(PORT) ckit up

serve: docs

down:
	@ckit down

status:
	@ckit status || true

BASE ?= /
site:
	@ckit export --out dist --base $(BASE)

kit-verify:
	@bash kit/verify.sh

kit-sync:
	@bash kit/verify.sh --sync
