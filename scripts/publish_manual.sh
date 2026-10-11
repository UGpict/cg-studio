#!/usr/bin/env bash
# Run yourself after authenticating Git with GitHub. Does not create credentials.
set -euo pipefail
mode=bundle
if [[ "${1:-}" == '--source' ]]; then
  mode=source
  source_dir="${2:?Provide the freshly extracted source package directory}"
  source_dir=$(cd "$source_dir" && pwd)
  target="${3:?Provide a new checkout directory}"
else
  bundle="${1:?Usage: publish_manual.sh BUNDLE NEW_CHECKOUT, or --source PACKAGE_DIR NEW_CHECKOUT}"
  target="${2:?Provide a new checkout directory}"
fi
repo='https://github.com/UGpict/cg-studio.git'
branch='feature/cg-studio-pipeline'
expected='ccd6f8b23b77b92f369b68038c3d6503682d31a0'
if [[ -e "$target" ]]; then echo 'Choose a new, nonexistent checkout directory.' >&2; exit 2; fi
if [[ "$mode" == bundle ]]; then
  git bundle list-heads "$bundle" >/dev/null
  git clone --branch main "$bundle" "$target"
  cd "$target"
  release=$(git rev-parse HEAD)
  git remote set-url origin "$repo"
  git fetch origin "refs/heads/$branch:refs/remotes/origin/$branch"
else
  test -f "$source_dir/PACKAGE_FILES.json" || { echo 'Missing package file manifest.' >&2; exit 2; }
  git clone --branch "$branch" "$repo" "$target"
  cd "$target"
fi
actual=$(git rev-parse "refs/remotes/origin/$branch")
if [[ "$actual" != "$expected" ]]; then
  echo "Remote branch changed ($actual). Stop and review before importing; nothing was pushed." >&2
  exit 3
fi
if ! git var GIT_AUTHOR_IDENT >/dev/null 2>&1; then
  echo 'Set your own Git author identity, then restart with another new checkout directory.' >&2
  exit 4
fi
git switch -c publish-cg-studio "refs/remotes/origin/$branch"
if [[ "$mode" == bundle ]]; then
  git restore --source="$release" --staged --worktree -- .
else
  python3 - "$source_dir" "$PWD" <<'PY_COPY'
import hashlib, json, os, shutil, sys
from pathlib import Path
src, dst = map(Path, sys.argv[1:])
entries = json.loads((src / 'PACKAGE_FILES.json').read_text())
for e in entries:
    p = Path(e['path'])
    if p.is_absolute() or '..' in p.parts or '.git' in p.parts:
        raise SystemExit('Unsafe manifest path')
    source = src / p
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(src):
        raise SystemExit('Missing or unsafe source: ' + str(p))
    if hashlib.sha256(source.read_bytes()).hexdigest() != e['sha256']:
        raise SystemExit('Package file changed: ' + str(p))
for e in entries:
    p = Path(e['path']); target = dst / p
    if target.is_symlink() or not target.resolve().is_relative_to(dst):
        raise SystemExit('Unsafe destination: ' + str(p))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / p, target)
    os.chmod(target, 0o755 if e['executable'] else 0o644)
PY_COPY
  git add --all
fi
git commit -m 'Import tested CG Studio pipeline and separate offline prototype'
# A concurrent branch change is safely rejected by a normal, non-force push.
git push origin "HEAD:refs/heads/$branch"
printf '\nPublished the draft PR branch only. Review: https://github.com/UGpict/cg-studio/pull/1\n'
