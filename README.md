# Prototype data

Nine official and secondary documents about fuel prices and subsidies, plus a script for the weekly price dataset. Collected 7 October 2026.

## Folder contents

| Item | What it is |
|---|---|
| `docs/*.txt` | One document per file, with a header (title, issuer, date, source URL, official or secondary) and the text below `---` |
| `metadata.csv` | One row per document: date, effective date, topic, fuel type, region, language, official or not, what it supersedes |
| `prepare_fuel_prices.py` | Turns the weekly price CSV into short text documents (standard library only) |

## Still to do by hand

1. Download `https://storage.data.gov.my/commodities/fuelprice.csv` in your browser and save it as `fuelprice.csv` in this folder. (My workspace could not reach that site.)
2. Run `python prepare_fuel_prices.py 26` for the last 26 weeks. The script lists the CSV columns it finds, so if a column name differs, edit the `LABELS` table at the top. I tested it on a sample file, not the real one.

## Timeline from the documents (a summary, not a source)

| Date | Event | Document |
|---|---|---|
| Oct to Nov 2024 | Diesel in Sabah, Sarawak and Labuan: RM2.15 per litre (Peninsular RM2.95) | `mof_2024-10-16`, `mof_2024-10-23`, `mof_2024-11-13` |
| 11 Mar 2026 | RON95 kept at RM1.99 (BUDI95). Sabah and Sarawak diesel kept at RM2.15. Budi Diesel assistance raised from RM200 to RM300 a month | `mof_2026-03-11_budi95_diesel_assistance` |
| 26 Mar 2026 | Subsidy cost about RM4 billion a month. BUDI95 monthly limit cut from 300 to 200 litres from 1 Apr 2026 | `mof_2026-03-26_subsidy_cost_rm4bn` |
| 7 Apr 2026 | MOF says the 200-litre limit stays, and claims of a general "additional limit" application are false | `rtm_2026-04-07_200_litre_limit_stays` |
| 23 Jun 2026 | Reported: subsidised diesel RM2.10 per litre nationwide from 1 Jul 2026 | `paultan_2026-06-23_budi_diesel_faq` |
| 31 Aug 2026 | Monthly limit raised from 200 to 300 litres from 1 Sep 2026 (pickups and jeeps with the extra 100 litres: 400). Diesel at RM2.10 | `rtm_2026-08-31_limit_raised_to_300` |

**The "conflicts" are really changes over time.** Sarawak diesel was RM2.15, then RM2.10 from 1 July 2026. The monthly limit went 300, then 200 (1 Apr), then back to 300 (1 Sep). The assistant's job is to answer with the value that applies on a given date, and to say which document it came from.

## Caveats

- The text was captured with an automated fetch. Compare against the source page before you present.
- The Paul Tan file is a summary of the article, and the 31 Aug file is an English rendering of the Malay RTM article.
- Two RTM links ("dinaikkan secara automatik" and "kembali 300 liter") returned the same article, so only one file is included.
- The RM2.10 price comes from Paul Tan and from the RTM article, not directly from an MOF page I opened. Find the MOF source if you can.
- Credit data.gov.my and the Ministry of Finance (CC BY 4.0) for the price dataset.
