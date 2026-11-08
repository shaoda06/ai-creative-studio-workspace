import { useMemo } from 'react';
import type { ProductionAccess } from './components/ProductionAccess';

export function useChloeProductionAccess(baseUrl: string, selected: string | null) {
  const projectUrl = (unit: string) => `${baseUrl}/projects/${encodeURIComponent(unit)}`;
  const workUrl = (unit: string) => `${projectUrl(unit)}/works/${encodeURIComponent(unit.split('-')[0])}`;
  return useMemo<ProductionAccess>(() => ({
    unitKind: 'work', unitDisplayName: unit => unit.split('-')[0], storyboardLabel: '分镜脚本', sourceDocumentLabel: '脚本', showStoryboardEditor: false, namespace: () => baseUrl,
    detail: (_, unit) => workUrl(unit) + '/production-detail',
    scope: (_, unit, scene) => ({ project: unit, episode: unit, scene, label: `${unit}整片`,
      notesUrl: workUrl(unit) + '/production-notes', stateKey: `${baseUrl}/${unit}/${scene}` }),
    notesSummary: scope => workUrl(scope.episode) + '/production-notes',
    notes: scope => workUrl(scope.episode) + '/production-notes',
    downloads: (_, unit, scene) => workUrl(unit) + '/production-downloads?scene=' + encodeURIComponent(scene),
    package: (_, unit) => projectUrl(unit) + '/download',
    document: (_, path) => projectUrl(selected!) + '/document?path=' + encodeURIComponent(path),
  }), [baseUrl, selected]);
}
