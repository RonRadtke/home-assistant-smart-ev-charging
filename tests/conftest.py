"""Load the pure planner without requiring Home Assistant in unit tests."""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "smart_ev_charging"
package = types.ModuleType("smart_ev_charging")
package.__path__ = [str(ROOT)]
sys.modules["smart_ev_charging"] = package
for name in ("models", "planner"):
    spec = importlib.util.spec_from_file_location(f"smart_ev_charging.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
