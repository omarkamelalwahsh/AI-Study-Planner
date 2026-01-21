# Security Policy

## Data Privacy

* **Sessions**: Chat history is stored in PostgreSQL.
* **Memory**: User preferences are stored only if explicitly enabled (`ENABLE_MEMORY`).
* **Personally Identifiable Information (PII)**: This system is designed to be anonymous by default. Do not store email/passwords unless implementing proper Auth (not currently included).

## Secrets Management

* **Credentials**: Never commit credentials to Git.
* **Configuration**: Use `.env` file for all secrets (`DATABASE_URL`, API Keys).
* **Defaults**: `.env.example` contains safe defaults.

## Vulnerability Reporting

If you find a security issue, please open an issue on GitHub or contact the maintainers directly. Do not disclose vulnerabilities publicly until patched.
