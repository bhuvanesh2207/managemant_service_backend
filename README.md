# 🔐 Admin Authentication & Security Architecture

## 📌 Overview
This project implements a **secure admin authentication system** using **JWT (JSON Web Tokens)** stored in **HttpOnly cookies**, combined with **Django CSRF protection**.  
The architecture is designed to prevent **XSS**, **CSRF**, and **token theft**, while still providing a **smooth admin user experience**.

---

## 🛡️ Security Goals
- Prevent JavaScript access to authentication tokens
- Protect against Cross-Site Scripting (XSS)
- Protect against Cross-Site Request Forgery (CSRF)
- Allow seamless login sessions without frequent re-authentication
- Restrict access strictly to admin (superuser) accounts
- Ensure **frontend can only communicate with trusted backend URLs**

---

## 🔑 Authentication Strategy

### JWT in HttpOnly Cookies
- **Access Token**
  - Short-lived (1 hour)
  - Stored in **HttpOnly cookie**
  - Used for authenticating protected admin APIs

- **Refresh Token**
  - Long-lived (7 days)
  - Stored in **HttpOnly cookie**
  - Used only to generate new access tokens
  - Blacklisted on logout

> Tokens are **never accessible via JavaScript**, eliminating XSS-based token theft.

---

## 🔄 Token Lifecycle

1. **Login**
   - User submits email & password
   - Server validates credentials
   - Confirms user is a **superuser**
   - Issues:
     - Access token (HttpOnly cookie)
     - Refresh token (HttpOnly cookie)
     - CSRF token (returned in response body)

2. **Authenticated Requests**
   - Browser automatically sends cookies
   - Frontend sends CSRF token via `X-CSRFToken` header
   - Django validates CSRF + JWT

3. **Access Token Expired**
   - API returns `401 Unauthorized`
   - Axios interceptor calls `/api/admin/refresh/`
   - New access token is issued automatically
   - Original request is retried

4. **Logout**
   - Refresh token is blacklisted
   - Access & refresh cookies are cleared
   - Session is fully invalidated

---

## 🔐 CSRF Protection

- Django CSRF middleware is enabled
- CSRF token is:
  - Generated on login & refresh
  - Stored in frontend (`localStorage`)
  - Sent in `X-CSRFToken` header for all requests
- Ensures that **only same-site requests are accepted**

---

## 🚪 API Endpoints

### 🔹 `POST /api/admin/login/`
- Public endpoint
- Validates credentials
- Allows **only superusers**
- Sets JWT cookies
- Returns CSRF token

---

### 🔹 `POST /api/admin/refresh/`
- Uses refresh token from HttpOnly cookie
- Issues a new access token
- Returns new CSRF token
- Keeps user logged in without re-authentication

---

### 🔹 `POST /api/admin/logout/`
- Blacklists refresh token (if present)
- Clears access & refresh cookies
- Works even if tokens are expired
- Fully invalidates admin session

---

### 🔹 `GET /api/admin/check_auth/`
- Uses **access token from HttpOnly cookie**
- Validates JWT and superuser access
- Returns user info for protected frontend routes

---

## 🧠 Why a Refresh Token Endpoint Exists

- Enables **short-lived access tokens** for security
- Allows **silent session renewal**
- Prevents frequent login prompts
- Keeps refresh token hidden from JavaScript
- Centralizes token renewal logic
- Enables secure logout using token blacklisting

---

## ✅ Security Benefits Achieved

✔ Protection against XSS
✔ Protection against CSRF
✔ Secure token storage
✔ Admin-only access enforcement
✔ Automatic token refresh
✔ Secure logout with token invalidation
✔ Protected frontend routes
✔ Frontend communicates only with allowed backend URL


