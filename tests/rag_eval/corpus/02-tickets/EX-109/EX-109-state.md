# EX-109: Example Client A file arrived 9 hours late

Status: resolved. Root cause: the client's SFTP login expired and their export job failed silently overnight. It was not a problem on our side. We told the client the file was late because of the expired login, they renewed it, and the file arrived by mid afternoon. No retry was involved.
