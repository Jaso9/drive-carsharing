import os

# Test-only key; never used by the running application.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-for-isolated-tests-123456")
