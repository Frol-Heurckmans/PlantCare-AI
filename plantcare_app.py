"""
PlantCare AI — Streamlit conversion of the React/TypeScript Figma export.
Python 3.11 | Streamlit | OpenRouter Vision (free tier)

Requirements (pip install):
    streamlit>=1.35
    requests>=2.31
    pillow>=10.0

Run:
    streamlit run plantcare_app.py

Get a FREE OpenRouter API key at: https://openrouter.ai  (no credit card needed)
Add it to .streamlit/secrets.toml next to this script:
    OPENROUTER_API_KEY = "sk-or-..."

History is persisted to  ./plantcare_history/  next to this script:
  - history.json  — metadata (result dicts) for all past scans, newest first
  - images/       — JPEG thumbnails named by scan ID
"""

import base64
import datetime
import io
import json
import os
import pathlib
import uuid

import requests
import streamlit as st
from PIL import Image

# ─── File-based persistence helpers ──────────────────────────────────────────
HISTORY_DIR   = pathlib.Path(__file__).parent / "plantcare_history"
IMAGES_DIR    = HISTORY_DIR / "images"
HISTORY_FILE  = HISTORY_DIR / "history.json"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _load_history_file() -> list[dict]:
    """Return history list from disk, newest first. Never raises."""
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_history_file(history: list[dict]) -> None:
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _save_image(scan_id: str, pil_image: Image.Image) -> str:
    """Save a JPEG thumbnail and return a data-URI for in-app display."""
    thumb = pil_image.copy()
    thumb.thumbnail((600, 600))
    dest = IMAGES_DIR / f"{scan_id}.jpg"
    thumb.save(dest, format="JPEG", quality=82)
    # Also return data-URI so the UI renders without hitting the filesystem again
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=82)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def _load_image_uri(scan_id: str) -> str:
    """Return a data-URI for a previously saved scan image, or empty string."""
    path = IMAGES_DIR / f"{scan_id}.jpg"
    if not path.exists():
        return ""
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


