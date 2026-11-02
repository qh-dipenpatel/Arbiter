# Decision: records with a missing encounter date

Records that arrive with an empty encounter_date are filtered out of the silver layer and written to a quarantine table with the reason recorded. We rejected filling the gap with a default date because it would distort every monthly volume report. The data integration team reviews the quarantine table each week and asks the client to resend corrected records.
