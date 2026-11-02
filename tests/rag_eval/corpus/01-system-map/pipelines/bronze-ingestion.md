# Bronze ingestion pipeline

Client files land in a landing volume. The pipeline checks each file against the schema registry, rejects files that fail validation, and appends the valid rows to the bronze Delta tables. Each row keeps the source file name and the load timestamp so any row can be traced back to its file.
