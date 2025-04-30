## Project Structure and Organization

The project follows a clean separation of concerns with three distinct layers:

```
entity-extraction-pipeline-impl/
├── dags/               # Orchestration (Airflow DAGs)
├── docker/             # Containerization 
├── pipeline/           # Core processing logic
├── data/               # Input data files
├── output/             # Pipeline results
└── tests/              # Unit tests for pipeline components
```

### Rationale for Separation

This three-part structure was chosen to improve maintainability, testability, and deployment flexibility:

1. **Orchestration Layer (`dags/`)**: Contains Airflow DAG definitions that coordinate the workflow but don't implement business logic. This separation allows the orchestration to evolve independently from the implementation details, making it easier to modify the workflow sequence or add monitoring without touching core processing code.

2. **Containerization Layer (`docker/`)**: Isolates the environment-specific configuration and dependencies. This creates a reproducible, portable execution environment for the entity extraction model, ensuring consistent results across development and production. The separate model cache directory prevents redundant downloads.

3. **Processing Layer (`pipeline/`)**: Houses the core business logic broken into focused, single-responsibility modules. Each component handles one stage of the pipeline (loading, extraction, matching, storing), making the code more testable and maintainable. This modular approach also enables independent development of different pipeline stages.

This separation enables parallel development by different team members, simplifies testing (as shown by the corresponding test structure), and allows each layer to evolve at its own pace. The clean boundaries between orchestration, environment, and core logic make the pipeline more adaptable for future extensions and scaling.


## Docker Communication Method

This implementation uses a simple and efficient volume mount approach for communication between Airflow and Docker, chosen for its reliability and straightforward implementation.

### Volume Mount Communication

The Docker container communicates with Airflow through shared filesystem volume mounts, leveraging three key mount points:

1. **Input Mount (`/input`)**:
   - Airflow writes document data as JSON to `output/docs_for_extraction.json`
   - The container reads this file from `/input/docs_for_extraction.json`

2. **Output Mount (`/output`)**:
   - The container writes extracted entities to `/output/extracted_entities.json`
   - Airflow reads this file from the host path after container completion

3. **Model Cache Mount (`/cache`)**:
   - Persists the GLiNER model between container executions
   - Prevents unnecessary model downloads on subsequent runs

### Data Format

JSON was chosen as the communication format due to its:
- Native representation of nested structures
- Support for Unicode text (essential for international documents)
- Preservation of data types (numbers, strings, booleans)
- Self-documenting structure

### Error Handling

The Docker container implements a robust error handling strategy:
- Exits with non-zero code on failure, signaling Airflow of task failure
- Logs detailed error messages to stdout/stderr (captured by Airflow logs)
- Implements explicit input validation before processing (checks for missing files, malformed JSON)

This approach was chosen over alternatives like API endpoints (more complex to set up) or direct command arguments (less suitable for large data volumes) due to its simplicity, reliability, and ease of debugging in a development environment.

## Output Schema Design

The pipeline implements a flattened CSV schema to represent the relationships between documents, extracted entities, and SoT matches.

### Schema Structure

The output is a row-per-entity CSV file with the following columns:

```
document_uuid, document_title_en, entity_text, entity_type, entity_start_pos, entity_end_pos, 
extractor_confidence_score, is_matched, matched_sot_name, matched_sot_entity_type
```

| Column                    | Type    | Description                                     |
|----------------|---------|------------------------------------------------|
| document_uuid             | str     | UUID of the document                            |
| document_title_en         | str     | Title of the document (English)                 |
| entity_text               | str     | The extracted entity mention                    |
| entity_type               | str     | Entity label (Person, Company, Location)        |
| entity_start_pos          | int     | Start character index document body_en       |
| entity_end_pos            | int     | End character index document body_en         |
| extractor_confidence_score| float   | Confidence score from GLiNER model              |
| is_matched                | bool    | True if matched to SoT entity                   |
| matched_sot_name          | str     | Name from SoT table (if matched, else empty)    |
| matched_sot_entity_type   | str     | Entity type from SoT table (if matched, else empty) |



Each row represents a single extracted entity mention with its document context and matching information:

- **Document Relationship**: Maintained through `document_uuid` and `document_title_en` fields
- **Entity Information**: Captured by `entity_text`, `entity_type`, and position fields 
- **Source of Truth Relationship**: Represented by `is_matched`, `matched_sot_name`, and `matched_sot_entity_type`

### Handling Special Cases

1. **Unmatched Entities**: 
   - Set `is_matched = False`
   - Empty string for `matched_sot_name` and `matched_sot_entity_type`

2. **Overlapping Entities**: 
   - Each extracted entity is stored as a separate row
   - Entity positions (`entity_start_pos`, `entity_end_pos`) allow reconstruction of overlaps

3. **Multiple Matches**: 
   - Implementation ensures first-match wins when an entity could match multiple SoT records
   - Logs warnings when ambiguous matches are detected

### Format Rationale

CSV was chosen as the output format for several reasons:
- Universal compatibility with analysis tools and spreadsheet applications
- Direct viewability without special software
- Straightforward implementation with Pandas
- Suitable for the flattened row-per-entity structure

This schema design provides the required three-way relationship tracking while maintaining simplicity and accessibility, making it ideal for this proof-of-concept pipeline.

## Docker Caching Strategies

The pipeline leverages Docker's caching mechanisms at both build time and runtime to optimize performance and resource usage:

1.  **Build Caching**: The `build_docker_images_task` in `entity_pipeline_dag.py` utilizes standard Docker build caching. Docker automatically caches layers during the image build process (`docker build`). If the instructions in the `Dockerfile` or the files copied into a layer haven't changed since the last build, Docker reuses the cached layer, significantly speeding up subsequent builds. The DAG task also includes a preliminary check using `docker image inspect` to see if the target images (`entity_extractor_base:latest`, `entity_extractor:latest`) already exist, skipping the build process entirely if they do.

2.  **Runtime Model Caching**: To avoid downloading the potentially large entity extraction model (e.g., GLiNER) on every pipeline run, a volume mount is configured in the `run_entity_extraction_task`. The host directory `docker/model_cache` (resolved to an absolute path) is mounted into the container at `/cache`. The entity extraction script within the container is expected to save and load the model from this `/cache` directory. This ensures that once the model is downloaded, it persists on the host machine and is readily available for subsequent container executions, saving considerable time and bandwidth.

This combination of build and runtime caching makes the pipeline more efficient, especially during development cycles and repeated runs with the same model.


## Scalability & Batching

This proof-of-concept pipeline processes all input documents in their separate individual batches. For production-scale workloads (e.g., thousands of articles per day), you would likely implement batching and/or parallelization—such as splitting documents into batches and running multiple Docker containers in parallel using Airflow's dynamic task mapping or using model's batching capabilities. This would reduce time-to-completion and improve resource utilization.

However, for this assignment, with its limited scope and dataset size, a single-batch approach was chosen for clarity and simplicity.

Note:
It is also interesting to note that GLiNer has limited token size of 348 tokens. This means that we can't use the entire article as input, we need to split the article into chunks of 348 tokens. This is a limitation of the GLiNer model. And if we add chunking with batching i.e. if we split the article into multiple chunks and then batch the chunks, we need to map the chunks back to the original article. This is a challenge and a topic for future work. The way the model does normalization of these chunks is also complex and a topic for future work.