GRANT SELECT ON TABLE public.ohlc_bars_v2 TO anon;

GRANT EXECUTE ON FUNCTION public.get_chart_data_v2(
  UUID,
  VARCHAR,
  TIMESTAMPTZ,
  TIMESTAMPTZ
) TO anon;
