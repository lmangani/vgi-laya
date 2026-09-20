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
"""HTTP entry point for the Laya VGI worker.

    uv run serve.py --port 9876

Then attach from DuckDB:

    ATTACH 'laya' (TYPE vgi, LOCATION 'http://localhost:9876');

The HTTP transport allows one worker to serve multiple clients, or to run on
a different machine than DuckDB.
"""

from __future__ import annotations

from vgi_laya.worker import main_http

if __name__ == "__main__":
    main_http()
