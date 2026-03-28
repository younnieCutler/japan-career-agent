# Japan Recruit AI Agent

---

**[한국어](#한국어) | [日本語](#日本語) | [English](#English)**

---

<a name="한국어"></a>
## 한국어

일본 IT/마케팅 전직 시장에서 대형 에이전트(リクルート、パーソルキャリア 등)의 내부 매칭 알고리즘을 리버스 엔지니어링하여 시뮬레이션하는 AI 에이전트 스킬 모음입니다.

> **에이전시 매칭 알고리즘을 리버스 엔지니어링하라.**
>
> 단순한 이력서 첨삭을 넘어, 지원 전 에이전트의 내부 시선으로 나를 먼저 객관화하세요.

### Agent Skills

3개의 에이전트 스킬이 각각의 폴더에 `SKILL.md` 파일로 존재합니다.

**1. job-seeker-agent (구직자 에이전트)**
후보자 담당 컨설턴트(CA)의 시점으로 내 이력서를 분석합니다. 대화형으로 진행되는 SPI3 진단과 포터블 스킬(Portable Skills) 분석을 통해 진짜 강점을 찾아내고, 이력서를 전략적으로 리프레이밍합니다.

**2. hiring-manager-agent (채용 매니저 에이전트)**
기업 담당 컨설턴트(RA)의 시점으로 구인공고(JD)를 최적화합니다. 팀 내 하이퍼포머(Hyperformer)를 모델링하고, 에이전시의 스킬 온톨로지(Ontology)가 잘 인식할 수 있도록 JD를 재작성합니다.

**3. matching-simulator (매칭 시뮬레이터)**
양측(CA/RA)의 시점과 데이터를 통합하여 최종 매칭 스코어와 합격 확률을 시뮬레이션합니다. 리쿠르트 방식(SPI3)과 파솔 방식(시맨틱 유사도)의 알고리즘을 모두 사용하여 체계적인 결과를 제공합니다.

### 핵심 매칭 포인트

- **100% 알고리즘 기반** — 감성적인 칭찬을 배제하고 철저히 데이터와 근거(Evidence)에 기반한 냉정한 전략적 산출
- **Interactive Mode** — 일방적인 출력이 아닌, 실제 컨설팅처럼 질문하고 답을 기다리는 대화형 진단 프로세스 (한 번에 2~3개 질문)
- **Anti-Hallucination** — 모든 평가는 사용자가 제공한 텍스트에서 명시적인 근거를 인용해야만 점수로 인정
- **Cross-Skill Pipeline** — 에이전트 간 YAML 데이터를 기반으로 구직자 프로필과 기업 프로필을 손실 없이 매칭 연동

### 사용법

1. 레포지토리를 클론하거나 필요한 에이전트 폴더를 다운로드합니다.
2. AI 에디터나 채팅창(Claude Code, ChatGPT, Gemini 등)에 해당 폴더의 `SKILL.md` 파일을 참조시키세요. (예: `@job-seeker-agent/SKILL.md`)
3. 에이전트가 호출되면, 내 이력서 파일(예: `@경력기술서.md`)을 전달합니다. (타겟 구인공고 JD가 있다면 함께 첨부하면 갭 분석(Gap Analysis)이 즉시 발동됩니다.)

이후에는 AI가 던지는 진단 질문에 답변하며 컨설팅을 진행하면 됩니다.

### 추천 실행 조합

| 상황 | 추천 에이전트 로드맵 |
|------|-----------|
| **내 이력서 강점 분석 및 리프레이밍** | `/job-seeker-agent` 단독 실행 |
| **특정 공고(JD) 합격 확률 시뮬레이션** | `/job-seeker-agent` 진행 후 ➔ `/matching-simulator` |
| **기업에서 매력적인 구인공고(JD) 작성** | `/hiring-manager-agent` 단독 실행 |

### 기술 및 프레임워크 기반

- **SPI3** (성격/직무 적합도 진단)
- **포터블 스킬 8요소** (후생노동성/리쿠르트 표준 직무 수행 능력)
- **Hataraku Well-being Index** (파솔그룹 조직 문화 지표)
- **Skill Ontology Mapping** (직무 역량 의미 연결망)

### 기여 및 피드백

GitHub Issue 또는 Pull Request를 통해 다양한 프레임워크나 엣지 케이스 추가를 환영합니다.

### 라이선스

MIT License. 자유롭게 사용, 수정, 배포가 가능합니다.

---

<a name="日本語"></a>
## 日本語

日本のIT・マーケティング転職市場において、大手エージェント（リクルート、パーソルキャリアなど）の内部マッチングアルゴリズムをリバースエンジニアリングしてシミュレーションする、AIエージェントスキルのコレクションです。

> **エージェントのマッチングアルゴリズムをリバースエンジニアリングする。**
>
> 単なる履歴書添削を超えて、応募前にエージェントの内部視点で自分を客観的に評価してください。

### Agent Skills

3つのエージェントスキルが、それぞれのフォルダに `SKILL.md` ファイルとして存在します。

**1. job-seeker-agent（求職者エージェント）**
候補者担当コンサルタント（CA）の視点から履歴書・職務経歴書を分析します。対話形式で進めるSPI3診断とポータブルスキル分析を通じて真の強みを発掘し、職務経歴書を戦略的にリフレーミングします。

**2. hiring-manager-agent（採用マネージャーエージェント）**
企業担当コンサルタント（RA）の視点から求人票（JD）を最適化します。チーム内ハイパフォーマーをモデリングし、エージェンシーのスキルオントロジーが正確に認識できるようJDを書き直します。

**3. matching-simulator（マッチングシミュレーター）**
両者（CA/RA）の視点とデータを統合し、最終マッチングスコアと合格確率をシミュレーションします。リクルート方式（SPI3）とパーソル方式（意味的類似度）のアルゴリズムを両方使用して体系的な結果を提供します。

### 主要マッチングポイント

- **100%アルゴリズムベース** — 感情的な称賛を排除し、データと根拠（Evidence）に基づいた冷静な戦略的アウトプット
- **インタラクティブモード** — 一方的な出力ではなく、実際のコンサルティングのように質問しながら進める対話型診断プロセス（1回につき2〜3問）
- **アンチハルシネーション** — すべての評価は、ユーザーが提供したテキストから明示的な根拠を引用した場合のみスコアとして認定
- **クロススキルパイプライン** — エージェント間のYAMLデータをベースに、求職者プロフィールと企業プロフィールをロスなくマッチング連携

### 使い方

1. リポジトリをクローンするか、必要なエージェントフォルダをダウンロードします。
2. AIエディタやチャット画面（Claude Code、ChatGPT、Geminiなど）で、該当フォルダの `SKILL.md` ファイルを参照させてください。（例：`@job-seeker-agent/SKILL.md`）
3. エージェントが呼び出されたら、自分の職務経歴書ファイル（例：`@職務経歴書.md`）を渡します。（ターゲットの求人票JDがある場合は一緒に添付すると、ギャップ分析（Gap Analysis）がすぐに発動します。）

あとはAIが投げかける診断質問に答えながらコンサルティングを進めてください。

### 推奨実行の組み合わせ

| 状況 | 推奨エージェントロードマップ |
|------|-----------|
| **自分の経歴の強み分析・リフレーミング** | `/job-seeker-agent` 単独実行 |
| **特定求人（JD）の合格確率シミュレーション** | `/job-seeker-agent` 実行後 ➔ `/matching-simulator` |
| **企業として魅力的な求人票（JD）の作成** | `/hiring-manager-agent` 単独実行 |

### 技術・フレームワーク基盤

- **SPI3**（性格・職務適性診断）
- **ポータブルスキル8要素**（厚生労働省・リクルート標準職務遂行能力）
- **Hataraku Well-being Index**（パーソルグループ組織文化指標）
- **スキルオントロジーマッピング**（職務能力の意味的連結ネットワーク）

### コントリビューション・フィードバック

GitHub IssueまたはPull Requestを通じて、さまざまなフレームワークやエッジケースの追加を歓迎します。

### ライセンス

MIT License. 自由に使用、修正、配布が可能です。

---

<a name="English"></a>
## English

A collection of AI agent skills that reverse-engineer and simulate the internal matching algorithms of major recruitment agencies (Recruit, Persol Career, etc.) in Japan's IT and marketing job market.

> **Reverse-engineer Agency Matching Algorithms.**
>
> Go beyond simple resume editing — objectively evaluate yourself through the agency's internal lens before you apply.

### Agent Skills

3 agent skills exist as `SKILL.md` files in their respective folders.

**1. job-seeker-agent**
Analyzes your resume from the perspective of a Candidate Advisor (CA). Through an interactive SPI3 diagnostic and Portable Skills analysis, it uncovers your true strengths and strategically reframes your resume.

**2. hiring-manager-agent**
Optimizes a job description (JD) from the perspective of a Recruiting Advisor (RA). It models the team's top performer and rewrites the JD so that the agency's skill ontology can accurately recognize and match it.

**3. matching-simulator**
Integrates data from both sides (CA/RA) to simulate a final matching score and acceptance probability. Uses both the Recruit method (SPI3) and the Persol method (semantic similarity) to deliver systematic results.

### Core Matching Points

- **100% Algorithm-Based** — Eliminates emotional praise; delivers cold, strategic output strictly grounded in data and evidence
- **Interactive Mode** — Not a one-way output, but a conversational diagnostic process that asks questions and waits for answers, just like real consulting (2–3 questions at a time)
- **Anti-Hallucination** — Every evaluation only counts as a score if it explicitly cites evidence from the text provided by the user
- **Cross-Skill Pipeline** — Seamlessly connects candidate profiles and company profiles via YAML data across agents, with zero information loss

### How to Use

1. Clone the repository or download the agent folder you need.
2. Reference the `SKILL.md` file from the relevant folder in your AI editor or chat interface (Claude Code, ChatGPT, Gemini, etc.). (e.g., `@job-seeker-agent/SKILL.md`)
3. Once the agent is invoked, provide your resume file (e.g., `@resume.md`). (If you have a target job description, attach it together — Gap Analysis will trigger immediately.)

From there, simply answer the diagnostic questions the AI asks to proceed with your consultation.

### Recommended Workflows

| Situation | Recommended Agent Roadmap |
|-----------|--------------------------|
| **Analyze and reframe your resume's strengths** | Run `/job-seeker-agent` standalone |
| **Simulate acceptance probability for a specific JD** | Run `/job-seeker-agent` first ➔ then `/matching-simulator` |
| **Write an attractive job description as a company** | Run `/hiring-manager-agent` standalone |

### Technology & Framework Basis

Each agent self-references `references/frameworks.md` in its folder, built on standard frameworks in the Japanese recruitment market:

- **SPI3** (personality and job aptitude assessment)
- **8 Portable Skills Elements** (Ministry of Health, Labour and Welfare / Recruit standard job performance competencies)
- **Hataraku Well-being Index** (Persol Group organizational culture indicator)
- **Skill Ontology Mapping** (semantic network of job competencies)

### Contributing & Feedback

Contributions of additional frameworks and edge cases via GitHub Issues or Pull Requests are welcome.

### License

MIT License. Free to use, modify, and distribute.
