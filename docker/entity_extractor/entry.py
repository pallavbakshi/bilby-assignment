import sys
import os
import json
import logging
from gliner import GLiNER

# Assumes pipeline package is in the python path (copied to /app/pipeline)
# If imports fail, check Dockerfile COPY commands and sys.path if necessary
try:
    from pipeline.extract_entities import extract_entities_from_text
except ImportError as e:
    logging.error(f"Failed to import from pipeline package: {e}. Check Dockerfile COPY and PYTHONPATH.")
    sys.exit(1)


# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - Docker - %(message)s')

# Define input/output paths within the container, mapped via volumes
# These paths are relative to the WORKDIR /app, but volumes map directly
INPUT_DOCS_JSON = "/input/docs_for_extraction.json"
OUTPUT_ENTITIES_JSON = "/output/extracted_entities.json"

def load_gliner_model() -> GLiNER:
    """
    Loads the pre-trained GLiNER model. Downloads if not cached.
    Uses TRANSFORMERS_CACHE env var set in Dockerfile.
    """
    logging.info("Loading GLiNER model (urchade/gliner_multi-v2.1)...")
    try:
        # Model is loaded using the cache path defined by TRANSFORMERS_CACHE
        model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
        logging.info("GLiNER model loaded successfully.")
        return model
    except Exception as e:
        logging.error(f"Failed to load GLiNER model: {e}", exc_info=True)
        raise # Propagate error to exit script


def main():
    logging.info("Starting entity extraction process in Docker container.")

    # Ensure output directory exists within the container mount point if needed
    # Although the mount itself should handle this, being explicit can help debug
    os.makedirs(os.path.dirname(OUTPUT_ENTITIES_JSON), exist_ok=True)

    try:
        # 1. Load documents from the input JSON file
        logging.info(f"Loading documents from {INPUT_DOCS_JSON}")
        if not os.path.exists(INPUT_DOCS_JSON):
             logging.error(f"Input file {INPUT_DOCS_JSON} not found. Check volume mounts.")
             sys.exit(1)
        with open(INPUT_DOCS_JSON, "r", encoding="utf-8") as f:
            documents = json.load(f)
        logging.info(f"Loaded {len(documents)} documents.")

        # 2. Load the GLiNER model
        model = load_gliner_model()

        # 3. Process each document and extract entities
        all_extracted_entities = []
        logging.info("Starting entity extraction for each document...")
        for i, doc in enumerate(documents):
            doc_uuid = doc.get("uuid", f"unknown_uuid_{i}")
            doc_title = doc.get("title_en", "unknown_title")
            text_to_process = doc.get("body_en", "")

            if not text_to_process:
                logging.warning(f"Document {doc_uuid} has empty 'body_en'. Skipping extraction.")
                continue

            # Use the imported function for extraction logic
            extracted = extract_entities_from_text(model, text_to_process) # Using default labels/threshold

            # Add document context to each extracted entity
            for entity in extracted:
                entity_record = {
                    "document_uuid": doc_uuid,
                    "document_title_en": doc_title,
                    "entity_text": entity["text"],
                    "entity_type": entity["label"],
                    "entity_start_pos": entity["start"],
                    "entity_end_pos": entity["end"],
                    "extractor_confidence_score": entity["score"],
                }
                all_extracted_entities.append(entity_record)

            if (i + 1) % 10 == 0 or (i + 1) == len(documents): # Log progress periodically
                 logging.info(f"Processed {i + 1}/{len(documents)} documents...")


        logging.info(f"Total extracted entity mentions: {len(all_extracted_entities)}")

        # 4. Write results to the output JSON file
        logging.info(f"Writing extracted entities to {OUTPUT_ENTITIES_JSON}")
        with open(OUTPUT_ENTITIES_JSON, "w", encoding="utf-8") as f:
            json.dump(all_extracted_entities, f, ensure_ascii=False, indent=2) # Indent for readability

        logging.info("Entity extraction process completed successfully.")

    except FileNotFoundError as e:
        logging.error(f"File not found error: {e}. Check paths and volume mounts.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON input file {INPUT_DOCS_JSON}: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred in the Docker entrypoint: {e}", exc_info=True)
        sys.exit(1) # Exit with non-zero code on failure


if __name__ == "__main__":
    main()