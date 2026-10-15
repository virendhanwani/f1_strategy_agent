"""Build the R2 upload bundle locally, with no credentials or raw cache."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = ROOT / "data"
    database = data / "chroma" / "chroma.sqlite3"
    if not database.is_file():
        raise FileNotFoundError("Build the regulation index first.")
    output = ROOT / "dist" / "f1-assets.zip"
    output.parent.mkdir(exist_ok=True)
    # Stop ingestion/index writes before packaging: SQLite backup gives a
    # consistent database, while Chroma's separate index files must stay stable.
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / "chroma.sqlite3"
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as source:
            with sqlite3.connect(snapshot) as target:
                source.backup(target)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(snapshot, "chroma/chroma.sqlite3")
            for folder in ("chroma", "processed"):
                for path in sorted((data / folder).rglob("*")):
                    if path.is_file() and not path.is_symlink() and not path.name.startswith("chroma.sqlite3"):
                        bundle.write(path, path.relative_to(data))
    with output.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    print(f"Bundle: {output}\nSHA256: {checksum}\nBytes: {output.stat().st_size}")


if __name__ == "__main__":
    main()
