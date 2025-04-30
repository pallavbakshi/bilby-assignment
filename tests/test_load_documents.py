import pytest
import os
import json
import pandas as pd
from pipeline.load_documents import prepare_documents_for_extraction

# Sample CSV content for testing
SAMPLE_DOCS_CSV_CONTENT = """uuid,title_en,body_en,other_col
doc1-uuid,Doc 1 Title,"This is the body for doc 1. Contains text.",extra1
doc2-uuid,Doc 2 Title,"Body for doc 2, much shorter.",extra2
doc3-uuid,Doc 3 Title,,extra3
doc4-uuid,,Body for doc 4,extra4
"""

# Expected JSON output (subset of columns, NaN handled)
EXPECTED_JSON_OUTPUT = [
    {
        "uuid": "doc1-uuid",
        "title_en": "Doc 1 Title",
        "body_en": "This is the body for doc 1. Contains text.",
    },
    {
        "uuid": "doc2-uuid",
        "title_en": "Doc 2 Title",
        "body_en": "Body for doc 2, much shorter.",
    },
    {
        "uuid": "doc3-uuid",
        "title_en": "Doc 3 Title",
        "body_en": "" # NaN in body_en becomes empty string
    },
    {
        "uuid": "doc4-uuid",
        "title_en": "",      # NaN in title_en becomes empty string
        "body_en": "Body for doc 4"
    }
]

def test_prepare_documents_success(tmp_path):
    """Tests successful preparation of documents to JSON."""
    input_csv = tmp_path / "input_docs.csv"
    output_json = tmp_path / "output" / "docs_for_extraction.json" # Test subdirectory creation

    # Create dummy input CSV
    input_csv.write_text(SAMPLE_DOCS_CSV_CONTENT, encoding='utf-8')

    # Run the function
    prepare_documents_for_extraction(str(input_csv), str(output_json))

    # Assertions
    assert output_json.exists()
    with open(output_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert data == EXPECTED_JSON_OUTPUT
    # Check if number of records match (excluding header)
    assert len(data) == len(SAMPLE_DOCS_CSV_CONTENT.strip().split('\n')) - 1

def test_prepare_documents_file_not_found(tmp_path):
    """Tests FileNotFoundError when input CSV is missing."""
    input_csv = tmp_path / "non_existent.csv"
    output_json = tmp_path / "output.json"

    with pytest.raises(FileNotFoundError):
        prepare_documents_for_extraction(str(input_csv), str(output_json))

def test_prepare_documents_missing_column(tmp_path):
    """Tests ValueError when a required column is missing."""
    input_csv = tmp_path / "input_docs_missing_col.csv"
    output_json = tmp_path / "output.json"

    # Create CSV missing 'uuid'
    bad_csv_content = """title_en,body_en
Doc 1 Title,Body 1
"""
    input_csv.write_text(bad_csv_content, encoding='utf-8')

    with pytest.raises(ValueError, match="missing required columns: \\['uuid'\\]"):
        prepare_documents_for_extraction(str(input_csv), str(output_json))

def test_prepare_documents_empty_input(tmp_path):
    """Tests handling of an empty input CSV."""
    input_csv = tmp_path / "empty.csv"
    output_json = tmp_path / "output.json"

    # Create empty file with header only
    input_csv.write_text("uuid,title_en,body_en\n", encoding='utf-8')

    prepare_documents_for_extraction(str(input_csv), str(output_json))

    assert output_json.exists()
    with open(output_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert data == [] # Expect empty list