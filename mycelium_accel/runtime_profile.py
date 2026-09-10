from __future__ import annotations

from copy import deepcopy
from importlib import import_module, reload
from typing import Any


def load_default_profile() -> dict[str, Any]:
    module = import_module("mycelium_accel.generated.default_profile")
    module = reload(module)
    return deepcopy(module.DEFAULT_PROFILE)
