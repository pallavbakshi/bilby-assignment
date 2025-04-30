import pytest
from unittest.mock import MagicMock # Can use mocker fixture too

# Import the function to test
from pipeline.extract_entities import extract_entities_from_text

# Mock GLiNER model's predict_entities output for specific text
MOCK_PREDICTION = [
    {'start': 11, 'end': 21, 'text': 'Xi Jinping', 'label': 'Person', 'score': 0.98},
    {'start': 45, 'end': 53, 'text': 'Shenzhen', 'label': 'Location', 'score': 0.92},
]

@pytest.fixture
def mock_gliner_model(mocker):
    """Fixture to create a mock GLiNER model."""
    mock_model = MagicMock()
    # Configure the mock's predict_entities method
    mock_model.predict_entities.return_value = MOCK_PREDICTION
    return mock_model

def test_extract_entities_success(mock_gliner_model):
    """Tests successful entity extraction using the mock model."""
    sample_text = "Speech by Xi Jinping was given in Shenzhen today."
    labels = ["Person", "Location", "Company"]
    threshold = 0.5
    
    # Setup mock tokenizer needed for chunking
    mock_tokenizer = MagicMock()
    mock_tokenizer.encode.return_value = [0, 1, 2, 3] # Simulate tokenizer behavior
    mock_gliner_model.data_processor.transformer_tokenizer = mock_tokenizer
    
    # Expected results - the function recalculates positions based on finding in original text
    expected_result = [
        {'start': 10, 'end': 20, 'text': 'Xi Jinping', 'label': 'Person', 'score': 0.98},
        {'start': 34, 'end': 42, 'text': 'Shenzhen', 'label': 'Location', 'score': 0.92}
    ]
    
    # Call the function with the mock model
    result = extract_entities_from_text(mock_gliner_model, sample_text, labels, threshold)
    
    # Assertions
    assert result == expected_result
    # Check if the mock method was called correctly
    mock_gliner_model.predict_entities.assert_called_once_with(sample_text, labels, threshold=threshold)

def test_extract_entities_default_labels(mock_gliner_model):
    """Tests extraction with default labels."""
    sample_text = "Another text."
    default_labels = ["Person", "Company", "Location"] # As defined in the function

    extract_entities_from_text(mock_gliner_model, sample_text) # No labels passed

    # Check call uses default labels
    mock_gliner_model.predict_entities.assert_called_once_with(sample_text, default_labels, threshold=0.5)

def test_extract_entities_empty_text(mock_gliner_model, caplog):
    """Tests behavior with empty input text."""
    result = extract_entities_from_text(mock_gliner_model, "")
    assert result == []
    # Check if the model's predict_entities was NOT called
    mock_gliner_model.predict_entities.assert_not_called()
    # Check for warning log
    assert "Received empty or non-string text" in caplog.text

def test_extract_entities_non_string_text(mock_gliner_model, caplog):
    """Tests behavior with non-string input text."""
    result_none = extract_entities_from_text(mock_gliner_model, None)
    assert result_none == []
    mock_gliner_model.predict_entities.assert_not_called()

    result_int = extract_entities_from_text(mock_gliner_model, 123)
    assert result_int == []
    mock_gliner_model.predict_entities.assert_not_called()
    assert "Received empty or non-string text" in caplog.text

def test_extract_entities_model_error(mocker):
    """Tests handling of an error during model prediction."""
    mock_model_error = MagicMock()
    mock_model_error.predict_entities.side_effect = Exception("Model prediction failed!")

    sample_text = "Text that causes failure."
    result = extract_entities_from_text(mock_model_error, sample_text)

    # Expect empty list on error, as per current implementation
    assert result == []
    # Check model was called
    mock_model_error.predict_entities.assert_called_once()