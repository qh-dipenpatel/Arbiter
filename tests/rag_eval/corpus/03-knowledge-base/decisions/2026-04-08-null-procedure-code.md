# Decision: records with a missing procedure code

A missing procedure_code does not remove the record. The row stays in silver with the code set to UNKNOWN and a flag column, because the rest of the claim line is still valid for volume and cost reports. This is different from a missing encounter date, which sends the record to quarantine.
