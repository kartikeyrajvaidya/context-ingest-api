"""Operator CLIs, run as `python -m scripts.<name>`.

`configs/` reads the environment when it is first imported, so `.env` is
loaded here, before any script module imports application code. Variables
already set in the shell win over `.env`.
"""

from dotenv import load_dotenv

load_dotenv()
