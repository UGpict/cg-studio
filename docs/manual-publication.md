# Manual publication after GitHub sign-in

## Verified remote state: 2026-10-11 13:30 UTC

[Draft PR #1](https://github.com/UGpict/cg-studio/pull/1) exists. Its branch,
`feature/cg-studio-pipeline`, points to `ccd6f8b23b77b92f369b68038c3d6503682d31a0`.
Only `.gitignore` and `pyproject.toml` have been added to the README-only main
branch. The complete local project has **not** been published.

The connector returned `user cancelled MCP tool call` for a later, small
commit-metadata request. No branch update followed it. This response does not
establish that a person clicked Cancel or that request size was the cause.
Remote writes were paused. The local package and tests remain available.

## Publish the complete package yourself

Prerequisites: Git installed, your own Git author name/email configured, and Git
already authenticated to GitHub with write access to `UGpict/cg-studio`. Use your
normal GitHub authentication flow; never paste a token into the project or chat.
Extract the compact source ZIP into a fresh directory. It includes every source/test file and the accepted prototype assets; historical raw PNGs/frame contact sheets and Git history are omitted and listed in `COMPACT_PACKAGE.txt`. From that package root, run:

```sh
bash scripts/publish_manual.sh --source . ../cg-studio-publish
```

The file manifest verifies exact package hashes before copying only the allowlisted files into a new checkout. Python 3.10+ is required. The source route publishes the compact file subset; the full checkpoint retains the omitted historical evidence.

The full source checkpoint also includes a clean Git history bundle. To import the complete history snapshot instead, run:

```sh
bash scripts/publish_manual.sh ./cg-studio-history.bundle ../cg-studio-publish
```

This creates a new checkout, imports the local release onto the existing PR
branch, and performs one normal, non-force push. It refuses to proceed if that
remote branch has changed since the verified state above. It does not update
main, merge the PR, create credentials, or change repository visibility. If the
branch has changed, inspect it before adjusting the expected commit. A failed
push can be diagnosed from the new checkout without rerunning the whole import.

Both helper routes were tested against an isolated filesystem Git remote: the expected branch was updated and main stayed unchanged. Its live authenticated GitHub push has not been run. Confirm the branch commit and files on GitHub after running it. The existing
PR body may still describe an incomplete import; update it to match the verified
files and the completion matrix. Browser A/C images and live autonomous vision
remain open validation gates even after publication.
