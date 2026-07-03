uv run python scripts/generate_mock_logs.py \
  --ioc-file days/day-30.prompt.md \
  --write-files \
  --write-bootstrap-kql \
  --bootstrap-base-url https://caddy \
  --output-name day-30

uv run python scripts/run_detection_agent_loop.py \
  days/day-30.prompt.md \
  --reuse-mock-log-bundle samples/generated_mock_logs/day-30 \
  --max-iterations 5 \
  --redact-paths

# The following command is commented out because the mock logs have already been generated and the loop has already been run. If you want to re-run the loop, you can uncomment this command.
# uv run python scripts/run_detection_agent_loop.py \
#   days/day-30.prompt.md \
#   --max-iterations 5 \
#   --rows-per-table 3 \
#   --bootstrap-base-url https://caddy \
#   --output-name day-30 \
#   --redact-paths

uv run python scripts/write_day_report.py \
  --day-number 30 \
  --title "The Mini Shai-Hulud Campaign" \
  --source-document days/day-30.source.md \
  --result-json samples/generated_mock_logs/day-30/loop_result.json \
  --output days/day-30.md \
  --link "https://www.stepsecurity.io/blog/a-mini-shai-hulud-has-appeared#indicators-of-compromise" \
  --link "https://snyk.io/blog/tanstack-npm-packages-compromised/" \
  --link "https://www.upwind.io/feed/mini-shai-hulud-targets-sap-npm-packages-ci-cd-publishing-pipeline-abused-in-supply-chain-attack"