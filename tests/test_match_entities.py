import pytest
import os
import json
import pandas as pd

# Import the function and helper to test
from pipeline.match_entities import perform_matching, _build_alias_lookup

# Sample aliases CSV content
SAMPLE_ALIASES_CSV_CONTENT = """,entity_type,name,aliases
0,Person,Xi Jinping,"['President Xi', 'Chairman Xi', 'Xi']"
1,Person,Li Qiang,"['Premier Li', 'Li']"
2,Company,Alibaba,"['BABA']"
3,Location,Shenzhen,"[]"
4,Person,Malformed,"['Valid', Malformed List]"
5,Person,DuplicateAlias,"['CommonAlias']"
6,Person,AlsoDuplicate,"['CommonAlias']"
"""

# Sample extracted entities JSON content (simulating output from extraction step)
SAMPLE_EXTRACTED_JSON_CONTENT = """
[
  {
    "document_uuid": "doc1-uuid",
    "document_title_en": "Doc 1 Title",
    "entity_text": "Chairman Xi",
    "entity_type": "Person",
    "entity_start_pos": 10,
    "entity_end_pos": 21,
    "extractor_confidence_score": 0.99
  },
  {
    "document_uuid": "doc1-uuid",
    "document_title_en": "Doc 1 Title",
    "entity_text": "Li",
    "entity_type": "Person",
    "entity_start_pos": 30,
    "entity_end_pos": 32,
    "extractor_confidence_score": 0.85
  },
  {
    "document_uuid": "doc2-uuid",
    "document_title_en": "Doc 2 Title",
    "entity_text": "Alibaba",
    "entity_type": "Company",
    "entity_start_pos": 5,
    "entity_end_pos": 12,
    "extractor_confidence_score": 0.95
  },
  {
    "document_uuid": "doc2-uuid",
    "document_title_en": "Doc 2 Title",
    "entity_text": "Unknown Person",
    "entity_type": "Person",
    "entity_start_pos": 20,
    "entity_end_pos": 34,
    "extractor_confidence_score": 0.70
  },
  {
    "document_uuid": "doc3-uuid",
    "document_title_en": "Doc 3 Title",
    "entity_text": "Shenzhen",
    "entity_type": "Location",
    "entity_start_pos": 0,
    "entity_end_pos": 8,
    "extractor_confidence_score": 0.91
  },
   {
    "document_uuid": "doc4-uuid",
    "document_title_en": "Doc 4 Title",
    "entity_text": "CommonAlias",
    "entity_type": "Person",
    "entity_start_pos": 0,
    "entity_end_pos": 11,
    "extractor_confidence_score": 0.88
  }
]
"""

# Expected output JSON after matching
EXPECTED_MATCHED_JSON_OUTPUT = [
  {
    "document_uuid": "doc1-uuid", "document_title_en": "Doc 1 Title", "entity_text": "Chairman Xi",
    "entity_type": "Person", "entity_start_pos": 10, "entity_end_pos": 21, "extractor_confidence_score": 0.99,
    "is_matched": True, "matched_sot_name": "Xi Jinping", "matched_sot_entity_type": "Person"
  },
  {
    "document_uuid": "doc1-uuid", "document_title_en": "Doc 1 Title", "entity_text": "Li",
    "entity_type": "Person", "entity_start_pos": 30, "entity_end_pos": 32, "extractor_confidence_score": 0.85,
    "is_matched": True, "matched_sot_name": "Li Qiang", "matched_sot_entity_type": "Person"
  },
  {
    "document_uuid": "doc2-uuid", "document_title_en": "Doc 2 Title", "entity_text": "Alibaba",
    "entity_type": "Company", "entity_start_pos": 5, "entity_end_pos": 12, "extractor_confidence_score": 0.95,
    "is_matched": True, "matched_sot_name": "Alibaba", "matched_sot_entity_type": "Company" # Matched via canonical name
  },
  {
    "document_uuid": "doc2-uuid", "document_title_en": "Doc 2 Title", "entity_text": "Unknown Person",
    "entity_type": "Person", "entity_start_pos": 20, "entity_end_pos": 34, "extractor_confidence_score": 0.70,
    "is_matched": False, "matched_sot_name": "", "matched_sot_entity_type": ""
  },
  {
    "document_uuid": "doc3-uuid", "document_title_en": "Doc 3 Title", "entity_text": "Shenzhen",
    "entity_type": "Location", "entity_start_pos": 0, "entity_end_pos": 8, "extractor_confidence_score": 0.91,
    "is_matched": True, "matched_sot_name": "Shenzhen", "matched_sot_entity_type": "Location" # Matched via canonical name, empty alias list ok
  },
   {
    "document_uuid": "doc4-uuid", "document_title_en": "Doc 4 Title", "entity_text": "CommonAlias",
    "entity_type": "Person", "entity_start_pos": 0, "entity_end_pos": 11, "extractor_confidence_score": 0.88,
    "is_matched": True, "matched_sot_name": "DuplicateAlias", "matched_sot_entity_type": "Person" # Matched first occurrence
  }
]


# --- Tests for _build_alias_lookup ---

