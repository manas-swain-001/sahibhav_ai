// Frontend TypeScript models matching backend SahiBhavResponse

export interface CleanedProduct {
  id: string;
  platform_name: string;
  name: string;
  brand?: string | null;
  mrp: number;
  offer_price: number;
  discount_pct: number;
  raw_quantity: string;
  parsed_quantity: number;
  parsed_unit: string;
  standard_unit: string;
  price_per_standard_unit: number;
  rating?: number | null;
  rating_count?: number | null;
  eta_mins?: number | null;
  deeplink?: string | null;
  image_url?: string | null;
  is_available: boolean;
  score: number;
}

export interface CartItemPick {
  item_name: string;
  search_query: string;
  quantity_requested: number;
  unit_requested: string;
  platform: string;
  product: CleanedProduct;
  item_total_price: number;
}

export interface PlatformOrder {
  platform: string;
  items: CartItemPick[];
  items_subtotal: number;
  delivery_fee: number;
  total_order_cost: number;
  subtotal: number;
  eta_mins?: number | null;
}

export interface CartCombination {
  combo_type: "single_platform" | "split_2_platform" | string;
  platforms: string[];
  orders: PlatformOrder[];
  items_subtotal: number;
  total_delivery_fees: number;
  total_price: number;
  max_eta_mins?: number | null;
  average_rating: number;
  composite_score: number;
  savings_vs_highest: number;
  savings_vs_best_single: number;
  is_split_beneficial: boolean;
  fee_explanation?: string | null;
}

export interface OptimizationResult {
  is_valid_grocery_query: boolean;
  detected_language: string;
  best_single_store?: CartCombination | null;
  best_split_combo?: CartCombination | null;
  winning_recommendation?: CartCombination | null;
  all_single_stores: CartCombination[];
  all_split_combos: CartCombination[];
  notes?: string | null;
}

export interface SahiBhavResponse {
  raw_query: string;
  detected_language: string;
  is_valid_grocery_query: boolean;
  natural_language_response: string;
  optimization?: OptimizationResult | null;
  notes?: string | null;
}

export interface PlatformMetadata {
  id: string;
  name: string;
  color: string;
  avg_eta_mins: number;
  free_delivery_above: number;
}
