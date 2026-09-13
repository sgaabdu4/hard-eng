"""Keep deployment copies out of package ownership without hiding real owners."""

import subprocess
from pathlib import Path

import pytest
from gate_config import package_manifests, validate_manifest_groups


@pytest.mark.parametrize("manifest", ["pubspec.yaml", "package.json", "pyproject.toml"])
@pytest.mark.parametrize("attribute", ["linguist-generated", "linguist-vendored"])
def test_generated_package_ownership(
    tmp_path: Path, manifest: str, attribute: str
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    files = [tmp_path / owner / manifest for owner in ("canonical", "copy", "real")]
    for path in files:
        path.parent.mkdir()
        path.touch()
    attributes = tmp_path / ".gitattributes"
    attributes.write_text(f"copy/** {attribute}\nreal/** {attribute}=false\n")
    manifests = package_manifests(tmp_path, files)
    assert {owner for owner, _ in manifests} == {"canonical", "real"}
    with pytest.raises(ValueError, match="missing from gate configuration"):
        validate_manifest_groups(tmp_path, {"packages": [], "shared": []}, manifests)
    attributes.unlink()
    assert {owner for owner, _ in package_manifests(tmp_path, files)} == {
        "canonical",
        "copy",
        "real",
    }
