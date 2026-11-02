# EX-117: duplicate rows in silver after the encounter join

Status: resolved. Root cause: the silver transform joined encounters to a lookup table that held two rows for some keys, so each encounter was copied twice. No retry was involved. Fix: remove repeated keys from the lookup table before the join and add a check that fails the job if the row count grows after the join.
