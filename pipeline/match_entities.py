import os
import json
import logging
import pandas as pd
import ast
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _build_alias_lookup(aliases_csv_path: str) -> dict:
    """
    Reads the entity aliases CSV and builds a lookup dictionary.
    The dictionary maps alias strings (case-sensitive) and the canonical name
    itself to the SoT entity details (name and type).

    Args:
        aliases_csv_path: Path to the entity_aliases.csv file.

    Returns:
        A dictionary for fast lookups:
        {'Alias Text': {'name': 'SoT Name', 'entity_type': 'SoT Type'}, ...}
    """
    logging.info(f"Building alias lookup from {aliases_csv_path}")
    alias_lookup = {}
    try:
        df = pd.read_csv(aliases_csv_path)

        # --- Validation ---
        required_columns = ["name", "entity_type", "aliases"]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Aliases CSV missing required columns: {missing_cols}")

        processed_count = 0
        for _, row in df.iterrows():
            sot_name = row['name']
            sot_type = row['entity_type']
            aliases_str = row['aliases']

            if not isinstance(sot_name, str) or not sot_name:
                logging.warning(f"Skipping row due to invalid SoT name: {row.to_dict()}")
                continue

            sot_details = {'name': sot_name, 'entity_type': sot_type}

            # Add the canonical name itself to the lookup (case-sensitive)
            if sot_name not in alias_lookup:
                alias_lookup[sot_name] = sot_details
            else:
                 logging.warning(f"Duplicate SoT name '{sot_name}' encountered in aliases file. Using first occurrence.")


            # Safely parse the aliases list string
            try:
                aliases = ast.literal_eval(aliases_str)
                if isinstance(aliases, list):
                    for alias in aliases:
                        if isinstance(alias, str) and alias: # Ensure alias is a non-empty string
                            # Add alias to lookup (case-sensitive)
                            # If alias already exists, log warning (potential ambiguity) but overwrite/keep first?
                            # Assignment says simple matching, so let's assume first encountered wins or data is clean.
                            if alias not in alias_lookup:
                                alias_lookup[alias] = sot_details
                            elif alias_lookup[alias]['name'] != sot_name:
                                # This indicates an alias maps to multiple SoT names - problematic for simple matching.
                                logging.warning(f"Alias '{alias}' maps to multiple SoT names ('{alias_lookup[alias]['name']}' and '{sot_name}'). Keeping mapping to '{alias_lookup[alias]['name']}'.")
                        else:
                            logging.warning(f"Skipping invalid alias '{alias}' for SoT name '{sot_name}'")
                else:
                    logging.warning(f"Could not parse aliases for SoT name '{sot_name}' as a list. Value: {aliases_str}")
            except (ValueError, SyntaxError, TypeError) as parse_error:
                logging.warning(f"Error parsing aliases string for SoT name '{sot_name}': {parse_error}. Value: {aliases_str}")
            processed_count += 1

        logging.info(f"Built alias lookup with {len(alias_lookup)} unique alias/name entries from {processed_count} SoT entities.")
        return alias_lookup

    except FileNotFoundError:
        logging.error(f"Aliases file not found: {aliases_csv_path}")
        raise
    except ValueError as ve:
        logging.error(f"Data validation failed for aliases CSV: {ve}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred building alias lookup: {e}", exc_info=True)
        raise


def perform_matching(extracted_entities_path: str, aliases_csv_path: str, matched_entities_path: str):
    """
    Reads extracted entities, loads aliases, performs case-sensitive matching,
    and writes the enriched entities (with matching info) to a JSON file.

    Args:
        extracted_entities_path: Path to the JSON file containing extracted entities.
        aliases_csv_path: Path to the entity_aliases.csv file.
        matched_entities_path: Path where the output JSON file with matched entities will be written.
    """
    logging.info(f"Starting entity matching. Extracted entities from: {extracted_entities_path}")

    try:
        # Load extracted entities
        with open(extracted_entities_path, "r", encoding="utf-8") as f:
            extracted_entities = json.load(f)
        logging.info(f"Loaded {len(extracted_entities)} extracted entity mentions.")

        # Build alias lookup
        alias_lookup = _build_alias_lookup(aliases_csv_path)

        # Perform matching
        matched_results = []
        match_count = 0
        for entity in extracted_entities:
            entity_text = entity.get("entity_text", "")

            # Perform case-sensitive lookup
            match_details = alias_lookup.get(entity_text)

            is_matched = match_details is not None
            if is_matched:
                match_count += 1
                matched_sot_name = match_details['name']
                matched_sot_entity_type = match_details['entity_type']
            else:
                matched_sot_name = ""
                matched_sot_entity_type = ""

            # Append all original fields plus matching info
            entity['is_matched'] = is_matched
            entity['matched_sot_name'] = matched_sot_name
            entity['matched_sot_entity_type'] = matched_sot_entity_type
            matched_results.append(entity)

        logging.info(f"Matching complete. Matched {match_count} out of {len(extracted_entities)} entity mentions.")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(matched_entities_path), exist_ok=True)

        # Write matched results to JSON
        with open(matched_entities_path, "w", encoding="utf-8") as f:
            json.dump(matched_results, f, ensure_ascii=False, indent=2) # Indent for readability

        logging.info(f"Successfully saved matched entities to {matched_entities_path}")

    except FileNotFoundError as fnf_error:
        logging.error(f"Input file not found during matching: {fnf_error}")
        raise
    except json.JSONDecodeError as json_error:
        logging.error(f"Error decoding JSON input file {extracted_entities_path}: {json_error}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred during entity matching: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Match extracted entities to SoT aliases.')
    parser.add_argument('--input_json', required=True, help='Path to extracted entities JSON (e.g. output/extracted_entities.json)')
    parser.add_argument('--aliases_csv', required=True, help='Path to entity_aliases.csv (e.g. data/entity_aliases.csv)')
    parser.add_argument('--output_json', required=True, help='Path to output matched JSON (e.g. output/matched_entities.json)')
    args = parser.parse_args()

    perform_matching(args.input_json, args.aliases_csv, args.output_json)