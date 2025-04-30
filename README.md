There are two ways to run the pipeline:

1. Using Airflow (recommended)
  - You need to have Docker and Python installed.
  - You need to run Airflow and then trigger the DAG.
    - You can use `bash start.sh` to quickly start Airflow.
2. Using the individual pipeline steps
  - This is best for development, testing, and debugging purposes.

## Airflow Setup

First, git clone this repo.

```sh
git clone <REPONAME>
```

Then, **_in this project's directory_**, run the following command:

```sh
cp .env.example .env
echo "AIRFLOW_HOME=$(pwd)/" >> .env
```

To start the airflow standalone server (requires Docker to be running), run:

```sh
docker info > /dev/null 2>&1 && export $(grep -v '^#' .env | xargs) && uv run airflow standalone || echo "Error: Docker is not running! Please start Docker first."
```

If the Airflow files are created somewhere else other this repository, you can unset AIRFLOW_HOME first with:

```sh
unset AIRFLOW_HOME
```

## Manual Setup

### Project Setup

- Ensure your local Python version is supported by the project (3.12)
- Install dependencies (including dev dependencies):
```sh
uv pip install --extra dev -r pyproject.toml
```


### Run Individual Pipeline Steps (if you don't want to use Airflow & Docker)

You can run each step of the pipeline individually using `uv run python ...`:

#### 1. Prepare Documents

```sh
uv run python pipeline/load_documents.py \
    --input_csv data/documents.csv \
    --output_json output/docs_for_extraction.json
```

#### 2. Extract Entities

```sh
uv run python pipeline/extract_entities.py \
    --input_json output/docs_for_extraction.json \
    --output_json output/dummy_extracted_entities.json
```

#### 3. Match Entities

```sh
uv run python pipeline/match_entities.py \
    --input_json output/dummy_extracted_entities.json \
    --aliases_csv data/entity_aliases.csv \
    --output_json output/matched_entities.json
```

#### 4. Store Results

```sh
uv run python pipeline/store_results.py \
    --input_json output/matched_entities.json \
    --output_csv output/results.csv
```

## Running Tests

```sh
uv run pytest
```

---
