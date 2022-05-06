import argparse
import os
import site
import sys
from io import StringIO
from pathlib import Path

from mypy.main import main

_original_getsitepackages = site.getsitepackages
_original_getusersitepackages = site.getusersitepackages


def monkey_patch_sitepackages(
    external_deps_manifest_path: str, runfiles_root: str
) -> None:
    """
    mypy will only find types from external (3rd party) packages when they are within directories returned by
    `site.getsitepackages` or `site.getusersitepackages`. It will not consider any other paths, including sys.path entries

    This does not work well with the bazel layout for external/ workspaces. The method monkey patches the two functions
    and returns a list of paths passed via the manifest created by the rh_mypy_test rule

    This will also patch over `getusersitepackages` as this can return paths that are outside of the sandbox and runfiles trees,
    leading to mypy finding packages that it shouldn't.

    These methods are restored once mypy has completed
    """
    try:
        external_deps_manifest = (
            Path(external_deps_manifest_path).read_text().split("\n")
        )
    except Exception as e:
        print(
            f"Unexpected error while reading dependency manifest file at '{external_deps_manifest_path}'",
            e,
        )
        sys.exit(1)

    site_packages = [
        # As per the bazel testing requirements, we are in blah.runfiles/rh and paths are rooted
        # at the root of the runfiles tree
        # use the env var 'TEST_SRCDIR' to get the absolute path to the runfiles root and append it to the
        # list of dependencies, see https://docs.bazel.build/versions/master/test-encyclopedia.html for more info
        # site-packages must be absolute paths
        os.path.join(runfiles_root, external_dep_path)
        for external_dep_path in external_deps_manifest
    ]

    # Sanity check that the paths actually exist.
    for site_package in site_packages:
        assert os.path.exists(site_package)

    def __bazel_override_getsitepackages__():
        # return both the list of manifest paths and the original to include any bundled packages with
        # the bazel python install
        return site_packages + _original_getsitepackages()

    def __bazel_override_getusersitepackages__():
        # don't return any paths, all userland site-packages should be ignored
        return ''

    site.getsitepackages = __bazel_override_getsitepackages__
    site.getusersitepackages = __bazel_override_getusersitepackages__


def restore_original_sitepackages() -> None:
    site.getsitepackages = _original_getsitepackages
    site.getusersitepackages = _original_getusersitepackages


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--external_deps", required=True)
    args, unknown = parser.parse_known_args()
    # We set the runfiles_root differently depending whether we run bazel build or test.
    runfiles_root = os.environ.get('TEST_SRCDIR') or os.path.join(
        os.getcwd(), "external"
    )
    monkey_patch_sitepackages(args.external_deps, runfiles_root)
    # The following ensures that nothing is printed to stdout and stderr in the
    # case when type checking succeeds.
    stdout = StringIO()
    stderr = StringIO()
    try:
        main(None, stderr, stderr, unknown)
        exit_status = 0
    except SystemExit as system_exit:
        exit_status = system_exit.code
        print(stdout.getvalue(), file=sys.stdout)
        print(stderr.getvalue(), file=sys.stderr)
    finally:
        restore_original_sitepackages()
    sys.exit(exit_status)
