import os
import json
import logging
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def prepare_documents_for_extraction(input_csv_path: str, output_json_path: str):
    """
    Reads the input documents CSV, validates required columns, selects relevant data,
    and writes it to a JSON file suitable for the entity extraction step.

    Args:
        input_csv_path: Path to the input documents.csv file.
        output_json_path: Path where the output JSON file will be written.
    """
    logging.info(f"Starting document preparation from {input_csv_path}")
    try:
        df = pd.read_csv(input_csv_path)
        logging.info(f"Read {len(df)} rows from {input_csv_path}")

        # --- Validation ---
        required_columns = ["uuid", "title_en", "body_en"]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Input CSV missing required columns: {missing_cols}")

        # Handle potential NaN values in text fields gracefully
        df['body_en'] = df['body_en'].fillna('')
        df['title_en'] = df['title_en'].fillna('')

        # Select relevant columns and convert to list of dicts
        docs_to_process = df[required_columns].to_dict(orient="records")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)

        # Write to JSON
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(docs_to_process, f, ensure_ascii=False, indent=2) # Indent for readability

        logging.info(f"Successfully prepared {len(docs_to_process)} documents and saved to {output_json_path}")

    except FileNotFoundError:
        logging.error(f"Input file not found: {input_csv_path}")
        raise
    except ValueError as ve:
        logging.error(f"Data validation failed: {ve}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred during document preparation: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Prepare documents for extraction.')
    parser.add_argument('--input_csv', required=True, help='Path to input CSV (e.g data/documents.csv)')
    parser.add_argument('--output_json', required=True, help='Path to output JSON (e.g output/docs_for_extraction.json)')
    args = parser.parse_args()

    prepare_documents_for_extraction(args.input_csv, args.output_json)