# alexify

**alexify** is a command-line tool and Python library that helps you enrich your BibTeX files with metadata from [OpenAlex](https://openalex.org/). It automates the process of matching entries by Title and/or DOI, retrieving corresponding OpenAlex IDs, and optionally fetching detailed JSON metadata about those works.

## Installation

You can install **alexify** via [Poetry](https://python-poetry.org/):

```bash
# Clone or download the alexify repository, then inside the project directory:
poetry install
```

This will install all dependencies in a Poetry-managed virtual environment.

If you want to install it system-wide (not always recommended), you can build a wheel or rely on Poetry’s export methods:

```bash
# Build a wheel or sdist
poetry build

# Install the wheel or sdist with pip
pip install dist/alexify-0.1.0-py3-none-any.whl
```

(Adjust version and filenames as appropriate.)

## Usage

After installation, a command-line script named `alexify` should be available.

> **Note:** You can optionally specify an email address (e.g., `--email yourname@example.com`) to configure `pyalex.config.email`. This helps identify you when making requests to OpenAlex and lets you join the [polite pool](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication) which has more consistent response times. If omitted, no email is set and your requests go via the [common pool](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication).

### Global Option: `--email`

You can place `--email` before any subcommand to configure your email for all requests. For example:

```bash
alexify --email yourname@example.com process /path/to/bib/files
```

or

```bash
alexify --email yourname@example.com fetch /path/to/processed-oa.bib -o /path/to/out
```

If you do not provide `--email`, the tool will make requests without an email address.

### 1. `alexify process`

```bash
alexify [--email you@example.com] process /path/to/bib/files [--interactive] [--force] [--strict]
```

- `/path/to/bib/files` can be a single `.bib` file or a directory containing multiple `.bib` files.
- `--interactive` (or `-i`) prompts the user for confirmation on borderline fuzzy matches.
- `--force` (or `-f`) overwrites existing `-oa.bib` files if they already exist.
- `--strict` applies more stringent thresholds for fuzzy matching, reducing the chance of incorrect matches.

**Result:**
Creates or updates a corresponding `*-oa.bib` file for each original `.bib` file, adding an `openalex` field to matched entries.

#### Example

```bash
# Process .bib files in /bibliography, with an email set for pyalex,
# interactive matches, and forcing overwrite of existing -oa.bib:
alexify --email yourname@example.com process /bibliography --interactive --force
```

### 2. `alexify fetch`

```bash
alexify [--email you@example.com] fetch /path/to/bib/files -o /path/to/out [--force]
```

- `/path/to/bib/files` can be a single processed `.bib` file (i.e., `*-oa.bib`) or a directory.
- `-o /path/to/out` specifies where to store OpenAlex JSON files.
- `--force` overwrites existing JSON files if they already exist.

**Result:**
For each entry that has an OpenAlex ID, retrieves JSON metadata from the OpenAlex API and saves it under `output_dir/<year>/<ID>.json`.

#### Example

```bash
# Fetch OpenAlex metadata from a processed -oa.bib, store results under /out/:
alexify --email yourname@example.com fetch /mybibfiles-oa.bib -o /out --force
```

### 3. `alexify missing`

```bash
alexify [--email you@example.com] missing /path/to/bib/files
```

- `/path/to/bib/files` can be a single `*-oa.bib` file or a directory containing multiple `*-oa.bib` files.

**Result:**
Lists any BibTeX entries that do not have an OpenAlex ID (i.e., the tool could not match them).

#### Example

```bash
alexify missing /mybibfiles-oa.bib
```

## License

This project is licensed under the MIT License.

## Development

To set up a development environment with all dependencies and cached wheels, run
`./setup-dev.sh` while online. The script installs required system packages,
creates a Python virtual environment and runs the test suite to verify the
setup.

