# Contributing to MCPFlow

Thank you for your interest in contributing to MCPFlow! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Commit Conventions](#commit-conventions)
- [Running Tests](#running-tests)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Documentation](#documentation)

## Code of Conduct

MCPFlow is committed to providing a welcoming and inclusive environment for all contributors. Please:

- Be respectful and professional
- Welcome different perspectives and experiences
- Focus on constructive feedback
- Report concerning behavior to the maintainers

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- pip or poetry

### Fork and Clone

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mcpflow.git
   cd mcpflow
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/mcpflow/mcpflow.git
   ```

## Development Setup

### Install Development Dependencies

```bash
cd python  # Navigate to Python package directory

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Or with poetry
poetry install --with dev
```

### Verify Installation

```bash
# Run a quick test to verify everything works
python -c "import mcpflow; print(f'MCPFlow {mcpflow.__version__}')"

# Run tests
pytest
```

### Project Structure

```
mcpflow/
├── python/                    # Python package
│   ├── mcpflow/
│   │   ├── __init__.py       # Public API
│   │   ├── server.py         # Core server
│   │   ├── chat.py           # Chat management
│   │   ├── registry.py       # Tool registry
│   │   ├── config.py         # Configuration
│   │   ├── http_bridge.py    # HTTP bridge
│   │   ├── tracing.py        # Tracing support
│   │   ├── testing.py        # Test utilities
│   │   ├── types.py          # Type definitions
│   │   └── cli.py            # CLI interface
│   ├── tests/                 # Test files
│   └── pyproject.toml         # Project configuration
├── docs/                      # Documentation
└── README.md                  # Root README
```

## Making Changes

### Create a Feature Branch

```bash
# Update your main branch
git fetch upstream
git checkout main
git merge upstream/main

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Branch Naming Conventions

- `feature/` - New features
- `bugfix/` - Bug fixes
- `docs/` - Documentation changes
- `test/` - Test additions or improvements
- `refactor/` - Code refactoring
- `chore/` - Maintenance tasks

### Making Your Changes

1. **Make focused changes** - Keep commits atomic and focused on a single concern
2. **Write tests** - Add tests for new functionality
3. **Update documentation** - Update relevant docs
4. **Run tests locally** - Ensure all tests pass

## Commit Conventions

MCPFlow follows conventional commits format for clear history and automated changelog generation.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, semicolons, etc.)
- **refactor**: Code refactoring without feature changes
- **perf**: Performance improvements
- **test**: Test additions or modifications
- **chore**: Build, dependencies, or other maintenance

### Scope

Optional scope specifying the part of the codebase:

- `server` - MCPServer component
- `registry` - Registry components
- `chat` - ChatManager component
- `config` - Configuration system
- `http` - HTTP Bridge
- `tracing` - Tracing/observability
- `cli` - Command-line interface
- `testing` - Testing utilities
- `types` - Type definitions

### Examples

```bash
# Feature with scope
git commit -m "feat(registry): add tool caching for performance"

# Bug fix
git commit -m "fix(chat): handle missing tool in response correctly"

# Documentation
git commit -m "docs: add architecture guide"

# With body for detailed explanation
git commit -m "feat(server): add async tool support

- Support async def tool handlers
- Automatically await async handlers
- Update tests to verify async behavior

Closes #42"
```

## Running Tests

### Run All Tests

```bash
# Basic test run
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=mcpflow

# HTML coverage report
pytest --cov=mcpflow --cov-report=html
```

### Run Specific Tests

```bash
# Run a specific test file
pytest tests/test_server.py

# Run a specific test class
pytest tests/test_server.py::TestMCPServer

# Run a specific test function
pytest tests/test_server.py::TestMCPServer::test_register_tool
```

### Run Tests with Options

```bash
# Stop on first failure
pytest -x

# Run failed tests only
pytest --lf

# Run failed tests first, then others
pytest --ff

# Show local variables in tracebacks
pytest -l

# Drop into debugger on failure
pytest --pdb
```

### Test Coverage

We maintain >80% code coverage. Check coverage:

```bash
pytest --cov=mcpflow --cov-report=term-missing

# Generate HTML report
pytest --cov=mcpflow --cov-report=html
# Open htmlcov/index.html in browser
```

## Pull Request Process

### Before Submitting

1. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run full test suite**:
   ```bash
   pytest
   pytest --cov=mcpflow
   ```

3. **Check code quality**:
   ```bash
   black mcpflow tests
   isort mcpflow tests
   flake8 mcpflow tests
   mypy mcpflow
   ```

### Submit PR

1. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create pull request** on GitHub with:
   - Clear title following commit conventions
   - Description of changes
   - Reference to related issues (Closes #123)
   - List of changes made
   - Any breaking changes noted

3. **PR Description Template**:
   ```markdown
   ## Description
   Brief description of the changes.

   ## Related Issues
   Closes #123

   ## Changes Made
   - Change 1
   - Change 2
   - Change 3

   ## Testing
   - Test 1 added
   - Test 2 added

   ## Breaking Changes
   None (or describe if applicable)

   ## Checklist
   - [x] Tests pass locally
   - [x] Code follows style guidelines
   - [x] Documentation updated
   - [x] No new warnings
   ```

### Review Process

1. **Automated checks** - All tests and linters must pass
2. **Code review** - Maintainers review for:
   - Code quality and style
   - Test coverage
   - Documentation
   - Alignment with project goals
3. **Approval** - At least one maintainer approval required
4. **Merge** - Maintainers merge approved PRs

## Code Style

### Python Style

MCPFlow follows PEP 8 with some opinionated choices:

#### Black Formatting

```bash
# Format code with Black
black mcpflow tests

# Check without modifying
black --check mcpflow tests
```

Configuration in `pyproject.toml`:
- Line length: 100
- Target Python 3.8+

#### Import Sorting

```bash
# Sort imports with isort
isort mcpflow tests

# Check without modifying
isort --check-only mcpflow tests
```

#### Linting

```bash
# Check code with flake8
flake8 mcpflow tests

# Configuration in .flake8:
# - max-line-length: 100
# - ignore: E203, W503 (black compatibility)
```

#### Type Checking

```bash
# Run mypy type checking
mypy mcpflow

# Configuration in pyproject.toml:
# - python_version: 3.8
# - warn_return_any: true
# - warn_unused_configs: true
```

### Code Guidelines

1. **Type Hints**: Use type hints for all functions and methods
   ```python
   # Good
   def register_tool(self, tool: ToolDefinition, handler: Callable) -> None:
       pass

   # Bad
   def register_tool(self, tool, handler):
       pass
   ```

2. **Docstrings**: Use Google-style docstrings
   ```python
   def method(self, param1: str, param2: int = 5) -> bool:
       """Brief description.

       Longer description if needed.

       Args:
           param1: First parameter description
           param2: Second parameter description

       Returns:
           Return value description

       Raises:
           ValueError: When something is wrong
       """
       pass
   ```

3. **Constants**: Use UPPER_CASE for module-level constants
   ```python
   DEFAULT_TIMEOUT = 30.0
   MAX_RETRIES = 3
   ```

4. **Private Members**: Prefix with underscore
   ```python
   class MyClass:
       def __init__(self):
           self._private_var = None
           self.public_var = None

       def _private_method(self):
           pass

       def public_method(self):
           pass
   ```

## Documentation

### Update Existing Docs

When making changes that affect user-facing functionality:

1. **Update QUICKSTART.md** - For user-facing changes
2. **Update ARCHITECTURE.md** - For structural changes
3. **Update API-REFERENCE.md** - For API changes
4. **Update EXAMPLES.md** - Add examples of new features
5. **Update README.md** - For major features

### Add New Docs

For significant features:

1. Create a new markdown file in `/docs`
2. Add a table of contents at the top
3. Link from main README
4. Use clear examples and code blocks

### Code Documentation

1. **Docstrings**: All public functions/classes need docstrings
2. **Comments**: Use comments to explain why, not what
3. **Examples**: Include usage examples for complex features

## Reporting Issues

### Bug Reports

Create a GitHub issue with:

```markdown
## Description
Brief description of the bug

## Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Python version
- MCPFlow version
- OS

## Code Sample
```python
# Minimal code to reproduce
```

## Screenshots
If applicable
```

### Feature Requests

Create a GitHub issue with:

```markdown
## Description
Brief description of the feature

## Use Case
Why this feature is needed

## Proposed Solution
How it should work

## Alternatives
Other ways to solve this

## Additional Context
Any other relevant information
```

## License

By contributing to MCPFlow, you agree that your contributions will be licensed under the MIT License.

## Questions?

- Open a GitHub discussion
- Join our community chat
- Contact the maintainers

## Acknowledgments

Thank you for contributing to MCPFlow! Your efforts help make this project better for everyone.
