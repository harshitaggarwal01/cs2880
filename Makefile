PY ?= python3
CFG ?= config.anthropic.yaml
RUN ?= data/outputs/anthropic-v1
MOCK ?=

.PHONY: help setup test fetch calibrate pilot phase1 generate ablation baseline verify repair sheets ledger evaluate report variance conformal cascade ppi policy redteam demo release clean-mock

help: ## Show this list of targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

setup: ## Install Python requirements
	$(PY) -m pip install -r requirements.txt

test: ## Run the offline unit tests
	$(PY) -m unittest discover -s tests -v

fetch: ## Download GSM8K and ASDiv into data/raw/
	$(PY) src/fetch_data.py

calibrate: ## Make annotation sheets for calibration
	$(PY) src/calibrate.py --make-sheets

pilot: ## Run the pilot stage
	$(PY) src/run_phase1.py --config $(CFG) --until pilot $(MOCK)

phase1: ## Run Phase 1 through annotation sheets
	$(PY) src/run_phase1.py --config $(CFG) --until sheets $(MOCK)

generate: ## Run the generate step
	$(PY) src/run_phase1.py --config $(CFG) --from generate --until generate $(MOCK)

ablation: ## Run the ablation step
	$(PY) src/run_phase1.py --config $(CFG) --from ablation --until ablation $(MOCK)

baseline: ## Run the baseline step
	$(PY) src/run_phase1.py --config $(CFG) --from baseline --until baseline $(MOCK)

verify: ## Run the verify step
	$(PY) src/run_phase1.py --config $(CFG) --from verify --until verify $(MOCK)

repair: ## Run the repair step
	$(PY) src/run_phase1.py --config $(CFG) --from repair --until repair $(MOCK)

sheets: ## Run the annotation sheets step
	$(PY) src/run_phase1.py --config $(CFG) --from sheets --until sheets $(MOCK)

ledger: ## Run the ledger step
	$(PY) src/run_phase1.py --config $(CFG) --from ledger --until ledger $(MOCK)

evaluate: ## Score adjudicated labels against the key
	$(PY) src/evaluate.py --labels $(RUN)/../../annotations/$(notdir $(RUN))/adjudicated.csv --key data/annotations/$(notdir $(RUN))/KEY_DO_NOT_OPEN.csv --analysis-dir $(RUN)/analysis

report: ## Generate the run report
	$(PY) src/report.py --run $(RUN)

variance: ## Run the variance check
	$(PY) src/variance_check.py --config $(CFG) $(MOCK)

conformal: ## Run conformal analysis
	$(PY) src/conformal.py --run $(RUN)

cascade: ## Run cost-aware cascade analysis
	$(PY) src/cascade.py --run $(RUN)

ppi: ## Run prediction-powered inference analysis
	$(PY) src/ppi.py --run $(RUN)

policy: ## Run bandit policy analysis
	$(PY) src/policy.py --run $(RUN)

redteam: ## Run the red-team checks
	$(PY) src/redteam.py --config $(CFG) $(MOCK)

demo: ## Launch the offline Streamlit demo
	streamlit run demo/app.py -- --offline $(RUN)

release: ## Package the release into data/release
	$(PY) src/release.py --run $(RUN) --out data/release

clean-mock: ## Delete all *-mock output and annotation folders
	rm -rf data/outputs/*-mock data/annotations/*-mock
