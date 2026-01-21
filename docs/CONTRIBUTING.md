# Contributing Guide

Thank you for your interest in contributing to Career Copilot!

## 🛠️ Development Workflow

1. **Fork the repository** and clone it locally.
2. **Create a new branch** for your feature or fix:

    ```bash
    git checkout -b feature/amazing-feature
    ```

3. **Make your changes**. Please follow the coding standards:
    - **Python**: PEP 8 (use `black` or `ruff` if possible).
    - **React**: Functional components, Hooks patterns.
4. **Test your changes**:
    - Verify backend starts: `uvicorn app.main:app`
    - Verify frontend builds: `npm run build`
5. **Commit and Push**:

    ```bash
    git commit -m "feat: add amazing feature"
    git push origin feature/amazing-feature
    ```

6. **Open a Pull Request**.

## 🧪 Testing

- Current tests are located in `tests/` (if re-added in future) or verify manually using the `verify_*.py` scripts in `scripts/`.

## 📜 Meaningful Commits

Please use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code restructuring without logic change
