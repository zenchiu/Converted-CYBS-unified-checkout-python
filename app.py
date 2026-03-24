"""
CyberSource Unified Checkout - Python/Flask Sample Application

Supports two payment flows:

Flow A – Widget-managed (completeMandate):
  1. Generate Capture Context with completeMandate (consumerAuthentication: true)
  2. up.show() captures card → up.complete(tt) orchestrates 3DS + Auth + TMS
  3. Widget posts result to /process-payment → complete_response.html

Flow B – Combined server-side 3DS (Payments API with CONSUMER_AUTHENTICATION):
  1. Generate Capture Context (manual-3ds config, no completeMandate)
  2. up.show() captures card → transient token submitted to /payer-auth-combined
  3. Server calls POST /pts/v2/payments with actionList: [CONSUMER_AUTHENTICATION]
     - AUTHORIZED (frictionless 3DS) → complete_response.html
     - PENDING_AUTHENTICATION → step_up.html (3DS challenge iframe)
  4. Cardholder completes OTP → ACS posts TransactionId to /step-up-complete
  5. blank_page.html redirects parent frame to /payer-auth-validate
  6. Server calls POST /pts/v2/payments with VALIDATE_CONSUMER_AUTHENTICATION
  7. Result displayed on complete_response.html
"""

import glob
import json
import base64
import os
import ssl
import traceback

from flask import Flask, render_template, request, session

