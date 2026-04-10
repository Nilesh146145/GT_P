from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from fastapi import APIRouter

router = APIRouter()
_ROUTER_DIR = Path(__file__).with_name("reviewer")


def _load_router(name: str):
    module_name = f"app.routers._reviewer_{name}"
    module_path = _ROUTER_DIR / f"{name}.py"
    spec = spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load reviewer router: {module_path}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


router.include_router(_load_router("dashboard").router)
router.include_router(_load_router("users").router)
