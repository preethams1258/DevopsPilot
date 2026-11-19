"""Bounded stress workload. Invoked only through fixed controller actions."""
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("kind", choices=["cpu", "memory"])
parser.add_argument("--seconds", type=int, default=45)
args = parser.parse_args()
deadline = time.monotonic() + max(1, min(args.seconds, 60))
if args.kind == "cpu":
    while time.monotonic() < deadline:
        sum(i * i for i in range(50_000))
else:
    blocks = []
    try:
        while time.monotonic() < deadline:
            blocks.append(bytearray(1024 * 1024))
            time.sleep(0.1)
    except MemoryError:
        pass
