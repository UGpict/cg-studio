# Coordinator

Use `python -m cgstudio` to validate, run, resume, and inspect. Reserve each iteration before launch. Enforce the smaller of the per-render and remaining-total time budgets, and kill timed-out process groups. Invoke no paid renderer, image generator, or vision endpoint.

After rendering all three fixed views, write a pending review request and stop. Resume only from a completed actual visual-review attestation bound to all current image hashes and the spec. Reject stale hashes, changed artifacts, malformed reviews, out-of-bounds values, code, camera changes, no-op patches, and unsupported fields. Apply approved numeric values to a copied spec, validate the whole result, and retain the review audit hash.

Report `review_pending`, `accepted`, `rejected`, `budget_exhausted`, `failed`, or `interrupted` precisely. Do not call pending work autonomous visual acceptance. Do not erase or reset accounting to obtain more renders. At the iteration ceiling, preserve the last review and explain that no new render was started.
