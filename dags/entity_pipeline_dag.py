import os
import logging
from datetime import timedelta

from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# --- Configuration ---
PROJECT_ROOT = os.getenv("AIRFLOW_HOME", ".")

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
DOCKER_CONTEXT_DIR = PROJECT_ROOT
MODEL_CACHE_DIR = os.path.join(PROJECT_ROOT, "docker", "model_cache")

DOCS_CSV = os.path.join(DATA_DIR, "documents.csv")
ALIASES_CSV = os.path.join(DATA_DIR, "entity_aliases.csv")

# Intermediate files (will be created in OUTPUT_DIR)
DOCS_FOR_EXTRACTION_JSON = os.path.join(OUTPUT_DIR, "docs_for_extraction.json")
EXTRACTED_ENTITIES_JSON = os.path.join(OUTPUT_DIR, "extracted_entities.json")
MATCHED_ENTITIES_JSON = os.path.join(OUTPUT_DIR, "matched_entities.json")

FINAL_RESULTS_CSV = os.path.join(OUTPUT_DIR, "documents_answer.csv")

DOCKER_IMAGE_NAME = "entity_extractor:latest"

# Correct path for Docker Desktop on macOS/Linux if symlinked
# This wasn't working on Mac properly, can be removed in the future
DOCKER_SOCKET_PATH = os.path.expanduser("~/.docker/run/docker.sock")
DOCKER_URL = f"unix://{DOCKER_SOCKET_PATH}"
if not os.path.exists(DOCKER_SOCKET_PATH):
    logging.warning(f"Docker socket not found at {DOCKER_SOCKET_PATH}. Falling back to default.")
    # Fallback or handle error appropriately, here we let DockerHook try default
    DOCKER_URL = "unix://var/run/docker.sock" # Default Docker socket (might fail on macOS)


# Ensure model cache directory exists on the host
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

# Import functions from the pipeline logic module
try:
    from pipeline.load_documents import prepare_documents_for_extraction
    from pipeline.match_entities import perform_matching
    from pipeline.store_results import save_matched_entities_to_csv
except ImportError as e:
    logging.error(f"Could not import pipeline modules: {e}. Ensure PROJECT_ROOT is in PYTHONPATH.")
    def prepare_documents_for_extraction(*args, **kwargs): raise ImportError("Missing pipeline.load_documents")
    def perform_matching(*args, **kwargs): raise ImportError("Missing pipeline.match_entities")
    def save_matched_entities_to_csv(*args, **kwargs): raise ImportError("Missing pipeline.store_results")


# --- DAG Definition ---
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="bilby_entity_extraction_pipeline",
    default_args=default_args,
    description="Extracts entities from documents using Docker, matches them, and stores results.",
    schedule=None, # Manual trigger
    start_date=days_ago(1),
    catchup=False,
    tags=["bilby", "nlp", "docker"],
) as dag:

    # Task to create output directory (idempotent)
    create_output_dir = BashOperator(
        task_id="create_output_directory",
        bash_command=f"mkdir -p {OUTPUT_DIR}",
    )

    # Task 1: Load documents and prepare JSON for extractor
    load_documents_task = PythonOperator(
        task_id="load_and_prepare_documents",
        python_callable=prepare_documents_for_extraction,
        op_kwargs={
            "input_csv_path": DOCS_CSV,
            "output_json_path": DOCS_FOR_EXTRACTION_JSON,
        },
        doc_md="Reads documents.csv, validates, and creates JSON input for the Docker extractor.",
    )

    # Task 2: Build the Docker image (runs only if image doesn't exist or context changed - Docker build caching)
    build_docker_images_task = BashOperator(
        task_id="build_docker_images",
        bash_command=(
            f"# Use normal Docker build for better resource utilization\n"
            f"# Build base image if needed\n"
            f"if ! docker image inspect entity_extractor_base:latest >/dev/null 2>&1; then\n"
            f"  echo 'Building base image...'\n"
            f"  docker build --platform linux/amd64 \\\n"
            f"    --memory=8g \\\n"
            f"    -f {os.path.join(DOCKER_CONTEXT_DIR, 'docker', 'entity_extractor', 'Dockerfile.base')} {DOCKER_CONTEXT_DIR} || exit 1\n"
            f"fi\n\n"
            f"# Build application image if needed\n"
            f"if ! docker image inspect {DOCKER_IMAGE_NAME} >/dev/null 2>&1; then\n"
            f"  echo 'Building application image...'\n"
            f"  docker build --platform linux/amd64 \\\n"
            f"    --memory=8g \\\n"
            f"    -f {os.path.join(DOCKER_CONTEXT_DIR, 'docker', 'entity_extractor', 'Dockerfile')} {DOCKER_CONTEXT_DIR} || exit 1\n"
            f"fi\n"
        ),
        doc_md="Builds Docker images with increased resource allocation.",
    )

    # Task 3: Run the Docker container to perform entity extraction
    run_entity_extraction_task = DockerOperator(
        task_id="run_entity_extraction_docker",
        image=DOCKER_IMAGE_NAME,
        container_name="entity_extractor_container_{{ ds_nodash }}_{{ ts_nodash }}",
        mounts=[
            Mount(source=os.path.abspath(OUTPUT_DIR), target="/input", type="bind"),
            Mount(source=os.path.abspath(OUTPUT_DIR), target="/output", type="bind"),
            Mount(source=os.path.abspath(MODEL_CACHE_DIR), target="/cache", type="bind")
        ],
        auto_remove='success',
        # Resource specifications:
        cpus=4.0,  # Specify CPU limit
        mem_limit="8G",  # Specify memory limit
        docker_url=DOCKER_URL, # Explicitly set the Docker socket URL
    )

    # Task 4: Match extracted entities against the aliases table
    match_entities_task = PythonOperator(
        task_id="match_entities_with_aliases",
        python_callable=perform_matching,
        op_kwargs={
            "extracted_entities_path": EXTRACTED_ENTITIES_JSON,
            "aliases_csv_path": ALIASES_CSV,
            "matched_entities_path": MATCHED_ENTITIES_JSON,
        },
        doc_md="Reads extracted entities and aliases, performs matching, and saves enriched entities.",
    )

    # Task 5: Store the final results to a CSV file
    store_results_task = PythonOperator(
        task_id="store_final_results",
        python_callable=save_matched_entities_to_csv,
        op_kwargs={
            "matched_entities_path": MATCHED_ENTITIES_JSON,
            "output_csv_path": FINAL_RESULTS_CSV,
        },
        doc_md="Saves the final matched entity results to a CSV file in the output directory.",
    )

    # Task 6: Clean up intermediate JSON files (optional)
    cleanup_intermediate_files = BashOperator(
        task_id="cleanup_intermediate_files",
        bash_command=(
            f"rm -f {DOCS_FOR_EXTRACTION_JSON} {EXTRACTED_ENTITIES_JSON} {MATCHED_ENTITIES_JSON}"
        ),
        trigger_rule=TriggerRule.ALL_SUCCESS, # Only cleanup if everything upstream succeeded
        doc_md="Removes temporary JSON files created during the pipeline run.",
    )


    # --- Task Dependencies ---
    create_output_dir >> load_documents_task >> build_docker_images_task >> run_entity_extraction_task
    run_entity_extraction_task >> match_entities_task >> store_results_task >> cleanup_intermediate_files