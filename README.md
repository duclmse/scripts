# scripts

A collection of Python utilities for Kubernetes management, Git operations, and
miscellaneous developer tooling.

## Requirements

- Python 3.12+
- Dependencies: `blessed`, `pandas`, `playwright`, `pypdf`, `pyyaml`

## Installation

```bash
uv sync
```

All scripts use absolute imports from the project root, so run them from this
directory or add it to `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/scripts
```

## Tools

### Kubernetes Manager (`k8s.py`)

A full-featured Kubernetes CLI with 40+ commands.

```bash
python k8s.py --help
python k8s.py -n <namespace> <command> [options]
```

**Global flags:** `-n/--namespace`, `-c/--context`, `-a/--app`, `-o/--output`,
`-v/--verbose`, `--no-color`

**Commands:**

| Command                           | Description                      |
| --------------------------------- | -------------------------------- |
| `list`                            | List resources                   |
| `logs` / `logs-all` / `logs-grep` | Fetch pod logs                   |
| `exec` / `shell-all`              | Execute commands in pods         |
| `status` / `health` / `doctor`    | Check cluster health             |
| `top` / `cost`                    | Resource usage and cost          |
| `scale` / `restart` / `rollout`   | Manage deployments               |
| `apply` / `delete` / `diff`       | Manage manifests                 |
| `secrets`                         | Manage secrets                   |
| `port-forward`                    | Forward ports                    |
| `describe` / `events`             | Inspect resources                |
| `deps` / `tree` / `compare`       | Analyze relationships            |
| `backup` / `clone`                | Copy resources across namespaces |
| `git-deploy`                      | Deploy from git                  |
| `jobs`                            | Manage jobs                      |
| `watch` / `alerts`                | Watch and alert                  |
| `fav`                             | Manage favorites                 |
| `complete`                        | Shell completion                 |

### Git Repository Manager (`git.py`)

Multi-repository management tool.

```bash
python git.py --help
python git.py -f repos.json clone
python git.py -f repos.json sync
python git.py -f repos.json status
```

**Commands:** `clone`, `push`, `sync`, `backup`, `discover`, `import`, `list`,
`validate`

**Config file format (`repos.json`):**

```json
{
  "remotes": { "origin": "https://github.com/user" },
  "repos": [{ "repo": "my-repo", "folder": "local-name", "branch": "main" }]
}
```

### ARM64 Assembler (`asm.py` / `asm.v9.py`)

ARM64/Apple Silicon assembler targeting Mach-O format.

```bash
python asm.py <input.s> -o <output>
```

### Markdown Extractor (`md_extract.py`)

Extract and save code blocks from Markdown files.

```bash
python md_extract.py <file.md> [--output-dir ./out] [--lang python]
```

### JaCoCo Parser (`jacoco.py`)

Parse JaCoCo XML coverage reports.

```bash
python jacoco.py <report.xml>
```

### Other Utilities

| File          | Description                |
| ------------- | -------------------------- |
| `scraper.py`  | Web scraper                |
| `leetcode.py` | LeetCode helpers           |
| `gzip_.py`    | Gzip compression utilities |
| `snippet.py`  | Code snippet manager       |

## Project Structure

```
scripts/
├── core/               # Shared: colors, logging, command decorators
├── utils/              # Shared: formatters, parsers, validators
├── k8s/                # Kubernetes manager
│   ├── commands/       # Individual command modules (40+)
│   └── config/         # Configuration
├── file_format/        # File format converters (CSV→SQL, flat files)
├── fs/                 # Filesystem utilities (gzip, rename)
├── graph/              # Graph visualization
├── shell/              # Shell scripts
├── git.py              # Git repository manager
├── asm.py              # ARM64 assembler
├── md_extract.py       # Markdown code extractor
└── jacoco.py           # JaCoCo coverage parser
```
