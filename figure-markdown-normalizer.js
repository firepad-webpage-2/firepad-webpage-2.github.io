(function(global) {
  function getOriginalFigureNumber(url) {
    const number = (url.match(/\/x(\d+)\.png$/) || [])[1];
    return number || "";
  }

  function getImageKey(url) {
    const match = url.match(/paper-assets\.alphaxiv\.org\/figures\/([^/\s)]+)\/x(\d+)\.png/);
    return match ? `${match[1]}/x${match[2]}` : url;
  }

  function slugifyLabel(text) {
    return text
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function getFigureLabel(altText, url) {
    return slugifyLabel(altText) || (getOriginalFigureNumber(url) ? `original-figure-${getOriginalFigureNumber(url)}` : "");
  }

  function makeUniqueLabel(label, counts) {
    if (!label) return "";
    counts[label] = (counts[label] || 0) + 1;
    return counts[label] === 1 ? label : `${label}-${counts[label]}`;
  }

  function getFigureLabels(md) {
    const labels = [];
    const labelsByKey = {};
    const counts = {};
    const imagePattern = /!\[([^\]]*)\]\(([^)]+)\)/g;
    let match;

    while ((match = imagePattern.exec(md))) {
      const key = getImageKey(match[2]);
      if (!labelsByKey[key]) {
        labelsByKey[key] = {
          label: makeUniqueLabel(getFigureLabel(match[1], match[2]), counts),
          number: Object.keys(labelsByKey).length + 1,
          key
        };
      }
      labels.push(labelsByKey[key]);
    }

    return labels;
  }

  function getFigureMetadata(md) {
    const labels = [];
    const labelsByKey = {};
    const counts = {};
    const imagePattern = /!\[([^\]]*)\]\(([^)]+)\)/g;
    let match;

    while ((match = imagePattern.exec(md))) {
      const afterImage = md.slice(match.index + match[0].length);
      const captionMatch = afterImage.match(/^\s*\n\s*\*{0,2}Figure\s+(\d+)\s*:/i);
      const key = getImageKey(match[2]);

      if (!labelsByKey[key]) {
        labelsByKey[key] = {
          label: makeUniqueLabel(getFigureLabel(match[1], match[2]), counts),
          number: Object.keys(labelsByKey).length + 1,
          captionNumber: captionMatch ? Number(captionMatch[1]) : Object.keys(labelsByKey).length + 1,
          key
        };
      }
      labels.push(labelsByKey[key]);
    }

    return labels;
  }

  function normalizeFigureAltText(md) {
    return md.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, altText, url) => {
      const label = getFigureLabel(altText, url);
      return label ? `![${label}](${url})` : match;
    });
  }

  function formatFigureReferenceList(numbers, figureLabels) {
    const refs = numbers.map(number => {
      const figure = figureLabels.find(item => item.captionNumber === number) || figureLabels[number - 1];
      return figure?.label ? `{fig:${figure.label}}` : `Figure ${number}`;
    });

    if (refs.length <= 1) return refs[0] || "";
    if (refs.length === 2) return `${refs[0]} and ${refs[1]}`;
    return `${refs.slice(0, -1).join(", ")}, and ${refs[refs.length - 1]}`;
  }

  function normalizeFigureTextReferences(md) {
    const figureLabels = getFigureMetadata(md);

    function replaceReferences(text) {
      return text.replace(/\b(?:Figures?|Figs?\.?)\s+(\d+(?:\s*,\s*\d+)*(?:\s*,?\s+and\s+\d+)?)/gi, (match, numberText) => {
        const numbers = numberText.match(/\d+/g)?.map(Number) || [];
        if (!numbers.length) return match;
        return formatFigureReferenceList(numbers, figureLabels);
      });
    }

    return md.split("\n").map(line => {
      if (/!\[[^\]]*\]\([^)]+\)/.test(line)) return line;

      const captionMatch = line.match(/^(\s*\*{0,2}Figure\s+\d+\s*:)(.*)$/i);
      if (captionMatch) {
        return `${captionMatch[1]}${replaceReferences(captionMatch[2])}`;
      }

      const labeledCaptionMatch = line.match(/^(\s*\*{0,2}\{fig:[^}]+\}\s*:)(.*)$/i);
      if (labeledCaptionMatch) {
        return `${labeledCaptionMatch[1]}${replaceReferences(labeledCaptionMatch[2])}`;
      }

      if (line.includes("{fig:") || line.includes("\\ref{fig:")) return line;

      return replaceReferences(line);
    }).join("\n");
  }

  function normalizeFigureCaptions(md) {
    const lines = md.split("\n");
    const figureLabels = getFigureLabels(md);
    let figureNumber = 0;

    for (let i = 0; i < lines.length; i++) {
      if (!/!\[[^\]]*\]\([^)]+\)/.test(lines[i])) continue;

      figureNumber++;
      const label = figureLabels[figureNumber - 1]?.label;
      const captionIndex = i + 1;
      if (captionIndex < lines.length && label && /^\s*\*{0,2}(?:Figure\s+\d+|\{fig:[^}]+\})\s*:/i.test(lines[captionIndex])) {
        lines[captionIndex] = lines[captionIndex].replace(/(\s*\*{0,2})(?:Figure\s+\d+|\{fig:[^}]+\})\s*:/i, `$1{fig:${label}}:`);
      }
    }

    return lines.join("\n");
  }

  function normalizeInitialMarkdown(md) {
    return normalizeFigureCaptions(normalizeFigureTextReferences(normalizeFigureAltText(md)));
  }

  global.FigureMarkdownNormalizer = {
    normalizeInitialMarkdown,
    normalizeFigureAltText,
    normalizeFigureTextReferences,
    normalizeFigureCaptions,
    getFigureLabels,
    getFigureMetadata,
    getFigureLabel,
    getImageKey,
    slugifyLabel
  };
})(window);