def test_build_alias_lookup_success(tmp_path, caplog):
    """Tests successful building of the alias lookup dictionary."""
    aliases_csv = tmp_path / "aliases.csv"
    aliases_csv.write_text(SAMPLE_ALIASES_CSV_CONTENT, encoding='utf-8')

    lookup = _build_alias_lookup(str(aliases_csv))

    # Basic checks
    assert isinstance(lookup, dict)
    assert len(lookup) == 14 # 6 names + 8 aliases ['President Xi', 'Chairman Xi', 'Xi', 'Premier Li', 'Li', 'BABA', 'Valid', 'CommonAlias']
    # Xi Jinping, President Xi, Chairman Xi, Xi -> Xi Jinping
    # Li Qiang, Premier Li, Li -> Li Qiang
    # Alibaba, BABA -> Alibaba
    # Shenzhen -> Shenzhen
    # Malformed, Valid -> Malformed (assuming 'Malformed List' fails parse)
    # DuplicateAlias, CommonAlias -> DuplicateAlias
    # AlsoDuplicate -> AlsoDuplicate (name only)
    # Total unique keys = 4 + 3 + 2 + 1 + 2 + 2 + 1 = 15. Let's check warning logic.
    # When CommonAlias is seen for AlsoDuplicate, it's already mapped to DuplicateAlias, so warning is logged, mapping stays.
    
    # Check specific mappings
    assert lookup["Xi Jinping"] == {"name": "Xi Jinping", "entity_type": "Person"}
    assert lookup["President Xi"] == {"name": "Xi Jinping", "entity_type": "Person"}
    assert lookup["Li"] == {"name": "Li Qiang", "entity_type": "Person"}
    assert lookup["Alibaba"] == {"name": "Alibaba", "entity_type": "Company"}
    assert lookup["BABA"] == {"name": "Alibaba", "entity_type": "Company"}
    assert lookup["Shenzhen"] == {"name": "Shenzhen", "entity_type": "Location"}
    assert lookup.get("Unknown") is None # Test non-existent key

    # Check handling of malformed/duplicate aliases via logs
    assert "Error parsing aliases string for SoT name 'Malformed'" in caplog.text
    assert "Alias 'CommonAlias' maps to multiple SoT names" in caplog.text
    assert lookup["CommonAlias"] == {"name": "DuplicateAlias", "entity_type": "Person"} # Check it kept the first mapping

def test_build_alias_lookup_file_not_found(tmp_path):
    """Tests FileNotFoundError for alias lookup."""
    with pytest.raises(FileNotFoundError):
        _build_alias_lookup(str(tmp_path / "non_existent.csv"))

def test_build_alias_lookup_missing_column(tmp_path):
    """Tests ValueError if aliases CSV misses columns."""
    aliases_csv = tmp_path / "bad_aliases.csv"
    aliases_csv.write_text("name,aliases\nSomeone,'[]'", encoding='utf-8') # Missing entity_type
    with pytest.raises(ValueError, match="missing required columns: \\['entity_type'\\]"):
        _build_alias_lookup(str(aliases_csv))

# --- Tests for perform_matching ---

def test_perform_matching_success(tmp_path):
    """Tests the main matching logic successfully."""
    extracted_json = tmp_path / "extracted.json"
    aliases_csv = tmp_path / "aliases.csv"
    matched_json = tmp_path / "output" / "matched.json" # Test subdirectory creation

    # Create dummy input files
    extracted_json.write_text(SAMPLE_EXTRACTED_JSON_CONTENT, encoding='utf-8')
    aliases_csv.write_text(SAMPLE_ALIASES_CSV_CONTENT, encoding='utf-8')

    # Run the function
    perform_matching(str(extracted_json), str(aliases_csv), str(matched_json))

    # Assertions
    assert matched_json.exists()
    with open(matched_json, 'r', encoding='utf-8') as f:
        result_data = json.load(f)

    # Compare length and content (order might matter if input order is preserved)
    assert len(result_data) == len(json.loads(SAMPLE_EXTRACTED_JSON_CONTENT))
    # Sort both lists by a unique key (e.g., text + start_pos) if order isn't guaranteed
    key_func = lambda x: (x['entity_text'], x['entity_start_pos'])
    assert sorted(result_data, key=key_func) == sorted(EXPECTED_MATCHED_JSON_OUTPUT, key=key_func)


def test_perform_matching_missing_input_file(tmp_path):
    """Tests FileNotFoundError if input files are missing."""
    extracted_json = tmp_path / "extracted.json"
    aliases_csv = tmp_path / "aliases.csv"
    matched_json = tmp_path / "matched.json"

    # Create only aliases file
    aliases_csv.write_text(SAMPLE_ALIASES_CSV_CONTENT, encoding='utf-8')

    # Test missing extracted entities file
    with pytest.raises(FileNotFoundError):
        perform_matching(str(extracted_json), str(aliases_csv), str(matched_json))

    # Create only extracted entities file
    extracted_json.write_text(SAMPLE_EXTRACTED_JSON_CONTENT, encoding='utf-8')
    aliases_csv.unlink() # Remove aliases file

    # Test missing aliases file
    with pytest.raises(FileNotFoundError):
        perform_matching(str(extracted_json), str(aliases_csv), str(matched_json))