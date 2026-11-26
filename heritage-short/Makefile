# Every target wraps `uv run film <command>`, so it also works without make.
# MOCK=1 runs any target on placeholder providers with the example storyboard.
UV ?= uv
FILM = $(UV) run film
EXAMPLE = tests/fixtures/storyboard.example.json

ifdef MOCK
FLAGS = --mock --storyboard $(EXAMPLE)
endif

.PHONY: setup check test costs smoke storyboard validate plan render radio assemble film mock proposals bundle-shots bundle-music

setup:
	$(UV) sync --all-extras

check: test

test:
	$(UV) run pytest -q

costs:
	$(FILM) costs

smoke:
	$(FILM) smoke $(if $(MOCK),--mock,)

storyboard:
	$(FILM) storyboard $(if $(MOCK),--mock,)

bundle-shots:
	$(FILM) bundle shots $(FLAGS)

bundle-music:
	$(FILM) bundle music $(FLAGS)

proposals:
	$(FILM) proposals $(FLAGS)

validate:
	$(FILM) validate $(FLAGS)

plan:
	$(FILM) plan $(FLAGS)

render:
	$(FILM) render $(FLAGS)

radio:
	$(FILM) radio $(FLAGS)

assemble:
	$(FILM) assemble $(FLAGS)

film:
	$(FILM) build $(FLAGS)

mock:
	$(FILM) build --mock --storyboard $(EXAMPLE)
	$(FILM) radio --mock --storyboard $(EXAMPLE)
