# Contributing to ViT-CORE-FORENSICS

Thanks for your interest in contributing. This is primarily a research/portfolio
project, but issues, bug reports, and pull requests are welcome.

## Reporting Issues

- Search existing issues before opening a new one.
- Include your OS, Python/Node versions, and full error output (logs are more
  useful than screenshots for backend issues).
- For model-output issues, include the input file type (image/video) and the
  `face_quality` / `is_low_confidence` fields from the response if available.

## Development Setup

See the [Quick Start](README.md#quick-start) section of the README. Run the
backend smoke tests before submitting a PR:

```bash
cd backend
pytest tests/ -v
```

And confirm the frontend builds cleanly:

```bash
cd frontend
npm run build
```

## Pull Requests

- Keep PRs focused — one logical change per PR.
- For changes to `model.py`, explain the rationale (this affects inference
  behaviour and should be considered carefully).
- Update `MODEL_CARD.md` if your change affects benchmark numbers, training
  data, or known limitations.
- CI must pass (`.github/workflows/ci.yml`) before review.

## Security

If you discover a security issue (auth bypass, injection, etc.), please do
**not** open a public issue. See [SECURITY.md](SECURITY.md) for disclosure
instructions.
