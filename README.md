# chEMBL_tools

Tools for querying the ChEMBL database, filtering compounds by physicochemical and bioactivity properties, selecting diverse subsets, and generating Boltz-2 structure prediction inputs.

## Features

- **Compound Search** — filter by MW, LogP, target name, IC50/EC50/Ki (nM) and purchasability against a local ChEMBL SQLite database
- **Diversity Filtering** — K-means or GMM clustering with tunable tightness quantile; interactive tSNE visualisation
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

Set MW range, LogP range, an optional target keyword (e.g. `EGFR`), and optional maximum activity values (IC50/EC50/Ki in nM). Click **Search** to query the database. Results appear in the table and a tSNE plot coloured by cluster is rendered automatically.

### Tab 2 — Diversity Filter

Choose K-means or GMM, set the number of clusters and tightness quantile, then click **Run Clustering**. The tightest clusters are collapsed to one representative each; all other compounds are kept. Click **Export Filtered Results as CSV** to save a file that includes target names, UniProt accessions, and best activity values.

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
│   ├── chemistry/                 # Fingerprints, tSNE, K-means/GMM clustering
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
| pyyaml, biopython, tqdm | conda-forge |
| requests | conda-forge |
| PyQt5, molbloom | pip |
