import pytest
import json
import pandas as pd

# Import the function to test
from pipeline.store_results import save_matched_entities_to_csv
# Import expected output from matching test
from tests.test_match_entities import EXPECTED_MATCHED_JSON_OUTPUT

# Use the expected output from the matching test as input for this test
SAMPLE_MATCHED_JSON_CONTENT = json.dumps(EXPECTED_MATCHED_JSON_OUTPUT, indent=2)

# Expected columns in the output CSV
EXPECTED_CSV_COLUMNS = [
    "document_uuid", "document_title_en", "entity_text", "entity_type",
    "entity_start_pos", "entity_end_pos", "extractor_confidence_score",
    "is_matched", "matched_sot_name", "matched_sot_entity_type"
]

def test_save_results_success(tmp_path):
    """Tests successfully saving matched results to CSV."""
    matched_json = tmp_path / "matched.json"
    output_csv = tmp_path / "output" / "results.csv" # Test subdirectory creation

    # Create dummy input JSON
    matched_json.write_text(SAMPLE_MATCHED_JSON_CONTENT, encoding='utf-8')

    # Run the function
    save_matched_entities_to_csv(str(matched_json), str(output_csv))

    # Assertions
    assert output_csv.exists()

    # Read CSV and verify content
    df = pd.read_csv(output_csv)

    # Check columns and order
    assert list(df.columns) == EXPECTED_CSV_COLUMNS

    # Check number of rows (should match input JSON)
    assert len(df) == len(EXPECTED_MATCHED_JSON_OUTPUT)

    # Check a few values (handle potential type differences between JSON and CSV read)
    assert df.loc[0, 'entity_text'] == 'Chairman Xi'
    assert df.loc[0, 'is_matched'] == True
    assert df.loc[0, 'matched_sot_name'] == 'Xi Jinping'

    assert df.loc[3, 'entity_text'] == 'Unknown Person'
    assert df.loc[3, 'is_matched'] == False
    assert pd.isna(df.loc[3, 'matched_sot_name']) or df.loc[3, 'matched_sot_name'] == "" # Handle how Pandas reads empty string

    # Test idempotency (overwrite)
    save_matched_entities_to_csv(str(matched_json), str(output_csv))
    df_overwrite = pd.read_csv(output_csv)
    assert len(df_overwrite) == len(EXPECTED_MATCHED_JSON_OUTPUT) # Length should not double


def test_save_results_empty_input(tmp_path):
    """Tests saving when the input matched JSON is empty."""
    matched_json = tmp_path / "empty_matched.json"
    output_csv = tmp_path / "empty_results.csv"

    # Create empty JSON list
    matched_json.write_text("[]", encoding='utf-8')

    save_matched_entities_to_csv(str(matched_json), str(output_csv))

    assert output_csv.exists()
    df = pd.read_csv(output_csv)

    # Expect empty DataFrame but with correct headers
    assert df.empty
    assert list(df.columns) == EXPECTED_CSV_COLUMNS

def test_save_results_file_not_found(tmp_path):
    """Tests FileNotFoundError when input JSON is missing."""
    matched_json = tmp_path / "non_existent.json"
    output_csv = tmp_path / "results.csv"

    with pytest.raises(FileNotFoundError):
        save_matched_entities_to_csv(str(matched_json), str(output_csv))