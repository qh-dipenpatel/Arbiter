# Runbook: bronze load job

The bronze job runs nightly at 2am. If it fails it retries up to 2 times, 10 minutes apart. After the second failure it stops and pages the data integration on-call. Rows with a null in a required field are routed according to the null handling decisions, not dropped silently.
