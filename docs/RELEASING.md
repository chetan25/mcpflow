# MCPFlow Release Guide

This guide covers the process for releasing new versions of MCPFlow to PyPI.

## Version Numbering

MCPFlow uses [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH** (e.g., `1.0.0`, `1.1.0`, `2.0.0`)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## Pre-Release Checklist

Before releasing, ensure:

- [ ] All tests pass: `cd python && pytest tests/ --ignore=tests/test_init.py`
- [ ] Code builds cleanly: `cd python && python -m build`
- [ ] No linting issues: `ruff check .` and `black --check .`
- [ ] README is up-to-date
- [ ] CHANGELOG.md documents changes
- [ ] Git repository is clean (no uncommitted changes)
- [ ] You're on the main branch: `git branch` shows `* main`

## Release Process

### 1. Update Version Numbers

Update to the new version in **two** places:

**python/pyproject.toml:**
```toml
version = "1.2.0"  # Update this line
```

**python/mcpflow/__init__.py:**
```python
__version__ = "1.2.0"  # Update this line
```

### 2. Commit Version Update

```bash
git add python/pyproject.toml python/mcpflow/__init__.py
git commit -m "chore: bump version to 1.2.0"
git push origin main
```

### 3. Create Git Tag

```bash
git tag v1.2.0
git push origin v1.2.0
```

This automatically triggers the **GitHub Actions publish workflow** (`.github/workflows/publish.yml`).

### 4. Monitor the Release

1. Go to https://github.com/chetan25/mcpflow/actions
2. Watch the "Publish to PyPI" workflow
3. It will:
   - Run full test suite
   - Build wheel + source distribution
   - Verify metadata
   - Upload to PyPI
   - Create GitHub Release

The process takes ~2-3 minutes.

### 5. Verify Publication

After the workflow succeeds:

- Check PyPI: https://pypi.org/project/mcpflow/
- Install and test: `pip install --upgrade mcpflow[webmcp]==1.2.0`
- Verify version: `mcpflow --version`

## Troubleshooting

### Build fails: "Version mismatch"
**Problem:** git tag version doesn't match pyproject.toml
```
Version mismatch: pyproject.toml has 1.2.0 but tag has 1.2.1
```
**Solution:** Delete the tag and create a new one with matching version
```bash
git tag -d v1.2.1
git push origin :v1.2.1  # Delete remote tag
# Fix versions in files
git commit -am "chore: fix version"
git tag v1.2.1
git push origin v1.2.1
```

### "PYPI_API_TOKEN not set"
**Problem:** GitHub secrets not configured
**Solution:** 
1. Generate PyPI API token at https://pypi.org/manage/account/token/
2. Go to https://github.com/chetan25/mcpflow/settings/secrets/actions
3. Add secret named `PYPI_API_TOKEN` with the token

### "User account is not verified"
**Problem:** PyPI account email not verified
**Solution:** Verify email address at https://pypi.org/manage/account/

### Manual Upload (Emergency Fallback)

If the GitHub Actions workflow fails:

```bash
cd python

# Build
python -m build

# Upload manually
pip install twine
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=<your-pypi-token>
twine upload dist/*
```

## After Release

- [ ] Upload release artifacts to GitHub Release page (auto-created by workflow)
- [ ] Announce on Reddit r/Python (if appropriate)
- [ ] Update project website/docs
- [ ] Close related GitHub issues

## Rollback

If a release has critical bugs:

1. Yank the release on PyPI:
   ```
   pip uninstall mcpflow  # WARNING: breaks existing installs
   ```
   (Use PyPI's "Yank" feature on the version page)

2. Fix the bugs on `main`

3. Do a new release with bumped version

4. Un-yank the broken version if it was a mistake

---

For questions, see `.github/workflows/publish.yml` or open an issue.
