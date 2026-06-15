# chEMBL_tools
Tools for retrieving chEMBL data and filtering

## Setup

### Using Anaconda

This project uses Conda for environment management. To set up the environment:

1. **Create the environment from environment.yml:**
   ```bash
   conda env create -f environment.yml
   ```

2. **Activate the environment:**
   ```bash
   conda activate chembl_tools
   ```

3. **Deactivate the environment (when done):**
   ```bash
   conda deactivate
   ```

### Requirements

- Python 3.10
- matplotlib
- rdkit
- pandas
- scikit-learn
- sqlite3 (built-in)
- tqdm
- molbloom
- numpy
- pyyaml
- biopython
- PyQt5
