# web-search-cli

`hermes-web-search-plus` の検索機能を置き換えるCLIおよびCodex Skillです。

Hermesのプラグインホストを置き換えるものではありません。複数プロバイダー検索、auto-routing、プロバイダーのfallback/cooldown、キャッシュ、ドメイン・期間フィルター、Exaのdeep mode、JSON出力に対応します。

英語版README: [README.md](README.md)

## クイックスタート

```bash
cp .env.example .env
pip install .
web-search-plus --query "OpenAI news today" --provider auto --max-results 5 --compact
```

開発時はeditable installも利用できます。

```bash
pip install -e .
web-search-plus --query "LLM scaling laws research" --provider auto --max-results 5
```

チェックアウトせずにGitHubから最新版を直接インストールする場合は、次を実行します。

```bash
pip install git+https://github.com/TOSUKUi/web-search-cli-skill
```

チェックアウトせずにインストールする場合は、認証情報をプロセスの環境変数または明示的な`--config PATH`で指定してください。`.env.example`はGitHubリポジトリにあります。

インストールされるCLIは、`pyproject.toml`の`web-search-plus` console scriptです。

## 残量ダッシュボード（Web UI）

どのプロバイダーのAPIキーが設定済みで、残量がどれだけ残っているかをブラウザで確認できます。

```bash
python -m web_search_cli.webui --port 8901   # その後 http://127.0.0.1:8901/ を開く
```

`--open`でデフォルトブラウザを自動で開きます。`WSP_WEBUI_PORT`・`WSP_WEBUI_HOST`で既定値を変更できます。

ページはCLIと同じconfig/envの読み込み経路で認証情報を確認し、各プロバイダーの公式使用量APIを直接参照します（読み取りのみで検索は消費しません）。

| プロバイダー | 残量API |
| --- | --- |
| Tavily | `GET /usage` — プランの使用量/上限 |
| SerpApi | `GET /account.json` — 残り検索数・月次リセット日 |
| ScraperAPI | `GET /account` — 残りクレジット・請求リセット日 |
| Serper、Exa、Querit、You.com、Perplexity、Google CSE、Bright Data、SearXNG | 公開の使用量APIなし — カードに設定有無とダッシュボードリンクを表示 |

ページとAPIは認証情報の値そのものを一切公開しません（設定有無と件数のみ）。

### 使用量ログ

CLI での検索成功ごとに `~/.cache/web-search-cli/usage.jsonl` へ1件追記されます（追記のみ・失敗しても検索は妨げません）。ダッシュボードには集計結果（プロバイダー別の検索回数・最終利用・Exa は累積コスト）を表示します。Exa は各レスポンスの `costDollars` から1回あたりのコストを記録し、無料枠（月 $10 相当）の残り推定に使えます。

レスポンスヘッダーのうち残量を示すもの（`x-remaining`、`x-ratelimit-*`、`x-quota-*` など）は全プロバイダーで自動捕捉し、あればログに記録します。現状どのプロバイダーも送信していないためログのヘッダー欄は空ですが、将来追加されればコード変更なしで表示されます。

## Docker Composeによる中央サーバー

`docker-compose.yml`で、APIキーと設定ファイルをイメージに含めず中央サーバーを起動できます。

```bash
cp .env.example .env
cp config.example.json config.json
# 必要に応じてWSP_SERVER_TOKENとプロバイダーの認証情報を.envに設定
docker compose up -d --build
docker compose ps
docker compose logs -f web-search-central
```

デフォルトではホストの`8765`番ポートで待ち受けます。変更する場合は`WSP_PUBLISHED_PORT`を設定してください。

```bash
web-search-plus --satellite http://127.0.0.1:8765 \
  --query "latest AI news" --compact
```

`WSP_SERVER_TOKEN`を設定した場合は、Satellite側で`--satellite-token "<トークンの値>"`を追加してください。`WSP_SERVER_TOKEN`は任意です。設定した場合だけBearer認証が有効になります。サーバー自身の実行中なら`GET /openapi.json`でAPI仕様（OpenAPI 3.0）を取得できます。`config.json`はread-onlyでマウントされ、キャッシュはDocker named volumeに保存されます。`.env`と`config.json`はコミットしないでください。

## 対応プロバイダー

- `auto`
- `serper`
- `tavily`
- `querit`
- `exa`
- `perplexity`
- `you`
- `searxng`
- `google_cse`
- `serpapi`
- `scraperapi`
- `brightdata`

無料枠・月間クォータの比較は[docs/providers.md](docs/providers.md)を参照してください。

Bright Dataでは`BRIGHTDATA_API_KEY`とSERP zone（`BRIGHTDATA_SERP_ZONE`または`config.json`の`brightdata.zone`）が必要です。

ライブ検索には、少なくとも1つのプロバイダー認証情報またはSearXNGインスタンスが必要です。

## 実行モード

### Standalone mode（デフォルト）

CLIがローカルで検索を実行します。認証情報と`config.json`/`.env`はローカルマシンから読み込みます。`.env`は必須ではなく、プロセスの環境変数を直接指定して実行することもできます。

```bash
EXA_API_KEY=your-exa-key web-search-plus \
  --provider exa --query "latest AI news" --compact
```

`export NAME=value`で後続コマンド向けに設定することもできます。同じ変数が`.env`とプロセス環境の両方にある場合は、プロセス環境の値が優先されます。

`--serve`や`--satellite`を指定しない場合はこのモードです。

### Server mode（中央サーバー）

`--serve`で中央HTTPサーバーを起動します。プロバイダーの認証情報と設定は中央サーバー側で管理され、Satelliteから受け取った検索を中央で実行します。