from CyberSource import (
    ApiClient,
    PaymentsApi,
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
CONFIG_FILE_PATTERN = "default-uc-capture-context-request*.json"


def _get_available_capture_context_configs():
    """Return list of (filename, display_name) for available capture context configs."""
    pattern = os.path.join(DATA_DIR, CONFIG_FILE_PATTERN)
    files = glob.glob(pattern)
    prefix = "default-uc-capture-context-request"
    base_name = f"{prefix}.json"

    def sort_key(p):
        name = os.path.basename(p)
        return (0 if name == base_name else 1, name)

    files = sorted(files, key=sort_key)
    result = []
    for f in files:
        name = os.path.basename(f)
        if name == base_name:
            display = "default"
        else:
            display = name.replace(f"{prefix}-", "").replace(".json", "").replace("-", " ")
        result.append((name, display))
    return result


def _load_capture_context_config(filename: str) -> str:
    """Load capture context JSON from data dir."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config not found: {filename}")
    with open(path, "r") as f:
        return f.read()


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


def _del_none(d: dict) -> dict:
    """Recursively remove None values from a dict (required by CyberSource SDK)."""
    for key, value in list(d.items()):
        if value is None:
            del d[key]
        elif isinstance(value, dict):
            _del_none(value)
    return d


def _parse_api_body(body) -> dict:
    """Normalise a CyberSource API response body to a plain dict."""
    if isinstance(body, dict):
        return body
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"rawBody": body}
    return {}


def _get_order_info(config_filename: str = "default-uc-capture-context-request-manual-3ds.json") -> dict:
    """Return the orderInformation block from a capture context config file."""
    raw = _load_capture_context_config(config_filename)
    return json.loads(raw).get("orderInformation", {})


# -------------------------------------------------------------------
# Routes – Capture Context Flow
# -------------------------------------------------------------------


@app.route("/")
def index():
    """Home page – choose use case."""
    return render_template("index.html")


@app.route("/ucoverview")
def uc_overview():
    """Display capture context request editor with config selection."""
    configs = _get_available_capture_context_configs()
    selected = request.args.get("config")
    # Validate selected or use first available
    filenames = [c[0] for c in configs]
    if not selected or selected not in filenames:
        selected = filenames[0] if filenames else "default-uc-capture-context-request.json"
    json_request = _load_capture_context_config(selected)
    return render_template(
        "uc_overview.html",
        json_request=json_request,
        configs=configs,
        selected_config=selected,
    )


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
        return (
            render_template(
                "error.html",
                message="Capture Context API Error",
                status=500,
                stack=str(e),
            ),
            500,
        )


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

        # Extract payment status from the decoded response.
        # The completeMandate response JWT may have status at the top level
        # or nested inside a "content" object (per CyberSource transient token format).
        payment_status = "UNKNOWN"
        if isinstance(decoded, dict):
            content = decoded.get("content") or {}
            payment_status = (
                decoded.get("status")
                or decoded.get("paymentStatus")
                or decoded.get("orderStatus")
                or content.get("status")
                or content.get("paymentStatus")
                or "COMPLETED"
            )

            # Log key info
            txn_id = (
                decoded.get("id")
                or decoded.get("transactionId")
                or content.get("id")
                or content.get("transactionId")
                or "N/A"
            )
            print(f"\n[process-payment] Status: {payment_status}")
            print(f"[process-payment] Transaction ID: {txn_id}")

        return render_template(
            "complete_response.html",
            response=widget_response,
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
# Routes – Combined Server-side 3DS (Payments API + CONSUMER_AUTHENTICATION)
# -------------------------------------------------------------------


@app.route("/payer-auth-combined", methods=["POST"])
def payer_auth_combined():
    """
    Combined 3DS Payer Authentication via a single Payments API call.

    Receives the transient token from up.show() and calls
    POST /pts/v2/payments with actionList: ["CONSUMER_AUTHENTICATION"].
    This single call replaces the separate setup / enrollment / validation
    risk API calls used in a traditional manual 3DS flow.

    Outcomes:
    - AUTHORIZED             → frictionless 3DS, render complete_response.html
    - PENDING_AUTHENTICATION → 3DS challenge needed, render step_up.html
    """
    try:
        transient_token = request.form.get("transientToken", "")
        if not transient_token:
            return (
                render_template(
                    "error.html",
                    message="Missing transient token",
                    status=400,
                    stack="",
                ),
                400,
            )

        # Persist token so /payer-auth-validate can reuse it after step-up
        session["transient_token"] = transient_token

        order_info = _get_order_info()
        amount = order_info.get("amountDetails", {})
        bill_to = order_info.get("billTo", {})

        payment_request = {
            "clientReferenceInformation": {
                "code": f"UC-3DS-{transient_token[:8]}"
            },
            "processingInformation": {
                "actionList": ["CONSUMER_AUTHENTICATION"],
                "capture": True,
            },
            "tokenInformation": {
                "transientTokenJwt": transient_token
            },
            "orderInformation": {
                "amountDetails": {
                    "totalAmount": amount.get("totalAmount", "0.00"),
                    "currency": amount.get("currency", "USD"),
                },
                "billTo": {
                    "firstName": bill_to.get("firstName", ""),
                    "lastName": bill_to.get("lastName", ""),
                    "address1": bill_to.get("address1", ""),
                    "locality": bill_to.get("locality", ""),
                    "administrativeArea": bill_to.get("administrativeArea", ""),
                    "postalCode": bill_to.get("postalCode", ""),
                    "country": bill_to.get("country", ""),
                    "email": bill_to.get("email", ""),
                    "phoneNumber": bill_to.get("phoneNumber", ""),
                },
            },
            "consumerAuthenticationInformation": {
                # The ACS posts TransactionId to this URL after OTP completion
                "returnUrl": f"https://{request.host}/step-up-complete",
            },
        }

        request_json = json.dumps(_del_none(payment_request))
        config_dict = _get_cybersource_config()
        api_client = ApiClient()
        api_instance = PaymentsApi(config_dict, api_client)
        data, status_code, body = api_instance.create_payment(request_json)

        response_body = _parse_api_body(body)
        payment_status = response_body.get("status", "UNKNOWN")

        print(f"\n[payer-auth-combined] HTTP {status_code}, status: {payment_status}")

        if payment_status == "PENDING_AUTHENTICATION":
            consumer_auth = response_body.get("consumerAuthenticationInformation", {})
            step_up_url = consumer_auth.get("stepUpUrl", "")
            access_token = consumer_auth.get("accessToken", "")

            if not step_up_url or not access_token:
                raise ValueError(
                    "PENDING_AUTHENTICATION but step-up data is missing: "
                    f"stepUpUrl={step_up_url!r}, accessToken present={bool(access_token)}"
                )

            return render_template(
                "step_up.html",
                step_up_url=step_up_url,
                access_token=access_token,
            )

        # Frictionless 3DS (AUTHORIZED) or any other terminal status
        return render_template(
            "complete_response.html",
            response=json.dumps(response_body),
            decoded_data=json.dumps(response_body, indent=2),
            payment_status=payment_status,
        )

    except Exception as e:
        print(f"\nException in payer_auth_combined: {e}")
        traceback.print_exc()
        return render_template(
            "complete_response.html",
            response=json.dumps({"error": str(e)}),
            decoded_data=json.dumps({"error": str(e)}, indent=2),
            payment_status="ERROR",
        )


@app.route("/step-up-complete", methods=["POST"])
def step_up_complete():
    """
    3DS step-up callback: receives the TransactionId posted by the ACS
    (card issuer) after the cardholder completes the OTP challenge.

    The ACS posts to this URL (configured as returnUrl in the enrollment
    request). This response loads inside the step-up iframe. blank_page.html
    uses window.top to redirect the full page to /payer-auth-validate.
    """
    transaction_id = request.form.get("TransactionId", "")
    print(f"\n[step-up-complete] TransactionId: {transaction_id!r}")
    session["three_ds_transaction_id"] = transaction_id
    return render_template("blank_page.html")


@app.route("/payer-auth-validate", methods=["GET"])
def payer_auth_validate():
    """
    Validates 3DS authentication and completes payment using
    POST /pts/v2/payments with actionList: ["VALIDATE_CONSUMER_AUTHENTICATION"].

    Retrieves the TransactionId (from session, set by /step-up-complete)
    and the transient token, then calls the Payments API to validate the
    3DS result and capture the payment.
    """
    try:
        transaction_id = session.get("three_ds_transaction_id", "")
        transient_token = session.get("transient_token", "")

        if not transaction_id or not transient_token:
            return (
                render_template(
                    "error.html",
                    message="3DS session data missing — please restart checkout.",
                    status=400,
                    stack="",
                ),
                400,
            )

        order_info = _get_order_info()
        amount = order_info.get("amountDetails", {})
        bill_to = order_info.get("billTo", {})

        payment_request = {
            "clientReferenceInformation": {
                "code": f"UC-3DS-VALIDATE-{transient_token[:8]}"
            },
            "processingInformation": {
                "actionList": ["VALIDATE_CONSUMER_AUTHENTICATION"],
                "capture": True,
            },
            "tokenInformation": {
                "transientTokenJwt": transient_token
            },
            "orderInformation": {
                "amountDetails": {
                    "totalAmount": amount.get("totalAmount", "0.00"),
                    "currency": amount.get("currency", "USD"),
                },
                "billTo": {
                    "firstName": bill_to.get("firstName", ""),
                    "lastName": bill_to.get("lastName", ""),
                    "address1": bill_to.get("address1", ""),
                    "locality": bill_to.get("locality", ""),
                    "administrativeArea": bill_to.get("administrativeArea", ""),
                    "postalCode": bill_to.get("postalCode", ""),
                    "country": bill_to.get("country", ""),
                    "email": bill_to.get("email", ""),
                    "phoneNumber": bill_to.get("phoneNumber", ""),
                },
            },
            "consumerAuthenticationInformation": {
                "authenticationTransactionId": transaction_id,
            },
        }

        request_json = json.dumps(_del_none(payment_request))
        config_dict = _get_cybersource_config()
        api_client = ApiClient()
        api_instance = PaymentsApi(config_dict, api_client)
        data, status_code, body = api_instance.create_payment(request_json)

        response_body = _parse_api_body(body)
        payment_status = response_body.get("status", "UNKNOWN")

        print(f"\n[payer-auth-validate] HTTP {status_code}, status: {payment_status}")

        # Clean up session after a successful or failed validation
        session.pop("three_ds_transaction_id", None)
        session.pop("transient_token", None)

        return render_template(
            "complete_response.html",
            response=json.dumps(response_body),
            decoded_data=json.dumps(response_body, indent=2),
            payment_status=payment_status,
        )

    except Exception as e:
        print(f"\nException in payer_auth_validate: {e}")
        traceback.print_exc()
        return render_template(
            "complete_response.html",
            response=json.dumps({"error": str(e)}),
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
