// Test YFinance API directly
const symbol = "AAPL";
const interval = "1h"; // Test hourly data

// Nov 14, 2024 to Dec 14, 2024
const start = Math.floor(new Date("2024-11-14").getTime() / 1000);
const end = Math.floor(new Date("2024-12-14").getTime() / 1000);

const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=${interval}&period1=${start}&period2=${end}`;

console.log(`Fetching: ${url}`);
console.log(`Start: ${start} (${new Date(start * 1000).toISOString()})`);
console.log(`End: ${end} (${new Date(end * 1000).toISOString()})`);

try {
  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0",
    },
  });

  console.log(`Response status: ${response.status}`);

  if (!response.ok) {
    const text = await response.text();
    console.log(`Error response: ${text}`);
  } else {
    const data = await response.json();
    const result = data.chart?.result?.[0];

    if (!result) {
      console.log("No result in response");
      console.log(JSON.stringify(data, null, 2));
    } else {
      const timestamps = result.timestamp || [];
      const quotes = result.indicators?.quote?.[0];

      console.log(`Timestamps: ${timestamps.length}`);

      if (timestamps.length > 0) {
        console.log(`First timestamp: ${timestamps[0]} (${new Date(timestamps[0] * 1000).toISOString()})`);
        console.log(`Last timestamp: ${timestamps[timestamps.length - 1]} (${new Date(timestamps[timestamps.length - 1] * 1000).toISOString()})`);
        console.log(`First bar: open=${quotes.open[0]}, high=${quotes.high[0]}, low=${quotes.low[0]}, close=${quotes.close[0]}, volume=${quotes.volume[0]}`);
      }
    }
  }
} catch (error) {
  console.error("Error:", error);
}
