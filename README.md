# CyberSource Unified Checkout - Python/Flask Sample

A Python conversion of the [CyberSource Unified Checkout Node.js sample](https://github.com/CyberSource/cybersource-unified-checkout-sample-node). This application demonstrates integrating CyberSource Unified Checkout using the [cybersource-rest-client-python](https://github.com/CyberSource/cybersource-rest-client-python) SDK.

## Prerequisites

- **Python 3.7+**
- A CyberSource sandbox account ([register here](https://developer.cybersource.com/))
- Merchant credentials (Merchant ID, Key ID, Secret Key)

## Installation

1. **Create a virtual environment** (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your merchant credentials**:

   Copy the example config and add your CyberSource credentials:

   ```bash
   cp config.ini.example config.ini
   ```

   Edit `config.ini` and set your values:

   ```ini
   [CyberSource]
   merchant_id = your_merchant_id
   key_id = your_key_id
   secret_key = your_secret_key
   run_environment = apitest.cybersource.com

   [App]
   port = 5000
   ```

## Running the Application

```bash
python app.py
```

The application starts an HTTPS server at **https://localhost:5000**.

## Full End-to-End Test (including browser)

The test uses Playwright to automate the full flow: Home → UC Overview → Capture Context → Checkout → Payment Widget → Card Entry → Confirm → Payment Result.

**1. Install test dependencies:**

```bash
pip install playwright
playwright install chromium
```

**2. Run the test** (start the app in another terminal first: `python app.py`):

```bash
# Headless (default)
python test_e2e.py

# Visible browser
python test_e2e.py --headed
```

**3. Or use the test runner** (starts server, runs test, stops server):

```bash
./run_e2e_test.sh           # Headless
./run_e2e_test.sh --headed  # Visible browser
```

Screenshots are saved to `test_screenshots/`.

**Test card (3DS / Payer Auth):** The test uses Visa `4000000000002503` (12/2026, CVV 123) from [CyberSource Test Case 2.9: Step-Up Authentication Is Successful](https://developer.cybersource.com/docs/cybs/en-us/payer-authentication/developer/all/so/payer-auth/pa-testing-intro/pa-testing-3ds-2x-intro/pa-testing-3ds-2x-success-stepup-auth-cruise-hybri.html). This card triggers 3DS/Payer Authentication step-up. The order amount ($500) is set to encourage challenge flow.

**Payer Authentication must be enabled:** Your CyberSource sandbox merchant must have Payer Authentication (EMV 3-D Secure) enabled. Enable it in Business Center → Payment Configuration, or contact CyberSource support.

**OTP / Step-Up flow:** See [docs/OTP_FLOW_VERIFICATION.md](docs/OTP_FLOW_VERIFICATION.md) for documentation verification and how to maximize the chance of triggering the 3DS challenge (OTP).

**"No such issuer" / DECLINED:** If the test fails with `PROCESSOR_ERROR` or "No such issuer", your sandbox merchant may not be configured for test cards. Options: (1) Check CyberSource Business Center → Payment Configuration for your processor, (2) Contact CyberSource support to enable test card processing, (3) Use `E2E_ALLOW_DECLINED=1` to run the test without requiring AUTHORIZED.

> **Note**: The included SSL certificates (`certs/server.cert` and `certs/server.key`) are self-signed for development purposes. Your browser will show a security warning — this is expected for local testing.

## Application Flow

1. **Home page** (`/`) — Choose use case
2. **Overview** (`/ucoverview`) — View/edit the capture context request JSON
3. **Generate Capture Context** (`POST /capture-context`) — Calls CyberSource API to generate a JWT capture context
4. **Checkout** (`POST /checkout`) — Loads the Unified Checkout widget with the capture context
5. **Process Payment** (`POST /process-payment`) — Receives the complete mandate result from the widget (3DS + auth + TMS)

### 3DS / Payer Authentication Flow (completeMandate)

The application uses **Unified Checkout completeMandate** with `consumerAuthentication: true`:

```
Unified Checkout Widget (completeMandate with consumerAuthentication: true)
  │
  ▼  up.show() captures card → up.complete(tt) orchestrates:
  │    1. Payer Authentication (3DS) — enrollment check, then challenge if required
  │    2. Payment authorization
  │    3. TMS token creation
  │
  ▼  Widget submits form to /process-payment with orchestrated result JWT
  │
  └─ AUTHORIZED / DECLINED / ERROR  →  Payment result page
```

- **Frictionless 3DS:** Cardholder authenticated silently; no challenge shown.
- **Step-up challenge:** Cardholder sees OTP/verification in an iframe; completes it; widget continues.

## Project Structure

```
unified-checkout-python/
├── app.py                          # Main Flask application
├── config.ini.example               # Example config (copy to config.ini)
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── certs/
│   ├── server.cert                 # SSL certificate (self-signed)
│   └── server.key                  # SSL private key
├── data/
│   ├── __init__.py
│   ├── configuration.py            # CyberSource merchant configuration
│   └── default-uc-capture-context-request.json
├── Resource/
│   └── NetworkTokenCert.pem        # PEM cert for JWE decryption
├── templates/
│   ├── index.html                  # Home page
│   ├── uc_overview.html            # Capture context request editor
│   ├── capture_context.html        # Capture context display
│   ├── checkout.html               # Checkout page with UC widget
│   ├── step_up.html                # 3DS step-up challenge page
│   ├── complete_response.html      # Payment result page
│   └── error.html                  # Error page
├── static/
│   └── stylesheets/
│       └── style.css               # Custom styles
└── log/                            # CyberSource SDK logs (auto-created)
```

## Environment Configuration

By default, the application connects to the CyberSource **sandbox** environment (`apitest.cybersource.com`). To switch to production, update `run_environment` in `config.ini`:

```ini
run_environment = api.cybersource.com
```

> **Important**: API credentials differ between sandbox and production. Ensure you use the correct credentials for each environment.

## Key Differences from the Node.js Version

| Aspect | Node.js | Python |
|---|---|---|
| Framework | Express | Flask |
| Template Engine | EJS | Jinja2 |
| Port | 3000 | 5000 |
| CyberSource SDK | `cybersource-rest-client` (npm) | `cybersource-rest-client-python` (pip) |
| API Call Style | Callback-based | Synchronous |

## License

See the [LICENSE](../LICENSE) file for details.
