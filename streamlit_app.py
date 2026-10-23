
# streamlit_app.py: FRESHGUARD AI — PRODUCE BIN COMMAND CENTER
# Call Chain: streamlit_app.py -> slm_engine.py -> decision_engine.py -> main_engine.py
# Run:  streamlit run streamlit_app.py      (or: python streamlit_app.py)
# v5 UI: white + crate-green theme, promotions as shelf-edge price tags, a
# ripeness bar per product, Groq SLM as the only copy generator, no settings panel.
# Behaviour kept from v3/v4: engine cached with st.cache_resource, results keyed to
# the uploaded file's hash, every dynamic string HTML-escaped, errors shown (never
# masked), main panel uses `return` (never st.stop()), approvals logged to
# outputs/approved_promotions.json.
import hashlib
import html
import io
import json
import os
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

# Self-launcher: `python streamlit_app.py` has no Streamlit script
# context. Hand off to `streamlit run` from the project folder so the white/green
# theme in .streamlit/config.toml is picked up from any starting directory.
if __name__ == "__main__" and get_script_run_ctx(suppress_warning=True) is None:
    from streamlit.web import cli as stcli
    os.chdir(Path(__file__).resolve().parent)
    sys.argv = ["streamlit", "run", str(Path(__file__).resolve())]
    sys.exit(stcli.main())

import config 
import decision_engine as de  
from slm_engine import SLMEngine 

