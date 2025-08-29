import io
import re
import warnings
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

warnings.filterwarnings("ignore")
st.set_page_config(page_title="DEAL File", page_icon="📂", layout="wide")

# --- Force embed mode & hide Streamlit chrome (CSS + JS + MutationObserver) ---
components.html(
    """
    <script>
      (function () {  // ensure ?embed=true to suppress Streamlit chrome
        try {
          const url = new URL(window.location.href);
          if (url.searchParams.get("embed") !== "true") {
            url.searchParams.set("embed", "true");
            window.history.replaceState({}, "", url.toString());
          }
        } catch (e) {}
      })();
    </script>
    """,
    height=0, width=0
)
components.html(
    """
    <style>
      div[data-testid="stToolbar"]{visibility:hidden!important;height:0!important;}
      #MainMenu{visibility:hidden!important;} header{visibility:hidden!important;}
      footer{visibility:hidden!important;}
      [data-testid="stDecoration"]{display:none!important;visibility:hidden!important;opacity:0!important;}
      [data-testid="stStatusWidget"]{display:none!important;visibility:hidden!important;opacity:0!important;}
      .viewerBadge_link__1S137,.viewerBadge_container__r5tak{display:none!important;}
      a[href*="streamlit.io"]{display:none!important;}
      .stApp{padding-bottom:0!important;}
    </style>
    <script>
      function kill(el){
        try{
          el.style.display="none"; el.style.visibility="hidden"; el.style.opacity="0";
          el.style.pointerEvents="none"; el.removeAttribute && el.removeAttribute("href");
        }catch(e){}
      }
      function zap(){
        const sels=[
          '[data-testid="stDecoration"]','[data-testid="stStatusWidget"]',
          '.viewerBadge_link__1S137','.viewerBadge_container__r5tak',
          'a[href*="streamlit.io"]','a[aria-label*="Streamlit"]','button[aria-label*="Streamlit"]'
        ];
        sels.forEach(s=>document.querySelectorAll(s).forEach(kill));
        document.querySelectorAll('*').forEach(el=>{
          const s=getComputedStyle(el);
          if(s.position==='fixed'){
            const b=(parseFloat(s.bottom)||0)<=48, r=(parseFloat(s.right)||0)<=48, l=(parseFloat(s.left)||0)<=48;
            if(b&&(r||l)){ if(!el.closest('[data-testid="stSidebar"]')){ kill(el); } }
          }
        });
      }
      zap();
      new MutationObserver(zap).observe(document.body,{subtree:true,childList:true,attributes:true});
      setInterval(zap,800);
    </script>
    """,
    height=0, width=0
)

# --- Sticky top bar styles ---
components.html("""
<style>
  .topbar-sticky { position: sticky; top: 0; z-index: 999; background: transparent; }
  .topbar-card { padding: 8px 12px; border-radius: 12px; backdrop-filter: blur(6px); }
  @media (prefers-color-scheme: dark) {
    .topbar-card { background: rgba(30, 41, 59, 0.55); border: 1px solid rgba(71, 85, 105, 0.5); }
  }
  @media (prefers-color-scheme: light) {
    .topbar-card { background: rgba(255, 255, 255, 0.65); border: 1px solid rgba(203, 213, 225, 0.7); }
  }
</style>
""", height=0, width=0)

PREVIEW_ROWS = 1000

def _arrow_safe_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or not isinstance(df, pd.DataFrame):
        return df
    out = df.copy()
    cols = pd.Index([str(c) for c in out.columns])
    mask = ~cols.str.match(r"^Unnamed(:\s*\d+)?$")
    out = out.loc[:, mask]
    out.columns = [str(c) for c in out.columns]
    for c in out.columns:
        if pd.api.types.is_object_dtype(out[c]):
            try:
                if out[c].map(type).nunique(dropna=False) > 1:
                    out[c] = out[c].astype(str)
            except Exception:
                out[c] = out[c].astype(str)
    return out

def _excel_engine_for_name(lower_name: str) -> str | None:
    if lower_name.endswith(".xls"):  return "xlrd"
    if lower_name.endswith(".xlsx"): return "openpyxl"
    return None

