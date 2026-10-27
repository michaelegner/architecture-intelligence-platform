"""v0.8 I3 token command (functional test, I3 §6): one Logto client-credentials access token.

Standard library only. It reads the app's client id and secret from the Kubernetes secret
`logto-credentials` that the environment's own `logto-seed` writes, posts the client-credentials
request exactly as the environment's seeder does (`cmd/seeder/internal/auth/auth.go`), and prints
only the access token. The secret never reaches a command line, stdout or stderr; a failure prints
its kind only and exits 1.

  python3 harness/v08/i3/tokens/token.py platform    # RegisterTenant (tenants:write)
  python3 harness/v08/i3/tokens/token.py ecommerce   # catalog, image, query (cross-tenant)
"""

import base64
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

# app -> (secret key prefix in logto-credentials, requested scope). The ecommerce scope is the
# seeder's; both apps are MachineToMachine apps of the pinned logto-seed seed.json.
APPS = {
    "platform": ("platform", "tenants:write"),
    "ecommerce": (
        "ecommerce-m2m",
        (
            "cross-tenant products:read products:write categories:read categories:write "
            "attributes:read attributes:write images:write"
        ),
    ),
}
RESOURCE = "https://api.sokolshop.com"


class TokenError(Exception):
    pass


def credentials(prefix: str) -> tuple[str, str]:
    try:
        out = subprocess.run(
            ["kubectl", "-n", "dev", "get", "secret", "logto-credentials", "-o", "json"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        data = json.loads(out)["data"]
        client_id = base64.b64decode(data[f"{prefix}-client-id"]).decode()
        client_secret = base64.b64decode(data[f"{prefix}-client-secret"]).decode()
        return client_id, client_secret
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TokenError(f"reading logto-credentials failed ({type(exc).__name__})") from None
    except (ValueError, KeyError, TypeError) as exc:
        raise TokenError(
            f"logto-credentials has no usable {prefix} entry ({type(exc).__name__})"
        ) from None


def fetch(app: str, logto_url: str) -> str:
    prefix, scope = APPS[app]
    client_id, client_secret = credentials(prefix)
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "resource": RESOURCE,
            "scope": scope,
        }
    ).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"{logto_url.rstrip('/')}/oidc/token", data=body, method="POST"),
            timeout=30,
        ) as resp:
            token = json.loads(resp.read()).get("access_token")
    except Exception as exc:  # noqa: BLE001 - the kind only; the response may echo the request
        raise TokenError(f"the token request failed ({type(exc).__name__})") from None
    if not isinstance(token, str) or not token:
        raise TokenError("the token response has no access_token")
    return token


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in APPS:
        sys.stderr.write(f"usage: token.py {{{','.join(sorted(APPS))}}}\n")
        return 1
    try:
        token = fetch(args[0], os.environ.get("LOGTO_URL", "http://localhost:3001"))
    except TokenError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(token + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
