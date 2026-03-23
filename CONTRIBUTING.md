# Contributing to MERALCO PH API

Thanks for your interest in contributing! This project benefits from community input, and we'd love to have your help.

## How to Contribute

1. **Fork** the repository
2. **Create a branch** for your feature or fix (`git checkout -b feat/my-feature`)
3. **Make your changes** and test them
4. **Submit a Pull Request** back to this repo

Please open a PR rather than maintaining a separate fork — it helps the whole community benefit from improvements.

## Development Setup

```bash
git clone https://github.com/rairulyle/meralco-ph.git
cd meralco-ph
pipenv install --dev
```

### Running the API

```bash
pipenv run start
```

### Running Tests

```bash
pipenv run test
```

## Guidelines

- **Keep changes focused.** One PR per feature or fix.
- **Write clear commit messages.** Use conventional commits when possible (e.g., `feat:`, `fix:`, `docs:`).
- **Test your changes.** Run `pipenv run test` before submitting.
- **Update the CHANGELOG.** If your change is user-facing, add an entry under `[Unreleased]` in `CHANGELOG.md`.
- **Don't bump the version.** Version bumps are handled by the maintainer during release.

## MERALCO PDF URL Pattern Changes

MERALCO hosts rate schedule PDFs on S3. If the URL pattern changes:

1. Check for the current PDF at `https://meralcomain.s3.ap-southeast-1.amazonaws.com/`
2. Update `get_pdf_url()` in `src/parser.py`
3. Include the old and new patterns in your PR description

If the PDF table structure changes (column order, header labels), update the `COL_*` constants and `parse_residential_tiers()` in `src/parser.py`.

## Reporting Issues

- Use [GitHub Issues](https://github.com/rairulyle/meralco-ph/issues) to report bugs or suggest features.
- Include steps to reproduce for bug reports.
- Check existing issues before opening a new one.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
