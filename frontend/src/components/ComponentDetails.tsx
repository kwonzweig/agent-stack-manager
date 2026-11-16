import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import { ExternalLink, FileText, MessageSquare, Pencil } from "lucide-react";
import { api, errorMessage, packagePath, externalUrl } from "../api";
import type { Comment, Component } from "../types";
import { DetailSheet } from "./DetailSheet";
import { KindBadge } from "./ComponentUI";
import { sourceLabel } from "../catalog/catalogItem";
const SkillMarkdown = lazy(() => import("./SkillMarkdown").then(module => ({ default: module.SkillMarkdown })));

export const displayValue = (value: unknown): string => typeof value === "string" ? value : JSON.stringify(value, null, 2) ?? "";
export const formatDate = (value: string) => new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
export function ValuePanel({ label, value, open = true }: { label: string; value: unknown; open?: boolean }) {
  return value != null && value !== "" ? <details className="value-panel" open={open}>
    <summary>{label}</summary><pre tabIndex={0}>{displayValue(value)}</pre>
  </details> : <section className="inspector-section"><h3>{label}</h3><p className="no-value">Not available</p></section>;
}

const commentDrafts = new Map<string, { author: string; body: string }>();
function Comments({ presetId, componentId }: { presetId: string; componentId: string }) {
  const key = JSON.stringify([presetId, componentId]);
  const [fields, setFields] = useState(() => commentDrafts.get(key) || { author: "", body: "" });
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [postError, setPostError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setLoadError("");
    const params = new URLSearchParams({ presetId, componentId });
    api<{ comments: Comment[] }>("/api/comments?" + params, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setComments(data.comments);
    }).catch(error => {
      if (!controller.signal.aborted) setLoadError(errorMessage(error));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [presetId, componentId, attempt]);

  function change(next: typeof fields) {
    setFields(next); commentDrafts.set(key, next);
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (posting || !fields.body.trim() || !fields.author.trim()) return;
    setPostError(""); setPosting(true);
    try {
      await api("/api/comments", { method: "POST", body: { presetId, componentId, author: fields.author.trim(), body: fields.body.trim() } });
      if (commentDrafts.get(key)?.body === fields.body) change({ ...fields, body: "" });
      setAttempt(prev => prev + 1);
    } catch (error) { setPostError(errorMessage(error)); }
    finally { setPosting(false); }
  }
  return <section className="asm-preset inspector-section comments" aria-label="Comments">
    <h3 className="flex items-center gap-2"><MessageSquare className="h-4 w-4" /> Comments</h3>
    <div className="comment-list" aria-live="polite">
      {loading ? <p>Loading comments…</p> : loadError ? <p role="alert">{loadError} <button type="button" onClick={() => setAttempt(v => v + 1)} className="underline">Retry</button></p> :
        comments.length ? <ul>{comments.map(comment => <li key={comment.id}>
          <header><strong>{comment.author}</strong><time dateTime={comment.createdAt}>{formatDate(comment.createdAt)}</time></header>
          <p>{comment.body}</p>
        </li>)}</ul> : <p>No comments yet.</p>}
    </div>
    <form className="comment-form" onSubmit={submit}>
      <label className="form-field">Author<input className="app-input" name="author" maxLength={120} required autoComplete="nickname"
        value={fields.author} disabled={posting} onChange={e => change({ ...fields, author: e.target.value })} /></label>
      <label className="form-field">Comment<textarea className="rounded-lg border border-border-subtle bg-surface p-3 text-[13px]" name="body" maxLength={8000} required rows={3}
        value={fields.body} disabled={posting} onChange={e => change({ ...fields, body: e.target.value })} /></label>
      {postError && <p role="alert" className="text-danger">{postError}</p>}
      <button type="submit" className="app-button-primary" disabled={posting || !fields.author.trim() || !fields.body.trim()}>{posting ? "Posting…" : "Post comment"}</button>
    </form>
  </section>;
}

export function ComponentDetails({ item, presetId, onClose, instruction, onInstruction, onBrowseStack }: {
  item: Component; presetId?: string; onClose: () => void;
  instruction?: string; onInstruction?: (value: string) => void; onBrowseStack?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const sourceUrl = externalUrl(item.sourceUrl || item.source?.repositoryUrl);
  return <DetailSheet open title={item.name} description={item.id !== "instruction" ? item.description : undefined}
    meta={<KindBadge kind={item.kind} />} onClose={onClose}>
    <div className="asm-preset mx-auto max-w-[1240px] space-y-5">
      {item.id === "instruction" && onInstruction ? <section aria-label="Instruction">
        <div className="section-heading">
          <h3 className="flex items-center gap-2"><FileText className="h-4 w-4 text-muted" /> Instruction</h3>
          <button type="button" className="app-button-secondary" onClick={() => setEditing(v => !v)}><Pencil className="h-4 w-4" /> {editing ? "Done" : "Edit Instruction"}</button>
        </div>
        {editing
          ? <textarea autoFocus rows={14} value={instruction} onChange={e => onInstruction(e.target.value)}
              aria-label="Instruction" className="w-full rounded-lg border border-border-subtle bg-surface p-4 font-mono text-[13px]" />
          : instruction ? <div className="app-panel p-4"><Suspense fallback={<p className="text-muted">Loading Instruction…</p>}><SkillMarkdown content={instruction} /></Suspense></div>
            : <p className="empty">No Instruction yet.</p>}
      </section> : <>
        {onBrowseStack && <button className="app-button-secondary" type="button" onClick={onBrowseStack}>Open stack</button>}
        {sourceUrl && <section className="inspector-section">
          <h3>Source</h3>
          <a href={sourceUrl.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-accent underline-offset-4 hover:underline">
            {sourceLabel(item)} <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </section>}
        <div className="values">
          {item.source && <ValuePanel label="Source reference" value={item.source} />}
          {item.configuration != null && <ValuePanel label="Configuration" value={item.configuration} />}
        </div>
      </>}
      {presetId && <Comments key={JSON.stringify([presetId, item.id])} presetId={presetId} componentId={item.id} />}
    </div>
  </DetailSheet>;
}


