# Remove Python build artifacts
rm -rf build/
rm -rf dist/
rm -rf ai_commit.egg-info/
rm -rf .pytest_cache/
rm -rf .commitLog/

# Remove Python cache files (if any)
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true