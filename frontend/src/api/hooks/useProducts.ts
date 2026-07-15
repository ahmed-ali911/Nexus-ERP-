import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "../client";

export type ProductType = "RAW_MATERIAL" | "SEMI_FINISHED" | "FINISHED_GOOD";

export interface ProductResponse {
  id: number;
  code: string;
  name_en: string;
  name_ar: string;
  category_id: number;
  product_type: ProductType;
  base_unit_id: number;
  purchase_unit_id: number | null;
  sales_unit_id: number | null;
  barcode: string | null;
  is_active: boolean;
  is_sellable: boolean;
  is_purchasable: boolean;
  is_stockable: boolean;
  is_batch_tracked: boolean;
  company_id: number;
  effective_purchase_unit_id: number;
  effective_sales_unit_id: number;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductCreate {
  code: string;
  name_en: string;
  name_ar: string;
  category_id: number;
  product_type: ProductType;
  base_unit_id: number;
  purchase_unit_id?: number | null;
  sales_unit_id?: number | null;
  barcode?: string | null;
  is_active?: boolean;
  is_sellable?: boolean;
  is_purchasable?: boolean;
  is_stockable?: boolean;
  is_batch_tracked?: boolean;
}

export type ProductUpdate = Partial<ProductCreate>;

const QUERY_KEY = ["products"] as const;

export function useProducts() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const { data } = await apiClient.get<ProductResponse[]>(
        "/api/v1/master-data/products"
      );
      return data;
    },
  });
}

export function useCreateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ProductCreate) => {
      const { data } = await apiClient.post<ProductResponse>(
        "/api/v1/master-data/products",
        payload
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: QUERY_KEY }),
  });
}

export function useUpdateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: ProductUpdate & { id: number }) => {
      const { data } = await apiClient.patch<ProductResponse>(
        `/api/v1/master-data/products/${id}`,
        payload
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: QUERY_KEY }),
  });
}

export function useDeleteProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/api/v1/master-data/products/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: QUERY_KEY }),
  });
}
