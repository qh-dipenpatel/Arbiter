# End product quality checks

After the data platform pipelines finish, the data integration team checks three things before downstream teams rely on the output: the row count is within 10 percent of the previous day, the share of null values in required columns has not jumped, and the newest record is no more than one day old. A failed check posts in the shared channel and blocks the hand off.
