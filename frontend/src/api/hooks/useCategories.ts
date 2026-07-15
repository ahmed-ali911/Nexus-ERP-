import { useQuery } from "@tanstack/react-query";
import apiClient from "../client";

export interface CategoryResponse {
  id: number;
  code: string;
  name_en: string;
  name_ar: string;
  parent_id: number | null;
  is_active: boolean;
  company_id: number;
  is_deleted: boolean;
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: async () => {
      const { data } = await apiClient.get<CategoryResponse[]>(
        "/api/v1/master-data/categories"
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
