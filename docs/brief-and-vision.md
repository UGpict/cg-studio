# Structured briefs and optional local vision review

## What is implemented, and what has actually run

Two optional modules extend the existing command-line pipeline without changing its spec, renderer or manual-review API:

- `cgstudio.brief` is a deterministic, closed English/Japanese brief compiler for the existing resin-pour scene. It is **not an LLM or a general text-to-3D model**.
- `cgstudio.auto` and `cgstudio.vision` implement a bounded JSON/stdio integration boundary for an explicitly configured, already installed, authorized **local** vision model executable. No model, API key, network service or paid fallback is supplied or discovered.

The compiler is exercised with real text inputs. The provider protocol and unattended revision loop are tested using clearly marked **test-double render/provider fixtures**. Those tests establish software behavior only. They do not establish that a vision model inspected a real resin image or that production quality passed. With no local provider, the actual pipeline stays `review_pending`.

A source checkout is required, as with the original pipeline. The wheel alone does not distribute the scene builder, QA criteria and base specs.

## Compile a brief

```sh
python -m cgstudio.brief describe
python -m cgstudio.brief compile \
  --brief 'Clear resin pours into a thick transparent cup. Show real wall thickness, a clean meniscus, readable refraction, soft contact shadows and a metal object for reflection reference. Resolution 512x512; samples=32.' \
  --output runs/brief-report.json --spec-output runs/compiled-spec.json
python -m cgstudio validate --spec runs/compiled-spec.json
python -m cgstudio run --spec runs/compiled-spec.json --output runs/my-shot
```

Japanese example:

```sh
python -m cgstudio.brief compile \
  --brief '透明なレジンを厚みのある透明なカップに注ぐ。壁の厚み、きれいなメニスカス、屈折を見せる、柔らかい接地影。解像度は512x512。サンプル数は32。' \
  --output runs/japanese-brief-report.json --spec-output runs/japanese-spec.json
```

Use `--brief-file` for UTF-8 text and `--base` for an explicit complete validated base spec. Outputs must be new files; the compiler never overwrites existing evidence.

Every nonempty clause must match a documented phrase or numeric assignment. The report includes the original text, recognized clauses, requested parameters, retained defaults, per-field provenance, base-spec identity and all unresolved issues. Only `status: compiled` includes a runnable spec. `needs_clarification` or `unsupported` returns `spec: null` and exits 2. No partially interpreted spec is used.

Examples of explicit assignments:

```text
cup.height=1.8; liquid.stream_top=3
wall thickness is 0.08
カップの高さは1.8
absorption color=[0.94,0.99,1.0]
animation.fill_start=0.6; animation.fill_end=1.4
budget.max_iterations=1
```

The complete alias list and bounds are in `describe`. Supported initial parameters cover render size/samples, cup dimensions/material, resin dimensions/material, stage, lighting, art-directed animation and budget reductions. Lengths are normalized benchmark units. Physical-unit conversion is not silently assumed.

Phrase defaults are documented choices. Explicit numeric values override phrase defaults, but conflicting repeated values, incompatible cup/fill geometry, or “clear resin” combined with cloudiness/non-transmission require clarification. Cameras, seed, renderer/device and nonnumeric settings are inherited from the base. Budget values can only tighten the base limits. New objects, arbitrary assets, code, shell commands, camera changes, fluid/chemical simulation and paid services are unsupported. Unknown wording blocks compilation instead of being discarded.

The compiler and vision adapter also apply conservative constraints for the current builder's fixed rolled lip, tapered interior, base offsets, card clearance, off-center stream envelope and nozzle position. `describe` lists the exact profile checks. These supplement schema ranges and prevent known incompatible geometry; they are not a manifold or visual-quality proof.

The compiler's `requirements` are requested visible cues for later inspection, not assertions that the generated image satisfies them. The original brief remains in the resulting spec and is sent to a configured reviewer as untrusted task data.

## Opt into a local vision provider

No configuration is needed for the ordinary human/agent review flow. This command makes no provider call and reports the missing integration honestly:

```sh
python -m cgstudio.auto --output runs/my-shot
```

To operate unattended, the user/operator must separately supply and authorize a local executable that really accepts image inputs, inspects them with an available local vision model, and implements the contract below. The repository does not install it or configure credentials. An example **configuration shape**, not a working included provider, is:

```json
{
  "protocol": "cgstudio.vision.v1",
  "provider_id": "my-approved-local-vision",
  "command": ["/absolute/path/to/installed-local-vision-adapter"],
  "kind": "local_vision_model",
  "declared_max_cost_usd": 0
}
```

```sh
python -m cgstudio.auto --output runs/my-shot \
  --provider-config /path/to/explicit-local-provider.json
```

The config is operator-owned executable configuration. Never create it from a brief, model response, web page or other untrusted content. It is not a sandbox for hostile executables. The operator must verify the provider's zero-cost/local-only declaration and have authorized that executable. The adapter cannot cryptographically prove how a separate program operates or bills. Paid providers are unsupported and any nonzero declared or returned cost fails validation. No positive spending allowance is exposed.

The adapter launches the configured argument vector directly, never through a shell. It does not use response content as arguments, Python, shell, imports or file paths. The child gets a minimal `PATH`/`LANG` environment; the adapter does not discover or forward environment credentials. No password/token fields are allowed in config or results. Child stderr and malformed raw output are not persisted, to avoid accidentally logging secrets.

