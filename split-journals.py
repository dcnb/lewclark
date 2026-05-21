#!/usr/bin/env python3
"""
split-journals.py

Reads the monolithic Lewis & Clark journals markdown file, extracts each
journal entry (## [Author, Date] sections), and writes them as individual
CB-Essay-compatible markdown files in _essay/.

Also rewrites the source file to just the intro/header content,
removing the table-of-contents block and the entry content.

Usage:
    python3 split-journals.py
"""

import re
import os
from pathlib import Path
from datetime import datetime

SOURCE_FILE = Path("_essay/01-the-journals-of-lewis-and-clark,-1804-1806.md")
ESSAY_DIR = Path("_essay")

# Map short author names to full names for the byline field
AUTHOR_MAP = {
    "Clark": "William Clark",
    "Lewis": "Meriwether Lewis",
    "Lewis and Clark": "Meriwether Lewis and William Clark",
    "Clark and Whitehouse": "William Clark and Joseph Whitehouse",
}

# Regex to match entry headings: ## [Author, Month Day, Year]
ENTRY_HEADING_RE = re.compile(r"^## \[(.+?)\]$", re.MULTILINE)

# Regex to parse the author and date out of the header label
LABEL_RE = re.compile(r"^(.+?),\s+(\w+ \d+,\s*\d+)$")


def slugify(text: str) -> str:
    """Convert text to a lowercase hyphenated slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text


def parse_label(label: str):
    """
    Parse a header label like 'Clark, May 14, 1804'.
    Returns (author_short, byline, date_str, date_obj_or_none).
    """
    m = LABEL_RE.match(label.strip())
    if not m:
        return label, label, label, None

    author_short = m.group(1).strip()
    date_str = m.group(2).strip()
    byline = AUTHOR_MAP.get(author_short, author_short)

    # Try to parse the date for sorting/slug
    date_obj = None
    for fmt in ("%B %d, %Y", "%B %d,%Y"):
        try:
            date_obj = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            pass

    return author_short, byline, date_str, date_obj


def main():
    source_text = SOURCE_FILE.read_text(encoding="utf-8")

    # ------------------------------------------------------------------ #
    # 1. Split off the YAML front matter from the rest
    # ------------------------------------------------------------------ #
    if source_text.startswith("---"):
        fm_end = source_text.index("---", 3)
        frontmatter = source_text[: fm_end + 3]
        body = source_text[fm_end + 3 :]
    else:
        frontmatter = ""
        body = source_text

    # ------------------------------------------------------------------ #
    # 2. Find the dividing line between the TOC and the actual content.
    #    The content section begins with a lone `---` separator followed
    #    by the book-level `# THE JOURNALS...` heading.
    # ------------------------------------------------------------------ #
    # Locate the last `---` that precedes `# THE JOURNALS`
    journals_heading_match = re.search(r"\n---\s*\n\n# THE JOURNALS", body)
    if not journals_heading_match:
        raise ValueError(
            "Could not find the '---\\n\\n# THE JOURNALS' boundary. "
            "Please check the source file structure."
        )

    intro_block = body[: journals_heading_match.start()].strip()
    content_block = body[journals_heading_match.start() :].strip()

    # ------------------------------------------------------------------ #
    # 3. Extract individual entries from the content block
    # ------------------------------------------------------------------ #
    # Find all heading positions
    heading_positions = [m for m in ENTRY_HEADING_RE.finditer(content_block)]

    if not heading_positions:
        raise ValueError("No '## [...]' entry headings found in content block.")

    entries = []
    for i, match in enumerate(heading_positions):
        label = match.group(1)  # e.g. "Clark, May 14, 1804"
        start = match.end()
        end = heading_positions[i + 1].start() if i + 1 < len(heading_positions) else len(content_block)
        entry_body = content_block[start:end].strip()
        entries.append((label, entry_body))

    print(f"Found {len(entries)} journal entries.")

    # ------------------------------------------------------------------ #
    # 4. Write individual essay files
    # ------------------------------------------------------------------ #
    # Track filenames to handle duplicate labels (same author + date)
    used_filenames: set[str] = set()
    # Skip the existing source file when checking for collisions
    used_filenames.add(SOURCE_FILE.name)

    for order, (label, entry_body) in enumerate(entries, start=1):
        author_short, byline, date_str, date_obj = parse_label(label)

        # Build a descriptive slug: author-month-day-year
        author_slug = slugify(author_short)
        if date_obj:
            date_slug = date_obj.strftime("%B-%d-%Y").lower()
        else:
            date_slug = slugify(date_str)

        base_name = f"{order:04d}-{author_slug}-{date_slug}"
        filename = f"{base_name}.md"

        # Guarantee uniqueness (shouldn't normally be needed, but just in case)
        counter = 2
        while filename in used_filenames:
            filename = f"{base_name}-{counter}.md"
            counter += 1
        used_filenames.add(filename)

        # Escape any internal quotes in label for YAML
        safe_label = label.replace('"', '\\"')

        fm_lines = [
            "---",
            f'title: "{safe_label}"',
            f"order: {order}",
            f'byline: "{byline}"',
            "---",
        ]
        file_content = "\n".join(fm_lines) + "\n\n" + entry_body + "\n"

        out_path = ESSAY_DIR / filename
        out_path.write_text(file_content, encoding="utf-8")

    print(f"Wrote {len(entries)} files to {ESSAY_DIR}/")

    # ------------------------------------------------------------------ #
    # 5. Rewrite the source file to contain only the intro/header block
    #    (removing the TOC and all entry content)
    # ------------------------------------------------------------------ #
    # Strip the auto-generated TOC: it's lines of bare [Author, Date] entries
    # Keep only the real intro text (title, notes, etc.)
    toc_line_re = re.compile(r"^\[.+,\s+\w+ \d+,\s*\d+\]\s*$")
    intro_lines = intro_block.splitlines()
    clean_intro_lines = [ln for ln in intro_lines if not toc_line_re.match(ln)]

    # Collapse runs of more than two blank lines into a single blank line
    cleaned_intro = re.sub(r"\n{3,}", "\n\n", "\n".join(clean_intro_lines)).strip()

    # Rebuild the source file with just the header/intro
    new_source = frontmatter + "\n\n" + cleaned_intro + "\n"
    SOURCE_FILE.write_text(new_source, encoding="utf-8")
    print(f"Rewrote {SOURCE_FILE} with intro content only.")


if __name__ == "__main__":
    # Run from the project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    main()
