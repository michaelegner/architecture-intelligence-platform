"""v0.8 I3 functional test (spec §6, D15): the Connect-RPC driver run after step 8.

Standard library only. It drives the services' own Connect-RPC endpoints (JSON over HTTP POST to
`<base>/<package.Service>/<Method>`), with the method names and fields of the pinned
`*-service-api` protos (catalog `7cecb3e`, image `2167948`, product-query `692895e`,
category-query `1638e1d`, tenant `d9b9097`):

1. Shop and product with an image: RegisterTenant, then CreateAttribute and CreateCategory (the
   objects steps 2 and 3 update), CreatePresign, the upload, ConfirmUpload and CreateProduct.
   Product Query returns the product with both image URLs (tenant, product, image promotion).
2. UpdateCategory renames the category; Category Query returns the new name (category flow).
3. UpdateAttribute renames the attribute; Product Query and Category Query return the new name
   (attribute flow).

Every object name carries the run id. Read-model checks poll with a bounded timeout; a timeout is a
recorded failure. Each call records the method, the SHA-256 of the response, the elapsed time and
pass or fail - never a token, a password or a request header. `--dry-run` prints the planned calls
and sends nothing; it needs no endpoint and no token.

Tokens come from operator commands whose stdout is the bearer token, as the environment's own
seeder gets them (Logto client credentials; `harness/v08/i3/tokens/`): `--s2s-token-command` (the
`platform-service` app, `tenants:write`) for RegisterTenant, and `--token-command` (the
`ecommerce-service` app, `cross-tenant`) for the catalog, image and query services. The second
runs once the registration is COMPLETED; from then on every non-tenant call carries
`X-Tenant-Slug: <the new shop>`, which selects the shop for a cross-tenant token.

Exit code: 0 PASSED, 2 FAILED. The verdict file uses the checker.py shape, so `checker.py collect`
merges it into checks.json.
"""

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PASSED, FAILED = "PASSED", "FAILED"
SERVICES = {
    "tenant": "tenant.v1.TenantRegistrationService",
    "attribute": "catalog.v1.AttributeService",
    "category": "catalog.v1.CategoryService",
    "product": "catalog.v1.ProductService",
    "image": "image.v1.ImageService",
    "product-query": "product_query.v1.ProductQueryService",
    "category-query": "category_query.v1.CategoryQueryService",
}
# The endpoint each service name resolves to (--endpoint NAME=URL): catalog serves three services.
ENDPOINT_OF = {
    "tenant": "tenant",
    "attribute": "catalog",
    "category": "catalog",
    "product": "catalog",
    "image": "image",
    "product-query": "product-query",
    "category-query": "category-query",
}
# A 1x1 PNG, the uploaded test image.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4570000000049454e44ae426082"
)


def field(message: dict | None, name: str):
    """A field of a protojson response: lowerCamelCase by default, the proto name if preserved."""
    if not message:
        return None
    head, *rest = name.split("_")
    camel = head + "".join(part.title() for part in rest)
    return message.get(camel, message.get(name))


def names(message: dict | None) -> list[str]:
    return sorted(field(item, "name") or "" for item in (field(message, "attributes") or []))


