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

インストールされるCLIは、`pyproject.toml`の`web-search-plus` console scriptです。

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

`WSP_SERVER_TOKEN`を設定した場合は、Satellite側で`--satellite-token "<トークンの値>"`を追加してください。`WSP_SERVER_TOKEN`は任意です。設定した場合だけBearer認証が有効になります。`config.json`はread-onlyでマウントされ、キャッシュはDocker named volumeに保存されます。`.env`と`config.json`はコミットしないでください。

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

CLIがローカルで検索を実行します。認証情報と`config.json`/`.env`はローカルマシンから読み込みます。

```bash
web-search-plus --provider auto --query "..." --compact
```

`--serve`や`--satellite`を指定しない場合はこのモードです。

### Server mode（中央サーバー）

`--serve`で中央HTTPサーバーを起動します。プロバイダーの認証情報と設定は中央サーバー側で管理され、Satelliteから受け取った検索を中央で実行します。

```bash
web-search-plus --serve \
  --config /srv/web-search/config.json \
  --server-host 127.0.0.1 --server-port 8765
```

`WSP_SERVER_TOKEN`/`--server-token`は任意です。設定した場合、Satellite側にも同じ値を`--satellite-token`で指定します。未設定の場合は認証なしになるため、信頼できるネットワーク内で使用してください。組み込みサーバーはHTTPのみなので、外部公開時はTLSリバースプロキシまたはSSHトンネルを利用してください。

### Satellite mode（クライアント）

`--satellite URL`を指定すると、ローカルでプロバイダーを呼ばず、中央サーバーへ検索を転送します。Satellite側にプロバイダーAPIキーは不要です。

```bash
web-search-plus --satellite http://127.0.0.1:8765 \
  --satellite-token "..." \
  --provider auto --query "..." --compact
```

プロバイダー認証情報は中央サーバー側で解決されます。Satelliteから中央設定や認証情報を送信先ごと上書きすることはできません。`WSP_SATELLITE_URL`でもSatellite modeを選択できます。

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
