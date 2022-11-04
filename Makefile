# ---- Setup ---- #
LOCAL_VERSION := "$(shell python setup.py --version)"
REMOTE_VERSION := "$(lastword $(shell pip index versions pyteal))"


# RELEASEABLE := echo "$(LOCAL_VERSION) $(REMOTE_VERSION)" | xargs python -c "import sys; print(0) if sys.argv[-2].split('.') <= sys.argv[-1].split('.') else print(1)"

# echo:
# 	echo $(RELEASEABLE)

# releasable-version:
# ifeq ($(REMOTE_VERSION), $(LOCAL_VERSION))
# 	@$(error Cannot release as remote version = local version = $(LOCAL_VERSION))
# else
# 	@echo "COPACETIC"
# endif

# releaseable-version:
# 	$(ifeq ($(strip $(RELEASEABLE)), 1) ,,$(error Cannot release as remote version = $(REMOTE_VERSION) >= local version = $(LOCAL_VERSION)))

fail-if-unreleasable:
	@echo "$(LOCAL_VERSION) $(REMOTE_VERSION)" | xargs python -c "import sys; a=sys.argv; f=lambda s: list(map(int, s.split('.'))); assert (x:=f(a[-2])) > (y:=f(a[-1])), f'cannot release as local={x} v. pipy={y}'"
	@echo "You're all good to go. Enjoy releasing new_version=$(LOCAL_VERSION) (> pypi=$(REMOTE_VERSION))"


setup-development:
	pip install -e .
	pip install -r requirements.txt --upgrade

setup-docs:
	pip install -r docs/requirements.txt
	pip install doc2dash

setup-wheel:
	pip install wheel

generate-init:
	python -m scripts.generate_init

# ---- Docs and Distribution ---- #

bdist-wheel:
	python setup.py sdist bdist_wheel

bundle-docs-clean:
	rm -rf docs/pyteal.docset

bundle-docs: bundle-docs-clean
	cd docs && \
	make html SPHINXOPTS="-W --keep-going" && \
	doc2dash --name pyteal --index-page index.html --online-redirect-url https://pyteal.readthedocs.io/en/ _build/html && \
	tar -czvf pyteal.docset.tar.gz pyteal.docset

# ---- Code Quality ---- #

check-generate-init:
	python -m scripts.generate_init --check

ALLPY = docs examples pyteal scripts tests *.py
black:
	black --check $(ALLPY)

flake8:
	flake8 $(ALLPY)

MYPY = pyteal scripts tests
mypy:
	mypy --show-error-codes $(MYPY)

lint: black flake8 mypy

# ---- Unit Tests (no algod) ---- #

# TODO: add blackbox_test.py to multithreaded tests when following issue has been fixed https://github.com/algorand/pyteal/issues/199
NUM_PROCS = auto
test-unit:
	pytest -n $(NUM_PROCS) --durations=10 -sv pyteal tests/unit --ignore tests/unit/blackbox_test.py --ignore tests/unit/user_guide_test.py
	pytest -n 1 -sv tests/unit/blackbox_test.py tests/unit/user_guide_test.py

lint-and-test: check-generate-init lint test-unit

# ---- Integration Tests (algod required) ---- #

algod-start:
	docker compose up -d algod --wait

algod-stop:
	docker compose stop algod

integration-run:
	pytest -n $(NUM_PROCS) --durations=10 -sv tests/integration

test-integration: integration-run

all-tests: lint-and-test test-integration

# ---- Local Github Actions Simulation via `act` ---- #
# assumes act is installed, e.g. via `brew install act`

ACT_JOB = run-integration-tests
local-gh-job:
	act -j $(ACT_JOB)

local-gh-simulate:
	act


# ---- Extras ---- #

coverage:
	pytest --cov-report html --cov=pyteal
