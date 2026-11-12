# One-command refresh. Phase 4 completes this (analyses, models, charts, screenshots, findings).
FIXTURE ?= 0
FLAG := $(if $(filter 1,$(FIXTURE)),--fixture,)

.PHONY: refresh check
refresh:
	./scripts/refresh.sh $(FLAG)

check:
	./scripts/check.sh $(FLAG)
