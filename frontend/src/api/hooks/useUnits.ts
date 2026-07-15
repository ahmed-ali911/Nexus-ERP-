import { useQuery } from "@tanstack/react-query";
import apiClient from "../client";

export type UnitType = "WEIGHT" | "COUNT" | "VOLUME";

export interface UnitResponse {
  id: number;
  code: string;
  name_en: string;
  name_ar: string;
  symbol: string;
  unit_type: UnitType;
  is_active: boolean;
  company_id: number;
  is_deleted: boolean;
}

export function useUnits() {
  return useQuery({
    queryKey: ["units"],
    queryFn: async () => {
      const { data } = await apiClient.get<UnitResponse[]>(
        "/api/v1/master-data/units"
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
