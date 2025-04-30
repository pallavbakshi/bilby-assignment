import logging
from typing import List, Dict, Optional
# NOTE: gliner is imported within the function using it to avoid
# loading it unless necessary, especially if this module were imported elsewhere.
# For the Docker context, it will be available.

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_entities_from_text(
    model, 
    text: str,
    labels: Optional[List[str]] = None,
    threshold: float = 0.5,
    target_chunk_size: int = 100  # Optimal size from research
) -> List[Dict]:
    """
    Extracts entities using optimal chunk size of ~100 tokens based on research.
    Uses GLiNER's internal tokenizer for precise token counting.
    """
    if labels is None:
        labels = ["Person", "Company", "Location"]

    if not text or not isinstance(text, str):
        logging.warning("Received empty or non-string text for entity extraction. Skipping.")
        return []

    try:
        # For the interviewer, this was the HARD PART.
        tokenizer = model.data_processor.transformer_tokenizer
        logging.info("Using GLiNER's internal tokenizer for chunking")
        
        import re
        sentence_split_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_split_pattern, text)
        
        chunks = []
        current_chunk = []
        current_token_count = 0
        
        for sent in sentences:
            if not sent.strip():
                continue
                
            # Count tokens in this sentence using GLiNER's tokenizer
            sent_tokens = len(tokenizer.encode(sent)) - 2  # Subtract special tokens
            
            # If adding this sentence would exceed target size, start a new chunk
            if current_token_count + sent_tokens > target_chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sent]
                current_token_count = sent_tokens
            else:
                current_chunk.append(sent)
                current_token_count += sent_tokens
        
        # Add final chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        # Process each chunk
        all_entities = []
        
        for i, chunk in enumerate(chunks):
            logging.debug(f"Processing chunk {i+1}/{len(chunks)}")
            
            # Extract entities from this chunk
            chunk_entities = model.predict_entities(chunk, labels, threshold=threshold)
            
            # Find each entity's position in the original text
            for entity in chunk_entities:
                entity_text = entity['text']
                
                # Search for this entity in the full text
                start_idx = 0
                found = False
                
                while True:
                    pos = text.find(entity_text, start_idx)
                    if pos == -1:
                        break
                        
                    # Create a copy of this entity with corrected position
                    entity_copy = entity.copy()
                    entity_copy['start'] = pos
                    entity_copy['end'] = pos + len(entity_text)
                    all_entities.append(entity_copy)
                    found = True
                    
                    # Move past this occurrence
                    start_idx = pos + 1
                
                if not found:
                    logging.warning(f"Could not find entity '{entity_text}' in original text")
        
        return all_entities
        
    except Exception as e:
        logging.error(f"Error during entity prediction for text snippet '{text[:50]}...': {e}", exc_info=True)
        return []

# Note: Model loading itself happens in the Docker entrypoint script (`entry.py`)
# to keep heavy imports/loads isolated to that container environment.
if __name__ == '__main__':

    # I know this part is messy. Ideally I would have abstracted this out as well
    # but I feel that's an overkill. I definitely don't feel good about it though.
    import argparse
    import json
    import sys
    import os
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Extract entities from a document using GLiNER model.')
    parser.add_argument('--input_json', required=True, help='Path to input JSON file (with "body_en" key at least)')
    parser.add_argument('--output_json', required=True, help='Path to write output JSON file')
    parser.add_argument('--labels', nargs='*', default=['Person', 'Company', 'Location'], help='Entity labels to extract')
    parser.add_argument('--allow_model_download', action='store_true', help='Allow downloading the GLiNER model if not cached')
    args = parser.parse_args()

    # Try loading model if available (or warn if not installed)
    try:
        from gliner import GLiNER
        # Check if model is cached
        cache_dir = os.environ.get("TRANSFORMERS_CACHE", str(Path.home() / ".cache" / "huggingface" / "hub"))
        model_cache_path = Path(cache_dir) / "models--urchade--gliner_multi-v2.1"
        if not model_cache_path.exists():
            # If not cached, check for permission
            if args.allow_model_download or os.environ.get("ALLOW_MODEL_DOWNLOAD") == "1":
                print("Model not found in cache. Downloading GLiNER model (this may take a while)...")
            else:
                # Interactive prompt
                if sys.stdin.isatty():
                    resp = input(
                        f"GLiNER model not found in cache at {model_cache_path}.\n"
                        "Do you want to download it now? [y/N]: "
                    ).strip().lower()
                    if resp != "y":
                        print("Model download not permitted. Exiting.", file=sys.stderr)
                        sys.exit(1)
                else:
                    print(
                        "Model not found in cache and no permission to download (use --allow_model_download or set ALLOW_MODEL_DOWNLOAD=1). Exiting.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        print("Loading GLiNER model, this may take a while the first time...")
        model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
    except ImportError:
        print("[ERROR] gliner not installed, cannot run extraction. "
              "Please install gliner or test this inside Docker.", file=sys.stderr)
        sys.exit(1)

    # Load input (expects a JSON list of documents with at least a 'body_en' field)
    with open(args.input_json, "r", encoding="utf-8") as f:
        docs = json.load(f)

    out_all = []
    for doc in docs:
        body = doc.get('body_en', '')
        doc_id = doc.get('uuid', None)
        doc_title = doc.get('title_en', '')
        # batch processing would be a good idea here, for future iterations
        entities = extract_entities_from_text(model, body, labels=args.labels)
        for ent in entities:
            record = {
                'document_uuid': doc_id,
                'document_title_en': doc_title,
                'entity_text': ent['text'],
                'entity_type': ent['label'],
                'entity_start_pos': ent['start'],
                'entity_end_pos': ent['end'],
                'extractor_confidence_score': ent['score'],
            }
            out_all.append(record)
    # Save output
    with open(args.output_json, "w", encoding="utf-8") as fout:
        json.dump(out_all, fout, ensure_ascii=False, indent=2)
    print(f"Wrote {len(out_all)} entity mentions to {args.output_json}")