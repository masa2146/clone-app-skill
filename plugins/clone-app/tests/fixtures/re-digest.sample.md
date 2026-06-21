# RE Digest — com.example.app

## Framework & Stack
Native Kotlin · Retrofit + OkHttp · Hilt · kotlinx.serialization · obfuscation: moderate

## Hosts
| Host | Party |
|------|-------|
| api.example.com | first |
| analytics.thirdparty.io | third |

## Endpoint Inventory
| Host | Method | Path | Auth | Source |
|------|--------|------|------|--------|
| api.example.com | POST | /v1/auth/login | none | com/example/api/AuthApi.java |
| api.example.com | GET | /v1/users/profile | Bearer | com/example/api/UserApi.java |
| api.example.com | POST | /v1/orders | Bearer | com/example/api/OrderApi.java |

## Key Flow Payloads
### POST /v1/auth/login (auth)
- request body: `{ "email": "string", "password": "string" }`
- response: `{ "token": "string", "user": {} }`
- headers: `Content-Type: application/json`

### POST /v1/orders (payment/core)
- request body: `{ "items": [], "total": "number" }`
- response: `{ "order_id": "string", "status": "string" }`
- headers: `Authorization: Bearer <token>`

## BuildConfig Secrets
- BASE_URL = https://api.example.com/v1
- ANALYTICS_KEY = <redacted-present>

## Feature Signals
~18 screens · SDKs: Firebase, AppsFlyer · permissions: INTERNET, ACCESS_NETWORK_STATE

## RE Method
re-skill
