"""
Database model definition
"""


class Database:
    """
    Database object representing a database instance.

    Note:
        - tenant is None for embedded/server mode (no tenant concept)
        - tenant is set for OceanBase mode (multi-tenant architecture)
    """

    def __init__(
        self,
        name: str,
        tenant: str | None = None,
        charset: str | None = None,
        collation: str | None = None,
        **kwargs,
    ):
        """
        Initialize Database object

        Args:
            name: database name
            tenant: tenant name (only for OceanBase, None for embedded/server mode)
            charset: character set
            collation: collation
            **kwargs: other metadata
        """
        self.name = name
        self.tenant = tenant
        self.charset = charset
        self.collation = collation
        self.metadata = kwargs

    def __repr__(self):
        if self.tenant:
            return f"<Database name={self.name} tenant={self.tenant}>"
        return f"<Database name={self.name}>"

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, Database):
            return self.name == other.name and self.tenant == other.tenant
        return False

    def __hash__(self):
        return hash((self.name, self.tenant))
