"""Offline archive checks: uv run python -m tests.test_deployment_assets."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from deployment.assets import extract_bundle


def main():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        archive = root / "bundle.zip"
        with ZipFile(archive, "w") as bundle:
            bundle.writestr("chroma/chroma.sqlite3", b"test")
            bundle.writestr("processed/race.parquet", b"test")
        extract_bundle(archive, root / "valid")
        assert (root / "valid/processed/race.parquet").is_file()
        for bad_path in ("../escape", "/absolute", "credentials/key"):
            with ZipFile(archive, "w") as bundle:
                bundle.writestr(bad_path, b"bad")
            try:
                extract_bundle(archive, root / "invalid")
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe archive accepted")
    print("Passed: valid bundle restoration and unsafe path rejection.")


if __name__ == "__main__":
    main()
