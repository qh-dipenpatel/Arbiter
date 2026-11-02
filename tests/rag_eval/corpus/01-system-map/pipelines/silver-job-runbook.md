# Runbook: silver transform job

The silver job runs after the bronze job finishes. If it fails it retries up to 4 times, 15 minutes apart, because most silver failures are short lived cluster problems. After the fourth failure it stops and posts in the data platform channel.