def _read_excel_generic(content_bytes: bytes, *, file_name: str, skiprows: int = 0, sheet_name=0, nrows: int | None = None):
    lower = file_name.lower() if file_name else ""
    engine = _excel_engine_for_name(lower)
    buf = io.BytesIO(content_bytes)
    try:
        return pd.read_excel(buf, skiprows=skiprows, nrows=nrows, sheet_name=sheet_name, engine=engine)
    except Exception:
        try:
            buf.seek(0)
            return pd.read_excel(buf, skiprows=skiprows, nrows=nrows, sheet_name=sheet_name)
        except Exception as e2:
            if lower.endswith(".xls"):
                st.error("Failed to read .xls. Install xlrd: `pip install xlrd`")
            elif lower.endswith(".xlsx"):
                st.error("Failed to read .xlsx. Install openpyxl: `pip install openpyxl`")
            raise e2

@st.cache_data(show_spinner=False)
def _read_csv_preview(content_bytes: bytes, skiprows: int = 0, nrows: int = PREVIEW_ROWS):
    buf = io.BytesIO(content_bytes)
    try:
        return pd.read_csv(buf, skiprows=skiprows, nrows=nrows)
    except Exception:
        buf.seek(0)
        return pd.read_csv(buf, skiprows=skiprows).head(nrows)

@st.cache_data(show_spinner=False)
def _read_excel_preview(content_bytes: bytes, file_name: str, skiprows: int = 0, nrows: int = PREVIEW_ROWS, sheet_name=0):
    try:
        return _read_excel_generic(content_bytes, file_name=file_name, skiprows=skiprows, nrows=nrows, sheet_name=sheet_name)
    except Exception:
        buf = io.BytesIO(content_bytes)
        return pd.read_excel(buf, skiprows=skiprows, sheet_name=sheet_name).head(nrows)

@st.cache_data(show_spinner=False)
def _read_csv_full(content_bytes: bytes, skiprows: int = 0):
    buf = io.BytesIO(content_bytes)
    return pd.read_csv(buf, skiprows=skiprows)

@st.cache_data(show_spinner=False)
def _read_excel_full(content_bytes: bytes, file_name: str, skiprows: int = 0, sheet_name=0):
    return _read_excel_generic(content_bytes, file_name=file_name, skiprows=skiprows, nrows=None, sheet_name=sheet_name)

def _file_to_bytes(uploaded):  return uploaded.getvalue() if uploaded else None
def _safe_cols(df):            return [str(c) for c in df.columns]

def _read_preview(uploaded, skiprows=0):
    if not uploaded: return None
    data = _file_to_bytes(uploaded); name = uploaded.name
    if name.lower().endswith(".csv"): return _read_csv_preview(data, skiprows=skiprows, nrows=PREVIEW_ROWS)
    return _read_excel_preview(data, file_name=name, skiprows=skiprows, nrows=PREVIEW_ROWS)

def _read_full(uploaded, skiprows=0):
    if not uploaded: return None
    data = _file_to_bytes(uploaded); name = uploaded.name
    if name.lower().endswith(".csv"): return _read_csv_full(data, skiprows=skiprows)
    return _read_excel_full(data, file_name=name, skiprows=skiprows)

st.sidebar.header("Upload Files")

file1 = st.sidebar.file_uploader("First File", type=["csv", "xlsx", "xls"], key="file1")
if file1: st.sidebar.write(f"📄 File 1 uploaded: **{file1.name}**")
skip1 = st.sidebar.number_input("Skip rows (File 1)", 0, 100000, 0, 1)

file2 = st.sidebar.file_uploader("Second File", type=["csv", "xlsx", "xls"], key="file2")
if file2: st.sidebar.write(f"📄 File 2 uploaded: **{file2.name}**")
skip2 = st.sidebar.number_input("Skip rows (File 2)", 0, 100000, 0, 1)

if "show_vlookup" not in st.session_state: st.session_state.show_vlookup = False
if "show_merge"   not in st.session_state: st.session_state.show_merge   = False

