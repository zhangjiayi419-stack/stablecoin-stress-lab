"""Verify content hashes without network, hidden credentials or source refresh."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def verify():
    manifest=json.loads((ROOT/'release_manifest.json').read_text())
    errors=[]
    for name,expected in manifest['files'].items():
        p=ROOT/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append(name)
    if errors:raise SystemExit('Hash mismatch / missing: '+', '.join(errors))
    print(f"Verified {len(manifest['files'])} files for {manifest['version']}; seed {manifest['seed']}.")
if __name__=='__main__':verify()
