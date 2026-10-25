# Inspect saved Hele-Shaw results on NFDI4Ing

Use the [NFDI4Ing Jupyter Service](https://jupyter.nfdi4ing.de/) to inspect
configuration parameters, saved simulation results and reference regression
checks in one executable notebook. The five notebook sections use repository
artifacts and produce tables and figures. They do not start OpenFOAM, build a
container or run a new simulation.

The [saved notebook view](https://simulation-benchmarks.github.io/hele-shaw-cells-example/notebooks/inspect_results.html) can be read without
an account. To execute the notebook, sign in and prepare your own repository
copy once. The launch link opens a file on **your own Jupyter server**; it does
not copy the repository or open another person's session.

## Prepare your workspace once

1. [Sign in with your institution](https://jhublogin-nfdi.tik.uni-stuttgart.de/login)
   and start the Python datascience environment. The notebook uses NumPy, Pandas
   and Matplotlib, which are available in the verified environment. The service
   is [free for academic use](https://jupyter.nfdi4ing.de/terms_of_use/).
2. Open a JupyterLab terminal and clone the `main` branch of the
   [public repository](https://github.com/Simulation-Benchmarks/hele-shaw-cells-example)
   into the service's persistent `~/work` directory:

   ```sh
   mkdir -p "$HOME/work"
   cd "$HOME/work"
   if [ -e hele-shaw-cells-example ] || [ -L hele-shaw-cells-example ]; then
     printf '%s\n' 'The folder already exists; keep it and inspect its contents before updating.'
   else
     git clone --branch main --single-branch https://github.com/Simulation-Benchmarks/hele-shaw-cells-example.git hele-shaw-cells-example
   fi
   ```

   An existing folder is left untouched. If you already have a clone, inspect
   its branch and local changes before updating it. Keep your work; do not
   replace the folder with another clone. The notebook needs its inputs and
   repository code at their original paths.
3. Open
   `work/hele-shaw-cells-example/docs/semantic/notebooks/inspect_results.ipynb`
   and select its Python kernel. Run all five code cells in order. They verify
   their input files before reading them. The expected saved results, including
   missing values, are explained beside the code.
4. If the selected kernel lacks a dependency, install only the inspection
   requirements from a temporary notebook cell, then restart the kernel:

   ```python
   %pip install -r requirements-jupyter.txt
   ```

   `%pip` installs into the notebook's kernel environment. The full semantic-site
   build requirements are unnecessary for this inspection workflow.

You can also [download the notebook](https://simulation-benchmarks.github.io/hele-shaw-cells-example/notebooks/inspect_results.ipynb), but that
file alone is not a complete execution package. Keep it at the path above in a
repository copy so its parameter files, saved evidence and reader code remain
available. The original `notebooks/Simulation_Walkthrough.ipynb` is a separate
simulation walkthrough; this service workflow uses `inspect_results.ipynb`.

## Open the workflow's notebook sections

The shareable destination is:

```text
https://jupyter-nfdi.tik.uni-stuttgart.de/hub/user-redirect/lab/workspaces/hele-shaw-inspection/tree/work/hele-shaw-cells-example/docs/semantic/notebooks/inspect_results.ipynb
```

JupyterHub's [`/hub/user-redirect/` route](https://jupyterhub.readthedocs.io/en/stable/faq/faq.html#how-do-i-share-links-to-notebooks)
directs each visitor to their own server. Every visitor must first place the
repository at the same path. Public repository access does not provide access
to someone else's Jupyter server. These links do not automatically clone or
update files.

The five workflow section links append `?#heading-anchor` to that destination,
following [JupyterLab's documented heading-link format](https://jupyterlab.readthedocs.io/en/stable/user/urls.html#linking-notebook-sections).
Exact anchors are recorded in `data/python-inspection-manifest.json`. Links use
the dedicated `hele-shaw-inspection` workspace in the same browser tab; use
browser Back to return to the workflow (the Hub redirect can require two Back
actions). In a narrow window, collapse the file
browser for more notebook space; the notebook Contents also links to every
section. Keep that workspace in one tab:
JupyterLab can clone duplicate workspaces, which can lose heading destinations.

When launch verification is incomplete, the site keeps the saved reading view
and setup guide available. An active launch destination is a tested path, not
evidence that every visitor has completed the first-use setup.

## Verify or update a launch destination

Maintainers should verify the exact source notebook in an authenticated Hub
session before enabling launch links. The repository notebook's SHA-256 is the
identity of the tested input. Executing it on the Hub may change that copy's
saved outputs or metadata; record the source hash before execution and retain
the execution evidence separately.

1. Prepare the current repository notebook and inputs on the Hub, preserving
   existing user files. Run its five code cells with no error outputs. Record
   the Python, NumPy, Pandas and Matplotlib versions and the actual execution
   counts. Confirm that no simulation was executed.
2. Open the notebook destination and each of the five section links through
   the workflow in the same tab. After JupyterLab finishes loading, check that
   each expected heading is visible. Record what was checked and the date.
3. Create `jupyter-validation.json` from the following shape, replacing the
   placeholders with the observed evidence. Keep the exact anchors in the same
   order as the inspection manifest:

   ```json
   {
     "verifiedOn": "YYYY-MM-DD",
     "notebookPath": "work/hele-shaw-cells-example/docs/semantic/notebooks/inspect_results.ipynb",
     "sourceNotebookSha256": "SHA256_OF_THE_TESTED_REPOSITORY_NOTEBOOK",
     "runtime": {
       "python": "OBSERVED_VERSION",
       "numpy": "OBSERVED_VERSION",
       "pandas": "OBSERVED_VERSION",
       "matplotlib": "OBSERVED_VERSION"
     },
     "execution": {
       "codeCellCounts": [1, 2, 3, 4, 5],
       "errorOutputs": 0,
       "simulationExecuted": false
     },
     "navigation": {
       "workspace": "hele-shaw-inspection",
       "target": "_self",
       "method": "DESCRIBE_THE_AUTHENTICATED_WORKFLOW_AND_HEADING_CHECKS",
       "sectionsVerified": [
         "1.-Locate-and-verify-sources",
         "2.-Inspect-the-parameter-sweep",
         "3.-Read-saved-results-and-missing-values",
         "4.-Check-reference-regression",
         "5.-Compare-recorded-outcomes-and-figures"
       ]
     }
   }
   ```

   The example execution counts apply to a freshly restarted kernel. Record
   the observed positive, increasing counts when a kernel already had a history.
   Additional evidence, such as source revisions or output checks, can be stored
   alongside these required fields. The verification file must describe actual
   checks, not planned checks.
4. Set `notebookUrl` in `jupyter.json` to the shareable destination above and
   `verifiedNotebookSha256` to the same tested source hash. The URL must have
   no query or fragment. Rebuild and check the site:

   ```sh
   python docs/semantic/tools/build_site.py --output-dir _site
   python -m unittest discover -s docs/semantic/tests -p 'test_*.py'
   ```

`tools/jupyter_service.py` rejects a changed notebook hash, missing runtime or
execution evidence, and incomplete or changed heading checks. Changing the
notebook requires verifying the new copy on the Hub before enabling its links.
Set `notebookUrl` to `null` to keep the saved-view links while verification is
pending. No account identifier or credential belongs in these configuration
files.
