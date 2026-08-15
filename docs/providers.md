# Search API provider catalog

This catalog is a current shortlist of web-search and search-result APIs with a
free allowance or a recurring quota. Provider plans change, so verify the linked
official page before relying on a number. “Credits” are not always one search:
SERP products may charge by result, rendering mode, or successful request.

## Implemented in this CLI

| Provider | Free allowance | Search type | CLI configuration |
| --- | --- | --- | --- |
| [Google Custom Search JSON API](https://developers.google.com/custom-search/v1/overview) | **100 queries/day** | Programmable Search Engine results; daily, not monthly | `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID`, `--provider google_cse` |
| [SerpApi](https://serpapi.com/pricing) | **250 searches/month** on the free plan | SERP scraping/normalization | `SERPAPI_API_KEY`, `--provider serpapi` |
| [ScraperAPI Google SERP](https://docs.scraperapi.com/structured-data-endpoints/search-and-insights/google/google-serp-api.md) | **1,000 API credits/month** on the free plan; separate **5,000-request first-7-days trial** | Structured Google SERP scraping | `SCRAPERAPI_API_KEY`, `--provider scraperapi` |
| [Bright Data SERP API](https://brightdata.com/pricing/serp) | **5,000 free records/month** | Google/Bing SERP scraping via direct REST API | `BRIGHTDATA_API_KEY` + `BRIGHTDATA_SERP_ZONE`, `--provider brightdata` |

The four providers above return the CLI’s normalized JSON result shape. They are
available as explicit (`--provider`) and fallback providers. Bright Data is also
an auto-routing target (Google-SERP scoring, same as Serper; ties are broken by
provider priority so the larger free allowance is used first). The other three
are not intent-routing targets; existing auto-routing behavior is preserved.

For ScraperAPI, the official billing documentation distinguishes the recurring
free plan from the trial: 1,000 API credits are provided each month, while the
5,000 requests are only available during the first seven days after signup.
Credits and requests are not interchangeable units.

Bright Data uses the direct REST endpoint documented in [Send your first request](https://docs.brightdata.com/scraping-automation/serp-api/send-your-first-request).
The configured SERP zone must support parsed JSON; the adapter adds
`brd_json=json` to the Google/Bing target URL.

## Recurring free allowances and additional candidates

| Provider | Current official allowance/status | Notes |
| --- | --- | --- |
| [Tavily](https://docs.tavily.com/documentation/api-credits) | **1,000 API credits/month** on the free plan | Existing adapter; official pricing says no credit card required. Keyless mode is also documented at [Keyless](https://docs.tavily.com/documentation/keyless). |
| [Exa](https://exa.ai/docs/reference/pricing) | **$10 free credits/month** plus initial credits | Existing adapter; credit usage varies by search mode. Payment-method requirement is not established here. |
| [Zenserp](https://zenserp.com/pricing-plans/) | **50 searches/month** | SERP scraping; free plan is explicitly listed. |
| [Naver Search API](https://developers.naver.com/docs/serviceapi/search/web/web.md) | **25,000 calls/day** | Real search API for Naver web documents; daily, not monthly. Requires client ID and client secret. |
| [Baidu Qianfan web search](https://cloud.baidu.com/doc/qianfan-api/s/Wmbq4z7e5) | **100 calls/day** on the current high-performance search page | Daily, not monthly; current product/region and postpaid activation requirements must be checked in the console. |
| [Firecrawl Search](https://docs.firecrawl.dev/features/search) | Public docs do not state a stable standard monthly free quota | Search plus extraction. Eligible partner offers may include **10,000 credits**; see [partner credits](https://docs.firecrawl.dev/partner-credits). |
| [Google Knowledge Graph Search API](https://developers.google.com/knowledge-graph/reference/rest/v1/usage-limits) | Up to **100,000 reads/day** quota at no charge | Entity/knowledge-graph search, not general web SERP. |

## Free trials or non-monthly options

These are useful additions but do **not** satisfy a recurring monthly-quota
requirement as documented on the linked page:

| Provider | Allowance/status | Notes |
| --- | --- | --- |
| [Serper](https://serper.dev/) | 2,500 free queries advertised | Existing adapter; treat as initial/free signup credit unless the account page states otherwise. |
| [ScrapingBee Google Search](https://www.scrapingbee.com/features/google/) | 1,000 free API credits advertised | Google SERP scraping; the public product page does not establish a monthly reset. |
| [serp.cheap](https://serp.cheap/) | 100 free searches on signup | Google SERP API; one-time signup allowance, not recurring. |
| [WebScrapingAPI SERP](https://www.webscrapingapi.com/pricing/serp-api) | 100-request free trial | SERP scraping; not a documented monthly quota. |
| [SearchApi.io](https://www.searchapi.io/pricing) | Free quota not verified on the current public pricing page | Multi-engine SERP API; re-check the account dashboard before integration. |
| [Serpstack](https://serpstack.com/) | Free plan exists; current quota not verified here | SERP scraping; verify the current plan before use. |
| [Mojeek Web Search API](https://www.mojeek.com/services/search/web-search-api/) | No public free monthly quota found | Independent index; pricing appears custom/paid. |
| [Kagi Search API](https://kagi.com/api/pricing) | No public free quota found | Paid search API; not a free-tier candidate. |

## Existing providers in this repository

Querit, Perplexity via Kilo Gateway, You.com, and SearXNG remain supported. Their
free allowances are account/plan dependent or self-hosted; see the official
provider pages before choosing them for a recurring quota:
[Querit](https://querit.ai/), [Kilo Gateway](https://api.kilo.ai/),
[You.com](https://you.com/pricing), and
[SearXNG](https://docs.searxng.org/admin/installation.html).

## Selection guidance

- Prefer Naver when an independent/index-backed search API is more important
  than Google-compatible SERP output.
- Use Google CSE when a daily allowance and a configured Programmable Search
  Engine are acceptable.
- Treat SerpApi, ScraperAPI, Bright Data, Zenserp, and similar services as
  provider-specific SERP credits, not guaranteed page counts.
- Bright Data requires a SERP zone configured for parsed JSON and a direct-API
  key; the CLI does not use the older proxy username/password flow.
- Keep API keys in `.env` or `config.json`; both are gitignored. Do not commit
  credentials or password notes.
