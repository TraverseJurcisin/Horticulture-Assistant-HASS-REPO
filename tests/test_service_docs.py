import ast
import pathlib

import yaml


def _collect_services(path: pathlib.Path) -> set[str]:
    """Collect service names registered within the given module."""

    code = path.read_text()
    tree = ast.parse(code)

    # Map module-level constants to their string values so service names defined
    # via symbols (``SERVICE_X = "x"``) are resolved correctly.
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    constants[target.id] = node.value.value

    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(getattr(node.func, "attr", None), str)
            and node.func.attr == "async_register"
            and len(node.args) >= 2
        ):
            service_arg = node.args[1]
            if isinstance(service_arg, ast.Constant) and isinstance(service_arg.value, str):
                names.add(service_arg.value)
            elif isinstance(service_arg, ast.Name) and service_arg.id in constants:
                names.add(constants[service_arg.id])
    return names


def test_services_documented():
    root = pathlib.Path(__file__).parents[1] / "custom_components" / "horticulture_assistant"
    documented = set(yaml.safe_load((root / "services.yaml").read_text()))
    registered = (
        _collect_services(root / "__init__.py")
        | _collect_services(root / "services.py")
        | _collect_services(root / "calibration" / "services.py")
    )
    assert documented == registered
