"""Прогрев и сравнение temperature на одинаковых seed."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
runs = [("warmup-temperature.json", 0.2, 42)]
runs += [(f"{label}{seed}.json", temperature, seed)
         for seed in (42, 43, 44)
         for label, temperature in (("cold", 0.2), ("hot", 0.8))]
for name, temperature, seed in runs:
    path = root / "results" / name
    if path.exists():
        raise SystemExit(f"Результат уже существует: {path}")
for name, temperature, seed in runs:
    print(f"RUN {name}: temperature={temperature}, seed={seed}", flush=True)
    subprocess.run([sys.executable, str(root / "experiment.py"),
                    "--mode", "system", "--model", "qwen3.5:9b",
                    "--temperature", str(temperature), "--seed", str(seed),
                    "--output", str(root / "results" / name)], check=True)
