export async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw Object.assign(new Error((await response.text()) || `读取失败（${response.status}）`), { status: response.status });
  return response.json();
}
export const projectUrl = (name: string) => `/api/projects/${encodeURIComponent(name)}`;
export const styleUrl = (path: string) => `/api/krea2/files/${path.split('/').map(encodeURIComponent).join('/')}`;
export interface DialogueLine { shot: string; index: number; speaker: string; original: string }
export interface GenerationContext {
  dialogues?: DialogueLine[];
  shotTimingSource?: 'recorded' | 'plan';
  scriptHtml: string; scriptUrl?: string; source?: string; issues: string[];
  shots: { id: string; duration: number | null; start?: number; html: string }[];
  prompts: { english: string; chinese: string; englishUrl?: string; chineseUrl?: string };
  references: Record<'common' | 'segment', { name: string; label: string; kind: 'image' | 'video' | 'audio'; url?: string; missing?: boolean }[]>;
}
// One recorded revision/stage; url and fileRevision are empty until a video exists.
export interface VideoProduct {
  id: string; label: string; default: boolean; key: string; url: string; fileRevision: string;
  previewUrl?: string; previewRevision?: string; previewNote?: string;
}
export interface SegmentVideo {
  adoptionKnown?: boolean;
  contextUrl?: string;
  products?: VideoProduct[];
  downloadUrl?: string;
  previewNote?: string;
  reviewFileRevision?: string; key: string; url: string; run: string; stage: string; approved: boolean; candidateNumber: number; context?: GenerationContext; fileRevision: string; deliveryStatus: string; taskStatus: string; taskStateUrl?: string; checkedAt: string }
export type ProductionWorkflow = 'aimixer' | 'songssx';
export interface SongssxScene {
  recorded: boolean;
  video?: SegmentVideo;
  segments: { id: string; gen: number; start: number; end: number; context?: GenerationContext }[];
}
export interface SceneRound { number: number; created_at: string; note?: string; episodeRound?: boolean; record?: FileItem | null; reviewOutputs?: FileItem[]; script: (FileItem & { version: string }) | null; storyboard: (FileItem & { version: string }) | null; issues: string[]; songssx?: SongssxScene; segments: { key?: string; carried?: boolean; id: string; duration: number; stage: string; run: string; scriptHtml: string; scriptUrl: string; shotIds?: string[] }[] }
export type DirectorSheetImage = FileItem & { page: number; version: string; sourceVersion: string; candidateNumber?: number | null; adopted?: boolean; sourceRecord?: FileItem };
export interface DirectorSheets { formal: DirectorSheetImage[]; candidates: DirectorSheetImage[]; history?: DirectorSheetImage[]; record: FileItem | null }
export interface FileItem {
  productionWorkflow?: ProductionWorkflow;
  productionWorkflows?: ProductionWorkflow[];
  workStatusLabel?: string;
  hasArchive?: boolean; productionTask?: FileItem | null; roundHistory?: FileItem | null; workStatus?: { label: string; summaryHtml: string; deliverySummary: string; record: FileItem }; readOnly?: boolean; jianying?: { jypack: string | null; zip: string | null }; materialGroup?: string; materialStatus?: string; materialNote?: string; materialReview?: FileItem; version?: string; directorSheets?: Record<string, DirectorSheets>; storyboardIndex?: FileItem | null; generationPlan?: FileItem | null; videoPrompts?: FileItem[]; materials?: FileItem[]; materialRecord?: FileItem | null; episodeRounds?: { number: number; scenes: string[] }[]; sceneRounds?: Record<string, SceneRound[]>; warnings?: string[]; previousEpisode?: FileItem | null; kind: string; name: string; title?: string; titleStatus?: string; productionComplete?: boolean; scenes?: string[]; productionIssues?: { key: string; message: string; scene?: string }[]; script?: FileItem | null; storyboards?: Record<string, FileItem>; segments?: Record<string, { id: string; label?: string; duration: number; historical?: boolean; planned?: boolean; scriptHtml: string; scriptUrl?: string; shotIds?: string[]; videos: SegmentVideo[] }[]>; key?: string; url?: string; children?: FileItem[]; files?: FileItem[]; summary?: string; category?: string; statusHtml?: string; approvalHtml?: string; sourceHtml?: string; duration?: string; media?: FileItem; doc?: Record<string, unknown>; prompts?: { english?: string; chinese?: string };
}
export interface Group { name: string; files: FileItem[] }
// Source records contain stage-specific fields; retain their original keys and text.
export type RecordData = Record<string, any>;

export function searchTree(items: FileItem[], search: string): FileItem[] {
  if (!search) return items;
  return items.flatMap(item => {
    if ((item.name + (item.summary || '')).toLowerCase().includes(search.toLowerCase())) return [item];
    const children = searchTree(item.children || item.files || [], search);
    return children.length ? [{ ...item, children, files: undefined }] : [];
  });
}

export interface ProjectArchive { status: 'active' | 'archived'; reason: string; archivedAt: string; restoredAt: string }
export interface WorkspaceSpace { project_layout?: 'flat' | 'nested'; id: string; name: string; view: 'serial-drama' | 'iris-commercial' | 'chloe-commerce' | 'files'; projects: { id: string; name: string; archive?: ProjectArchive }[] }
export function numberProjects(projects: WorkspaceSpace['projects']) {
  const counts = { active: 0, archived: 0 };
  return projects.map(project => ({ ...project, number: ++counts[project.archive?.status === 'archived' ? 'archived' : 'active'] }));
}
export const spaceProjectPath = (space: WorkspaceSpace, name: string) => space.view === 'serial-drama'
  ? `/projects/${encodeURIComponent(name)}` : space.project_layout === 'nested' ? `/spaces/${space.id}/contexts/${encodeURIComponent(name)}` : `/spaces/${space.id}/projects/${encodeURIComponent(name)}`;
