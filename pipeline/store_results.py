import os
import json
import logging
import pandas as pd
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_matched_entities_to_csv(matched_entities_path: str, output_csv_path: str):
    """
    Reads the matched entities from a JSON file, converts them to a Pandas DataFrame,
    and saves the results to a CSV file, overwriting if it exists.

    Args:
        matched_entities_path: Path to the JSON file containing matched entities.
        output_csv_path: Path where the final results CSV file will be written.
    """
    logging.info(f"Starting final storage process. Input: {matched_entities_path}")
    try:
        # Load matched entities from JSON
        with open(matched_entities_path, "r", encoding="utf-8") as f:
            matched_entities = json.load(f)
        logging.info(f"Loaded {len(matched_entities)} matched entity records.")

        if not matched_entities:
            logging.warning("No matched entities found to store. Output CSV will be empty or not created.")
            # Just to be safe, we create an empty DataFrame with the expected columns
            df = pd.DataFrame(columns=[
                "document_uuid", "document_title_en", "entity_text", "entity_type",
                "entity_start_pos", "entity_end_pos", "extractor_confidence_score",
                "is_matched", "matched_sot_name", "matched_sot_entity_type"
            ])
        else:
             # Convert list of dicts to DataFrame
            df = pd.DataFrame(matched_entities)

            # Ensure specific column order as defined in schema (optional but good practice)
            output_columns = [
                "document_uuid", "document_title_en", "entity_text", "entity_type",
                "entity_start_pos", "entity_end_pos", "extractor_confidence_score",
                "is_matched", "matched_sot_name", "matched_sot_entity_type"
            ]
             # Reorder columns, handling potential missing ones if schema changes
            df = df.reindex(columns=output_columns)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)

        # Save to CSV, overwriting existing file
        df.to_csv(output_csv_path, index=False, encoding='utf-8')

        logging.info(f"Successfully saved {len(df)} results to {output_csv_path}")

    except FileNotFoundError:
        logging.error(f"Input file not found: {matched_entities_path}")
        raise
    except json.JSONDecodeError as json_error:
        logging.error(f"Error decoding JSON input file {matched_entities_path}: {json_error}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred during result storage: {e}", exc_info=True)
        raise

# Example usage (optional, for testing)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Store matched entities to CSV.')
    parser.add_argument('--input_json', required=True, help='Path to matched entities JSON (e.g. output/matched_entities.json)')
    parser.add_argument('--output_csv', required=True, help='Path to output CSV (e.g. output/results.csv)')
    args = parser.parse_args()

    save_matched_entities_to_csv(args.input_json, args.output_csv)