class Driver:
    def __init__(
        self,
        run_id: str,
        endpoints: dict[str, str],
        token_commands: dict[str, str],
        dry_run: bool,
    ):
        self.run_id = run_id
        self.endpoints = endpoints
        self.token_commands = token_commands
        self.tokens: dict[str, str] = {}
        self.tenant_slug: str | None = None
        self.dry_run = dry_run
        self.calls: list[dict] = []

    def enter_shop(self, slug: str) -> None:
        """Once the shop exists: resolve the service token and send `X-Tenant-Slug: <slug>` on every
        later non-tenant call."""
        self.tenant_slug = slug
        if not self.dry_run:
            self.tokens["user"] = token_from(self.token_commands["user"])

    def need(self, value, what: str):
        """A value an earlier response must carry: a placeholder in a dry run, else a failure."""
        if self.dry_run:
            return f"<{what}>"
        if value in (None, ""):
            raise StepFailed(f"the response carries no {what}")
        return value

    def version(self, message: dict | None, what: str):
        """An object's version for an update: protojson omits 0, so a missing version is 0."""
        if self.dry_run:
            return f"<{what}.version>"
        return field(message, "version") or 0

    def call(self, service: str, method: str, request: dict) -> dict:
        """One RPC; its record never carries the token or the request body."""
        full = f"{SERVICES[service]}/{method}"
        if self.dry_run:
            self.calls.append({"method": full, "request": request})
            return {}
        url = f"{self.endpoints[ENDPOINT_OF[service]].rstrip('/')}/{full}"
        role = "s2s" if service == "tenant" else "user"
        if role not in self.tokens:
            if role == "user":
                raise StepFailed(f"{full}: no service token (the shop is not registered yet)")
            self.tokens[role] = token_from(self.token_commands[role])
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.tokens[role]}",
        }
        if role == "user":
            headers["X-Tenant-Slug"] = self.tenant_slug or ""
        start = time.monotonic()
        record: dict = {"method": full}
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(request).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
            record["result"] = PASSED
            return json.loads(body or b"{}")
        except Exception as exc:  # noqa: BLE001 - every failure is recorded, never re-raised raw
            record["result"] = FAILED
            record["error"] = type(exc).__name__
            body = b""
            raise StepFailed(f"{full} failed ({type(exc).__name__})") from None
        finally:
            record["response_sha256"] = hashlib.sha256(body).hexdigest() if body else None
            record["elapsed_ms"] = round((time.monotonic() - start) * 1000)
            self.calls.append(record)

    def upload(self, url: str) -> None:
        """PUT the test image to the presigned URL (MinIO). The URL itself is never recorded."""
        if self.dry_run:
            self.calls.append({"method": "PUT <presigned upload_url>", "bytes": len(PNG)})
            return
        start = time.monotonic()
        record: dict = {"method": "PUT presigned upload_url"}
        try:
            req = urllib.request.Request(
                url, data=PNG, headers={"Content-Type": "image/png"}, method="PUT"
            )
            with urllib.request.urlopen(req, timeout=30):
                record["result"] = PASSED
        except Exception as exc:  # noqa: BLE001
            record["result"] = FAILED
            record["error"] = type(exc).__name__
            raise StepFailed(f"the image upload failed ({type(exc).__name__})") from None
        finally:
            record["elapsed_ms"] = round((time.monotonic() - start) * 1000)
            self.calls.append(record)

    def poll(self, what: str, service: str, method: str, request: dict, ok, timeout: int) -> dict:
        """Poll a read model until `ok(response)`; a timeout is a recorded failure."""
        if self.dry_run:
            self.calls.append(
                {
                    "method": f"{SERVICES[service]}/{method}",
                    "request": request,
                    "poll_until": what,
                    "timeout_seconds": timeout,
                }
            )
            return {}
        deadline = time.monotonic() + timeout
        while True:
            try:
                response = self.call(service, method, request)
                if ok(response):
                    return response
            except StepFailed:
                pass  # not there yet, or not yet readable: retried until the deadline
            if time.monotonic() >= deadline:
                raise StepFailed(f"timeout after {timeout} s: {what}")
            time.sleep(2)


class StepFailed(Exception):
    pass


