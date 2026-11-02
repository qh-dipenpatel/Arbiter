# Anti-pattern: delete then insert

Do not load a table by deleting the old rows and inserting the new ones. If the job stops between the two steps, the table is left empty or half full, and a retry cannot tell which state it is in. Use a single merge instead.