with st.container():
    st.markdown('<div class="topbar-sticky"><div class="topbar-card">', unsafe_allow_html=True)
    top_l, top_r = st.columns([0.75, 0.25])
    with top_r:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔍 VLOOKUP", use_container_width=True):
                st.session_state.show_vlookup = not st.session_state.show_vlookup
        with col_b:
            if st.button("🧾 Merge Files", use_container_width=True):
                st.session_state.show_merge = not st.session_state.show_merge
    st.markdown('</div></div>', unsafe_allow_html=True)

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
                    left_key  = st.selectbox("Key column in File 1", options=cols1)
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
                    right = df2_full.drop_duplicates(subset=[right_key], keep="first")
                    renamed_cols = {col: col for col in fetch_cols if col in df1_full.columns}
                    right = right.rename(columns=renamed_cols)
                    use_cols = [right_key] + [renamed_cols.get(c, c) for c in fetch_cols]

                    merged = df1_full.merge(
                        right[use_cols],
                        how="left",
                        left_on=left_key,
                        right_on=right_key,
                        suffixes=("", " "),
                    )

                    if right_key != left_key and right_key in merged.columns:
                        merged.drop(columns=[right_key], inplace=True)

                    # Preview
                    merged_preview = _arrow_safe_df(merged.head(PREVIEW_ROWS))
                    st.dataframe(merged_preview, width="stretch", height=440)

                    # Build output filename using originals (without extensions)
                    f1 = (file1.name.rsplit('.', 1)[0] if file1 else "file1").strip().replace(" ", "_")
                    f2 = (file2.name.rsplit('.', 1)[0] if file2 else "file2").strip().replace(" ", "_")
                    output_name = f"vlookup_{f1}_{f2}.xlsx"

                    # Download as Excel
                    xbuf = io.BytesIO()
                    with pd.ExcelWriter(xbuf, engine="openpyxl") as writer:
                        merged.to_excel(writer, index=False, sheet_name="VLOOKUP")
                    xbuf.seek(0)
                    st.download_button(
                        "⬇️ Download VLOOKUP Result (Excel)",
                        data=xbuf,
                        file_name=output_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                except Exception as e:
                    st.error(f"VLOOKUP failed: {e}")

if st.session_state.show_merge:
    st.markdown("---")
    st.subheader("🧾 Merge Files into One Excel (Rows Appended, Columns Auto-Union)")

    with st.form("merge_form_simple", clear_on_submit=False):
        files_to_merge = st.file_uploader(
            "Pick files to merge (CSV/XLSX/XLS) — drag & drop multiple",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="merge_files_uploader_simple",
        )
        run_merge = st.form_submit_button("Build Single Excel")

    if run_merge:
        try:
            selected = files_to_merge or []
            if not selected:
                st.warning("Please select at least one file.")
            else:
                # Read & normalize (auto-union columns)
                frames, all_cols = [], set()
                for up in selected:
                    name = up.name
                    data = _file_to_bytes(up)
                    if name.lower().endswith(".csv"):
                        df = pd.read_csv(io.BytesIO(data))
                    else:
                        df = _read_excel_generic(data, file_name=name)
                    df = _arrow_safe_df(df)
                    all_cols |= set(map(str, df.columns))
                    frames.append((name, df))

                all_cols = list(all_cols)
                combined = []
                for nm, df in frames:
                    tmp = df.copy()
                    for c in all_cols:
                        if c not in tmp.columns:
                            tmp[c] = pd.NA
                    tmp = tmp[all_cols]
                    tmp["__source_file"] = nm
                    combined.append(tmp)

                combined_df = pd.concat(combined, ignore_index=True)

                # Write single-sheet Excel
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine="openpyxl") as writer:
                    combined_df.to_excel(writer, index=False, sheet_name="Combined")
                out.seek(0)

                # Filename from first couple of files
                parts = [f.name.rsplit('.',1)[0] for f in selected[:3]]
                if len(selected) > 3:
                    parts.append(f"+{len(selected)-3}more")
                out_name = (("_".join(p.replace(" ", "_") for p in parts) or "merged") + ".xlsx")

                st.success("Single-sheet Excel is ready.")
                st.download_button(
                    "⬇️ Download Combined Excel",
                    data=out,
                    file_name=out_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                st.caption("Preview of 'Combined' (first rows)")
                st.dataframe(_arrow_safe_df(combined_df.head(PREVIEW_ROWS)), width="stretch", height=420)

        except Exception as e:
            st.error(f"Merge failed: {e}")

st.title("📂 File Viewer")

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
