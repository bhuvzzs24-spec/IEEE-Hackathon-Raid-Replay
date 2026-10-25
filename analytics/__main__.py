"""Run analytics as a module: python -m analytics"""
import sys
from pathlib import Path
from analytics.pipeline import run_analytics_pipeline

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    data = run_analytics_pipeline(root)
    sys.exit(0)
