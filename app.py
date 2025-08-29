import io
import warnings
import pandas as pd
import streamlit as st

warnings.filterwarnings("ignore")
st.set_page_config(page_title="DEAL File", page_icon="📂", layout="wide")

# -------- Constants --------
PREVIEW_ROWS = 1000

# -------- Helpers to make DataFrames Arrow-safe for st.dataframe --------
def _arrow_safe_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Drop index-like Unnamed columns and fix mixed-type object columns to avoid PyArrow errors."""
    if df is None or not isinstance(df, pd.DataFrame):
        return df
    out = df.copy()

    # 1) Drop 'Unnamed:*' columns (common when Excel index is saved)
    cols = pd.Index([str(c) for c in out.columns])
    mask = ~cols.str.match(r"^Unnamed(:\s*\d+)?$")
    out = out.loc[:, mask]
    out.columns = [str(c) for c in out.columns]

    # 2) For object columns with mixed Python types, cast to string
    for c in out.columns:
        if pd.api.types.is_object_dtype(out[c]):
            # If column contains mixed types (e.g., int + str), cast to str
            try:
                if out[c].map(type).nunique(dropna=False) > 1:
                    out[c] = out[c].astype(str)
            except Exception:
                # Fallback: still coerce to string
                out[c] = out[c].astype(str)

    return out


# -------- Cached Readers --------
@st.cache_data(show_spinner=False)
def _read_csv_preview(content_bytes: bytes, skiprows: int = 0, nrows: int = PREVIEW_ROWS):
    buf = io.BytesIO(content_bytes)
    try:
        return pd.read_csv(buf, skiprows=skiprows, nrows=nrows)
    except Exception:
        buf.seek(0)
        return pd.read_csv(buf, skiprows=skiprows).head(nrows)


@st.cache_data(show_spinner=False)
def _read_excel_preview(content_bytes: bytes, skiprows: int = 0, nrows: int = PREVIEW_ROWS, sheet_name=0):
    buf = io.BytesIO(content_bytes)
    try:
        return pd.read_excel(buf, skiprows=skiprows, nrows=nrows, sheet_name=sheet_name)
    except Exception:
        buf.seek(0)
        return pd.read_excel(buf, skiprows=skiprows, sheet_name=sheet_name).head(nrows)


@st.cache_data(show_spinner=False)
def _read_csv_full(content_bytes: bytes, skiprows: int = 0):
    buf = io.BytesIO(content_bytes)
    return pd.read_csv(buf, skiprows=skiprows)


@st.cache_data(show_spinner=False)
def _read_excel_full(content_bytes: bytes, skiprows: int = 0, sheet_name=0):
    buf = io.BytesIO(content_bytes)
    return pd.read_excel(buf, skiprows=skiprows, sheet_name=sheet_name)


def _file_to_bytes(uploaded):
    return uploaded.getvalue() if uploaded else None


def _read_preview(uploaded, skiprows=0):
    if not uploaded:
        return None
    data = _file_to_bytes(uploaded)
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return _read_csv_preview(data, skiprows=skiprows, nrows=PREVIEW_ROWS)
    return _read_excel_preview(data, skiprows=skiprows, nrows=PREVIEW_ROWS)


def _read_full(uploaded, skiprows=0):
    if not uploaded:
        return None
    data = _file_to_bytes(uploaded)
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return _read_csv_full(data, skiprows=skiprows)
    return _read_excel_full(data, skiprows=skiprows)


def _safe_cols(df):
    return [str(c) for c in df.columns]


# -------- Sidebar: Upload (needed before VLOOKUP) --------
st.sidebar.header("Upload Files")
file1 = st.sidebar.file_uploader("First File", type=["csv", "xlsx", "xls"], key="file1")
skip1 = st.sidebar.number_input("Skip rows (File 1)", 0, 100000, 0, 1)
file2 = st.sidebar.file_uploader("Second File", type=["csv", "xlsx", "xls"], key="file2")
skip2 = st.sidebar.number_input("Skip rows (File 2)", 0, 100000, 0, 1)

# -------- Top Controls: VLOOKUP Toggle (ABOVE the title) --------
if "show_vlookup" not in st.session_state:
    st.session_state.show_vlookup = False

ctrl_left, ctrl_right = st.columns([0.7, 0.3])
with ctrl_right:
    if st.button("🔍 VLOOKUP"):
        st.session_state.show_vlookup = not st.session_state.show_vlookup

# -------- VLOOKUP Logic (renders ABOVE the DEAL File Viewer) --------
if st.session_state.show_vlookup:
    st.markdown("---")
    st.subheader("🔍 VLOOKUP (File 2 → File 1)")

    if not (file1 and file2):
        st.info("Upload both files first to use VLOOKUP.")
    else:
        try:
            df1_full = _read_full(file1, skip1)
            df2_full = _read_full(file2, skip2)
        except Exception as e:
            st.error(f"Error loading full data for VLOOKUP: {e}")
            df1_full, df2_full = None, None

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
                run = st.form_submit_button("Apply VLOOKUP")

            if run:
                try:
                    # De-duplicate on the right key to emulate Excel's first-match behavior
                    right = df2_full.drop_duplicates(subset=[right_key], keep="first")

                    # If any fetched column name already exists in File 1, keep same name (no suffix)
                    renamed_cols = {}
                    for col in fetch_cols:
                        if col in df1_full.columns:
                            renamed_cols[col] = f"{col}"
                    right = right.rename(columns=renamed_cols)

                    use_cols = [right_key] + [renamed_cols.get(c, c) for c in fetch_cols]

                    merged = df1_full.merge(
                        right[use_cols],
                        how="left",
                        left_on=left_key,
                        right_on=right_key,
                        suffixes=("", " "),
                    )

                    # Drop duplicate key column if keys differ
                    if right_key != left_key and right_key in merged.columns:
                        merged.drop(columns=[right_key], inplace=True)

                    # Show preview (Arrow-safe) and allow download
                    merged_preview = _arrow_safe_df(merged.head(PREVIEW_ROWS))
                    st.dataframe(merged_preview, width="stretch", height=440)

                    csv = merged.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        "⬇️ Download VLOOKUP Result (CSV)",
                        data=csv,
                        file_name="vlookup_result.csv",
                        mime="text/csv",
                    )

                except Exception as e:
                    st.error(f"VLOOKUP failed: {e}")

# -------- Title --------
st.title("📂 File Viewer")

# -------- Previews (BELOW title) --------
df1_prev = _read_preview(file1, skip1) if file1 else None
df2_prev = _read_preview(file2, skip2) if file2 else None

df1_prev_safe = _arrow_safe_df(df1_prev) if isinstance(df1_prev, pd.DataFrame) else None
df2_prev_safe = _arrow_safe_df(df2_prev) if isinstance(df2_prev, pd.DataFrame) else None

c1, c2 = st.columns(2)
if isinstance(df1_prev_safe, pd.DataFrame):
    with c1:
        st.markdown(f"### 📄 File 1: `{file1.name}` (skip {skip1})")
        st.dataframe(df1_prev_safe, width="stretch", height=420)

if isinstance(df2_prev_safe, pd.DataFrame):
    with c2:
        st.markdown(f"### 📄 File 2: `{file2.name}` (skip {skip2})")
        st.dataframe(df2_prev_safe, width="stretch", height=420)
