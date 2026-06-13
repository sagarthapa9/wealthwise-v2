# Sample CSV Files

Test files for the CSV import feature. Format accuracy verified against web sources and community documentation.

| File | Broker | Verified? | Source |
|------|--------|-----------|--------|
| `sample-trading212.csv` | Trading 212 Invest/ISA | ✅ Confirmed | [Community discussion](https://community.trading212.com/t/csv-headers-with-different-currency/60788) — 19 columns, currency suffixes on some headers |
| `sample-ajbell.csv` | AJ Bell Youinvest | ✅ Confirmed | [Sharesight integration docs](https://www.sharesight.com/uk/partners/aj-bell/) — 7 columns |
| `sample-hargreaves.csv` | Hargreaves Lansdown | ⚠️ Project spec | Original WealthWise parser spec — not independently verified |
| `sample-vanguard.csv` | Vanguard UK | ⚠️ Project spec | Original WealthWise parser spec — transaction history format (18-month limit) |
| `sample-international.csv` | Generic multi-currency | 🧪 Test data | Manufactured to test USD/GBP mixed portfolios |

## Notes

- Trading 212 headers can include currency suffixes like `Result (GBP)` — our parser strips these during matching
- AJ Bell uses `Instrument code` instead of `Ticker` — our alias table maps both
- Vanguard UK index funds often have **no ticker** — the parser flags these as valid-but-unenriched
- Hargreaves Lansdown uses SEDOL codes (7 chars, starts with letter) for funds, not ISINs or tickers
