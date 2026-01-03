CREATE TABLE IF NOT EXISTS public.symbol_model_weights (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id uuid NOT NULL REFERENCES public.symbols(id) ON DELETE CASCADE,
    horizon text NOT NULL,
    rf_weight numeric,
    gb_weight numeric,
    synth_weights jsonb NOT NULL DEFAULT '{}'::jsonb,
    diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_updated timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(symbol_id, horizon)
);

CREATE INDEX IF NOT EXISTS idx_symbol_model_weights_symbol_horizon
ON public.symbol_model_weights(symbol_id, horizon);
