import io
import os
import tempfile
import warnings
import pandas as pd
import streamlit as st

warnings.filterwarnings("ignore")
st.set_page_config(page_title="DEAL File", page_icon="📂", layout="wide")

# -------- Constants --------
PREVIEW_ROWS = 1000


# -------- Utility: save uploaded file to temp path --------
def _to_tempfile(uploaded) -> str | None:
    if not uploaded:
        return None
    suffix = os.path.splitext(uploaded.name)[1].lower()
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded.getvalue())
    return path


# -------- Cached Readers (by path) --------
@st.cache_data(show_spinner=False)
def _read_csv_preview_path(path: str, skiprows: int = 0, nrows: int = PREVIEW_ROWS):
    try:
        return pd.read_csv(path, skiprows=skiprows, nrows=nrows)
    except Exception:
        return pd.read_csv(path, skiprows=skiprows).head(nrows)


@st.cache_data(show_spinner=False)
def _read_excel_preview_path(path: str, skiprows: int = 0, nrows: int = PREVIEW_ROWS, sheet_name=0):
    try:
        return pd.read_excel(path, skiprows=skiprows, nrows=nrows, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.read_excel(path, skiprows=skiprows, sheet_name=sheet_name, engine="openpyxl").head(nrows)


@st.cache_data(show_spinner=False)
def _read_csv_full_path(path: str, skiprows: int = 0, usecols=None, dtype_backend="pyarrow"):
    try:
        return pd.read_csv(path, skiprows=skiprows, usecols=usecols, dtype_backend=dtype_backend)
    except TypeError:
        # For older pandas without dtype_backend
        return pd.read_csv(path, skiprows=skiprows, usecols=usecols)


@st.cache_data(show_spinner=False)
def _read_excel_full_path(path: str, skiprows: int = 0, sheet_name=0, usecols=None, dtype_backend="pyarrow"):
    try:
        return pd.read_excel(
            path,
            skiprows=skiprows,
            sheet_name=sheet_name,
            usecols=usecols,
            engine="openpyxl",
            dtype_backend=dtype_backend,
        )
    except TypeError:
        return pd.read_excel(path, skiprows=skiprows, sheet_name=sheet_name, usecols=usecols, engine="openpyxl")


@st.cache_data(show_spinner=False)
def _get_excel_sheet_names(path: str):
    try:
        import openpyxl  # ensure engine availability
        xls = pd.ExcelFile(path, engine="openpyxl")
        return xls.sheet_names
    except Exception:
        return [0]


def _safe_cols(df):
    return [str(c) for c in df.columns]


# -------- Sidebar: Upload (no manual sheet/column picks for loading) --------
st.sidebar.header("Upload Files")
file1 = st.sidebar.file_uploader("First File", type=["csv", "xlsx", "xls"], key="file1")
skip1 = st.sidebar.number_input("Skip rows (File 1)", 0, 100000, 0, 1)
file2 = st.sidebar.file_uploader("Second File", type=["csv", "xlsx", "xls"], key="file2")
skip2 = st.sidebar.number_input("Skip rows (File 2)", 0, 100000, 0, 1)

# Always use first sheet for Excel
sheet1 = 0
sheet2 = 0

path1 = _to_tempfile(file1) if file1 else None
path2 = _to_tempfile(file2) if file2 else None

# -------- VLOOKUP Toggle (button retained) --------
if "show_vlookup" not in st.session_state:
    st.session_state.show_vlookup = False

_, ctrl_right = st.columns([0.7, 0.3])
with ctrl_right:
    if st.button("🔍 VLOOKUP"):
        st.session_state.show_vlookup = not st.session_state.show_vlookup

# -------- Title --------
st.title("📂 File Viewer")

# -------- Previews --------
df1_prev, df2_prev = None, None
if path1:
    if file1.name.lower().endswith((".csv", ".csv.gz", ".csv.zip")):
        df1_prev = _read_csv_preview_path(path1, skip1, PREVIEW_ROWS)
    else:
        df1_prev = _read_excel_preview_path(path1, skip1, PREVIEW_ROWS, sheet1)

if path2:
    if file2.name.lower().endswith((".csv", ".csv.gz", ".csv.zip")):
        df2_prev = _read_csv_preview_path(path2, skip2, PREVIEW_ROWS)
    else:
        df2_prev = _read_excel_preview_path(path2, skip2, PREVIEW_ROWS, sheet2)

c1, c2 = st.columns(2)
if isinstance(df1_prev, pd.DataFrame):
    with c1:
        st.markdown(f"### 📄 File 1: `{file1.name}` (skip {skip1})")
        st.dataframe(df1_prev, use_container_width=True, height=420)

if isinstance(df2_prev, pd.DataFrame):
    with c2:
        st.markdown(f"### 📄 File 2: `{file2.name}` (skip {skip2})")
        st.dataframe(df2_prev, use_container_width=True, height=420)

# -------- Always load FULL files immediately after upload --------
df1_full, df2_full = None, None
if path1 or path2:
    with st.spinner("Loading full datasets..."):
        if path1:
            if file1.name.lower().endswith((".csv", ".csv.gz", ".csv.zip")):
                df1_full = _read_csv_full_path(path1, skip1, usecols=None)
            else:
                df1_full = _read_excel_full_path(path1, skip1, sheet1, usecols=None)

        if path2:
            if file2.name.lower().endswith((".csv", ".csv.gz", ".csv.zip")):
                df2_full = _read_csv_full_path(path2, skip2, usecols=None)
            else:
                df2_full = _read_excel_full_path(path2, skip2, sheet2, usecols=None)

    if isinstance(df1_full, pd.DataFrame):
        st.success(f"Loaded File 1 with {len(df1_full):,} rows and {len(df1_full.columns)} columns.")
    if isinstance(df2_full, pd.DataFrame):
        st.success(f"Loaded File 2 with {len(df2_full):,} rows and {len(df2_full.columns)} columns.")

# -------- VLOOKUP Logic (manual trigger via button preserved) --------
if st.session_state.show_vlookup:
    st.markdown("---")
    st.subheader("🔍 VLOOKUP (File 2 → File 1)")

    if not (path1 and path2):
        st.info("Upload both files first to use VLOOKUP.")
    else:
        if isinstance(df1_full, pd.DataFrame) and isinstance(df2_full, pd.DataFrame):
            cols1, cols2 = _safe_cols(df1_full), _safe_cols(df2_full)

            with st.form("vlookup_form", clear_on_submit=False):
                a, b, c = st.columns(3)
                with a:
                    left_key = st.selectbox("Key column in File 1", options=cols1)
                with b:
                    right_key = st.selectbox("Key column in File 2", options=cols2)
                with c:
                    fetch_cols = st.multiselect(
                        "Columns to bring from File 2",
                        options=[col for col in cols2 if col != right_key],
                    )
                stream_mode = st.toggle(
                    "Stream mode (very large CSVs)",
                    value=False,
                    help="Processes File 1 in chunks; only works if File 1 is CSV.",
                )
                run = st.form_submit_button("Apply VLOOKUP")

            if run:
                try:
                    if stream_mode and file1.name.lower().endswith((".csv", ".csv.gz", ".csv.zip")):
                        tmp_path = vlookup_stream_csv( # type: ignore
                            path1, path2, left_key, right_key, fetch_cols, skip1, skip2
                        )
                        with open(tmp_path, "rb") as f:
                            data = f.read()
                        st.success("Streamed VLOOKUP complete.")
                        st.download_button(
                            "⬇️ Download VLOOKUP Result (CSV)",
                            data=data,
                            file_name="vlookup_result.csv",
                            mime="text/csv",
                        )
                    else:
                        # Ensure both keys are strings to avoid dtype mismatch (int64 vs string)
                        right = df2_full.drop_duplicates(subset=[right_key], keep="first").copy()
                        right[right_key] = right[right_key].astype(str)
                        right = right.set_index(right_key)

                        out = df1_full.copy()
                        out[left_key] = out[left_key].astype(str)

                        for col in fetch_cols:
                            out[col] = out[left_key].map(right[col])

                        st.dataframe(out.head(PREVIEW_ROWS), use_container_width=True, height=440)
                        csv = out.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            "⬇️ Download VLOOKUP Result (CSV)",
                            data=csv,
                            file_name="vlookup_result.csv",
                            mime="text/csv",
                        )
                except Exception as e:
                    st.error(f"VLOOKUP failed: {e}")


# -------- Streaming helper for very large CSVs (with safe key casting) --------
def vlookup_stream_csv(
    path_file1, path_file2, left_key, right_key, fetch_cols, skip1=0, skip2=0, chunk=200_000
):
    # Build right-side dicts once (keys as string)
    right = pd.read_csv(path_file2, skiprows=skip2)
    if right_key not in right.columns:
        raise KeyError(f"Key `{right_key}` not found in File 2.")
    right[right_key] = right[right_key].astype(str)
    right = right.drop_duplicates(subset=[right_key], keep="first").set_index(right_key)
    maps = {col: right[col].to_dict() for col in fetch_cols}

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    os.close(tmp_fd)
    first = True

    for chunk_df in pd.read_csv(path_file1, skiprows=skip1, chunksize=chunk):
        if left_key not in chunk_df.columns:
            raise KeyError(f"Key `{left_key}` not found in File 1 chunk.")
        chunk_df[left_key] = chunk_df[left_key].astype(str)
        for col in fetch_cols:
            chunk_df[col] = chunk_df[left_key].map(maps[col])
        chunk_df.to_csv(
            tmp_path, index=False, mode="w" if first else "a", header=first, encoding="utf-8-sig"
        )
        first = False

    return tmp_path
