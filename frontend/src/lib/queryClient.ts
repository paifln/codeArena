import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, refetchOnWindowFocus: true, staleTime: 1000 },
  },
});

export function clearPrivateQueries() {
  const filters = {
    predicate: (q: { queryKey: readonly unknown[] }) =>
      !["status", "me"].includes(String(q.queryKey[0])),
  };
  void queryClient.cancelQueries(filters);
  queryClient.removeQueries(filters);
}
