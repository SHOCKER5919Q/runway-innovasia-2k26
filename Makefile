# Thin wrapper over ./run.sh so `make` works for anyone who expects it.
.PHONY: setup dev api web seed test test-pg test-web test-all verify evaluate audit build migrate reset clean help
.DEFAULT_GOAL := help

SCENARIO ?= B

help:          ## Show this help
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:         ## Install dependencies and seed the demo workspace
	./run.sh setup $(SCENARIO)
dev:           ## Run the API and the web app together
	./run.sh dev
api:           ## Run only the API
	./run.sh api
web:           ## Run only the web app
	./run.sh web
seed:          ## Reseed the demo workspace (make seed SCENARIO=C)
	./run.sh seed $(SCENARIO)
reset:         ## Drop and rebuild the database
	./run.sh seed $(SCENARIO)
test:          ## Run the backend test suite (SQLite)
	./run.sh test
test-pg:       ## Run the same suite against PostgreSQL
	./run.sh test-pg
test-web:      ## Run the frontend test suite
	./run.sh test-web
test-all:      ## Backend and frontend tests together
	./run.sh test-all
migrate:       ## Apply database migrations
	./run.sh migrate
audit:         ## Check every VARCHAR column is wide enough
	./run.sh audit-schema
verify:        ## Check every accounting invariant
	./run.sh verify
evaluate:      ## Reproduce every published accuracy figure
	./run.sh evaluate
build:         ## Production build of the web app
	./run.sh build
clean:         ## Remove build artefacts and the demo database
	rm -rf frontend/.next data/runway.db data/runway.db-wal data/runway.db-shm
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
