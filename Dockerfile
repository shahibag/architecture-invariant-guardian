FROM python:3.12-slim

WORKDIR /action
COPY pyproject.toml README.md constraints.txt ./
COPY src ./src
RUN pip install --no-cache-dir -c constraints.txt .

ENTRYPOINT ["invariant-guardian"]