def persist_scan(result: dict, pil_image: Image.Image) -> str:
    """Save result metadata + image to disk. Returns data-URI of the thumbnail."""
    scan_id   = result["id"]
    image_uri = _save_image(scan_id, pil_image)
    history   = _load_history_file()
    # Avoid duplicates if re-run
    history   = [h for h in history if h.get("id") != scan_id]
    history.insert(0, result)           # newest first
    _save_history_file(history)
    return image_uri

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PlantCare AI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS (mirrors the green/emerald theme from the React app) ───────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

    /* Page background */
    .stApp { background: linear-gradient(160deg, #f0fdf4 0%, #ecfdf5 100%); }

    /* Hide default Streamlit header chrome */
    #MainMenu, footer, header { visibility: hidden; }

    /* Custom header */
    .pc-header {
        background: #14532d;
        color: white;
        padding: 1rem 2rem;
        border-radius: 0 0 1rem 1rem;
        display: flex;
        align-items: center;
        gap: .75rem;
        margin-bottom: 2rem;
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: -.5px;
    }
    .pc-header span.badge {
        margin-left: auto;
        background: #ea580c;
        font-size: .75rem;
        font-weight: 600;
        padding: .25rem .75rem;
        border-radius: 9999px;
    }

    /* Card shell */
    .pc-card {
        background: white;
        border: 2px solid #bbf7d0;
        border-radius: 1.25rem;
        padding: 1.75rem;
        box-shadow: 0 4px 24px rgba(20,83,45,.07);
        margin-bottom: 1.25rem;
    }

    /* Result header — healthy */
    .result-healthy {
        background: linear-gradient(135deg, #22c55e, #10b981);
        color: white;
        border-radius: 1rem 1rem 0 0;
        padding: 1.25rem 1.5rem;
    }
    /* Result header — sick */
    .result-sick {
        background: linear-gradient(135deg, #f97316, #ef4444);
        color: white;
        border-radius: 1rem 1rem 0 0;
        padding: 1.25rem 1.5rem;
    }
    .result-body { padding: 1.5rem; }

    /* Instruction step badge */
    .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.5rem;
        height: 1.5rem;
        background: #ea580c;
        color: white;
        border-radius: 9999px;
        font-size: .75rem;
        font-weight: 700;
        flex-shrink: 0;
        margin-right: .5rem;
    }

    /* How-it-works card */
    .how-card {
        background: linear-gradient(135deg, #fff7ed, #fffbeb);
        border: 2px solid #fed7aa;
        border-radius: 1.25rem;
        padding: 1.25rem 1.5rem;
    }

    /* Health score bar */
    .health-bar-bg {
        background: #dcfce7;
        border-radius: 9999px;
        height: .65rem;
        overflow: hidden;
        margin-top: .35rem;
    }
    .health-bar-fill {
        height: 100%;
        border-radius: 9999px;
        transition: width .6s ease;
    }

    /* History item */
    .hist-item {
        display: flex;
        gap: 1rem;
        align-items: flex-start;
        background: #f0fdf4;
        border: 2px solid #bbf7d0;
        border-radius: 1rem;
        padding: .9rem 1rem;
        margin-bottom: .75rem;
        cursor: pointer;
        transition: border-color .2s;
    }
    .hist-item:hover { border-color: #ea580c; }

    /* Buttons */
    div.stButton > button {
        border-radius: .75rem !important;
        font-weight: 600 !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Session state init (history loaded from disk once per session) ───────────
if "history_meta" not in st.session_state:
    # List of result dicts (no images — those are loaded on demand)
    st.session_state.history_meta = _load_history_file()
if "current_result" not in st.session_state:
    st.session_state.current_result = None   # {"result": dict, "image_uri": str}
if "view" not in st.session_state:
    st.session_state.view = "main"           # "main" | "history"


# ─── OpenRouter analysis ──────────────────────────────────────────────────────
def analyze_with_openrouter(pil_image: Image.Image) -> dict:
    """Call OpenRouter free vision models with automatic fallback on rate limit."""
    api_key = os.environ.get("OPENROUTER_API_KEY", st.secrets.get("OPENROUTER_API_KEY", ""))
    if not api_key:
        st.error("⚠️  OPENROUTER_API_KEY not set. Add it to .streamlit/secrets.toml — get one free at openrouter.ai")
        st.stop()

    # Convert image to base64 JPEG
    rgb = pil_image.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = """You are an expert botanist and plant health specialist.
Analyse the plant in this image and respond ONLY with a valid JSON object — no markdown, no extra text.

JSON schema:
{
  "plantName": "Common name",
  "scientificName": "Genus species",
  "isHealthy": true or false,
  "healthScore": integer 0-100,
  "diagnosis": "2-3 sentence assessment of the plant's condition",
  "careInstructions": ["instruction 1", "instruction 2", "instruction 3", "instruction 4"]
}

Rules:
- healthScore 80-100 = healthy, 50-79 = mild issues, below 50 = serious problems
- careInstructions: if healthy give maintenance tips; if sick give recovery steps
- Be specific, practical and concise"""

    # Try these models in order — if one is rate-limited, move to the next
    models = [
        "openrouter/free",
        "meta-llama/llama-4-scout:free",
        "google/gemma-3-12b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]

    last_error = None
    for model in models:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
            timeout=60,
        )

        # On rate limit or server error, try next model
        if response.status_code in (429, 503, 502):
            last_error = f"Model {model} rate-limited, trying next…"
            continue

        if not response.ok:
            raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")

        raw = response.json()["choices"][0]["message"]["content"].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        data["id"]        = str(uuid.uuid4())
        data["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
        return data

    raise RuntimeError("All free models are currently rate-limited. Please try again in a moment.")



# ─── UI helpers ───────────────────────────────────────────────────────────────
def render_header():
    st.markdown(
        """
        <div class="pc-header">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ea580c"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                       0 5.5-4.78 10-10 10Z"/>
              <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
            </svg>
            PlantCare AI
            <span class="badge">Powered by AI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_falling_leaves():
    """Inject falling leaves into the parent page by accessing window.parent."""
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        (function() {
            var doc = window.parent.document;
            var old = doc.getElementById('pc-leaf-canvas');
            if (old) old.remove();

            var canvas = doc.createElement('canvas');
            canvas.id = 'pc-leaf-canvas';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:99999';
            doc.body.appendChild(canvas);
            canvas.width  = window.parent.innerWidth;
            canvas.height = window.parent.innerHeight;
            var ctx = canvas.getContext('2d');

            var DURATION = 5000;
            var start    = performance.now();
            var colors   = ['#22c55e','#16a34a','#4ade80','#86efac','#14532d','#bbf7d0','#dcfce7'];

            function drawLeaf(x, y, size, angle, color, alpha) {
                ctx.save();
                ctx.globalAlpha = alpha;
                ctx.translate(x, y);
                ctx.rotate(angle);
                ctx.beginPath();
                ctx.moveTo(0, -size);
                ctx.bezierCurveTo( size*.7,-size*.5, size*.7, size*.5, 0, size*.3);
                ctx.bezierCurveTo(-size*.7, size*.5,-size*.7,-size*.5, 0,-size);
                ctx.closePath();
                ctx.fillStyle = color;
                ctx.fill();
                ctx.strokeStyle = 'rgba(255,255,255,.3)';
                ctx.lineWidth = size * .07;
                ctx.beginPath();
                ctx.moveTo(0,-size);
                ctx.lineTo(0, size*.3);
                ctx.stroke();
                ctx.restore();
            }

            var leaves = Array.from({length: 65}, function() {
                return {
                    x:    Math.random() * canvas.width,
                    y:   -Math.random() * canvas.height,
                    size: 10 + Math.random() * 22,
                    vy:   1.5 + Math.random() * 2.5,
                    vx:   (Math.random()-.5) * 1.5,
                    angle: Math.random() * Math.PI * 2,
                    spin:  (Math.random()-.5) * .05,
                    color: colors[Math.floor(Math.random()*colors.length)],
                    alpha: .6 + Math.random() * .4,
                    wobble: Math.random() * Math.PI * 2,
                    ws:    .02 + Math.random() * .03,
                };
            });

            function animate(now) {
                var elapsed = now - start;
                var fade = Math.max(0, 1 - Math.max(0, elapsed-(DURATION-1000))/1000);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                leaves.forEach(function(l) {
                    l.wobble += l.ws;
                    l.x += l.vx + Math.sin(l.wobble)*.9;
                    l.y += l.vy;
                    l.angle += l.spin;
                    if (l.y > canvas.height+30) { l.y=-30; l.x=Math.random()*canvas.width; }
                    drawLeaf(l.x, l.y, l.size, l.angle, l.color, l.alpha*fade);
                });
                if (elapsed < DURATION) requestAnimationFrame(animate);
                else canvas.remove();
            }
            requestAnimationFrame(animate);
        })();
        </script>
        """,
        height=1,
        scrolling=False,
    )


def render_result(result: dict, image_uri: str):
    is_healthy = result.get("isHealthy", True)
    score = result.get("healthScore", 0)

    # 🍃 Trigger falling leaves for healthy plants
    if score > 80:
        render_falling_leaves()

    header_cls = "result-healthy" if is_healthy else "result-sick"
    status_label = "Healthy Plant" if is_healthy else "Needs Attention"

    # SVG check vs alert icon
    status_icon = """
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white"
           stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>""" if is_healthy else """
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white"
           stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>"""

    # SVG leaf icon for section headings
    leaf_svg = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#14532d"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline;vertical-align:middle;margin-right:.35rem">
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
    </svg>"""

    # SVG magnifier for diagnosis
    search_svg = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#14532d"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline;vertical-align:middle;margin-right:.35rem">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>"""

    care_label = f"{leaf_svg} Maintenance Tips" if is_healthy else f"{leaf_svg} Recovery Instructions"

    st.markdown(
        f"""
        <div style="border:2px solid #bbf7d0;border-radius:1.25rem;overflow:hidden;
                    box-shadow:0 4px 24px rgba(20,83,45,.1);background:white;margin-bottom:1rem">
          <div class="{header_cls}">
            <div style="display:flex;align-items:center;gap:.6rem;font-size:1.35rem;font-weight:700">
              {status_icon}{status_label}
            </div>
            <div style="font-size:.875rem;opacity:.9;margin-top:.4rem">
              Health Score: {score}%
              <div class="health-bar-bg" style="background:rgba(255,255,255,.3)">
                <div class="health-bar-fill"
                     style="width:{score}%;background:white;opacity:.85"></div>
              </div>
            </div>
          </div>
          <div class="result-body">
            <p style="font-size:1.2rem;font-weight:700;color:#14532d;margin:0">
              {result.get('plantName','Unknown')}
            </p>
            <p style="font-style:italic;color:#6b7280;font-size:.875rem;margin:.1rem 0 1rem">
              {result.get('scientificName','')}
            </p>
            <p style="font-weight:600;color:#14532d;margin-bottom:.4rem">{search_svg} Diagnosis</p>
            <p style="color:#374151;line-height:1.6;margin-bottom:1rem">
              {result.get('diagnosis','')}
            </p>
            <p style="font-weight:600;color:#14532d;margin-bottom:.6rem">{care_label}</p>
        """,
        unsafe_allow_html=True,
    )

    for i, tip in enumerate(result.get("careInstructions", []), 1):
        st.markdown(
            f"""
            <div style="display:flex;align-items:flex-start;gap:.6rem;
                        background:#f0fdf4;border:1px solid #bbf7d0;
                        border-radius:.75rem;padding:.7rem .9rem;margin-bottom:.5rem">
              <span class="step-badge">{i}</span>
              <span style="color:#374151;font-size:.9rem;line-height:1.5">{tip}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;
                    border-top:1px solid #e5e7eb;margin-top:1rem;padding-top:1rem;text-align:center">
          <div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#3b82f6"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="margin:0 auto .3rem;display:block">
              <path d="M12 2v1M12 21v1M4.22 4.22l.7.7M19.07 19.07l.71.71
                       M2 12h1M21 12h1M4.22 19.78l.7-.71M19.07 4.93l.71-.71"/>
              <path d="M12 6a6 6 0 0 1 0 12 6 6 0 0 1 0-12z"/>
            </svg>
            <span style="font-size:.75rem;color:#6b7280">Water regularly</span>
          </div>
          <div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#eab308"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="margin:0 auto .3rem;display:block">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41
                       M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
            </svg>
            <span style="font-size:.75rem;color:#6b7280">Bright light</span>
          </div>
          <div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#22c55e"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 style="margin:0 auto .3rem;display:block">
              <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2
                       m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/>
            </svg>
            <span style="font-size:.75rem;color:#6b7280">Good airflow</span>
          </div>
        </div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )


def render_history():
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1rem">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#14532d"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span style="font-size:1.3rem;font-weight:700;color:#14532d">Analysis History</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    history_meta = st.session_state.history_meta
    if not history_meta:
        st.info("No scans yet — upload a plant image to get started.")
        return

    # Delete-all button
    if st.button("🗑️ Clear all history", type="secondary"):
        _save_history_file([])
        for f in IMAGES_DIR.glob("*.jpg"):
            f.unlink(missing_ok=True)
        st.session_state.history_meta = []
        st.rerun()

    for result in history_meta:
        is_healthy = result.get("isHealthy", True)
        icon  = "✔" if is_healthy else "!"
        score = result.get("healthScore", 0)
        name  = result.get("plantName", "Unknown")
        sci   = result.get("scientificName", "")
        ts    = result.get("timestamp", "")
        sid   = result.get("id", "")

        col_img, col_info, col_btn = st.columns([1, 4, 1.2])
        with col_img:
            uri = _load_image_uri(sid)
            if uri:
                st.image(uri, width=80)
            else:
                st.markdown("🌿", unsafe_allow_html=True)
        with col_info:
            st.markdown(
                f"**{name}** {icon}  \n"
                f"*{sci}*  \n"
                f"🕐 {ts} &nbsp;|&nbsp; "
                f"<span style='background:{'#dcfce7' if is_healthy else '#ffedd5'};"
                f"color:{'#166534' if is_healthy else '#9a3412'};"
                f"padding:.15rem .5rem;border-radius:9999px;font-size:.8rem'>"
                f"{score}% Health</span>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("View", key=f"hist_{sid}"):
                image_uri = _load_image_uri(sid)
                st.session_state.current_result = {"result": result, "image_uri": image_uri}
                st.session_state.view = "main"
                st.rerun()
        st.divider()


# ─── Main render ──────────────────────────────────────────────────────────────
render_header()

# Top navigation — orange History button
nav_col1, nav_col2 = st.columns([6, 1])
with nav_col2:
    btn_label = "History" if st.session_state.view == "main" else "← Back"
    if st.button(btn_label, key="nav_toggle", use_container_width=True, type="primary"):
        st.session_state.view = "history" if st.session_state.view == "main" else "main"
        st.rerun()

# Make just the nav button orange via CSS (primary buttons are easy to target)
st.markdown(
    """
    <style>
    button[kind="primary"] {
        background: #ea580c !important;
        border-color: #ea580c !important;
    }
    button[kind="primary"]:hover {
        background: #c2410c !important;
        border-color: #c2410c !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── HISTORY VIEW ──────────────────────────────────────────────────────────────
if st.session_state.view == "history":
    render_history()

# ── MAIN VIEW ─────────────────────────────────────────────────────────────────
else:
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        # Upload card
        st.markdown(
            """
            <div class="pc-card">
              <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:1.25rem">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ea580c"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                           0 5.5-4.78 10-10 10Z"/>
                  <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                </svg>
                <span style="font-weight:700;font-size:1.1rem;color:#14532d">Upload Plant Image</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Single file uploader that accepts both gallery and camera photos.
        # On mobile, the OS sheet lets the user choose "Camera" or "Photo Library".
        # CSS below makes the Browse Files button look like our two styled buttons.
        st.markdown(
            """
            <style>
            /* Hide drag-drop zone text, keep only the clickable button */
            [data-testid="stFileUploaderDropzoneInstructions"] { display:none !important; }
            [data-testid="stFileUploaderDropzone"] {
                background: transparent !important;
                border: none !important;
                padding: 0 !important;
                display: flex !important;
                justify-content: stretch !important;
            }
            [data-testid="stFileUploaderDropzone"] button {
                width: 100% !important;
                background: #ea580c !important;
                color: white !important;
                border: none !important;
                border-radius: .9rem !important;
                padding: 1rem !important;
                font-weight: 700 !important;
                font-size: 1rem !important;
                font-family: 'DM Sans', sans-serif !important;
                cursor: pointer !important;
            }
            [data-testid="stFileUploaderDropzone"] button:hover {
                background: #c2410c !important;
            }
            [data-testid="stFileUploader"] small { display:none !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Choose an image",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
            key="uploader_gallery",
        )
        camera_file = None  # camera_input removed — use phone's native camera via file picker

        # Determine active file (gallery upload takes priority over camera)
        active_file = uploaded_file or camera_file
        pil_img = None

        if active_file:
            pil_img = Image.open(active_file)
            st.markdown(
                """<div style="border-radius:.9rem;overflow:hidden;
                              border:2px dashed #bbf7d0;margin-bottom:.75rem">""",
                unsafe_allow_html=True,
            )
            st.image(pil_img, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if st.button("Analyse Plant", use_container_width=True, type="primary"):
                with st.spinner("Analysing your plant…"):
                    try:
                        result    = analyze_with_openrouter(pil_img)
                        image_uri = persist_scan(result, pil_img)
                        entry     = {"result": result, "image_uri": image_uri}
                        st.session_state.current_result = entry
                        st.session_state.history_meta = _load_history_file()
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Unexpected response from AI. Please try again.")
                    except Exception as exc:
                        st.error(f"Analysis failed: {exc}")
        else:
            st.markdown(
                "<p style='color:#6b7280;font-size:.875rem;text-align:center;"
                "margin-top:.25rem'>Upload or take a photo of your plant to get started</p>",
                unsafe_allow_html=True,
            )

        # How it works card
        st.markdown(
            """
            <div class="how-card">
              <p style="font-weight:700;color:#14532d;margin-bottom:.5rem;display:flex;align-items:center;gap:.4rem">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#ea580c"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                           0 5.5-4.78 10-10 10Z"/>
                  <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                </svg>
                How it works
              </p>
              <ul style="margin:0;padding-left:1.1rem;color:#374151;font-size:.875rem;line-height:1.9">
                <li>Upload a clear photo of your plant</li>
                <li>AI identifies the species and health status</li>
                <li>Get personalised care or recovery instructions</li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        current = st.session_state.current_result
        if current:
            render_result(current["result"], current["image_uri"])
        else:
            st.markdown(
                """
                <div class="pc-card" style="min-height:300px;display:flex;flex-direction:column;
                            align-items:center;justify-content:center;text-align:center">
                  <div style="background:#dcfce7;border-radius:9999px;width:5rem;height:5rem;
                              display:flex;align-items:center;justify-content:center;margin-bottom:1rem">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#14532d"
                         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8
                               0 5.5-4.78 10-10 10Z"/>
                      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                    </svg>
                  </div>
                  <h3 style="color:#14532d;margin:0 0 .5rem">Ready to analyse your plant</h3>
                  <p style="color:#6b7280;font-size:.9rem;max-width:280px">
                    Upload an image to get instant AI-powered identification
                    and health insights.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ─── OPTIONAL: swap in Supabase backend ───────────────────────────────────────
# Replace `analyze_with_claude()` with something like:
#
# import requests, os
# SUPABASE_PROJECT_ID = os.environ["SUPABASE_PROJECT_ID"]
# SUPABASE_ANON_KEY   = os.environ["SUPABASE_ANON_KEY"]
# API_BASE = f"https://{SUPABASE_PROJECT_ID}.supabase.co/functions/v1/make-server-3c18dd01"
#
# def analyze_with_supabase(pil_image):
#     buf = io.BytesIO()
#     pil_image.save(buf, format="JPEG")
#     buf.seek(0)
#     r = requests.post(
#         f"{API_BASE}/analyze-plant",
#         headers={"Authorization": f"Bearer {SUPABASE_ANON_KEY}"},
#         files={"image": ("plant.jpg", buf, "image/jpeg")},
#         timeout=30,
#     )
#     r.raise_for_status()
#     return r.json()
