# Stop the video-cut web workbench

Steps:

1. Find listeners on port 8462: `lsof -ti:8462`
2. If none, report "not running" and stop.
3. Otherwise kill them: `lsof -ti:8462 | xargs kill` — then re-check `lsof -ti:8462`.
4. If still listening, escalate to `kill -9` on remaining pids.
5. Confirm port free, report pids killed.
