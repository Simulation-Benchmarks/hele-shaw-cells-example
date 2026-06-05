# Publishing hele-shaw-cells-example

This checklist walks through publishing the new benchmark repo to GitHub and
registering it with the platform hub. Run from the repo root unless noted.

## 1. Create the remote repository

The example will live at `https://github.com/Simulation-Benchmarks/hele-shaw-cells-example`.
Create it via the GitHub web UI or `gh repo create`:

```bash
gh repo create Simulation-Benchmarks/hele-shaw-cells-example \
    --public --description "Blueprint-aligned instance repo for the Hele-Shaw cells benchmark (NFDI4IngModelValidationPlatform)."
```

(requires write access to the Simulation-Benchmarks org)

## 2. Push the local repo

```bash
git remote add origin git@github.com:Simulation-Benchmarks/hele-shaw-cells-example.git
git push -u origin main
git push origin --tags    # if you have any tags to push
```

## 3. Add a row to the hub's benchmark registry

Edit `NFDI4IngModelValidationPlatform/docs/index.md` and add a row to the
"Available Benchmarks" table for the new example. The exact row text is:

```
| Hele-Shaw Cells | [hele-shaw-cells-example](https://github.com/Simulation-Benchmarks/hele-shaw-cells-example) | Radial viscous fingering in a 2D circular Hele-Shaw cell (VOF, gap-averaged, OpenFOAM heleShawFoam) |
```

Then commit and push that edit to the hub repo.

## 4. Enable branch protection (optional but recommended)

In the GitHub UI: Settings → Branches → Branch protection rules → add rule
for `main` requiring CI to pass before merging.

## 5. Add ROHub secrets (only if you want CI to upload)

If you want the tag-triggered ROHub upload job (see
`.github/workflows/run-benchmark.yml`) to run automatically, add these
GitHub Actions secrets in the new repo:

- `ROHUB_USERNAME`: your ROHub username (use the dev endpoint's credentials, not production)
- `ROHUB_PASSWORD`: your ROHub password

If these are missing, the upload job will SKIP cleanly and you'll see
"ROHUB_USERNAME/ROHUB_PASSWORD not set; skipping upload" in the CI log.

## 6. Configure Zenodo (optional)

To mint a DOI for v1.0.0:

1. Go to https://zenodo.org/ and link your GitHub account
   (Settings → GitHub → select Simulation-Benchmarks).
2. Enable the new repo in Zenodo's settings.
3. Tag a v1.0.0 release (see step 7); Zenodo will mint a DOI automatically.

## 7. Tag and release v1.0.0

```bash
git tag -a v1.0.0 -m "Initial release of the Hele-Shaw cells example"
git push origin v1.0.0
```

The tag push triggers `.github/workflows/run-benchmark.yml`'s
`rohub-upload` job. If you've configured Zenodo (step 6), go to
GitHub → Releases → Draft a new release → choose v1.0.0 → publish. Zenodo
will mint the DOI within a few minutes.
