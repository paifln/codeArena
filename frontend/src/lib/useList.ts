import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
export function useList(path: string, enabled = true) {
  return useQuery<any[]>({
    queryKey: [path],
    queryFn: () => api(path),
    enabled,
    refetchInterval: 10000,
  });
}
