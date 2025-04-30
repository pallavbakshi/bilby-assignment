FROM entity_extractor_base:latest
   
WORKDIR /app

# Copy the pipeline logic needed by the entrypoint
COPY pipeline /app/pipeline

# Copy the entrypoint script
COPY docker/entity_extractor/entry.py ./

# Define the entrypoint for the container
ENTRYPOINT ["python", "entry.py"]