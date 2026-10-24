FROM python:3.11-slim

WORKDIR /app

# Ensure non-root execution and reproducible env
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy source and data
COPY bench /app/bench
COPY tests /app/tests
COPY data /app/data
COPY README.md /app/README.md
COPY REPORT.md /app/REPORT.md

# Default entrypoint runs safe dry-run microbench
ENTRYPOINT ["python", "-m", "bench.cli"]
CMD ["--dry-run", "--validators-count", "6", "--blocks-per-validator", "2"]
