# Start the video-cut web workbench

Start `uv run video-cut serve` in background, log to fixed path `/tmp/video-cut-serve.log`, verify it answers on http://127.0.0.1:8462.

Steps:

1. If port 8462 already has a listener (`lsof -ti:8462`), do not start a second instance. Curl `http://127.0.0.1:8462/` to confirm it responds; if it answers, report "already running" and stop.
2. Otherwise run: `uv run video-cut serve > /tmp/video-cut-serve.log 2>&1 &`
3. Poll until `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8462/` returns 200 (max ~15s, reload mode needs time to boot).
4. Report the URL and the log path. On failure, tail `/tmp/video-cut-serve.log` and quote the error.
