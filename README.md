# chEMBL_tools

Tools for querying the ChEMBL database, filtering compounds by physicochemical and bioactivity properties, selecting diverse subsets, and generating Boltz-2 structure prediction inputs.

## Features

- **Compound Search** — filter by MW, LogP, one or more target names, IC50/EC50/Ki (nM) and purchasability against a local ChEMBL SQLite database; multi-target results include a `Matched Targets` column
- **Diversity Filtering** — K-means, GMM, or Butina (Tanimoto threshold) clustering; fast automatic class estimation via coarse-to-fine MiniBatchKMeans sweep on a subsample; centroid-near random sampling or tightness representatives; pre/post tSNE visualisation
- **CSV Export** — enriched output including target names, UniProt accessions, and best activity values
- **Boltz-2 YAML Export** — generate per-compound YAML inputs (affinity or template mode) distributed across subdirectories
- **MSA Generation** — query the ColabFold API to generate `.a3m` MSA files, or load a pre-computed one

## Setup

### 1. Download ChEMBL SQLite database

Download the ChEMBL 37 SQLite release from [https://chembl.gitbook.io/chembl-interface-documentation/downloads](https://chembl.gitbook.io/chembl-interface-documentation/downloads) and unpack it:

```
chembl_37/
└── chembl_37_sqlite/
    └── chembl_37.db
```

### 2. Create the Conda environment

```bash
conda env create -f environment.yml
conda activate chembl_tools
```

### 3. Run the application

```bash
python chembl_app/main.py
```

On first launch a settings dialog will prompt you to locate `chembl_37.db`. The path is saved for future sessions.

## Usage

### Tab 1 — Search

Set MW range, LogP range, and optional activity thresholds (IC50/EC50/Ki in nM).

**Target field** accepts a single target or multiple comma-separated targets (e.g. `EGFR, BRAF, CDK2`). Compounds active against any of the listed targets are returned. When multiple targets are given, a **Matched Targets** column in the results table shows which search terms each compound matched. Autocomplete is available for each token — type a target name, select from the dropdown, then add a comma to enter the next target.

Click **Search** to query the database. Results appear in the table and tSNE/PCA plots coloured by cluster are rendered automatically.

### Tab 2 — Diversity Filter

Choose a **Clustering Algorithm**:

- **K-means** — standard centroid-based clustering; specify the number of classes manually or let auto-estimation find it.
- **GMM** (Gaussian Mixture) — soft-assignment clustering; auto-estimation supported.
- **Butina** (Tanimoto threshold) — sphere-exclusion clustering based on pairwise Tanimoto distances. Set the **Distance cutoff** (0–1; default 0.4): compounds within this distance of a cluster center are merged into the same cluster. The number of clusters is determined automatically from the cutoff; the Class Estimation panel is hidden for this algorithm.

When **K-means** or **GMM** is selected with **Estimate class count automatically**, the sweep runs on a random subsample (≤ 2 000 compounds) using a coarse-to-fine MiniBatchKMeans search, making estimation fast even for large result sets. The final clustering always uses the full dataset.

Choose either **centroid-near random sampling** or **tightness representatives**, then click **Run Diversity** to generate a filtered set and inspect pre/post tSNE views. Curated diversity results are used for export and YAML when active.

### Tab 3 — Boltz-2 YAML Export

1. Paste or load a protein sequence (FASTA).
2. Browse to an existing `.a3m` MSA file, or click **Query ColabFold** to generate one automatically.
3. Choose **Affinity** or **Template** mode, set the output directory, and click **Generate YAML Files**.

## Project structure

```
chembl_app/
├── main.py                        # Entry point
├── app/
│   ├── main_window.py             # QMainWindow, signal wiring
│   ├── tabs/                      # search_tab, diversity_tab, boltz_tab
│   ├── dialogs/settings_dialog.py # DB path (persisted via QSettings)
│   └── widgets/                   # tsne_canvas, results_table
├── core/
│   ├── db/                        # SQL queries (property, target, activity, export)
│   ├── chemistry/                 # Fingerprints, tSNE, K-means/GMM/Butina clustering
│   ├── io/                        # FASTA reader, YAML generator, CSV exporter
│   └── msa/                       # ColabFold REST API client
├── workers/                       # QThread workers (search, diversity, yaml, msa)
└── models/                        # AppState dataclass, QAbstractTableModel
```

## Dependencies

| Package | Source |
|---------|--------|
| Python 3.10 | conda |
| rdkit | conda-forge |
| pandas, numpy, matplotlib, seaborn | conda-forge |
| scikit-learn | conda-forge |
| hdbscan | conda-forge |
| umap-learn | conda-forge |
| pyyaml, biopython, tqdm | conda-forge |
| requests | conda-forge |
| PyQt5, molbloom | pip |

## Troubleshooting

If `run_umap` fails with an import error (for example `cannot import name UMAP`), install UMAP in the active environment:

```bash
conda install -c conda-forge umap-learn
```

If the environment already existed before this dependency was added, run:

```bash
conda env update -f environment.yml --prune
```

If HDBSCAN-based auto-class estimation is selected in the Diversity tab and dependencies are missing, update the environment with the same command above.
