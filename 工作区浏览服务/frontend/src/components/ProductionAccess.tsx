import { createContext, useContext } from 'react';
import { projectUrl } from '../api';
import { sceneNotesUrl } from '../revisionNotes';
import type { NoteScope } from './RevisionNotes';

// Business adapters supply addresses and terms; the complete reviewer stays shared.
export interface ProductionAccess {
  unitKind: 'episode' | 'work';
  storyboard?: (unit: string, scene: string) => string;
  namespace: (project: string) => string;
  detail: (project: string, unit: string) => string;
  scope: (project: string, unit: string, scene: string) => NoteScope;
  notesSummary: (scope: NoteScope) => string;
  notes: (scope: NoteScope, scene: string) => string;
  downloads: (project: string, unit: string, scene: string) => string;
  package: (project: string, unit: string) => string;
  document: (project: string, path: string) => string;
}
export const noraProductionAccess: ProductionAccess = {
  unitKind: 'episode',
  storyboard: (unit, scene) => `09-剧集制作/${unit}/03-分镜脚本/${unit}-${scene}-场次分镜.md`,
  namespace: project => project,
  detail: (project, unit) => `${projectUrl(project)}/episodes/${unit}`,
  scope: (project, episode, scene) => ({ project, episode, scene }),
  notesSummary: scope => `${projectUrl(scope.project)}/revision-notes/${scope.episode}`,
  notes: (scope, scene) => sceneNotesUrl(scope.project, scope.episode, scene),
  downloads: (project, unit, scene) => `${projectUrl(project)}/episodes/${unit}/downloads?scene=${encodeURIComponent(scene)}`,
  package: (project, unit) => `${projectUrl(project)}/episodes/${unit}/download`,
  document: (project, path) => `${projectUrl(project)}/document?path=${encodeURIComponent(path)}`,
};
export const ProductionAccessContext = createContext<ProductionAccess>(noraProductionAccess);
export const useProductionAccess = () => useContext(ProductionAccessContext);
