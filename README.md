# DEAL File Streamlit App

A Streamlit app to preview large CSV/XLSX files and perform Excel-like VLOOKUP between two files.
Optimized for big files with temp-file reads, optional column selection, and a streamed mode for huge CSVs.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push this folder to GitHub
2. Go to https://share.streamlit.io
3. New App → pick repo/branch → file: `app.py` → Deploy

## Notes
- Max upload size is set to 500 MB in `.streamlit/config.toml` (subject to platform limits).
- For very large CSVs, enable **Stream mode** inside the VLOOKUP form.