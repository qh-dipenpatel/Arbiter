# Decision: schema registry versioning

Every schema in the registry carries a version number. A change that removes or renames a column is a breaking change: it gets a new major version, the old version keeps running, and the client receives written notice with a cutover date. Adding an optional column is not breaking and only raises the minor version.
