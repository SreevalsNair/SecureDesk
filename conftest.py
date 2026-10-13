# conftest.py
# Ensures the project root is on sys.path so 'import app' works from tests/
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
