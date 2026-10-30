"""VQ S1 traffic: RegisterTenant for one shop through the I3 driver, then poll its status.
Usage: python3 register_tenant.py SLUG <AIP checkout>. The password is generated and never printed."""

import json
import secrets
import sys
from pathlib import Path

slug, checkout = sys.argv[1], Path(sys.argv[2])
sys.path.insert(0, str(checkout / "harness/v08/i3"))
import functional_test as ft

tok = f"python3 {checkout}/harness/v08/i3/tokens/token.py"
d = ft.Driver(
    "vq",
    {"tenant": "http://ecommerce-tenant-service.127.0.0.1.nip.io"},
    {"s2s": f"{tok} platform", "user": f"{tok} ecommerce"},
    False,
    connect_to="127.0.0.1",
)
r = d.call(
    "tenant",
    "RegisterTenant",
    {
        "slug": slug,
        "name": f"AIP VQ shop {slug}",
        "email": f"aip-{slug}@example.test",
        "password": secrets.token_urlsafe(18),
        "first_name": "AIP",
        "last_name": "VQ",
    },
)
print("RegisterTenant", json.dumps({"slug": slug, "status": ft.field(r, "status")}))
s = d.poll(
    "COMPLETED",
    "tenant",
    "GetRegistrationStatus",
    {"slug": slug},
    lambda x: ft.field(x, "status") == "REGISTRATION_STATUS_COMPLETED",
    120,
)
print("GetRegistrationStatus", json.dumps({"slug": slug, "status": ft.field(s, "status")}))
