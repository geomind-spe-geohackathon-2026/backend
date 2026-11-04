"""Backend test suite.

The tests read the settings of ``.env.example``, never a deploy's ``.env``,
and seed no first admin at start.
"""

import os

os.environ["APP_ENV_FILE"] = ".env.example"
os.environ["FIRST_ADMIN_EMAIL"] = ""
os.environ["FIRST_ADMIN_PASSWORD"] = ""
