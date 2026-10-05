# Controlled two-Workload capture harness image (v0.6.0 I2.6a; I1 capture runbook §3).
# One image for orders, orders-canary, pricing and legacy-pricing; ROLE selects the behaviour.
FROM python:3.13-slim@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b
WORKDIR /harness
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt
COPY app.py .
USER 65534
CMD ["python", "app.py"]
