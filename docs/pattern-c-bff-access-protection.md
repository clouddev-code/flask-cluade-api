# Pattern C: 公開 BFF (Cloud Run) のアクセス保護方式

> 対象: `docs/pattern-c-implementation.md` で採用している
> 「BFF = `--allow-unauthenticated` の Next.js Cloud Run」構成
> 論点: Cloud Run プラットフォームレベルでは無認証になる BFF を、どう保護するか

---

## 1. 結論

**Google アカウント認証 (Google OAuth 2.0 / OIDC) を BFF アプリケーション層で実装することで保護する。**

Cloud Run の `--allow-unauthenticated` は「OAuth コールバックを受け取るために URL を開けておく」ためのものに過ぎず、ユーザーの識別とアクセス制御は完全に BFF コード (`iron-session` + Google OIDC) が担う。

---

## 2. 二段構えの保護モデル

| 層 | 認証 | 役割 |
|---|---|---|
| Cloud Run プラットフォーム層 | なし (`--allow-unauthenticated`) | BFF URL に誰でも到達可 |
| **BFF アプリケーション層** | **Google OAuth → sealed HttpOnly Cookie** | **実際のアクセス保護** |
| バックエンド Cloud Run | IAM (`run.invoker` = BFF SA のみ) | SA ID トークン必須 |

ポイント:
- Cloud Run 層で完全に閉じる (IAP / IAM 必須化) わけではない理由は、Google OAuth のコールバック URL を外部 (accounts.google.com → ユーザーのブラウザ → BFF) からアクセスできるようにするため。
- 「無認証 Cloud Run」と書くと無防備に見えるが、**実体は OAuth でゲートされた SaaS とほぼ同じ構造**。

---

## 3. エンドポイント別の保護状況

`docs/pattern-c-implementation.md:44-63` のシーケンスに準拠。

| エンドポイント | 認証要否 | 理由 |
|---|---|---|
| `GET /api/auth/login` | **不要** | OAuth フローの開始点。Google にリダイレクトするだけ |
| `GET /api/auth/callback` | **不要** (state + PKCE で防御) | OAuth コールバックの受け口。誰でも到達できる必要がある |
| `GET /api/auth/me` | 必要 | Cookie 無しなら 401 |
| `POST /api/auth/logout` | 必要 | Cookie の revoke 対象が必要 |
| `POST /api/chat/stream` | 必要 | 未ログインなら 401、Origin 不一致なら 403 |
| `POST /api/chat/reset` | 必要 | 同上 |

`bff_session` Cookie は Google OAuth を完走したリクエストにのみ発行される (`app/api/auth/callback/route.ts`) ため、「ログインしていない人がチャット API を叩いても 401」になる。

---

## 4. 「特定の Google アカウントだけ」に絞る方法

素の Google OAuth は **Google アカウントを持つ全員** が通ってしまう。社内利用や限定公開なら下記のいずれかを追加する。

### 4-1. OAuth 同意画面を「内部」に設定する (最も簡単)

- 前提: Google Workspace を使っている
- GCP Console → APIs & Services → OAuth consent screen → **User Type: Internal**
- 効果: 同一 Workspace ドメインの Google アカウントしか通らない (Google 側で弾く)
- 追加コード不要

### 4-2. `hd` クレーム検証 (Workspace ドメイン限定、Internal にできない時)

認可リクエストに `hd=example.com` を付与し、`callback/route.ts` で id_token の `hd` クレームを検証する。

```ts
// app/api/auth/login/route.ts
const authUrl = client.generateAuthUrl({
  scope: ['openid', 'email', 'profile'],
  state,
  code_challenge: challenge,
  code_challenge_method: 'S256',
  hd: 'example.com',       // ← 追加
});
```

```ts
// app/api/auth/callback/route.ts
const ticket = await client.verifyIdToken({ idToken: id_token, audience: CLIENT_ID });
const payload = ticket.getPayload();
if (payload?.hd !== 'example.com') {
  return new Response('forbidden', { status: 403 });
}
```

注意: `hd` パラメータは UI ヒントに過ぎず、Google 側で強制されない。**必ず id_token 側でも検証する** こと。

### 4-3. email allowlist (個人 Gmail も混在する場合)

```ts
// app/api/auth/callback/route.ts
const ALLOWED_EMAILS = (process.env.ALLOWED_EMAILS ?? '').split(',').map(s => s.trim());
if (!ALLOWED_EMAILS.includes(payload.email!)) {
  return new Response('forbidden', { status: 403 });
}
```

Secret Manager に `allowed-emails` を置き、`--update-secrets=ALLOWED_EMAILS=allowed-emails:latest` で注入する。

### 4-4. バックエンド側での再検証 (多層防御)

