PY ?= python3

.PHONY: film demo radio validate test smoke reference costs web clean

film:            ## the whole pipeline: validate -> narration -> keyframes -> shots -> music -> assemble
	$(PY) -m pipeline.run_all

demo:            ## no keys needed: placeholder frames + synthetic voice, real FFmpeg assembly
	DRY_RUN=1 $(PY) -m pipeline.run_all --dry-run

radio:           ## narration-only prototype for user test 1
	$(PY) -m pipeline.narration && $(PY) -m pipeline.radiocut

validate:
	$(PY) -m pipeline.validate

smoke:           ## call each provider once, log latency to runs.jsonl
	$(PY) -m pipeline.smoke_test

reference:       ## N options per character, choose a golden reference
	$(PY) -m pipeline.keyframes reference

costs:           ## aggregate runs.jsonl into the COSTS.md measurement tables
	$(PY) -m pipeline.report_costs

web:             ## launch local showcase & family story studio at http://127.0.0.1:8000
	$(PY) -m pipeline.web

test:
	$(PY) -m unittest discover -s tests -v

clean:
	rm -rf outputs/segments outputs/tmp outputs/mix outputs/final outputs/radiocut
