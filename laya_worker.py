# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "vgi-python[http]>=0.34.0",
#     "vgi-rpc>=0.46.0",
#     "laya>=0.3.4",
#     "pyarrow>=15.0.0",
# ]
# ///
"""Stdio entry point for the Laya VGI worker.

    ATTACH 'laya' (TYPE vgi, LOCATION 'uv run /path/to/laya_worker.py');

The PEP-723 header above is load-bearing: it lets ``uv run`` resolve the
worker's dependencies from an ephemeral environment, so the ATTACH works from
any directory and on a machine that has never seen this project.
"""

from __future__ import annotations

from vgi_laya.worker import main

if __name__ == "__main__":
    main()
