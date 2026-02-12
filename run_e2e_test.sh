#!/bin/bash
# Full end-to-end test: starts server, runs Playwright browser test, stops server

set -e
cd "$(dirname "$0")"

PORT=5000
BASE_URL="https://localhost:$PORT"

echo "=============================================="
echo "  CyberSource Unified Checkout - E2E Test"
echo "=============================================="
echo ""

# Check if server is already running
if lsof -ti:$PORT >/dev/null 2>&1; then
    echo "Port $PORT in use. Stopping existing process..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Start server in background
echo "Starting Flask server on https://localhost:$PORT..."
python app.py &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to be ready
echo "Waiting for server to be ready..."
for i in {1..30}; do
    if curl -sk "$BASE_URL/" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q 200; then
        echo "Server is ready."
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Server failed to start in time"
        kill $SERVER_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

echo ""
echo "Running Playwright browser test..."
echo ""

# Run e2e test (headless by default, pass --headed for visible browser)
HEADED=""
if [ "$1" = "--headed" ]; then
    HEADED="--headed"
    echo "Running with visible browser"
fi

python test_e2e.py $HEADED 2>&1 | tee e2e_run_log.txt
TEST_EXIT=${PIPESTATUS[0]}

# Stop server
echo ""
echo "Stopping server..."
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

echo ""
echo "=============================================="
if [ $TEST_EXIT -eq 0 ]; then
    echo "  E2E TEST COMPLETED (exit code: $TEST_EXIT)"
    echo "  Screenshots: test_screenshots/"
else
    echo "  E2E TEST FAILED (exit code: $TEST_EXIT)"
fi
echo "=============================================="

exit $TEST_EXIT