st.set_page_config(page_title="FreshGuard AI · Produce Command Center", page_icon="🥬", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Figtree:wght@400;500;600;700&display=swap');
:root{
  --paper:#FFFFFF; --leaf:#1F7A4D; --leaf-deep:#165C39; --sprout:#EEF6F0; --stem:#D6E7DC;
  --ink:#17251D; --muted:#56675C; --amber:#A65F0B; --amber-bg:#FDF3E4; --red:#B42318; --red-bg:#FDECEA;
  --unripe:#A8D5B4; --ripe:#1F7A4D; --overripe:#D9952B; --rotten:#B42318;
}
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], button, input, textarea {
  font-family:'Figtree', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
[data-testid="stAppViewContainer"]{ background:var(--paper); color:var(--ink); }
[data-testid="stHeader"]{ background:transparent; }
.block-container{ padding-top:1.6rem; max-width:1320px; }
h1, h2, h3, .fg-display{ font-family:'Bricolage Grotesque','Figtree',system-ui,sans-serif; color:var(--ink); letter-spacing:-0.015em; }

/* Sidebar */
[data-testid="stSidebar"]{ background:var(--sprout); border-right:1px solid var(--stem); }
.fg-brand{ display:flex; align-items:center; gap:.6rem; margin:.2rem 0 1.4rem; }
.fg-brand svg{ flex:none; }
.fg-brand b{ font-family:'Bricolage Grotesque',sans-serif; font-size:1.45rem; font-weight:800; color:var(--leaf-deep); letter-spacing:-0.02em; }
.fg-brand span{ display:block; font-size:.82rem; color:var(--muted); margin-top:-2px; }
.fg-side-note{ font-size:.85rem; color:var(--muted); line-height:1.45; margin-top:1rem; }
.fg-model{ font-size:.84rem; color:var(--leaf-deep); margin-top:.8rem; display:flex; gap:.45rem; align-items:baseline; line-height:1.4; }
.fg-model i{ flex:none; width:8px; height:8px; border-radius:50%; background:var(--leaf); display:inline-block; }
.fg-model--busy{ color:var(--muted); } .fg-model--busy i{ background:#9BB8A6; }
.fg-model--err{ color:var(--red); } .fg-model--err i{ background:var(--red); }

/* Buttons */
button[kind="primary"], [data-testid="stBaseButton-primary"]{
  background:var(--leaf) !important; border:1px solid var(--leaf) !important; color:#fff !important;
  font-weight:600; border-radius:10px;
}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover{ background:var(--leaf-deep) !important; }
button[kind="secondary"], [data-testid="stBaseButton-secondary"]{ border-radius:10px; border-color:var(--leaf); color:var(--leaf-deep); font-weight:600; }
button:focus-visible{ outline:3px solid #8CC7A1 !important; outline-offset:2px; }

/* Header */
.fg-top{ display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; flex-wrap:wrap;
  padding-bottom:1rem; border-bottom:2px solid var(--leaf); margin-bottom:1.2rem; }
.fg-top h1{ font-size:2.1rem; font-weight:800; margin:0; padding:0; line-height:1.1; }
.fg-top p{ margin:.35rem 0 0; color:var(--muted); font-size:1rem; max-width:60ch; }
.fg-chip{ display:inline-flex; align-items:center; gap:.45rem; padding:.32rem .75rem; border-radius:999px;
  font-size:.85rem; font-weight:600; border:1px solid var(--stem); background:var(--paper); color:var(--ink); white-space:nowrap; }
.fg-chip i{ width:8px; height:8px; border-radius:50%; background:var(--leaf); display:inline-block; }
.fg-chip--warn{ background:var(--amber-bg); border-color:#F0D2A8; color:var(--amber); }
.fg-chip--warn i{ background:var(--amber); }

/* Summary strip: one ruled band, not a row of cards */
.fg-strip{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); border:1px solid var(--stem); border-radius:14px;
  background:var(--paper); margin-bottom:1.3rem; overflow:hidden; }
.fg-strip div{ padding:.85rem 1.1rem; border-left:1px solid var(--stem); }
.fg-strip div:first-child{ border-left:none; }
.fg-strip b{ display:block; font-family:'Bricolage Grotesque',sans-serif; font-size:1.9rem; font-weight:700; line-height:1.1;
  color:var(--ink); font-variant-numeric:tabular-nums; }
.fg-strip span{ font-size:.88rem; color:var(--muted); }
.fg-strip .is-alert b{ color:var(--red); }
.fg-strip .is-deal b{ color:var(--amber); }
@media (max-width:700px){ .fg-strip{ grid-template-columns:repeat(2,1fr); } .fg-strip div:nth-child(3){ border-left:none; }
  .fg-strip div:nth-child(n+3){ border-top:1px solid var(--stem); } }

/* Tabs */
.stTabs [data-baseweb="tab-list"]{ gap:.25rem; border-bottom:1px solid var(--stem); }
.stTabs [data-baseweb="tab"]{ font-weight:600; color:var(--muted); padding:.5rem .9rem; }
.stTabs [aria-selected="true"]{ color:var(--leaf-deep) !important; }
.stTabs [data-baseweb="tab-highlight"]{ background:var(--leaf) !important; height:3px; }

/* Photo */
[data-testid="stImage"] img{ border-radius:14px; border:1px solid var(--stem); }

/* Inventory table with ripeness bars */
.fg-inv{ width:100%; border-collapse:collapse; font-size:.95rem; border:0 !important; }
.fg-inv th, .fg-inv td{ border-left:0 !important; border-right:0 !important; border-top:0 !important; }
.fg-inv th{ text-align:left; font-weight:600; color:var(--muted); font-size:.85rem; padding:.55rem .6rem; border-bottom:1px solid var(--stem); }
.fg-inv td{ padding:.8rem .6rem; border-bottom:1px solid var(--stem); vertical-align:middle; }
.fg-inv td.num{ font-variant-numeric:tabular-nums; font-weight:600; }
.fg-prod{ font-family:'Bricolage Grotesque',sans-serif; font-weight:700; font-size:1.08rem; }
.fg-bar{ display:flex; height:12px; border-radius:6px; overflow:hidden; background:var(--sprout); min-width:140px; }
.fg-bar i{ display:block; height:100%; }
.fg-bar .u{ background:var(--unripe); } .fg-bar .r{ background:var(--ripe); }
.fg-bar .o{ background:var(--overripe); } .fg-bar .x{ background:var(--rotten); }
.fg-bar-txt{ font-size:.8rem; color:var(--muted); margin-top:.3rem; font-variant-numeric:tabular-nums; }
.fg-legend{ display:flex; gap:1rem; flex-wrap:wrap; font-size:.82rem; color:var(--muted); margin:.8rem 0 0; }
.fg-legend span::before{ content:""; display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:.35rem; vertical-align:-1px; background:var(--c); }
.fg-status{ display:inline-block; padding:.2rem .6rem; border-radius:999px; font-size:.8rem; font-weight:600; white-space:nowrap; }
.s-red{ background:var(--red-bg); color:var(--red); } .s-amber{ background:var(--amber-bg); color:var(--amber); }
.s-green{ background:var(--sprout); color:var(--leaf-deep); } .s-hold{ background:#EEF2F7; color:#3E5470; }
.fg-foot{ font-size:.82rem; color:var(--muted); margin-top:.9rem; }

/* Store actions: ruled list */
.fg-action{ padding:1rem 0; border-bottom:1px solid var(--stem); }
.fg-action:first-child{ padding-top:.3rem; }
.fg-action h4{ margin:0 0 .4rem; font-family:'Bricolage Grotesque',sans-serif; font-size:1.15rem; display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; }
.fg-action p{ margin:0; line-height:1.55; max-width:72ch; }

/* Promotions as shelf-edge price tags */
.fg-tags{ display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:1rem; }
.fg-tag{ background:var(--paper); border:1px solid var(--stem); border-radius:6px 6px 14px 14px; overflow:hidden; display:flex; flex-direction:column; }
.fg-tag-head{ background:var(--leaf); color:#fff; padding:.55rem .9rem; display:flex; justify-content:space-between; align-items:center; gap:.5rem; }
.fg-tag-head b{ font-family:'Bricolage Grotesque',sans-serif; font-size:1.15rem; font-weight:700; }
.fg-tag-head small{ font-size:.75rem; font-weight:600; background:rgba(255,255,255,.18); padding:.12rem .5rem; border-radius:999px; }
.fg-tag--deal .fg-tag-head{ background:var(--amber); }
.fg-tag-body{ padding:.9rem; }
.fg-price{ font-family:'Bricolage Grotesque',sans-serif; font-size:2.4rem; font-weight:800; line-height:1; color:var(--ink); font-variant-numeric:tabular-nums; }
.fg-price s{ font-family:'Figtree',sans-serif; font-size:1rem; font-weight:500; color:var(--muted); margin-left:.4rem; }
.fg-per{ font-size:.8rem; color:var(--muted); margin:.2rem 0 .7rem; }
.fg-tag p{ margin:0; line-height:1.5; font-size:.93rem; border-top:1px dashed var(--stem); padding-top:.7rem; }

/* Bundles */
.fg-bundle{ border:1px solid var(--stem); border-left:5px solid var(--leaf); border-radius:10px; padding:1rem 1.1rem; margin-bottom:.9rem; background:var(--paper); }
.fg-bundle h4{ margin:0; font-family:'Bricolage Grotesque',sans-serif; font-size:1.15rem; }
.fg-offer{ color:var(--leaf-deep); font-weight:600; margin:.3rem 0 .6rem; }
.fg-items{ display:flex; gap:.4rem; flex-wrap:wrap; margin-bottom:.6rem; }
.fg-items span{ background:var(--sprout); border:1px solid var(--stem); border-radius:999px; padding:.15rem .6rem; font-size:.82rem; }
.fg-bundle p{ margin:0; line-height:1.5; }

/* Empty state */
.fg-empty{ border:1px dashed #A9CDB6; border-radius:16px; padding:2rem 2.2rem; background:var(--sprout); max-width:760px; }
.fg-empty h2{ margin:0 0 .4rem; font-size:1.6rem; }
.fg-empty p{ color:var(--muted); margin:0 0 1rem; max-width:60ch; }
.fg-empty ol{ margin:0; padding-left:1.2rem; line-height:1.9; }
@media (prefers-reduced-motion:reduce){ *{ transition:none !important; animation:none !important; } }
</style>
""", unsafe_allow_html=True)

esc = lambda x: html.escape(str(x))  # every dynamic string goes through this

LEAF_SVG = ('<svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">'
            '<rect width="34" height="34" rx="9" fill="#1F7A4D"/>'
            '<path d="M10 23c0-8 6-13 15-13-1 9-6 14-13 14" fill="#EEF6F0"/>'
            '<path d="M10 24c3-4 6-6.5 10-8.5" stroke="#1F7A4D" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>')

# Plain-language shelf status for each decision-engine scenario: (label, css class)
SHELF_STATUS = {
    de.ROTTEN_ONLY: ("Cull whole bin", "s-red"),
    de.DETERIORATING: ("Mark down now", "s-amber"),
    de.FRESH_OVERSTOCKED: ("Overstocked, bundle it", "s-green"),
    de.UNRIPE_HOLD: ("Ripening, hold back", "s-hold"),
    de.OPTIMAL: ("Healthy", "s-green"),
}


# MODEL PRELOADING: the 3 vision models are loaded and warmed up in a background
# thread as soon as the dashboard opens, so the first "Analyze bin" does not wait
# for TensorFlow/PyTorch start-up. One engine per server process (cache_resource).
def _build_engine(use_sample: bool) -> SLMEngine:
    engine = SLMEngine(use_sample_inventory=use_sample, backend="groq")
    engine.warmup()            # loads the models + one dummy pass through each
    return engine


@st.cache_resource(show_spinner=False)
def engine_loader(use_sample: bool) -> Future:
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="fg-preload").submit(_build_engine, use_sample)


def get_engine(use_sample: bool) -> SLMEngine:
    """Blocks until the preloaded engine is ready. A failed load (e.g. weights copied in
    after start-up) is retried on the next click."""
    fut = engine_loader(use_sample)
    if fut.done() and fut.exception() is not None:
        engine_loader.clear()
        fut = engine_loader(use_sample)
    return fut.result()


@st.cache_data(show_spinner=False, max_entries=8)
def display_image(data: bytes) -> bytes:
    """Downscaled JPEG for the browser; the full-resolution file still goes to the models."""
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((config.DISPLAY_MAX_PX, config.DISPLAY_MAX_PX))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def render_model_status() -> None:
    """Sidebar chip; polls every 2 s while the background load is running."""
    if (not config.PRELOAD_MODELS or config.USE_SAMPLE_INVENTORY
            or get_script_run_ctx(suppress_warning=True) is None):
        return
    fut = engine_loader(config.USE_SAMPLE_INVENTORY)

    @st.fragment(run_every=None if fut.done() else 2)
    def _chip():
        f = engine_loader(config.USE_SAMPLE_INVENTORY)
        if not f.done():
            st.markdown('<div class="fg-model fg-model--busy"><i></i>Loading models in the background. '
                        'You can upload a photo meanwhile.</div>', unsafe_allow_html=True)
        elif f.exception() is not None:
            st.markdown(f'<div class="fg-model fg-model--err"><i></i>Models could not load: '
                        f'{esc(str(f.exception())[:140])}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="fg-model"><i></i>Models loaded and ready</div>', unsafe_allow_html=True)
    _chip()


def save_upload(uploaded) -> tuple:
    data = uploaded.getvalue()
    digest = hashlib.sha1(data).hexdigest()[:12]
    config.UPLOAD_DIR.mkdir(exist_ok=True)
    suffix = "." + uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ".png"
    path = config.UPLOAD_DIR / f"shelf_{digest}{suffix}"
    if not path.exists():
        path.write_bytes(data)
    return path, digest


def status_chip(scenario: str) -> str:
    label, css = SHELF_STATUS.get(scenario, ("Review", "s-hold"))
    return f'<span class="fg-status {css}">{esc(label)}</span>'


# RENDER HELPERS
def render_header(results) -> None:
    note = (results or {}).get("meta", {}).get("note", "")
    if not config.GROQ_API_KEY or note:
        chip = '<span class="fg-chip fg-chip--warn"><i></i>Groq offline: using backup copy</span>'
    else:
        chip = '<span class="fg-chip"><i></i>Copy written by Groq SLM</span>'
    demo = '<span class="fg-chip">Demo inventory</span> ' if config.USE_SAMPLE_INVENTORY else ""
    st.markdown(f"""<div class="fg-top"><div><h1>Produce bin report</h1>
        <p>Freshness, stock and pricing actions for the bin you photographed.</p></div>
        <div>{demo}{chip}</div></div>""", unsafe_allow_html=True)


def render_summary(results) -> None:
    inv = results.get("inventory", {})
    counted = sum(r["Product_Count"] for r in inv.values())
    rotten = sum(r["Rotten_Count"] for r in inv.values())
    markdowns = sum(1 for d in results.get("decisions", {}).values() if d.get("discount_pct", 0) > 0)
    st.markdown(f"""<div class="fg-strip">
        <div><b>{counted}</b><span>items counted</span></div>
        <div><b>{len(inv)}</b><span>products in the bin</span></div>
        <div class="{'is-alert' if rotten else ''}"><b>{rotten}</b><span>rotten units to remove</span></div>
        <div class="{'is-deal' if markdowns else ''}"><b>{markdowns}</b><span>markdowns to approve</span></div>
        </div>""", unsafe_allow_html=True)


def render_inventory(results) -> None:
    decisions = results.get("decisions", {})
    rows = []
    for prod, r in results.get("inventory", {}).items():
        total = max(r["Product_Count"], 1)
        segs = [("u", r["Unripe_Count"], "unripe"), ("r", r["Ripe_Count"], "ripe"),
                ("o", r["Overripe_Count"], "overripe"), ("x", r["Rotten_Count"], "rotten")]
        bar = "".join(f'<i class="{c}" style="width:{n / total * 100:.1f}%" title="{n} {lbl}"></i>' for c, n, lbl in segs if n)
        txt = ", ".join(f"{n} {lbl}" for _, n, lbl in segs if n)
        d = decisions.get(prod, {})
        price = (f'{config.money(d["new_price"])} <s style="color:#56675C">{config.money(d["base_price"])}</s>'
                 if d.get("discount_pct") else (config.money(d["base_price"]) if d else "—"))
        rows.append(f"""<tr><td><span class="fg-prod">{esc(prod)}</span></td>
            <td class="num">{r['Product_Count']}</td>
            <td><div class="fg-bar">{bar}</div><div class="fg-bar-txt">{esc(txt)}</div></td>
            <td>{status_chip(d.get('scenario', '')) if d else '—'}</td>
            <td class="num">{price}</td></tr>""")
    st.markdown(f"""<table class="fg-inv"><thead><tr><th>Product</th><th>Count</th><th>Ripeness mix</th>
        <th>Shelf status</th><th>Price</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
        <div class="fg-legend"><span style="--c:var(--unripe)">Unripe</span><span style="--c:var(--ripe)">Ripe</span>
        <span style="--c:var(--overripe)">Overripe</span><span style="--c:var(--rotten)">Rotten</span></div>""",
                unsafe_allow_html=True)
    t = results.get("meta", {}).get("timings_s", {})
    if t:
        st.markdown(f'<div class="fg-foot">Scan processed in {t.get("total", 0):.1f} s: vision {t.get("vision", 0):.1f} s, '
                    f'pricing {t.get("decisions", 0):.2f} s, Groq copy {t.get("copy", 0):.1f} s.</div>', unsafe_allow_html=True)


def render_actions(results) -> None:
    decisions = results.get("decisions", {})
    items = results.get("merchandising_strategies", [])
    if not items:
        st.info("No store actions for this scan.")
        return
    blocks = "".join(
        f"""<div class="fg-action"><h4>{esc(it.get('product_type', 'Product'))}
        {status_chip(decisions.get(it.get('product_type'), {}).get('scenario', ''))}</h4>
        <p>{esc(it.get('strategy', ''))}</p></div>""" for it in items)
    st.markdown(blocks, unsafe_allow_html=True)


def render_promotions(results, image_path: Path) -> None:
    promotions = results.get("promotions", [])
    if not promotions:
        st.info("No promotions for this scan. The bin is stocked at regular price.")
        return
    tags = []
    for p in promotions:
        new_p, base_p = p.get("new_price", ""), p.get("base_price", "")
        deal = bool(base_p and base_p != new_p)
        strike = f"<s>{esc(base_p)}</s>" if deal else ""
        tags.append(f"""<article class="fg-tag {'fg-tag--deal' if deal else ''}">
            <div class="fg-tag-head"><b>{esc(p.get('product_type', 'Product'))}</b><small>{esc(p.get('badge', 'Offer'))}</small></div>
            <div class="fg-tag-body"><div class="fg-price">{esc(new_p)}{strike}</div><div class="fg-per">per unit</div>
            <p>{esc(p.get('loyalty_message', ''))}</p></div></article>""")
    st.markdown(f'<div class="fg-tags">{"".join(tags)}</div>', unsafe_allow_html=True)
    st.write("")
    if st.button("Approve and send to loyalty app", type="primary"):
        config.OUTPUT_DIR.mkdir(exist_ok=True)
        log_path = config.OUTPUT_DIR / "approved_promotions.json"
        try:
            log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
        except json.JSONDecodeError:
            log = []
        stamp = datetime.now().isoformat(timespec="seconds")
        log.append({"approved_at": stamp, "image": image_path.name, "promotions": promotions})
        log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
        st.session_state["approved_at"] = stamp
        st.toast("Promotions sent to the loyalty app", icon="✅")
    if st.session_state.get("approved_at"):
        st.success(f"Sent to the loyalty app at {st.session_state['approved_at']}. "
                   "Saved to outputs/approved_promotions.json.")


def render_bundles(results) -> None:
    combos = results.get("combos", [])
    if not combos:
        st.info("No bundles for this scan.")
        return
    cards = "".join(
        f"""<div class="fg-bundle"><h4>{esc(c.get('combo_title', 'Bundle'))}</h4>
        <div class="fg-offer">{esc(c.get('bundle_offer', ''))}</div>
        <div class="fg-items">{''.join(f'<span>{esc(i)}</span>' for i in c.get('included_products', []))}</div>
        <p>{esc(c.get('pitch', ''))}</p></div>""" for c in combos)
    st.markdown(cards, unsafe_allow_html=True)


# SIDEBAR
with st.sidebar:
    st.markdown(f'<div class="fg-brand">{LEAF_SVG}<div><b>FreshGuard</b><span>Produce command center</span></div></div>',
                unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Photo of a produce bin or shelf", type=["png", "jpg", "jpeg"])
    run_button = st.button("Analyze bin", type="primary", width="stretch", disabled=uploaded_file is None)
    status_slot = st.empty()          # filled at the end of the run, after the page has drawn
    st.markdown('<div class="fg-side-note">FreshGuard counts each item, grades its ripeness, prices '
                'markdowns within your cost floor and drafts the promotions for you to approve.</div>',
                unsafe_allow_html=True)


# MAIN
def render_main(uploaded_file, run_button: bool) -> None:
    """Main panel. Uses `return` (not st.stop()) so it is safe even without a
    Streamlit script context, where st.stop() silently does nothing."""
    use_sample = config.USE_SAMPLE_INVENTORY
    if uploaded_file is None:
        render_header(None)
        st.markdown("""<div class="fg-empty"><h2>Scan a produce bin</h2>
            <p>Upload a clear photo of one bin or shelf section in the sidebar. You will get stock counts,
            ripeness, markdown prices and ready-to-send promotions.</p>
            <ol><li>Upload a photo</li><li>Select Analyze bin</li><li>Review and approve the promotions</li></ol></div>""",
                    unsafe_allow_html=True)
        return

    image_path, image_hash = save_upload(uploaded_file)
    run_key = f"{image_hash}|{use_sample}"

    if run_button:
        loading = config.PRELOAD_MODELS and not engine_loader(use_sample).done()
        msg = ("Finishing the model load, then scanning..." if loading
               else "Counting items, grading ripeness and drafting promotions...")
        with st.spinner(msg):
            try:
                engine = get_engine(use_sample)
                st.session_state["slm_results"] = engine.generate_recommendations(str(image_path))
                st.session_state["results_key"] = run_key
                st.session_state.pop("approved_at", None)
            except Exception as e:
                st.session_state.pop("slm_results", None)
                render_header(None)
                st.error(f"Analysis failed: **{type(e).__name__}**: {e}")
                st.caption("Check that the three model files are in the project folder (see README).")
                return

    results = st.session_state.get("slm_results")
    fresh = results is not None and st.session_state.get("results_key") == run_key
    render_header(results if fresh else None)

    if fresh:
        render_summary(results)

    col_img, col_results = st.columns([1, 1.9], gap="large")
    with col_img:
        st.image(display_image(uploaded_file.getvalue()), caption=uploaded_file.name, width="stretch")

    with col_results:
        if not fresh:
            st.info("Select **Analyze bin** in the sidebar to scan this photo.")
            return
        meta = results.get("meta", {})
        if meta.get("note"):
            st.warning(f"Groq could not write the copy, so FreshGuard used its built-in backup text. "
                       f"Reason: {meta['note']}")
        if not results.get("inventory"):
            st.warning("No produce was detected with enough confidence. Try a closer, well-lit photo of a single bin.")

        tab_inv, tab_act, tab_promo, tab_bundle, tab_raw = st.tabs(
            ["Inventory", "Store actions", "Promotions", "Bundles", "Raw output"])
        with tab_inv:
            render_inventory(results)
        with tab_act:
            render_actions(results)
        with tab_promo:
            render_promotions(results, image_path)
        with tab_bundle:
            render_bundles(results)
        with tab_raw:
            st.json(results)


render_main(uploaded_file, run_button)

# Start loading the models as soon as the page has drawn (the heavy TensorFlow/PyTorch
# imports would otherwise compete with the first render). Skipped in bare/no-context runs.
if config.PRELOAD_MODELS and get_script_run_ctx(suppress_warning=True) is not None:
    engine_loader(config.USE_SAMPLE_INVENTORY)
    with status_slot.container():
        render_model_status()
