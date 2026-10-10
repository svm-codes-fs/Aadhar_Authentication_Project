"""
Build a STATIC version of the dashboard that can be published as a claude.ai
Artifact (static hosting: no Python server).

How it works
------------
* Every analysis page is rendered by the real Flask app (same templates, same
  analysis/ functions) for every combination of the global filters
  (state x area type x service = 7 x 4 x 5 = 140 combinations).
* The rendered HTML is saved in one JSON file per page; a small JavaScript
  shell (src/app.js) shows the right fragment when the viewer picks a filter.
* The Simulator and Data Explorer need live interaction, so they are
  re-implemented in JavaScript in src/app.js, using the generator's
  ASSUMPTIONS exported to assumptions.json (same numbers, same rules).

Run from the project root:
    python artifact/build_artifact.py
Output goes to artifact/site/.
"""

import itertools
import json
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import app as flask_app  # noqa: E402  (needs the path set above)
from analysis import metrics, simulator  # noqa: E402
from data.generate_aadhaar_auth_dataset import ASSUMPTIONS  # noqa: E402

SOURCE_DIR = Path(__file__).resolve().parent / "src"
SITE_DIR = Path(__file__).resolve().parent / "site"

# Pages whose content depends on the global filters, and their Flask paths.
FILTERED_PAGES = {
    "overview": "/",
    "bias": "/bias",
    "quality": "/quality",
    "system": "/system",
    "repeated": "/repeated",
    "fairness": "/fairness",
}


def client_side_scatter(_rows):
    """Placeholder for the quality scatter plot.

    WHY: the scatter holds ~7,000 points. Storing them 140 times would make
    the site huge, so the browser draws them from the CSV instead.
    """
    return {"genuine": [], "impostor": [], "client_side": True}


def filter_combinations():
    """Every (state, area_type, service_type) choice, '' meaning 'All'."""
    choices = []
    for column in metrics.FILTER_COLUMNS:
        choices.append([""] + flask_app.FILTER_OPTIONS[column])
    return list(itertools.product(*choices))


def split_page(html):
    """Cut a rendered page into its <main> content and its page scripts."""
    main = re.search(r"<main>(.*)</main>", html, re.S).group(1)
    # The global filters are handled by the shell, so drop the inline
    # auto-submit handler (the shell listens for 'change' itself).
    main = main.replace(' onchange="this.form.submit()"', "")
    after_footer = html.split("</footer>", 1)[1]
    scripts = re.findall(r"<script>(.*?)</script>", after_footer, re.S)
    return {"body": main.strip(), "scripts": [code.strip() for code in scripts]}


def render(client, path):
    """GET a page from the Flask app and fail loudly on any error."""
    response = client.get(path)
    if response.status_code != 200:
        raise RuntimeError(f"{path} returned {response.status_code}")
    return response.get_data(as_text=True)


def build_filtered_pages(client):
    """Render each filtered page for all filter combinations."""
    pages_dir = SITE_DIR / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    combos = filter_combinations()
    for page, path in FILTERED_PAGES.items():
        started = time.time()
        fragments = {}
        for combo in combos:
            chosen = dict(zip(metrics.FILTER_COLUMNS, combo))
            query = urlencode({key: value for key, value in chosen.items() if value})
            url = f"{path}?{query}" if query else path
            fragments["|".join(combo)] = split_page(render(client, url))
        target = pages_dir / f"{page}.json"
        target.write_text(json.dumps(fragments, separators=(",", ":")), encoding="utf-8")
        size_mb = target.stat().st_size / 1_000_000
        print(f"  {page:<10} {len(fragments)} views, {size_mb:.1f} MB, {time.time() - started:.0f}s")


def build_methodology(client):
    """The Methodology page does not use filters: render it once."""
    fragment = split_page(render(client, "/methodology"))
    (SITE_DIR / "pages" / "methodology.json").write_text(
        json.dumps(fragment, separators=(",", ":")), encoding="utf-8")


def build_simulator_settings():
    """Export the generator assumptions and simulator profiles for the JS port."""
    settings = {
        "assumptions": ASSUMPTIONS,
        "form_options": simulator.FORM_OPTIONS,
        "default_profile": simulator.DEFAULT_PROFILE,
        "comparison_profile": simulator.COMPARISON_PROFILE,
        "runs": simulator.DEFAULT_RUNS,
        "min_age": simulator.MIN_AGE,
        "max_age": simulator.MAX_AGE,
    }
    (SITE_DIR / "simulator.json").write_text(json.dumps(settings, indent=1), encoding="utf-8")


def copy_static_files():
    """Copy the shell, the shared CSS/JS and the dataset into the site."""
    shutil.copy(SOURCE_DIR / "index.html", SITE_DIR / "index.html")
    shutil.copy(SOURCE_DIR / "app.js", SITE_DIR / "app.js")
    shutil.copy(PROJECT_ROOT / "static" / "css" / "style.css", SITE_DIR / "style.css")
    shutil.copy(PROJECT_ROOT / "static" / "js" / "charts.js", SITE_DIR / "charts.js")
    shutil.copy(flask_app.DATA_FILE, SITE_DIR / "attempts.csv")
    write_local_preview()


def write_local_preview():
    """Wrap index.html in a full document for testing with a local web server.

    The Artifact host adds this skeleton itself, so this file is NOT published.
    """
    page = (SOURCE_DIR / "index.html").read_text(encoding="utf-8")
    wrapper = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
               "</head><body>" + page + "</body></html>")
    (SITE_DIR / "_local_preview.html").write_text(wrapper, encoding="utf-8")


def main():
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    flask_app.metrics.quality_score_points = client_side_scatter
    client = flask_app.app.test_client()
    print("Rendering filtered pages...")
    build_filtered_pages(client)
    build_methodology(client)
    build_simulator_settings()
    copy_static_files()
    print(f"Done. Site written to {SITE_DIR}")


if __name__ == "__main__":
    main()
