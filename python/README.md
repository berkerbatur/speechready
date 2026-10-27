# speechready (Python)

Prepare text for text-to-speech. See the [repository README](https://github.com/berkerbatur/speechready) for the project overview.

```
pip install speechready
```

Version 0.0.1 is a placeholder that reserves the name. The first working release follows.

## Development

```
cd python
python -m pip install -e ".[dev]"
pytest
```

Tests load the shared fixtures from `../spec`, which both the Python and the JavaScript package must pass.
