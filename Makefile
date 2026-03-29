# OCI Robot Cloud — Developer Makefile
# Run: make help

PYTHON     ?= python3
OCI_HOST   ?= ubuntu@138.1.153.110
ROBOTICS   ?= $(HOME)/roboticsai
CHECKPOINT ?= /tmp/finetune_1000_5k/checkpoint-5000

.PHONY: help install test lint mock-all server eval-mock dagger-mock report ssh-status push clean

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "OCI Robot Cloud — Make Targets"
	@echo "==============================="
	@echo ""
	@echo "  Development:"
	@echo "    make install       Install Python deps (pip install -r requirements.txt)"
	@echo "    make test          Run unit tests (no GPU required)"
	@echo "    make lint          Run ruff linter"
	@echo ""
	@echo "  Local demo (mock mode — no OCI/GPU needed):"
	@echo "    make mock-all      Start all mock services in background"
	@echo "    make stop-all      Stop all background services"
	@echo "    make mock-eval     Run closed-loop eval in mock mode"
	@echo "    make mock-dagger   Run DAgger training in mock mode"
	@echo "    make report        Generate journey HTML report"
	@echo ""
	@echo "  OCI A100 (requires SSH to $(OCI_HOST)):"
	@echo "    make server        Start GR00T inference server on OCI"
	@echo "    make ssh-status    Check OCI services status"
	@echo "    make eval          Run 20-episode closed-loop eval on OCI"
	@echo "    make dagger        Launch DAgger run on OCI (uses tmux)"
	@echo ""
	@echo "  Reporting:"
	@echo "    make profile       Inference latency profile (mock)"
	@echo "    make sla           SLA report (mock)"
	@echo "    make benchmark     Cost benchmark vs AWS/DGX"
	@echo ""
	@echo "  Misc:"
	@echo "    make push          git push to origin/main"
	@echo "    make clean         Remove /tmp report files"

# ── Development ───────────────────────────────────────────────────────────────

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/ --select=E,W,F --ignore=E501

# ── Mock mode (local, no GPU) ─────────────────────────────────────────────────

mock-all:
	@echo "[make] Starting all services in mock mode..."
	@for svc in \
		"src/api/training_monitor.py --port 8004 --mock" \
		"src/api/cost_calculator.py --port 8005" \
		"src/api/design_partner_portal.py --port 8006 --mock" \
		"src/api/data_flywheel.py --port 8020 --mock" \
		"src/api/analytics_dashboard.py --port 8026" \
		"src/api/webhook_notifications.py --port 8021 --mock" \
		"src/api/partner_sla_monitor.py --port 8022 --mock" \
		; do \
		$(PYTHON) $$svc &>/tmp/mock_$$(echo $$svc | md5 | head -c6).log & \
		echo "  Started: $$svc"; \
	done
	@echo ""
	@echo "Services running (check http://localhost:<port>):"
	@echo "  8004 Training Monitor    8005 Cost Calculator"
	@echo "  8006 Partner Portal      8020 Data Flywheel"
	@echo "  8021 Webhooks            8022 SLA Monitor"
	@echo "  8026 Analytics           "
	@echo ""
	@echo "Stop with: make stop-all"

stop-all:
	@pkill -f "training_monitor\|cost_calculator\|design_partner_portal\|data_flywheel\|analytics_dashboard\|webhook_notifications\|partner_sla" 2>/dev/null || true
	@echo "[make] All mock services stopped."

mock-eval:
	$(PYTHON) src/eval/closed_loop_eval.py --mock --n-episodes 20 \
		--output /tmp/mock_eval.html
	@echo "Report: /tmp/mock_eval.html"

mock-dagger:
	$(PYTHON) src/training/dagger_train.py --mock --n-iters 3 --n-episodes 10

report:
	$(PYTHON) src/eval/generate_journey_report.py \
		--output /tmp/journey_report.html
	@echo "Report: /tmp/journey_report.html"

profile:
	$(PYTHON) src/eval/inference_profiler.py --mock \
		--output /tmp/inference_profile.html
	@echo "Profile: /tmp/inference_profile.html"

sla:
	$(PYTHON) src/api/partner_sla_monitor.py --mock &
	@sleep 3
	@curl -s http://localhost:8022/report > /tmp/sla_report.html
	@pkill -f partner_sla_monitor 2>/dev/null || true
	@echo "SLA report: /tmp/sla_report.html"

benchmark:
	$(PYTHON) src/training/cloud_benchmark.py --mock \
		--output /tmp/benchmark.html
	@echo "Benchmark: /tmp/benchmark.html"

# ── OCI A100 ──────────────────────────────────────────────────────────────────

server:
	@echo "[make] Starting GR00T server on OCI GPU4..."
	ssh $(OCI_HOST) "tmux new-session -d -s groot_server \
		'export CUDA_VISIBLE_DEVICES=4; \
		 /home/ubuntu/Isaac-GR00T/.venv/bin/python3 \
		 $(ROBOTICS)/src/inference/groot_franka_server.py \
		 --checkpoint $(CHECKPOINT) --port 8002 \
		 2>&1 | tee /tmp/groot_server.log'"
	@echo "Server launching... check with: make ssh-status"

ssh-status:
	ssh $(OCI_HOST) 'echo "=== GPU ==="; nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv,noheader; \
		echo ""; echo "=== tmux sessions ==="; tmux list-sessions 2>/dev/null || echo "none"; \
		echo ""; echo "=== service ports ==="; \
		for p in 8002 8004 8005 8006 8015 8016 8017 8018 8019 8020; do \
			curl -sf http://localhost:$$p/health -m 2 && echo " :$$p OK" || echo " :$$p DOWN"; \
		done'

eval:
	ssh $(OCI_HOST) "/home/ubuntu/Isaac-GR00T/.venv/bin/python3 \
		$(ROBOTICS)/src/eval/closed_loop_eval.py \
		--server-url http://localhost:8002 --n-episodes 20 \
		--output /tmp/eval_result.html && \
		echo 'Eval done. Report at /tmp/eval_result.html'"

dagger:
	@echo "[make] Launching DAgger run6 on OCI in tmux..."
	ssh $(OCI_HOST) "tmux new-session -d -s dagger_run6 \
		'bash $(ROBOTICS)/src/training/dagger_run6.sh 2>&1 | tee /tmp/dagger_run6.log'"
	@echo "DAgger started. Monitor: ssh $(OCI_HOST) 'tmux attach -t dagger_run6'"

preflight:
	ssh $(OCI_HOST) "bash $(ROBOTICS)/src/infra/aiworld_demo_setup.sh"

# ── Misc ──────────────────────────────────────────────────────────────────────

push:
	git push origin main

clean:
	@rm -f /tmp/mock_*.log /tmp/eval_*.html /tmp/journey_report.html \
		/tmp/inference_profile.* /tmp/sla_report.html /tmp/benchmark.html
	@echo "[make] Cleaned /tmp report files."