BFF が `X-End-User-Email` をバックエンドに渡しているので、バックエンド側でも allowlist を持って二重チェックすると、BFF の認可ロジックを誤って削っても侵入されない。

```python
# flask-cloud-api-v2/src/app.py
ALLOWED_EMAILS = set(os.environ.get("ALLOWED_EMAILS", "").split(","))

def get_end_user(request):
    email = request.headers.get("X-End-User-Email", "")
    if email not in ALLOWED_EMAILS:
        abort(403)
    ...
```

---

## 5. 別案: BFF を Cloud Run IAM / IAP で守る場合

「Google アカウント認証を BFF アプリで書きたくない」「監査ログを GCP 側で取りたい」場合は、Pattern C ではなく Pattern A (IAP) または Pattern B (IAM + ID token) を選択することになる。

| 案 | BFF 側の認証 | 利点 | 欠点 |
|---|---|---|---|
| **Pattern C (本書)** | OAuth を BFF が実装 | Workspace 不要、IdP 選択肢広い、SPA UX 制御自在 | アプリ層実装が必要 |
| Pattern A (IAP) | Cloud IAP がフロントで Google 認証 | コード不要、監査ログ強い、Context-Aware Access 可 | Workspace / プロジェクト IAM 必須、UX 制限あり |
| Pattern B (IAM のみ) | クライアント側が ID token を取得 | サーバー間呼び出しに最適 | ブラウザ SPA には実質不向き |

詳細比較は `docs/bff-oauth-iap-cloudrun.md` 第3章参照。

---

## 6. 攻撃面と緩和策

| 攻撃面 | 緩和策 |
|---|---|
| 不正ログイン試行 (`/api/auth/login` 連打) | Google OAuth 側で leak / abuse 検知。BFF 側で Cloud Run の rate-limit、必要なら Cloud Armor |
| OAuth コードインジェクション | **state + PKCE** で防御 (`pattern-c-implementation.md` 5-3) |
| CSRF (cross-site POST) | SameSite=Lax + **Origin ヘッダ検証** (`pattern-c-implementation.md` 5-3) |
| Cookie 盗難 (XSS) | HttpOnly + Secure。さらにフロントの XSS 対策 (Next.js のデフォルトサニタイズ + CSP) |
| Cookie 盗難 (中間者) | HTTPS 強制 (Cloud Run は自動)、SESSION_SECRET ローテーション |
| `bff_session` 偽造 | iron-session の AES-256-GCM seal で改ざん検知 |
| BFF URL 直叩きでスクレイピング | OAuth 必須なので未ログインは 401。public ページがある場合は別途 reCAPTCHA / Cloud Armor |
| Google アカウントは持つが社内ではない人 | §4 の Internal / hd / allowlist |
| `X-End-User-*` ヘッダ偽造 | バックエンドは IAM で BFF SA のみ受信、ブラウザから直接付与不可能 |

---

## 7. 運用上の注意

### 7-1. 監査ログ

- バックエンド Cloud Run のリクエストログは `principalEmail` が常に **BFF SA**。
- エンドユーザーの identity は構造化ログで `X-End-User-Email` / `X-End-User-Id` を明示出力すること。
- 必要なら BFF 側でも「誰が何時にログインしたか」をログ出力 (`callback/route.ts`)。

### 7-2. SESSION_SECRET ローテーション

- iron-session の seal 鍵が漏れると Cookie を任意発行できる。
- 6〜12ヶ月毎に rotate。`iron-session` は複数鍵対応 (`password: { 2: 'new', 1: 'old' }`) なので無停止切替可能。

### 7-3. Refresh token の扱い

- Cookie に refresh_token を含めると、`SESSION_SECRET` 漏洩時の被害が大きい。
- 高セキュリティ要件なら refresh_token を Firestore に置き、Cookie には session id のみ持たせる構成へ移行 (`pattern-c-implementation.md` 第8章)。

### 7-4. セッション失効

- sealed cookie 方式は**サーバー側で即時失効ができない** (Cookie の exp まで有効)。
- 強制ログアウト要件があるなら Firestore セッション + revocation flag が必須。

---

## 8. まとめ

- Pattern C の「公開 Cloud Run BFF」のアクセス保護 = **Google OAuth + sealed HttpOnly Cookie をアプリ層で実装** で正しい理解。
- Cloud Run の `--allow-unauthenticated` は OAuth コールバックを受けるための開口部であり、無防備という意味ではない。
- 不特定多数の Google ユーザーに使わせたくないなら、**OAuth 同意画面を Internal にする** のが最も簡単で確実。Internal にできない場合は `hd` クレーム検証または email allowlist を追加する。
- GCP プラットフォーム層で守りたいなら Pattern A (IAP) を選択する。