### Request

Optional real image references can be supplied without fetching anything or changing the scene:

```json
[
  {
    "label": "material-reference",
    "path": "/absolute/path/to/authorized-reference.jpg",
    "sha256": "replace-with-the-exact-64-character-lowercase-file-sha256",
    "source_url": "https://verified-source.example/reference-page"
  }
]
```

Pass this operator-owned file with `--reference-config references.json`. Relative paths resolve beside that config. Up to four PNG/JPEG files, each at most 8 MiB, are supported. Labels must be unique. Their bytes and hashes are included, and the provider must bind every reference in its response. Source URLs are provenance only; the adapter never visits them. The operator is responsible for supplying authorized images and accurate source metadata. With no references, no image-reference agreement may be claimed. Even with references, this code does not generate a similarity score or certify a match.

One JSON object is supplied on standard input. It contains:

- Protocol, unique request ID, configured provider ID and explicit three-view-still scope
- Exact iteration spec, brief, frame, QA criteria, review template, strict response schema and limits
- Three native PNG byte payloads in base64, each labeled `hero`, `side` or `top`, plus its SHA-256, size and fixed camera parameters
- Optional labeled reference image bytes, exact hashes and source URLs

Before sending, the adapter checks all artifact/spec/builder hashes and verifies every camera's manifest against the same spec, frame, builder, seed, sample count, engine, device and denoising setting. It rechecks evidence after the provider returns, and the existing resume gate checks it again before acceptance or rendering a revision. A request contains actual image bytes, not just filenames or pixel statistics.

### Response

The provider must output exactly one JSON object and no Markdown wrapper or log prefix. The machine-readable schema is `schemas/vision-response.schema.json`. The envelope contains `protocol`, `provider_id`, `request_id`, `review`, `references_sha256` and `usage.paid_cost_usd: 0`. `references_sha256` is the exact ordered list of supplied `{label, sha256}` identities, or an empty array when no references were supplied.

`review` uses the unchanged strict existing completed-review schema. It must bind the exact run, iteration, spec and three image hashes. The reviewer must identify the configured provider, attest actual inspection of all three cameras, and return `accepted`, `revise` or `rejected`.

- At most six concrete issues, ordered P0/P1 before P2/P3
- Each issue observation identifies `hero`, `side` or `top`
- At most three genuinely changing numeric parameters from the existing review allowlist
- Full patched-spec and supported-builder-profile validation; no code, camera, seed, paths, dimensions, geometry expansion, budget change or unknown fields
- No acceptance with unresolved P0/P1 issues

The external provider's attestation remains a trust boundary. A schema-valid statement alone cannot prove that its model looked at pixels. There is no synthetic quality score, histogram acceptance heuristic, or fallback approval. Three stills cannot certify motion, physical simulation, browser appearance or finished-film quality.

### Limits, retries and recovery

Hard ceilings are six calls total, two attempts per iteration, 60 seconds per call and 180 cumulative review seconds. These can only be tightened through CLI options. Provider time is also charged against the original pipeline's 1,800-second active-time ceiling; no extra render allowance is granted. The original three-iteration cap still applies.

The process tree is killed at timeout, oversize output, interruption or completion. Standard input/output/error are pumped concurrently to avoid deadlock. Inputs are size-bounded, stdout is capped at 256 KiB and stderr at 64 KiB. Requests are capped at 68 MiB, with each PNG capped at 16 MiB.

Attempts and a conservative time reservation are persisted to `vision_ledger.json` before launch. A normal malformed/failed call can retry once if time remains. No retry changes the provider, limits or image evidence. An interrupted attempt with an uncertain outcome blocks automatic retries; its reserved time remains charged. A validated review is saved to the iteration before `resume_run` is called. If interrupted between saving and resuming, inspect that receipt and use the existing explicit resume command. Do not edit the ledger to reset allowances.

After unavailable, invalid, exhausted or uncertain review attempts, production stills remain unaccepted at `review_pending` unless another authorized operation already changed the pipeline. A separately saved valid review can still be supplied through the original manual-review flow.

## Test-double discipline

The integration tests explicitly request `test_fixture_only=True`, configure `kind: test_double`, use renderer manifests marked `test_fixture: true`, and require review summaries beginning `TEST DOUBLE ONLY:`. The adapter refuses to mix fixture and production evidence or accept an unlabeled fixture verdict. An `accepted` state inside those tests means the state-machine branch worked, **not production visual acceptance**.

```sh
python -m unittest discover -s tests -v
```

Coverage includes supported Japanese/English phrases; unknown, ambiguous and contradictory requests; original-text/default provenance; strict numeric and geometry validation; actual PNG/reference payload/hash binding; camera alignment; malformed/duplicate-key JSON; forged IDs/hashes; unknown fields/code; bounded patches/priorities; no-op patches; $0 cost enforcement; process-tree termination; blocked stdin; output limits; persistent retry accounting; preserved camera/seed; and render-iteration exhaustion.

## Extending beyond the resin scene

This version separates brief interpretation, strict scene specs, rendering, evidence, provider review and safe numeric revision. A future scene family needs its own complete schema, builder, supported-intent compiler, bounded patch surface, review criteria and test/evidence set. Replacing the local provider does not broaden geometry support. Adding an LLM that emits specs would still require validation and explicit unsupported-intent handling; model-generated Python or shell must never become a scene-building path.
