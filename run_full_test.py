#!/usr/bin/env python3
"""Start server, run e2e test, stop server. Writes all output to e2e_run.log"""
import os
import subprocess
import sys
import time
import urllib.request
import ssl

DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "e2e_run.log")

def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

# Clear log
with open(LOG, "w") as f:
    f.write("")

log("=== Starting E2E Test ===")

# Kill existing server
subprocess.run(["lsof", "-ti:5000"], capture_output=True)
kill = subprocess.run("lsof -ti:5000 | xargs kill -9 2>/dev/null", shell=True, capture_output=True)
time.sleep(2)

# Start server
log("Starting Flask server...")
server = subprocess.Popen(
    [sys.executable, "app.py"],
    cwd=DIR,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

# Wait for server ready
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
for i in range(30):
    try:
        urllib.request.urlopen("https://localhost:5000/", context=ctx, timeout=2)
        log("Server ready.")
        break
    except Exception:
        time.sleep(1)
else:
    log("ERROR: Server did not start")
    server.kill()
    sys.exit(1)

time.sleep(2)

# Run e2e test
log("Running Playwright e2e test...")
result = subprocess.run(
    [sys.executable, "test_e2e.py"],
    cwd=DIR,
    capture_output=True,
    text=True,
    timeout=120,
)
with open(LOG, "a") as f:
    f.write(result.stdout or "")
    f.write(result.stderr or "")
log(f"Test exit code: {result.returncode}")

# Stop server
server.terminate()
server.wait(timeout=5)

log("=== E2E Test Complete ===")
sys.exit(result.returncode)
