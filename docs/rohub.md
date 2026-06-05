# Using RoHub with the Hele-Shaw benchmark

This is the Hele-Shaw-flavoured counterpart of the platform's
[RoHub guide](../NFDI4IngModelValidationPlatform/docs/rohub.md). It
covers the four steps you actually need for this benchmark: install the
opt-in env, log in, upload the per-configuration
`solution_field_data.zip`, and pull `phase1_volume_fraction` back out of
the ROHub SPARQL endpoint.

The ROHub Python API lives at
[gitlab.pcss.pl/daisd-public/rohub/rohub-api](https://gitlab.pcss.pl/daisd-public/rohub/rohub-api).
A Dev account is at [rohub2020-devel.apps.paas-dev.psnc.pl](https://rohub2020-devel.apps.paas-dev.psnc.pl/);
Prod at [www.rohub.org](https://www.rohub.org/). The two endpoints use
**separate accounts** — pick one and stick to it for the duration of a
campaign.

## Setup

The Hele-Shaw benchmark ships its own opt-in conda environment so you
don't pull `rohub` into the simulation env. Create it once:

```bash
mamba env create -n hs-rohub -f openfoam/environment_rohub.yml
mamba activate hs-rohub
```

`environment_rohub.yml` is a thin wrapper: `python>=3.10`, `sparqlwrapper`,
plus the `rohub-api` package installed editable from the `develop` branch.
Activate `hs-rohub` for every step below.

## Login

Credentials are read from env vars so the same code works in CI:

```bash
export ROHUB_USERNAME=...
export ROHUB_PASSWORD=...
```

> **Note on dev vs prod credentials.** The username/password you set
> here must belong to the endpoint you intend to upload to. The
> `--endpoint dev` (default) and `--endpoint prod` choices toggle
> between two completely separate Keycloak realms; cross-endpoint logins
> fail with `401`.

There is no separate "set endpoint" step: the upload script
(`openfoam/upload_to_rohub.py`) does that for you. If you want to drive
the API from a notebook, mirror the endpoint switch in Cell 2 of
`notebooks/RoCrate.ipynb` (`rohub.settings.API_URL = ...`,
`KEYCLOAK_URL = ...`, `KEYCLOAK_CLIENT_ID = ...`, `SPARQL_ENDPOINT = ...`).

## Uploading research objects

The benchmark produces one `solution_field_data.zip` per configuration,
each containing a hand-rolled `ro-crate-metadata.json` (see
`openfoam/ro_crate.py`). Upload them one at a time:

```python
import os
import rohub

rohub.settings.API_URL = "https://rohub2020-devel.apps.paas-dev.psnc.pl/api/"
rohub.settings.KEYCLOAK_CLIENT_ID = "rohub2020-cli"
rohub.settings.KEYCLOAK_CLIENT_SECRET = "714617a7-87bc-4a88-8682-5f9c2f60337d"
rohub.settings.KEYCLOAK_URL = (
    "https://keycloak-dev.apps.paas-dev.psnc.pl/auth/realms/rohub/"
    "protocol/openid-connect/token"
)
rohub.settings.SPARQL_ENDPOINT = "https://virtuoso-rohub2020-devel.apps.bst2.paas.psnc.pl/sparql"

rohub.login(username=os.environ["ROHUB_USERNAME"], password=os.environ["ROHUB_PASSWORD"])
ro = rohub.ros_upload(path_to_zip="results/1/solution_field_data.zip")
print(f"UUID: {ro.identifier}  (https://w3id.org/ro-id-dev/{ro.identifier})")
```

The returned `ro.identifier` is a UUID. For dev uploads the public URL
is `https://w3id.org/ro-id-dev/<UUID>`; for prod it's
`https://w3id.org/ro-id/<UUID>`. Record the UUIDs in
`results/rohub_uuids.json` so the SPARQL step below can find them.

## Accessing via SPARQL

The Hele-Shaw RO-Crate is generic 1.1 — there is no `m4i:` ontology
involved (see [Note on `m4i:`](#note-on-m4i) below). The metrics live
inside `solution_metrics.json` as plain JSON, not as standalone RDF
triples. To extract `phase1_volume_fraction` for one uploaded research
object, walk the Dataset → `hasPart` → `solution_metrics.json` chain,
then read the metrics JSON. In practice the simplest working query
finds the named graph first, then queries the metrics file's value
node:

### Parameterized template (paste into the ROHub SPARQL UI)

Replace `%UUID%` with the UUID returned by `ros_upload`.

```sparql
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?metric_label ?metric_value ?metric_unit
WHERE {
  # ---- Input UUID ----
  VALUES ?uuid { "%UUID%" }

  # ---- Construct the full Dataset IRI from UUID ----
  BIND(IRI(CONCAT("https://w3id.org/ro-id-dev/", ?uuid)) AS ?dataset)

  # ---- Find which graph contains the Dataset ----
  {
    SELECT ?g WHERE {
      GRAPH ?g { ?dataset a schema:Dataset . }
    }
  }

  # ---- Read metrics from the solution_metrics.json file inside the crate ----
  GRAPH ?g {
    ?dataset schema:hasPart ?metrics_file .
    ?metrics_file a schema:File ;
                  schema:name "solution_metrics.json" .

    # The metrics file itself is a File entity; the actual value triples
    # hang off it via schema:value on a PropertyValue-shaped node.
    ?metrics_file schema:value ?metric_value .
    ?value_node rdfs:label ?metric_label .
    OPTIONAL { ?value_node schema:unitCode ?metric_unit . }
  }
}
ORDER BY ?metric_label
```

> **A note on the walk.** The Hele-Shaw crate is intentionally minimal:
> the `phase1_volume_fraction` is the `schema:value` of a node whose
> `rdfs:label` is the metric name. The exact predicate shape depends
> on the version of `ro_crate.py` you're using — if a future rev
> switches to a dedicated `schema:PropertyValue` node, replace
> `?metrics_file schema:value ?metric_value` with
> `?pv a schema:PropertyValue ; rdfs:label ?metric_label ;
> schema:value ?metric_value .` and add `?pv` to the `?metrics_file`
> connection via `schema:hasPart`.

### Python form using `SPARQLWrapper`

```python
import os
from SPARQLWrapper import SPARQLWrapper, JSON

SPARQL = SPARQLWrapper("https://virtuoso-rohub2020-devel.apps.bst2.paas.psnc.pl/sparql")

uuid = "YOUR-UUID-HERE"  # from rohub.ros_upload(...).identifier
dataset_iri = f"https://w3id.org/ro-id-dev/{uuid}"

query = f"""
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?metric_label ?metric_value WHERE {{
  GRAPH ?g {{ <{dataset_iri}> a schema:Dataset . }}
  GRAPH ?g {{
    <{dataset_iri}> schema:hasPart ?metrics_file .
    ?metrics_file a schema:File ; schema:name "solution_metrics.json" ;
                  schema:value ?metric_value .
    ?value_node rdfs:label ?metric_label .
  }}
}}
"""
SPARQL.setQuery(query)
SPARQL.setReturnFormat(JSON)
for row in SPARQL.query().convert()["results"]["bindings"]:
    print(row["metric_label"]["value"], "=", row["metric_value"]["value"])
```

## Sample results

The three Hele-Shaw configurations vary the mesh resolution
(`NPA = NPZ`) and the inlet flow rate. Typical `phase1_volume_fraction`
values (endTime = 15.0 s) for the dev endpoint are:

| configuration | phase1_volume_fraction | NPA | flow_rate_m3_s | uuid |
|---|---|---|---|---|
| 1 | ~0.21 | 60 | 4e-07 | *(filled in by upload_to_rohub.py)* |
| 2 | ~0.22 | 80 | 4e-07 | *(filled in by upload_to_rohub.py)* |
| 3 | ~0.30 | 60 | 8e-07 | *(filled in by upload_to_rohub.py)* |

Convergence behaviour: configurations 1 and 2 share the same flow rate
but config 2 has a finer mesh (NPA = NPZ = 80), so the volume fraction
should agree to within mesh discretisation error. Configuration 3
doubles the flow rate at the same mesh resolution as config 1, so
`phase1_volume_fraction` is visibly higher.

## Note on `m4i:`

The plate benchmark (`linear-elastic-plate-with-hole`) uses the
`metadata4ing` Snakemake reporter plugin, which writes its provenance
into the RO-Crate with `m4i:`-namespaced predicates
(`m4i:hasParameter`, `m4i:implementedByTool`, …). The Hele-Shaw
benchmark does **not** depend on that plugin — its `ro-crate-metadata.json`
is a small, generic RO-Crate 1.1 document with `schema:value` for the
metrics. The SPARQL queries above are written for the Hele-Shaw shape;
they will return empty results against a `m4i:`-namespaced crate. A
follow-up may unify the two crates; until then, use the platform's
[rohub.md](../NFDI4IngModelValidationPlatform/docs/rohub.md) for the
plate benchmark and this file for the Hele-Shaw benchmark.

## Programmatic upload

For CI / cron use, prefer `openfoam/upload_to_rohub.py` over the
notebook. It walks `--results-dir` for `<cfg>/solution_field_data.zip`,
uploads each in turn, and writes a `{cfg: uuid}` mapping to
`--output`:

```bash
python openfoam/upload_to_rohub.py \
    --results-dir results/ \
    --endpoint dev \
    --output results/rohub_uuids.json
```

The script is a soft-skip citizen: if `ROHUB_USERNAME` /
`ROHUB_PASSWORD` are unset, it prints a notice to stderr and exits 0,
so a CI job without credentials can still validate that the rest of
the pipeline succeeded. Exit code is 0 if every config uploads, 1 if
at least one upload fails, and 2 for argument errors (e.g. results-dir
not found).

## Troubleshooting

- **Login fails with 401**: Check `ROHUB_USERNAME` and `ROHUB_PASSWORD`
  match the endpoint you passed to `--endpoint`. The default is `dev`.
- **Upload fails with RO-Crate validation error**: Open
  `ro-crate-metadata.json` inside the offending zip and check that all
  `@id` values are valid URIs (no leading spaces, no special characters).
- **SPARQL returns no results**: The named graph may not be public yet.
  Wait a few minutes after upload and re-run.
- **Re-running on a fresh results tree**: Just re-run the upload step.
  The UUIDs are persisted in `--output` for reference.
