## Development

### UV cheat sheet

install all dependencies

```bash
uv sync --frozen --all-groups
```

add new dependency

```bash
uv add <package_name>
```

add new dev dependency

```bash
uv add <package_name> --group dev
```

update local env including the lockfile:

```bash
uv sync -U --all-groups
```

update only the lockfile:

```bash
uv lock -U
```
