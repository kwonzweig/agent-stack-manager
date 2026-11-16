import { useState } from "react";
import { Copy, Download } from "lucide-react";
import { downloadArchive, errorMessage } from "../api";
import type { NativeFile } from "../types";

export function SourceFiles({ files, id, dirty }: { files: NativeFile[]; id: string; dirty: boolean }) {
  const [path, setPath] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const current = files.find(file => file.path === path) || files[0];
  async function download() {
    setError(""); setDownloading(true);
    try { await downloadArchive(id); }
    catch (err) { setError(errorMessage(err)); }
    finally { setDownloading(false); }
  }
  async function copy() {
    setError(""); setStatus("");
    try { await navigator.clipboard.writeText(current.content); setStatus("Copied text preview."); }
    catch (err) { setError(errorMessage(err)); }
  }
  return <section className="asm-lab source" aria-label="Source files">
    <div className="section-heading"><h2>Source files</h2>
      <button className="app-button-secondary" type="button" onClick={download} disabled={downloading}><Download className="h-4 w-4" /> Download APM package</button>
    </div>
    {dirty && <p className="mb-2 text-[12px] text-muted">Showing the saved revision.</p>}
    {error && <p role="alert" className="mb-2 text-[13px] text-danger">{error}</p>}
    {status && <p role="status" className="mb-2 text-[12px] text-muted">{status}</p>}
    {current ? <div className="source-panel">
      <div className="file-toolbar">
        <label className="file-picker"><span className="sr-only">Source file</span>
          <select value={current.path} onChange={e => { setPath(e.target.value); setStatus(""); setError(""); }}>
            {files.map(file => <option value={file.path} key={file.path}>{file.path}</option>)}
          </select>
        </label>
        <div className="file-actions">
          <button type="button" className="lab-icon-button" title="Copy text preview" aria-label="Copy text preview" onClick={copy}><Copy className="h-4 w-4" /></button>
        </div>
      </div>
      <pre className="source-code" tabIndex={0} aria-label={current.path}><code>{current.content}</code></pre>
    </div> : <p className="empty">No source files.</p>}
  </section>;
}


