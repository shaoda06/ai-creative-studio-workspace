import { useParams } from 'react-router-dom';

export function useChloeScope() {
  const { spaceId = '', context = '' } = useParams();
  const suffix = context ? `/contexts/${encodeURIComponent(context)}` : '';
  return {
    context,
    api: `/api/workspaces/${encodeURIComponent(spaceId)}${suffix}`,
    page: `/spaces/${encodeURIComponent(spaceId)}${suffix}`,
    workspacePage: `/spaces/${encodeURIComponent(spaceId)}`,
  };
}
