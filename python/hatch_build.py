"""Bundle the shared provider profiles (../spec/profiles) into the package at build time.

When building from the repository, the profiles live outside the Python project
in spec/profiles and are copied into speechready/profiles/data. When building a
wheel from the sdist, that copy is already inside src/, so nothing is added.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

SPEC = Path(__file__).resolve().parent.parent / "spec" / "profiles"


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if not SPEC.is_dir():
            return
        target = "speechready/profiles/data" if self.target_name == "wheel" else "src/speechready/profiles/data"
        build_data.setdefault("force_include", {})[str(SPEC)] = target
