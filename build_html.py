"""
Production build script for single-page static HTML projects.
- Scans HTML img references to determine asset paths
- Creates dist/ with correct directory structure
- Copies image assets to their expected locations under dist/
- Minifies HTML (inline CSS + JS) using minify-html
- Verifies all referenced assets are present in output

Usage:
    python build_html.py

Customization points (edit before running):
    ROOT       — project root directory
    HTML_FILE  — the source HTML filename (output will be index.html)
"""
import os
import shutil
import re
from pathlib import Path
from minify_html import minify

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION — edit these for your project
# ═══════════════════════════════════════════════════════════════
ROOT = Path.cwd()            # Project root
HTML_FILE = "index.html"     # Source HTML filename
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
# ═══════════════════════════════════════════════════════════════

DIST = ROOT / "dist"


def scan_html_for_images(html_path):
    """Extract all relative image paths referenced in the HTML."""
    content = html_path.read_text(encoding="utf-8")
    pattern = re.compile(r'src=["\']([^"\']+)')
    refs = set()
    for match in pattern.findall(content):
        # Ignore runtime-generated template expressions such as
        # src="${canvas.toDataURL(...)}"; they are not file assets.
        if not match.startswith(("http://", "https://", "data:", "${", "blob:")):
            refs.add(match)
    return refs


def find_images_in_root():
    """Find all image files at the project root."""
    images = {}
    for f in ROOT.iterdir():
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            images[f.name] = f
    return images


def main():
    # ── 1. Prepare output directory ──────────────────────────
    print("[1/4] Preparing output directory...")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    html_path = ROOT / HTML_FILE
    if not html_path.exists():
        print(f"  ✗ ERROR: {HTML_FILE} not found at {ROOT}")
        exit(1)

    # ── 2. Scan references and copy assets ───────────────────
    print("[2/4] Analyzing image references and copying assets...")
    refs = scan_html_for_images(html_path)
    source_images = find_images_in_root()

    if refs:
        # Create subdirectories based on referenced paths
        for ref in refs:
            ref_path = Path(ref)
            parent = ref_path.parent
            if str(parent) != ".":
                (DIST / parent).mkdir(parents=True, exist_ok=True)

        copied = 0
        for ref in refs:
            ref_path = Path(ref)
            basename = ref_path.name
            if basename in source_images:
                dest = DIST / ref
                shutil.copy2(source_images[basename], dest)
                copied += 1
                print(f"  ✓ {ref}")
            elif (DIST / ref).exists():
                print(f"  - {ref} (already in dist/)")
                copied += 1
            else:
                print(f"  ✗ MISSING source for: {ref}")
                print(f"     (Looking for '{basename}' at project root)")

        print(f"  → {copied}/{len(refs)} referenced images copied")
    else:
        print("  - No local image references found")
        # Copy all images anyway to dist/ just in case
        for name, path in source_images.items():
            shutil.copy2(path, DIST / name)
            print(f"  ✓ {name} (no explicit ref, copied anyway)")

    # ── 3. Minify HTML → dist/index.html ─────────────────────
    print("[3/4] Minifying HTML...")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    minified = minify(
        html_content,
        keep_closing_tags=True,
        keep_html_and_head_opening_tags=False,
        allow_removing_spaces_between_attributes=True,
        minify_css=True,
        minify_js=True,
        remove_bangs=False,
        remove_processing_instructions=True,
    )

    output_path = DIST / "index.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(minified)

    size_before = len(html_content.encode("utf-8"))
    size_after = len(minified.encode("utf-8"))
    print(f"  → Original: {size_before:,} bytes")
    print(f"  → Minified: {size_after:,} bytes")
    print(f"  → Reduced:  {(1 - size_after / size_before) * 100:.1f}%")

    # ── 4. Verify output ─────────────────────────────────────
    print("[4/4] Verifying output...")
    content = output_path.read_text(encoding="utf-8")
    # Only inspect real <img> elements; bundled JavaScript often contains
    # unrelated `src=` text that is not an asset reference.
    img_pattern = re.compile(r'<img\b[^>]*src=["\']?([^"\'\s>]+)', re.IGNORECASE)
    refs_after = img_pattern.findall(content)
    local_refs = [
        r for r in refs_after
        if not r.startswith(("http://", "https://", "data:", "${", "blob:"))
    ]

    all_good = True
    if local_refs:
        for r in local_refs:
            p = DIST / r
            if p.exists():
                print(f"  ✓ {r}")
            else:
                print(f"  ✗ MISSING: {r}")
                all_good = False
    else:
        print("  - No local image references found in output")

    all_files = list(DIST.rglob("*"))
    file_count = len([f for f in all_files if f.is_file()])
    print(f"\n  Total files in dist/: {file_count}")
    for f in sorted(all_files):
        rel = f.relative_to(DIST)
        print(f"    dist/{rel}")

    if all_good:
        print("\n✅ Build successful! dist/ is ready for deployment.")
    else:
        print("\n⚠️  Build completed — some assets are missing.")
        exit(1)


if __name__ == "__main__":
    main()
