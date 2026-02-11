"""
CyberSource Unified Checkout - Python/Flask Sample Application

This is a Python conversion of the CyberSource Unified Checkout Node.js sample.
It demonstrates generating a capture context, loading the Unified Checkout SDK,
and processing payment responses with widget-managed service orchestration.

Flow (with completeMandate):
  1. Generate Capture Context with completeMandate configuration:
       - type: AUTH (authorize payment)
       - consumerAuthentication: true (Payer Authentication / 3DS)
       - tms.tokenCreate: true (create TMS token)
  2. Unified Checkout widget captures payment info via up.show()
  3. up.complete(tt) orchestrates: 3DS Authentication → Authorization → TMS Token
  4. Widget returns orchestrated result to server via form POST
  5. Server displays the authorization result
"""

import json
import base64
import os
import ssl
import traceback

from flask import Flask, render_template, request

from CyberSource import (
    ApiClient,
    UnifiedCheckoutCaptureContextApi,
)
from CyberSource.rest import ApiException

from data.configuration import MerchantConfiguration

app = Flask(__name__)
app.secret_key = os.urandom(24)

# -------------------------------------------------------------------
# Utility
# -------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _decode_jwt_payload(jwt_token: str) -> dict:
    """Decode the payload (second segment) of a JWT without verification."""
    payload_segment = jwt_token.split(".")[1]
    # Add padding if needed
    padding = 4 - len(payload_segment) % 4
    if padding != 4:
        payload_segment += "=" * padding
    decoded_bytes = base64.urlsafe_b64decode(payload_segment)
    return json.loads(decoded_bytes)


def _get_cybersource_config():
    """Build and return a CyberSource configuration dictionary."""
    config = MerchantConfiguration()
    return config.get_configuration()


# -------------------------------------------------------------------
# Routes – Capture Context Flow
# -------------------------------------------------------------------


@app.route("/")
def index():
    """Home page – choose use case."""
    return render_template("index.html")


@app.route("/ucoverview")
def uc_overview():
    """Display capture context request editor."""
    json_path = os.path.join(DATA_DIR, "default-uc-capture-context-request.json")
    with open(json_path, "r") as f:
        json_request = f.read()
    return render_template("uc_overview.html", json_request=json_request)


@app.route("/capture-context", methods=["POST"])
def capture_context():
    """Generate a Unified Checkout Capture Context via the CyberSource API."""
    try:
        # The CyberSource SDK expects the request body as a JSON string
        request_json_str = request.form["captureContextRequest"]
        # Validate it's valid JSON
        json.loads(request_json_str)

        config_dict = _get_cybersource_config()
        api_client = ApiClient()
        api_instance = UnifiedCheckoutCaptureContextApi(config_dict, api_client)

        data, status, body = (
            api_instance.generate_unified_checkout_capture_context_with_http_info(
                request_json_str
            )
        )

        if data:
            decoded_data = _decode_jwt_payload(data)
            return render_template(
                "capture_context.html",
                capture_context=data,
                decoded_data=json.dumps(decoded_data, indent=2),
            )
        else:
            return f"Error: No data returned. Status: {status}", 500

    except Exception as e:
        print(f"\nException on calling the API: {e}")
        traceback.print_exc()
        return f"Error: {e}", 500


# -------------------------------------------------------------------
# Routes – Checkout
# -------------------------------------------------------------------


@app.route("/checkout", methods=["POST"])
def checkout():
    """Render the checkout page with the Unified Checkout widget."""
    try:
        decoded_data = json.loads(request.form["captureContextDecoded"])
        capture_context_jwt = request.form["captureContext"]

        # Extract the client library URL and integrity hash from the decoded JWT
        client_library_url = decoded_data["ctx"][0]["data"]["clientLibrary"]
        client_library_integrity = decoded_data["ctx"][0]["data"][
            "clientLibraryIntegrity"
        ]

        return render_template(
            "checkout.html",
            url=json.dumps(client_library_url),
            client_library_integrity=json.dumps(client_library_integrity),
            capture_context=capture_context_jwt,
        )

    except Exception as e:
        return f"Error: {e}", 500


# -------------------------------------------------------------------
# Routes – Payment Result (widget-managed via completeMandate)
# -------------------------------------------------------------------


@app.route("/process-payment", methods=["POST"])
def process_payment():
    """
    Display the payment result from the Unified Checkout widget.

    With completeMandate configured (type=AUTH, consumerAuthentication=true,
    tms.tokenCreate=true), the UC widget orchestrates all services:
      - Payer Authentication (3DS) enrollment + challenge
      - Payment authorization
      - TMS token creation

    The widget's up.complete() returns the orchestrated result as a JWT.
    This route decodes and displays that result.
    """
    try:
        widget_response = request.form.get("response", "")

        if not widget_response:
            return render_template(
                "complete_response.html",
                response="{}",
                decoded_data="{}",
                payment_status="ERROR",
            )

        # The widget response is a JWT — decode its payload for display
        try:
            decoded = _decode_jwt_payload(widget_response)
            response_json = json.dumps(decoded, indent=2)
        except Exception:
            # If it's not a JWT, treat it as raw JSON or string
            try:
                decoded = json.loads(widget_response)
                response_json = json.dumps(decoded, indent=2)
            except (json.JSONDecodeError, TypeError):
                decoded = {"rawResponse": widget_response[:2000]}
                response_json = json.dumps(decoded, indent=2)

        # Extract payment status from the decoded response
        payment_status = "UNKNOWN"
        if isinstance(decoded, dict):
            # The complete mandate response may contain different structures
            # depending on the outcome (authorized, declined, error, etc.)
            payment_status = (
                decoded.get("status")
                or decoded.get("paymentStatus")
                or decoded.get("orderStatus")
                or "COMPLETED"
            )

            # Log key info
            txn_id = decoded.get("id", decoded.get("transactionId", "N/A"))
            print(f"\n[process-payment] Status: {payment_status}")
            print(f"[process-payment] Transaction ID: {txn_id}")

        return render_template(
            "complete_response.html",
            response=response_json,
            decoded_data=response_json,
            payment_status=payment_status,
        )

    except Exception as e:
        print(f"\nException processing payment result: {e}")
        traceback.print_exc()
        return render_template(
            "complete_response.html",
            response=json.dumps({"error": str(e)}, indent=2),
            decoded_data=json.dumps({"error": str(e)}, indent=2),
            payment_status="ERROR",
        )


# -------------------------------------------------------------------
# Error handlers
# -------------------------------------------------------------------


@app.errorhandler(404)
def not_found(e):
    return (
        render_template("error.html", message="Not Found", status=404, stack=""),
        404,
    )


@app.errorhandler(500)
def internal_error(e):
    return (
        render_template(
            "error.html",
            message="Internal Server Error",
            status=500,
            stack=str(e),
        ),
        500,
    )


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------


if __name__ == "__main__":
    # Read port from config
    config = MerchantConfiguration()
    port = config.port

    cert_dir = os.path.join(os.path.dirname(__file__), "certs")
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(
        certfile=os.path.join(cert_dir, "server.cert"),
        keyfile=os.path.join(cert_dir, "server.key"),
    )

    print(f" * Running on https://localhost:{port}")
    app.run(host="0.0.0.0", port=port, ssl_context=ssl_context, debug=True)
