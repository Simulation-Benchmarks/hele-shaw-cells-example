# Zenodo release

The v1.0.0 GitHub release is published:
https://github.com/Simulation-Benchmarks/hele-shaw-cells-example/releases/tag/v1.0.0

To mint a Zenodo DOI, do one of the following:

## Option A: GitHub-Zenodo integration (recommended)

1. Go to https://zenodo.org/ and sign in (create an account if needed).
2. Link your GitHub account: Settings → GitHub → enable.
3. In the same Settings page, flip the toggle next to
   `Simulation-Benchmarks/hele-shaw-cells-example` to **On**.
4. Zenodo's webhook will fire on the next GitHub release publish (a
   `release` event from a tagged commit). For the v1.0.0 release that
   was published before enabling, click **"Publish"** again on the
   v1.0.0 release page (or push a `v1.0.1` tag) to retrigger the
   webhook. Zenodo will mint a DOI like `10.5281/zenodo.XXXXXXX`
   within a few minutes.

## Option B: Mint the DOI directly via the Zenodo REST API

1. Generate a Zenodo personal access token at
   https://zenodo.org/account/settings/applications/tokens/new/.
2. Create a new deposition via the API and upload the release tarball:

   ```bash
   curl -H "Authorization: Bearer $ZENODO_TOKEN" \
        -X POST https://zenodo.org/api/deposit/depositions \
        -H "Content-Type: application/json" \
        -d '{"metadata": {"title": "hele-shaw-cells-example v1.0.0", ...}}'
   ```

3. Upload the files via the deposition's bucket URL.
4. Publish the deposition; Zenodo returns the DOI.

## Verifying the DOI

After Zenodo mints the DOI, it will appear:
- In the GitHub release page sidebar (as a badge "DOI: 10.5281/...").
- In the rightmost column of the repo's GitHub page.
- Searchable at https://zenodo.org/search?q=metadata.title%3A%22hele-shaw-cells-example%22.

When the DOI is available, add it to `README.md` and to the
[`CITATION.cff`](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)
file (creating one if it doesn't exist).