```bash
web-search-plus --serve \
  --config /srv/web-search/config.json \
  --server-host 127.0.0.1 --server-port 8765
```

`WSP_SERVER_TOKEN`/`--server-token`は任意です。設定した場合、Satellite側にも同じ値を`--satellite-token`で指定します。未設定の場合は認証なしになるため、信頼できるネットワーク内で使用してください。組み込みサーバーはHTTPのみなので、外部公開時はTLSリバースプロキシまたはSSHトンネルを利用してください。サーバーは `POST /search` / `GET /health` / `GET /openapi.json` を提供します。API仕様は[中央サーバーのHTTP APIとopenapi.json](#中央サーバーのhttp-apiとopenapijson)を参照してください。

### Satellite mode（クライアント）

`--satellite URL`を指定すると、ローカルでプロバイダーを呼ばず、中央サーバーへ検索を転送します。Satellite側にプロバイダーAPIキーは不要です。

```bash
web-search-plus --satellite http://127.0.0.1:8765 \
  --satellite-token "..." \
  --provider auto --query "..." --compact
```

プロバイダー認証情報は中央サーバー側で解決されます。Satelliteから中央設定や認証情報を送信先ごと上書きすることはできません。`WSP_SATELLITE_URL`でもSatellite modeを選択できます。

### 中央サーバーのHTTP APIと`openapi.json`

中央サーバーは自分のAPI仕様を OpenAPI 3.0 文書として `GET /openapi.json` で公開します。文書はインストール済みのCLIパーサーから生成されるため、公開されるフラグ・型・列挙値は常にそのサーバーが実際に受け付けるものと一致します（手書き仕様がズレることはありません）。

```bash
curl -H "Authorization: Bearer $WSP_SERVER_TOKEN" http://127.0.0.1:8765/openapi.json

# サーバーを起動せずに同じ文書を表示
web-search-plus --openapi > openapi.json
```

`POST /search`は次の2つの等価な形式を受け取ります。どちらで送っても中央CLIと同じ検索が実行されます。

```bash
# CLIのargv形式
curl -X POST http://127.0.0.1:8765/search \
  -H "Authorization: Bearer $WSP_SERVER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"argv": ["--provider", "auto", "--query", "latest AI news", "--compact"]}'

# 名前付きフィールド形式（同じ列挙値で送信時に検証される）
curl -X POST http://127.0.0.1:8765/search \
  -H "Authorization: Bearer $WSP_SERVER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"query": "latest AI news", "provider": "auto", "max_results": 5, "compact": true}'
```

JSONでない、既知フィールドがない、`query`/`similar_url`がない、未知のフィールド、列挙値外、拒否されたフラグはいずれもHTTP 400を返します。拒否されるのは、認証情報を含むリクエストの送信先を奪うもの（`--config`、`--searxng-url`、`--querit-base-url`、`--querit-base-path`）と別のサーバー/Satelliteを起動するもの（`--serve`、`--satellite*`）で、文書内の `x-web-search-plus.unexposedFlags` に理由付きで列挙されます。

## 設定

CLIは次を読み込みます。

- リポジトリルートの`.env`
- リポジトリルートの`config.json`（`--config`で変更可能）
- 環境変数

Server modeでは、`--config`で指定した設定ファイルと同じディレクトリの`.env`も読み込みます。検索結果のキャッシュはデフォルトで`~/.cache/web-search-cli`に保存されます。`WSP_CACHE_DIR`で変更できます。

### 複数APIキー

1つのプロバイダーに複数のAPIキーを設定する場合は、環境変数をカンマ区切りにします。左側のキーから順に使用し、失敗した場合は次のキーを試します。

```bash
SERPER_API_KEY=serper-key-1,serper-key-2
TAVILY_API_KEY=tavily-key-1,tavily-key-2
```

`config.json`では文字列または配列も利用できます。

```json
{
  "serper": {
    "api_key": ["serper-key-1", "serper-key-2"]
  }
}
```

既存の単一`PROVIDER_API_KEY`設定も引き続き利用できます。APIキーにカンマが含まれる場合は、`config.json`の配列形式を使用してください。

## 主な環境変数

```bash
SERPER_API_KEY=
TAVILY_API_KEY=
EXA_API_KEY=
QUERIT_API_KEY=
PERPLEXITY_API_KEY=
KILOCODE_API_KEY=
YOU_API_KEY=
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_ID=
SERPAPI_API_KEY=
SCRAPERAPI_API_KEY=
BRIGHTDATA_API_KEY=
BRIGHTDATA_SERP_ZONE=
SEARXNG_INSTANCE_URL=
SEARXNG_ALLOW_PRIVATE=0
WSP_SATELLITE_URL=
WSP_SATELLITE_TOKEN=
WSP_SERVER_TOKEN=
WSP_PUBLISHED_PORT=8765
```

`SEARXNG_INSTANCE_URL`がLANやDockerなどのプライベート／内部アドレスを指す場合は、`SEARXNG_ALLOW_PRIVATE=1`に変更してください。公開インスタンスでは`0`のままにします。この設定は内部ネットワーク向けURLの保護を無効にします。

## Codex Skill

Codex Skillは[skills/web-search-plus-cli/SKILL.md](skills/web-search-plus-cli/SKILL.md)にあります。ローカルワークスペースから現在のWeb情報が必要な場合に、このCLIを使うための指示を提供します。

## 検証

ネットワークを使わない確認:

```bash
web-search-plus --help
web-search-plus --cache-stats --compact
web-search-plus --explain-routing --query "alternatives to Notion" --compact
python -m unittest discover -v
```
