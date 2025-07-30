from importlib import import_module
from pathlib import Path

package_path = Path(__file__).resolve().parent.parent / 'custom_components/horticulture_assistant/plant_engine'
__path__ = [str(package_path)]

_module = import_module('custom_components.horticulture_assistant.plant_engine')

globals().update(_module.__dict__)
__all__ = getattr(_module, '__all__', [])
