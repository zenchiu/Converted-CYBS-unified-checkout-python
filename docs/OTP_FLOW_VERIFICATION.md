# OTP / Step-Up Flow Verification

This document cross-references the CyberSource documentation to ensure our setup can trigger the 3DS step-up (OTP) flow.

## Documentation Sources Verified

| Document | Purpose |
|---------|---------|
| [2.9: Step-Up Authentication Is Successful](https://developer.cybersource.com/docs/cybs/en-us/payer-authentication/developer/all/so/payer-auth/pa-testing-intro/pa-testing-3ds-2x-intro/pa-testing-3ds-2x-success-stepup-auth-cruise-hybri.html) | Test case 2.9 – Cruise/Hybrid step-up success |
| [Capture Context API](https://developer.cybersource.com/docs/cybs/en-us/unified-checkout/developer/all/rest/unified-checkout/uc-setup-capture-context.html) | UC capture context request structure |
| [Unified Checkout Field Reference](https://developer.cybersource.com/docs/cybs/en-us/unified-checkout/developer/all/rest/unified-checkout/uc-appendix/uc-appendix-pass-through-fields.html) | Pass-through fields for capture context |
| [Check Enrollment Request Fields](https://developer.cybersource.com/docs/cybs/en-us/payer-authentication/developer/all/so/payer-auth/pa2-ccdc-enroll-intro/pa2-ccdc-enrollrequest-fields.html) | Payer Auth Check Enrollment fields |

## Current Configuration Checklist

### ✅ 1. Test Card (2.9 Step-Up)

- **Card:** Visa `4000 0000 0000 2503` (4000000000002503) or Mastercard `5200 0000 0000 1096` (5200000000001096)
- **Expiry:** 12/2026  
- **CVV:** 123  
- **Source:** [CyberSource 2.9 Step-Up Success](https://developer.cybersource.com/docs/cybs/en-us/payer-authentication/developer/all/so/payer-auth/pa-testing-intro/pa-testing-3ds-2x-intro/pa-testing-3ds-2x-success-stepup-auth-cruise-hybri.html)

### ✅ 2. Capture Context – `completeMandate.consumerAuthentication`

- `completeMandate.consumerAuthentication: true` — required for 3DS
- `completeMandate.type: "AUTH"`
- `completeMandate.tms.tokenCreate: true`

### ✅ 3. Order Amount

- `orderInformation.amountDetails.totalAmount: "500.00"` — higher amounts favor challenge flow

### ✅ 4. Billing / Shipping Data

- `billTo` and `shipTo` present — improves risk data for DS/ACS decisions

### ✅ 5. Integration Type

- **2.9 applies to Cruise/Hybrid** — Unified Checkout uses Cardinal (Cruise) for 3DS. Our integration matches the supported type.

## Why OTP May Not Always Appear

The decision between **frictionless** and **step-up challenge** is made by:

1. **Directory Server (DS)** – evaluates risk, BIN, acquirer configuration  
2. **Access Control Server (ACS)** – issuer-side logic  
3. **Regional mandates** – may require or forbid challenge

The UC capture context does **not** expose:

- `challengeRequested`  
- `challengeIndicator`  
- Any “force challenge” flag

So merchants cannot programmatically force a challenge; the flow is driven by backend and issuer logic.

## What We Can Control

| Factor | Our Setting | Notes |
|--------|-------------|-------|
| `consumerAuthentication` | `true` | Must be set for 3DS |
| Order amount | $500 | Higher amount increases chance of challenge |
| Test card | 4000000000002503 | Visa 2.9 step-up |
| Test card | 5200000000001096 | Mastercard |
| Merchant config | Payer Auth enabled | Required in Business Center |

## Recommended Actions to Maximize OTP Appearance

1. **Merchant configuration**  
   - Confirm Payer Authentication (EMV 3-D Secure) is enabled in CyberSource Business Center → Payment Configuration.  
   - Contact CyberSource support to verify challenge flow is enabled for your sandbox merchant.

2. **Alternative test cards**  
   - Try other Payer Auth test cards (e.g. [2.10 Unsuccessful Step-Up](https://developer.cybersource.com/docs/cybs/en-us/payer-authentication/developer/all/so/payer-auth/pa-testing-intro/pa-testing-3ds-2x-intro/pa-testing-3ds-2x-unsuccess-stepup-auth-cruise-hyb.html)) if your issuer setup behaves differently.

3. **UC Field Reference**  
   - The [Unified Checkout Field Reference](https://developer.cybersource.com/docs/cybs/en-us/unified-checkout/developer/all/rest/unified-checkout/uc-appendix/uc-appendix-pass-through-fields.html) documents pass-through fields. No documented pass-through currently forces a challenge; `consumerAuthentication: true` is the only relevant control.

4. **Business Center / Acquirer config**  
   - Some acquirers/processors allow configuration of challenge preference. Check with your CyberSource or acquirer representative.

## Summary

- **Documentation:** All referenced docs have been checked; our setup matches the documented requirements for the 2.9 step-up flow.
- **Configuration:** Capture context, test card, and amount are correctly configured.
- **Limitation:** The challenge vs frictionless decision is made by the 3DS ecosystem, not by our application.
- **E2E test:** The test is prepared for both frictionless and step-up; when step-up occurs, it will detect OTP fields and submit/approve buttons.

The project is **correctly configured** for the OTP flow. If the challenge does not appear, the cause is likely:

- Sandbox merchant not configured for challenge flow  
- Acquirer/issuer sandbox rules favoring frictionless  
- Need to verify with CyberSource support that challenge flow is enabled for your merchant ID

---

## Troubleshooting: COMPLETE_AUTHENTICATION_FAILED

**Error:** `{"name":"AcceptError","reason":"COMPLETE_AUTHENTICATION_FAILED","message":"Consumer Authentication failure."}`

**Cause:** Payer Authentication (3DS) is failing — usually because the merchant does not have EMV 3-D Secure enabled or properly configured in CyberSource Business Center.

**Solutions:**

1. **Enable Payer Authentication** (recommended)
   - Contact CyberSource support to enable EMV 3-D Secure 2.x for your merchant ID
   - See [Enable Merchant Account for EMV 3-D Secure](https://developer.cybersource.com/docs/cybs/en-us/payer-authentication/developer/all/so/payer-auth/pa2-intro-intro/pa2-intro-account-setup.html)
   - Check Business Center → Payment Configuration for Payer Authentication settings

2. **Test without 3DS** (temporary workaround)
   - Use the `no-3ds` preset: `default-uc-capture-context-request-no-3ds.json`
   - Or `no-3ds-token-with-prefix`: `default-uc-capture-context-request-no-3ds-token-with-prefix.json` (adds tokenCreate, includeCardPrefix, requestSaveCard)
   - These set `consumerAuthentication: false` so the flow skips 3DS and processes payment only
   - Run: `./run_e2e_no_3ds_token_test.sh`
