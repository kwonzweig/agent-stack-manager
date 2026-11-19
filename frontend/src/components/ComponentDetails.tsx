import { lazy, Suspense, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ExternalLink, FileText, MessageSquare, Pencil } from "lucide-react";
import { api, errorMessage, packagePath, externalUrl } from "../api";
import type { Comment, Component, ComponentDefinition } from "../types";
import { DetailSheet } from "./DetailSheet";
import ItemProperties from "../catalog/ItemProperties";
import { readAtLabel, sourceLabel } from "../catalog/catalogItem";
import { displayDescription, observationAppName, componentLocations } from "../lib/componentLocation";
import { ComponentLocation } from "./ComponentLocation";
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

// Where a description was read: the file's name, or the repository whose GitHub description it is.
function readFrom(url: URL) {
  const [owner, repository, blob, ...rest] = url.pathname.split("/").filter(Boolean);
  return blob === "blob" ? rest[rest.length - 1] : `the GitHub description of ${owner}/${repository}`;
}

export function ComponentDetails({ item: initialItem, presetId, backLabel, onClose, instruction, onInstruction, onBrowseStack, membership }: {
  item: Component; presetId?: string; backLabel: string; onClose: () => void;
  instruction?: string; onInstruction?: (value: string) => void; onBrowseStack?: () => void;
  membership?: ReactNode | ((definition: ComponentDefinition) => ReactNode);
}) {
  const [editing, setEditing] = useState(false);
  const [definition, setDefinition] = useState<ComponentDefinition>();
  const [sourceError, setSourceError] = useState("");
  const [enriching, setEnriching] = useState(false);
  useEffect(() => {
    setDefinition(undefined); setSourceError(""); setEnriching(false);
    if (!initialItem.canonicalId || initialItem.kind === "package") return;
    const request = new AbortController();
    const path = "/api/components/" + encodeURIComponent(initialItem.canonicalId);
    api<ComponentDefinition>(path, { signal: request.signal })
      .then(async value => {
        if (request.signal.aborted) return;
        setDefinition(value);
        if (!value.remoteApproved && value.sourceAccess !== "verify") return;
        setEnriching(true);
        try {
          const found = await api<ComponentDefinition>(path + "/source", { signal: request.signal });
          if (!request.signal.aborted) setDefinition(found);
        } finally {
          if (!request.signal.aborted) setEnriching(false);
        }
      })
      .catch(error => { if (!request.signal.aborted) setSourceError(errorMessage(error)); });
    return () => request.abort();
  }, [initialItem.canonicalId]);
  const item = definition ?? initialItem;
  const description = displayDescription(item);
  const sourceUrl = externalUrl(item.sourceUrl || item.source?.repositoryUrl);
  const read = externalUrl(item.descriptionUrl);
  const githubSource = externalUrl(item.source?.repositoryUrl)?.hostname === "github.com";
  return <DetailSheet open title={item.name} backLabel={backLabel} onClose={onClose}
    description={initialItem.id !== "instruction" && description ? <>
      <p>{description}</p>
      {read && <p className="mt-1 text-[12px] leading-5 text-muted">
        From <a href={read.href} target="_blank" rel="noreferrer" className="underline underline-offset-4 hover:text-secondary">{readFrom(read)}</a>, read {readAtLabel(item.descriptionReadAt)}.
      </p>}
    </> : undefined}
    meta={<div className="flex flex-wrap items-center gap-2"><ItemProperties item={item} repository="link" /></div>}>
    <div className="asm-preset mx-auto max-w-[1240px] space-y-5">
      {sourceError && <p role="alert" className="text-danger">{sourceError}</p>}
      {definition?.addable === false && <p className="app-panel p-3 text-secondary">Reusable source unavailable.</p>}
      {enriching && <p role="status" className="text-muted">Reading the component source…</p>}
      {initialItem.canonicalId && initialItem.kind !== "package" && !definition && !sourceError && <p role="status" className="text-muted">Loading component…</p>}
      {initialItem.id === "instruction" && onInstruction ? <section aria-label="Instruction">
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
        {definition && typeof membership === "function" ? membership(definition) : typeof membership !== "function" ? membership : null}
        {onBrowseStack && <button className="app-button-secondary" type="button" onClick={onBrowseStack}>Open stack</button>}
        {sourceUrl && <section className="inspector-section">
          <h3>Source</h3>
          <a href={sourceUrl.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-accent underline-offset-4 hover:underline">
            {sourceLabel(item)} <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </section>}
        <section className="inspector-section" aria-label="Source reference">
          <h3>Source reference</h3>
          <dl className="app-panel mt-2 grid grid-cols-[7rem_minmax(0,1fr)] gap-2 p-3 text-[13px]">
            <dt className="text-muted">Repository</dt><dd className="break-all">{item.source?.repositoryUrl ?? "Local or account-managed component"}</dd>
            <dt className="text-muted">Path</dt><dd className="break-all">{item.source?.path ?? componentLocations(item)[0]?.location ?? "Not recorded"}</dd>
            <dt className="text-muted">Branch</dt><dd>{item.source?.ref ?? "Unknown"}</dd>
            {item.sourceResolvedRef && <><dt className="text-muted">Source read</dt><dd>Current default branch ({item.sourceResolvedRef})</dd></>}
            <dt className="text-muted">GitHub stars</dt><dd>{!githubSource ?
              <span aria-label="Not applicable">—</span> : item.stars?.toLocaleString() ?? "Unavailable"}</dd>
            <dt className="text-muted">Skill installs</dt><dd>{!githubSource || item.kind !== "skill" ?
              <span aria-label="Not applicable">—</span> : item.installs?.toLocaleString() ?? "Unavailable"}</dd>
          </dl>
        </section>
        {definition && <section className="inspector-section" aria-label="Component content">
          <h3>Content</h3>
          {definition.details.availability === "available" && definition.details.content !== undefined ?
            definition.details.format === "markdown" ?
              <div className="app-panel p-4"><Suspense fallback={<p>Loading content…</p>}><SkillMarkdown content={definition.details.content} sourceUrl={definition.contentUrl} /></Suspense></div> :
              <ValuePanel label={definition.details.format === "json" ? "JSON" : "Text"} value={definition.details.content} /> :
            <p className="app-panel p-3 text-secondary">{definition.details.reason ??
              (definition.remoteApproved ? "The source body is unavailable." : "Only observed metadata is available. The local or private source body was not captured.")}</p>}
          {definition.details.selectionConflict && <p className="mt-2 text-amber-700">This container has different saved selections for its fields. Review them before choosing the container.</p>}
          {definition.details.fields?.length ? <div className="summary-box mt-2"><table className="summary-table">
            <thead><tr><th scope="col">Field</th><th scope="col">Type</th>{definition.details.selectionConflict && <><th scope="col">Codex selection</th><th scope="col">{observationAppName("claude", definition.origins.find(origin => origin.app === "claude"))} selection</th></>}</tr></thead>
            <tbody>{definition.details.fields.map(field => <tr key={field.name}><th scope="row">{field.name}</th><td>{field.type}</td>
              {definition.details.selectionConflict && (["codex", "claude"] as const).map(app => <td key={app}>{field.selections?.[app] == null ? "Not set" : field.selections[app] ? "Included" : "Excluded"}</td>)}</tr>)}</tbody>
          </table></div> : null}
          {definition.details.resourceCount !== undefined && <p className="mt-2">Resource files: {definition.details.resourceCount}</p>}
          {definition.details.files?.length ? <details className="value-panel mt-2"><summary>Resource files</summary>
            <ul className="space-y-1 p-3 text-[13px]">{definition.details.files.map(file => <li key={file} className="break-all">{file}</li>)}</ul>
          </details> : null}
        </section>}
        {componentLocations(item).length > 0 ? <section className="inspector-section" aria-label="Observed locations">
          <h3>Observed locations</h3><div className="app-panel mt-2 p-3"><ComponentLocation item={item} /></div>
        </section> : definition?.origins.length ? <section className="inspector-section" aria-label="Observed locations">
          <h3>Observed locations</h3>
          <div className="values mt-2">{definition.origins.filter(origin => origin.type !== "catalog").map((origin, index) =>
            <dl key={index} className="app-panel grid grid-cols-[7rem_minmax(0,1fr)] gap-2 p-3 text-[13px]">
              {origin.app && <><dt className="text-muted">App</dt><dd>{observationAppName(origin.app, origin)}</dd></>}
              {origin.scope && <><dt className="text-muted">Scope</dt><dd className="break-all">{origin.scope}</dd></>}
              <dt className="text-muted">Location</dt><dd className="break-all">{origin.locator ?? origin.file ?? origin.path ?? "Not recorded"}</dd>
              {origin.parentId && <><dt className="text-muted">Container</dt><dd>{origin.parentName ?? "Parent component unavailable"}</dd></>}
            </dl>)}</div>
        </section> : null}
        {!definition && item.configuration != null && <ValuePanel label="Configuration" value={item.configuration} />}
      </>}
      {presetId && <Comments key={JSON.stringify([presetId, item.id])} presetId={presetId} componentId={item.id} />}
    </div>
  </DetailSheet>;
}