def run(driver: Driver, timeout: int) -> list[dict]:
    rid = driver.run_id
    steps: list[dict] = []
    ids: dict[str, str] = {}

    def step(name: str, body) -> None:
        start = len(driver.calls)
        try:
            body()
            result = PASSED
            reason = None
        except StepFailed as exc:
            result, reason = FAILED, str(exc)
        steps.append(
            {"step": name, "result": result, "reason": reason, "calls": driver.calls[start:]}
        )
        if result == FAILED:
            raise StepFailed(reason)

    def shop_and_product() -> None:
        slug = f"i3-{rid}"[:16]
        email = f"aip-i3-{rid}@example.test"
        password = "<generated>" if driver.dry_run else secrets.token_urlsafe(18)
        driver.call(
            "tenant",
            "RegisterTenant",
            {
                "slug": slug,
                "name": f"AIP I3 shop {rid}",
                "email": email,
                "password": password,
                "first_name": "AIP",
                "last_name": f"I3 {rid}"[:32],
            },
        )
        driver.poll(
            "the registration is COMPLETED",
            "tenant",
            "GetRegistrationStatus",
            {"slug": slug},
            lambda r: field(r, "status") == "REGISTRATION_STATUS_COMPLETED",
            timeout,
        )
        driver.enter_shop(slug)
        attribute = field(
            driver.call(
                "attribute",
                "CreateAttribute",
                {
                    "name": f"AIP I3 attribute {rid}",
                    "slug": f"aip-i3-{rid}",
                    "type": "ATTRIBUTE_TYPE_TEXT",
                    "enabled": True,
                },
            ),
            "attribute",
        )
        ids["attribute"] = driver.need(field(attribute, "id"), "attribute.id")
        category = field(
            driver.call(
                "category",
                "CreateCategory",
                {
                    "name": f"AIP I3 category {rid}",
                    "enabled": True,
                    "attributes": [
                        {
                            "attribute_id": ids["attribute"],
                            "role": "CATEGORY_ATTRIBUTE_ROLE_SPECIFICATION",
                        }
                    ],
                },
            ),
            "category",
        )
        ids["category"] = driver.need(field(category, "id"), "category.id")
        ids["category_version"] = driver.version(category, "category")
        presign = driver.call(
            "image",
            "CreatePresign",
            {
                "owner_type": "OWNER_TYPE_DRAFT",
                "owner_id": f"aip-i3-{rid}",
                "filename": f"aip-i3-{rid}.png",
                "content_type": "IMAGE_CONTENT_TYPE_PNG",
                "size": len(PNG),
                "role": "IMAGE_ROLE_MAIN",
            },
        )
        driver.upload(driver.need(field(presign, "upload_url"), "presign.upload_url"))
        image = field(
            driver.call(
                "image",
                "ConfirmUpload",
                {
                    "upload_token": driver.need(
                        field(presign, "upload_token"), "presign.upload_token"
                    ),
                    "alt": f"AIP I3 image {rid}",
                    "role": "IMAGE_ROLE_MAIN",
                },
            ),
            "image",
        )
        ids["image"] = driver.need(field(image, "id"), "image.id")
        product = field(
            driver.call(
                "product",
                "CreateProduct",
                {
                    "name": f"AIP I3 product {rid}",
                    "price": 1,
                    "quantity": 1,
                    "image_id": ids["image"],
                    "category_id": ids["category"],
                    "enabled": True,
                    "attributes": [
                        {"attribute_id": ids["attribute"], "text_value": f"value {rid}"}
                    ],
                },
            ),
            "product",
        )
        ids["product"] = driver.need(field(product, "id"), "product.id")
        driver.poll(
            "Product Query returns the product with both image URLs",
            "product-query",
            "GetProductById",
            {"id": ids["product"]},
            lambda r: bool(
                field(field(r, "product"), "small_image_url")
                and field(field(r, "product"), "large_image_url")
            ),
            timeout,
        )

    def category_update() -> None:
        new_name = f"AIP I3 category {rid} renamed"
        driver.call(
            "category",
            "UpdateCategory",
            {
                "id": ids["category"],
                "name": new_name,
                "enabled": True,
                "version": ids["category_version"],
                "attributes": [
                    {
                        "attribute_id": ids["attribute"],
                        "role": "CATEGORY_ATTRIBUTE_ROLE_SPECIFICATION",
                    }
                ],
            },
        )
        driver.poll(
            "Category Query returns the new category name",
            "category-query",
            "GetCategoryById",
            {"id": ids["category"]},
            lambda r: field(field(r, "category"), "name") == new_name,
            timeout,
        )

    def attribute_update() -> None:
        new_name = f"AIP I3 attribute {rid} renamed"
        current = field(
            driver.call("attribute", "GetAttributeById", {"id": ids["attribute"]}), "attribute"
        )
        driver.call(
            "attribute",
            "UpdateAttribute",
            {
                "id": ids["attribute"],
                "name": new_name,
                "enabled": True,
                "version": driver.version(current, "attribute"),
            },
        )
        driver.poll(
            "Product Query returns the new attribute name",
            "product-query",
            "GetProductById",
            {"id": ids["product"]},
            lambda r: new_name in names(field(r, "product")),
            timeout,
        )
        driver.poll(
            "Category Query returns the new attribute name",
            "category-query",
            "GetCategoryById",
            {"id": ids["category"]},
            lambda r: new_name in names(field(r, "category")),
            timeout,
        )

    try:
        step("1-shop-product-image", shop_and_product)
        step("2-category-update", category_update)
        step("3-attribute-update", attribute_update)
    except StepFailed:
        pass  # the failed step is recorded; later steps depend on it and are not run
    return steps


def token_from(command: str) -> str:
    """Run an operator token command; its stdout is the bearer token. Failures are recorded by
    kind only: neither the token nor the command's output ever reaches the record."""
    try:
        out = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StepFailed(f"a token command failed ({type(exc).__name__})") from None
    token = out.strip()
    if not token:
        raise StepFailed("a token command printed nothing")
    return token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--endpoint",
        action="append",
        default=[],
        metavar="NAME=URL",
        help="tenant, catalog, image, product-query, category-query",
    )
    parser.add_argument("--s2s-token-command")
    parser.add_argument("--token-command")
    parser.add_argument("--timeout", type=int, default=60, help="seconds per read-model poll")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    # The run id goes into the tenant and attribute slugs: lowercase letters and digits only.
    if not re.fullmatch(r"[a-z0-9]{1,12}", args.run_id):
        parser.error("--run-id must be 1-12 lowercase letters or digits")
    endpoints = dict(item.split("=", 1) for item in args.endpoint)
    if not args.dry_run:
        missing = sorted(set(ENDPOINT_OF.values()) - set(endpoints))
        if missing or not args.s2s_token_command or not args.token_command or not args.out:
            parser.error(
                "a live run needs --out, both token commands and every --endpoint "
                f"(missing: {', '.join(missing) or 'none'})"
            )
    token_commands = {"s2s": args.s2s_token_command or "", "user": args.token_command or ""}
    driver = Driver(args.run_id, endpoints, token_commands, args.dry_run)
    steps = run(driver, args.timeout)
    if args.dry_run:
        sys.stdout.write(
            json.dumps({"run_id": args.run_id, "planned": driver.calls}, indent=2) + "\n"
        )
        return 0
    result = PASSED if len(steps) == 3 and all(s["result"] == PASSED for s in steps) else FAILED
    verdict = {
        "kind": "functional",
        "rule": "the three I3 §6 steps pass through the services' Connect-RPC endpoints",
        "result": result,
        "sources": [],
        "run_id": args.run_id,
        "utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timeout_seconds": args.timeout,
        "steps": steps,
    }
    args.out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    return 0 if result == PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
