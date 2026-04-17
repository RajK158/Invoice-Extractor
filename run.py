"""
run.py - Convenience launcher for the Multi-Language Invoice Extractor.

Usage:
    python run.py                  # Launch Streamlit app
    python run.py --api            # Launch FastAPI backend
    python run.py --generate       # Generate sample invoice images
    python run.py --benchmark      # Run retrieval speed benchmark
    python run.py --test           # Run test suite
    python run.py --reindex        # Rebuild Whoosh search index from DB
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def launch_streamlit():
    print("🚀 Starting Streamlit app…")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(ROOT / "app" / "streamlit_app.py"),
        "--server.port", "8501",
        "--server.headless", "false",
    ])


def launch_api():
    print("🔌 Starting FastAPI backend on http://localhost:8001")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.api:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8001",
    ])


def generate_samples(count: int = 10):
    print(f"🖼  Generating {count} sample invoices…")
    subprocess.run([
        sys.executable,
        str(ROOT / "data" / "samples" / "generate_samples.py"),
        "--count", str(count),
        "--output", str(ROOT / "data" / "samples"),
    ])


def run_benchmark(n: int = 500, queries: int = 30):
    print(f"📊 Running benchmark: {n} records, {queries} queries…")
    subprocess.run([
        sys.executable,
        str(ROOT / "benchmarks" / "benchmark_search.py"),
        "--n", str(n),
        "--queries", str(queries),
    ])


def run_tests():
    print("🧪 Running test suite…")
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"])


def reindex():
    print("🔁 Rebuilding Whoosh search index from database…")
    sys.path.insert(0, str(ROOT))
    from app.retrieval.search import rebuild_index_from_db
    rebuild_index_from_db()
    print("✅ Reindex complete.")


def main():
    parser = argparse.ArgumentParser(description="Multi-Language Invoice Extractor launcher")
    parser.add_argument("--api", action="store_true", help="Launch FastAPI backend")
    parser.add_argument("--generate", action="store_true", help="Generate sample invoice images")
    parser.add_argument("--benchmark", action="store_true", help="Run retrieval benchmark")
    parser.add_argument("--test", action="store_true", help="Run tests")
    parser.add_argument("--reindex", action="store_true", help="Rebuild search index")
    parser.add_argument("--count", type=int, default=10, help="Number of samples to generate")
    parser.add_argument("--n", type=int, default=500, help="Records for benchmark")
    parser.add_argument("--queries", type=int, default=30, help="Queries for benchmark")
    args = parser.parse_args()

    if args.api:
        launch_api()
    elif args.generate:
        generate_samples(args.count)
    elif args.benchmark:
        run_benchmark(args.n, args.queries)
    elif args.test:
        run_tests()
    elif args.reindex:
        reindex()
    else:
        launch_streamlit()


if __name__ == "__main__":
    main()
