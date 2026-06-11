#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const SKIPPED_DIRS = new Set([".git", "node_modules", "dist", "build"]);

function printUsage() {
  console.error("Usage: node normalize-markdown-files.js --out <output-dir> <file-or-dir> [...more files/dirs]");
}

function loadNormalizer() {
  const source = fs.readFileSync(path.join(__dirname, "figure-markdown-normalizer.js"), "utf8");
  const sandbox = { window: {} };
  vm.runInNewContext(source, sandbox);
  return sandbox.window.FigureMarkdownNormalizer;
}

function collectMarkdownFiles(inputPath) {
  const stat = fs.statSync(inputPath);

  if (stat.isFile()) {
    return /\.md$/i.test(inputPath) ? [inputPath] : [];
  }

  if (!stat.isDirectory()) return [];

  const files = [];
  const entries = fs.readdirSync(inputPath, { withFileTypes: true });

  entries.forEach(entry => {
    if (entry.isDirectory() && SKIPPED_DIRS.has(entry.name)) return;

    const entryPath = path.join(inputPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectMarkdownFiles(entryPath));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(entryPath);
    }
  });

  return files;
}

function parseArgs(argv) {
  const outIndex = argv.indexOf("--out");
  if (outIndex === -1 || !argv[outIndex + 1]) return null;

  const outDir = argv[outIndex + 1];
  const inputs = argv.filter((arg, index) => index !== outIndex && index !== outIndex + 1);

  if (!inputs.length) return null;
  return { outDir, inputs };
}

function getOutputPath(filePath, inputRoots, outDir) {
  const inputRoot = inputRoots.find(root => {
    const stat = fs.statSync(root);
    return stat.isDirectory() && path.resolve(filePath).startsWith(path.resolve(root) + path.sep);
  });
  const relativePath = inputRoot
    ? path.relative(inputRoot, filePath)
    : path.basename(filePath);

  return path.join(outDir, relativePath);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args) {
    printUsage();
    process.exit(1);
  }

  const normalizer = loadNormalizer();
  const inputRoots = args.inputs.map(input => path.resolve(input));
  const files = Array.from(new Set(args.inputs.flatMap(input => collectMarkdownFiles(path.resolve(input)))));

  if (!files.length) {
    console.error("No markdown files found.");
    process.exit(1);
  }

  files.forEach(filePath => {
    const outputPath = getOutputPath(filePath, inputRoots, path.resolve(args.outDir));
    const markdown = fs.readFileSync(filePath, "utf8");
    const normalized = normalizer.normalizeInitialMarkdown(markdown);

    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, normalized);
    console.log(`${filePath} -> ${outputPath}`);
  });
}

main();
