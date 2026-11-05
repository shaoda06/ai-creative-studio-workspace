import { ProductionWorkbench } from './ProductionWorkbench';

// Nora keeps its public entry and all existing state/API behavior.
export function EpisodeProduction(props: Parameters<typeof ProductionWorkbench>[0]) {
  return <ProductionWorkbench {...props} />;
}
