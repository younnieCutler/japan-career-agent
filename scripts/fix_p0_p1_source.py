from pathlib import Path

path = Path("frontend/src/screens/Applications.jsx")
text = path.read_text(encoding="utf-8")
start = text.index('const normalize = (value) => String(value || "").trim().toLocaleLowerCase();')
end = text.index('/* Recommendations only reorder confirmed, externally usable evidence.', start)
replacement = r'''const normalize = (value) => String(value || "").trim().toLocaleLowerCase();

const POSTING_LABELS = {
  company: new Set([
    "company", "company name",
    "\u4f1a\u793e", "\u4f1a\u793e\u540d", "\u4f01\u696d", "\u4f01\u696d\u540d",
    "\ud68c\uc0ac", "\ud68c\uc0ac\uba85",
  ].map(normalize)),
  position: new Set([
    "position", "job title", "role",
    "\u30dd\u30b8\u30b7\u30e7\u30f3", "\u8077\u7a2e", "\u52df\u96c6\u8077\u7a2e",
    "\ud3ec\uc9c0\uc158", "\uc9c1\ubb34", "\ucc44\uc6a9\uc9c1\ubb34",
  ].map(normalize)),
};

/* Only explicit labelled lines are read from pasted posting text. Free prose is never interpreted
   as a company name or a position title; missing fields stay for the user to enter. */
function explicitPostingField(text, labels) {
  for (const line of splitLines(text)) {
    const ascii = line.indexOf(":");
    const fullwidth = line.indexOf("\uff1a");
    const separator = ascii < 0 ? fullwidth : fullwidth < 0 ? ascii : Math.min(ascii, fullwidth);
    if (separator < 0) continue;
    const key = normalize(line.slice(0, separator));
    const value = line.slice(separator + 1).trim();
    if (value && labels.has(key)) return value;
  }
  return "";
}

function postingFields(text) {
  return {
    company: explicitPostingField(text, POSTING_LABELS.company),
    position: explicitPostingField(text, POSTING_LABELS.position),
  };
}

'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8", newline="\n")
