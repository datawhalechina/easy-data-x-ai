"""
Version class for representing and comparing database versions
"""


class Version:
    """
    Represents a version number with support for comparison operations.

    Supports versions in format: x.x.x or x.x.x.x (3 or 4 numeric parts)

    Examples:
        >>> v1 = Version("1.0.1.0")
        >>> v2 = Version("1.0.0.1")
        >>> v1 > v2
        True

        >>> v1 = Version("1.2.3")
        >>> v2 = Version("1.2.4")
        >>> v1 < v2
        True
    """

    def __init__(self, version_str: str):
        """
        Initialize Version from string.

        Args:
            version_str: Version string in format x.x.x or x.x.x.x

        Raises:
            ValueError: If version string format is invalid
        """
        if not version_str:
            raise ValueError("Version string cannot be empty")

        parts = version_str.split(".")
        if len(parts) not in (3, 4):
            raise ValueError(f"Version format should be x.x.x or x.x.x.x (3 or 4 numeric parts), got: {version_str}")

        try:
            self._parts = [int(part) for part in parts]
        except ValueError as e:
            raise ValueError(f"Version parts must be numeric, got: {version_str}") from e

        # Normalize to 4 parts for comparison (pad with 0 if needed)
        if len(self._parts) == 3:
            self._parts.append(0)

    @property
    def parts(self) -> tuple[int, int, int, int]:
        """Get version parts as tuple"""
        return tuple(self._parts)

    @property
    def major(self) -> int:
        """Get major version number"""
        return self._parts[0]

    @property
    def minor(self) -> int:
        """Get minor version number"""
        return self._parts[1]

    @property
    def patch(self) -> int:
        """Get patch version number"""
        return self._parts[2]

    @property
    def build(self) -> int:
        """Get build version number (0 if not specified)"""
        return self._parts[3]

    def __str__(self) -> str:
        """Convert to string representation"""
        # Always return full version (preserve all parts including trailing .0)
        return ".".join(str(p) for p in self._parts)

    def __repr__(self) -> str:
        """Representation for debugging"""
        return f"Version('{self}')"

    def __eq__(self, other) -> bool:
        """Check equality"""
        if not isinstance(other, Version):
            return NotImplemented
        return self._parts == other._parts

    def __lt__(self, other) -> bool:
        """Check if less than"""
        if not isinstance(other, Version):
            return NotImplemented
        return self._parts < other._parts

    def __le__(self, other) -> bool:
        """Check if less than or equal"""
        if not isinstance(other, Version):
            return NotImplemented
        return self._parts <= other._parts

    def __gt__(self, other) -> bool:
        """Check if greater than"""
        if not isinstance(other, Version):
            return NotImplemented
        return self._parts > other._parts

    def __ge__(self, other) -> bool:
        """Check if greater than or equal"""
        if not isinstance(other, Version):
            return NotImplemented
        return self._parts >= other._parts

    def __hash__(self) -> int:
        """Hash for use in sets and dicts"""
        return hash(tuple(self._parts))
