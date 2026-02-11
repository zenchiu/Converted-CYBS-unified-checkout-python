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

   Edit `data/configuration.py` and uncomment/set your credentials:

   ```python
   self.merchant_id = "YOUR_MERCHANT_ID"
   self.merchant_key_id = "YOUR_MERCHANT_KEY_ID"
   self.merchant_secret_key = "YOUR_MERCHANT_SECRET_KEY"
   ```

## Running the Application

```bash
python app.py
```

The application starts an HTTPS server at **https://localhost:5000**.

> **Note**: The included SSL certificates (`certs/server.cert` and `certs/server.key`) are self-signed for development purposes. Your browser will show a security warning — this is expected for local testing.

## Application Flow

1. **Home page** (`/`) — Choose use case
2. **Overview** (`/ucoverview`) — View/edit the capture context request JSON
3. **Generate Capture Context** (`POST /capture-context`) — Calls CyberSource API to generate a JWT capture context
4. **Checkout** (`POST /checkout`) — Loads the Unified Checkout widget with the capture context
5. **Process Payment** (`POST /process-payment`) — Bundled payment + 3DS Payer Authentication call
6. **3DS Step-Up** (`POST /step-up-callback`) — Handles the 3DS challenge callback (if required)
7. **Payment Result** — Displays the authorization response

### Bundled Payer Authentication (3DS) Flow

This application uses the **bundled** approach for 3D Secure authentication, which simplifies the integration:

```
Unified Checkout Widget (completeMandate.type = "CUSTOM")
  │
  ▼  Returns transient token JWT
Server: POST /pts/v2/payments  (bundled 3DS + authorization)
  │
  ├─ AUTHORIZED (frictionless)  →  Show success
  ├─ PENDING_AUTHENTICATION     →  3DS step-up challenge
  │       │
  │       ▼  Cardholder completes challenge
  │   POST /step-up-callback (TransactionId)
  │       │
  │       ▼  Server: POST /pts/v2/payments (with authenticationTransactionId)
  │       └─ AUTHORIZED / DECLINED  →  Show result
  └─ DECLINED / ERROR             →  Show result
```

The bundled approach makes a **single API call** (`POST /pts/v2/payments`) that includes `consumerAuthenticationInformation`. CyberSource handles the 3DS enrollment check internally and either:
- **Authorizes immediately** (frictionless 3DS) — no cardholder interaction needed
- **Returns PENDING_AUTHENTICATION** — the cardholder must complete a 3DS step-up challenge with their issuer, after which a second payment call completes the authorization

## Project Structure

```
unified-checkout-python/
├── app.py                          # Main Flask application
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

By default, the application connects to the CyberSource **sandbox** environment (`apitest.cybersource.com`). To switch to production, update `run_environment` in `data/configuration.py`:

```python
self.run_environment = "api.cybersource.com"
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
