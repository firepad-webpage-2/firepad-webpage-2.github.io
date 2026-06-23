import re


def get_original_figure_number(url):
    match = re.search(r"/x(\d+)\.png$", url)
    return match.group(1) if match else ""


def get_image_key(url):
    match = re.search(r"paper-assets\.alphaxiv\.org/figures/([^/\s)]+)/x(\d+)\.png", url)
    return f"{match.group(1)}/x{match.group(2)}" if match else url


def slugify_label(text):
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", text.strip().lower()))


def get_figure_label(alt_text, url):
    return slugify_label(alt_text) or (
        f"original-figure-{get_original_figure_number(url)}"
        if get_original_figure_number(url)
        else ""
    )


def make_unique_label(label, counts):
    if not label:
        return ""

    counts[label] = counts.get(label, 0) + 1
    return label if counts[label] == 1 else f"{label}-{counts[label]}"


def get_figure_labels(md):
    labels = []
    labels_by_key = {}
    counts = {}
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    for match in image_pattern.finditer(md):
        key = get_image_key(match.group(2))
        if key not in labels_by_key:
            labels_by_key[key] = {
                "label": make_unique_label(get_figure_label(match.group(1), match.group(2)), counts),
                "number": len(labels_by_key) + 1,
                "key": key,
            }
        labels.append(labels_by_key[key])

    return labels


def get_figure_metadata(md):
    labels = []
    labels_by_key = {}
    counts = {}
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    for match in image_pattern.finditer(md):
        after_image = md[match.end():]
        caption_match = re.match(r"^\s*\n\s*\*{0,2}Figure\s+(\d+)\s*:", after_image, re.I)
        key = get_image_key(match.group(2))

        if key not in labels_by_key:
            labels_by_key[key] = {
                "label": make_unique_label(get_figure_label(match.group(1), match.group(2)), counts),
                "number": len(labels_by_key) + 1,
                "captionNumber": int(caption_match.group(1)) if caption_match else len(labels_by_key) + 1,
                "key": key,
            }
        labels.append(labels_by_key[key])

    return labels


def normalize_figure_alt_text(md):
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    def replace(match):
        label = get_figure_label(match.group(1), match.group(2))
        return f"![{label}]({match.group(2)})" if label else match.group(0)

    return image_pattern.sub(replace, md)


def format_figure_reference_list(numbers, figure_labels):
    refs = []
    for number in numbers:
        figure = next((item for item in figure_labels if item.get("captionNumber") == number), None)
        if figure is None and 0 <= number - 1 < len(figure_labels):
            figure = figure_labels[number - 1]
        refs.append(f"{{fig:{figure['label']}}}" if figure and figure.get("label") else f"Figure {number}")

    if len(refs) <= 1:
        return refs[0] if refs else ""
    if len(refs) == 2:
        return f"{refs[0]} and {refs[1]}"
    return f"{', '.join(refs[:-1])}, and {refs[-1]}"


def normalize_figure_text_references(md):
    figure_labels = get_figure_metadata(md)
    reference_pattern = re.compile(
        r"\b(?:Figures?|Figs?\.?)\s+(\d+(?:\s*,\s*\d+)*(?:\s*,?\s+and\s+\d+)?)",
        re.I,
    )

    def replace_references(text):
        def replace(match):
            numbers = [int(number) for number in re.findall(r"\d+", match.group(1))]
            if not numbers:
                return match.group(0)
            return format_figure_reference_list(numbers, figure_labels)

        return reference_pattern.sub(replace, text)

    normalized_lines = []
    for line in md.split("\n"):
        if re.search(r"!\[[^\]]*\]\([^)]+\)", line):
            normalized_lines.append(line)
            continue

        caption_match = re.match(r"^(\s*\*{0,2}Figure\s+\d+\s*:)(.*)$", line, re.I)
        if caption_match:
            normalized_lines.append(f"{caption_match.group(1)}{replace_references(caption_match.group(2))}")
            continue

        labeled_caption_match = re.match(r"^(\s*\*{0,2}\{fig:[^}]+\}\s*:)(.*)$", line, re.I)
        if labeled_caption_match:
            normalized_lines.append(
                f"{labeled_caption_match.group(1)}{replace_references(labeled_caption_match.group(2))}"
            )
            continue

        if "{fig:" in line or "\\ref{fig:" in line:
            normalized_lines.append(line)
            continue

        normalized_lines.append(replace_references(line))

    return "\n".join(normalized_lines)


def normalize_figure_captions(md):
    lines = md.split("\n")
    figure_labels = get_figure_labels(md)
    figure_number = 0

    for index, line in enumerate(lines):
        if not re.search(r"!\[[^\]]*\]\([^)]+\)", line):
            continue

        figure_number += 1
        label = figure_labels[figure_number - 1]["label"] if figure_number - 1 < len(figure_labels) else ""
        caption_index = index + 1
        if (
            caption_index < len(lines)
            and label
            and re.match(r"^\s*\*{0,2}(?:Figure\s+\d+|\{fig:[^}]+\})\s*:", lines[caption_index], re.I)
        ):
            lines[caption_index] = re.sub(
                r"(\s*\*{0,2})(?:Figure\s+\d+|\{fig:[^}]+\})\s*:",
                rf"\1{{fig:{label}}}:",
                lines[caption_index],
                count=1,
                flags=re.I,
            )

    return "\n".join(lines)


def normalize_initial_markdown(md):
    return normalize_figure_captions(normalize_figure_text_references(normalize_figure_alt_text(md)))
