"""Allow ``python -m BODtoJSON ...``."""

import sys

from .cli import main

sys.exit(main())
