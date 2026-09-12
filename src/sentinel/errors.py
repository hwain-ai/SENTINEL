class SentinelError(Exception):
    """A safe, assertable CLI failure without sensitive implementation detail."""

    def __init__(self, code: str, message: str, exit_code: int = 3):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
