from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "frontend/src/screens/Career.jsx"
text = path.read_text(encoding="utf-8")
old = '''const fileAsBase64 = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => {
    const value = String(reader.result || "");
    resolve(value.includes(",") ? value.split(",", 2)[1] : value);
  };
  reader.onerror = () => reject(reader.error || new Error("file read failed"));
  reader.readAsDataURL(file);
});
'''
new = '''const fileAsBase64 = (file) => new Promise(function(onResolve, onReject) {
  const reader = new globalThis.FileReader();
  reader.onload = () => {
    const value = String(reader.result || "");
    onResolve(value.includes(",") ? value.split(",", 2)[1] : value);
  };
  reader.onerror = () => onReject(reader.error || new Error("file read failed"));
  reader.readAsDataURL(file);
});
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one FileReader helper, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
