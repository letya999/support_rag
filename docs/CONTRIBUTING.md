# Contributing to Support RAG

We are excited that you are interested in contributing to Support RAG! This project aims to be a robust, modular, and easy-to-use RAG system, and your contributions help make it better.

## 🌟 Philosophy

- **Modularity First**: Every transformation should be a "Node".
- **Transparency**: Clear contracts (Input/Output) for everything.
- **Accuracy**: RAG is only as good as its retrieval and reasoning.
- **Community**: Be respectful and helpful.

## 🚀 How to Contribute

1.  **Fork** the repository on GitHub.
2.  **Clone** your fork locally:
    ```bash
    git clone https://github.com/your-username/support_rag.git
    cd support_rag
    ```
3.  **Create a branch** for your changes:
    - Features: `feature/description`
    - Bug fixes: `bugfix/issue-number`
    - Docs: `docs/what-changed`
4.  **Make your changes**.
5.  **Test** your changes locally (see [DEVELOPMENT.md](DEVELOPMENT.md)).
6.  **Commit** your changes using [Conventional Commits](https://www.conventionalcommits.org/):
    ```bash
    git commit -m "feat(nodes): add hybrid reranker node"
    ```
7.  **Push** to your fork:
    ```bash
    git push origin feature/description
    ```
8.  **Open a Pull Request** against the `main` branch.

## 📜 Commit Message Guidelines

We follow the Conventional Commits specification. This leads to more readable messages that are easy to follow when looking through the project history.

- `feat:` A new feature
- `fix:` A bug fix
- `docs:` Documentation only changes
- `style:` Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
- `refactor:` A code change that neither fixes a bug nor adds a feature
- `perf:` A code change that improves performance
- `test:` Adding missing tests or correcting existing tests
- `chore:` Changes to the build process or auxiliary tools and libraries

## 🎨 Code Style

- **Python**: Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/).
- **Indentation**: 4 spaces.
- **Type Hints**: Required for all new functions and classes.
- **Docstrings**: Required for all public modules, functions, and classes (Google Style).
- **Logging**: Use `app.logging_config.logger` instead of `print()`.

## 🛠️ Pull Request Process

- Ensure your PR description clearly explains the problem it solves or the feature it adds.
- Link any related issues in the PR description (e.g., `Fixes #123`).
- One of the maintainers will review your PR as soon as possible.
- Please address any feedback provided during the review process.

## ⚖️ License

By contributing, you agree that your contributions will be licensed under its [MIT License](LICENSE).
