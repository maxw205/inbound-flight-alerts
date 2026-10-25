import os
import sys

# Make the project root importable so tests can "import alert" etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
