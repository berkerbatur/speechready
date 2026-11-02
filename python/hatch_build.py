"""Bundle the shared provider profiles and lexicons (../spec) into the package at build time.

When building from the repository, spec/profiles and spec/lexicons live outside
the Python project and are copied into speechready/profiles/data and
speechready/lexicons/data. When building a wheel from the sdist, those copies
are already inside src/, so nothing is added.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

SPEC = Path(__file__).resolve().parent.parent / "spec"
BUNDLED = ("profiles", "lexicons")


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        for name in BUNDLED:
            source = SPEC / name
            if not source.is_dir():
                continue
            target = f"speechready/{name}/data" if self.target_name == "wheel" else f"src/speechready/{name}/data"
            build_data.setdefault("force_include", {})[str(source)] = target
