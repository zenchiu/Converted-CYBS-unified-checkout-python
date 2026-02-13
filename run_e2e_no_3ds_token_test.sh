#!/bin/bash
# E2E test for no-3ds-token-with-prefix config
# Uses: default-uc-capture-context-request-no-3ds-token-with-prefix.json
# - No 3DS (consumerAuthentication: false)
# - tokenCreate + tokenTypes, includeCardPrefix
# - Ticks Save card checkbox
# No OTP step - use when COMPLETE_AUTHENTICATION_FAILED or Payer Auth not enabled

set -e
cd "$(dirname "$0")"

PORT=5000
BASE_URL="https://localhost:$PORT"

echo "=============================================="
echo "  E2E Test: no-3ds-token-with-prefix"
echo "  Config: no 3DS, tokenCreate, includeCardPrefix"
echo "  Save card: ticked"
echo "=============================================="
echo ""

if lsof -ti:$PORT >/dev/null 2>&1; then
    echo "Port $PORT in use. Stopping existing process..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 2
fi

echo "Starting Flask server on https://localhost:$PORT..."
python app.py &
SERVER_PID=$!

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
echo "Running test..."
python test_e2e_no_3ds_token.py ${1:-} 2>&1 | tee e2e_no_3ds_token_log.txt
TEST_EXIT=${PIPESTATUS[0]}

echo ""
echo "Stopping server..."
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

echo ""
echo "=============================================="
if [ $TEST_EXIT -eq 0 ]; then
    echo "  E2E TEST COMPLETE (exit code: $TEST_EXIT)"
else
    echo "  E2E TEST FAILED (exit code: $TEST_EXIT)"
fi
echo "  Screenshots: test_screenshots/"
echo "=============================================="

exit $TEST_EXIT
