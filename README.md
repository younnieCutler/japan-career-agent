# Japan Recruit AI Agent (for Claude Code / Gemini)

> **Reverse-engineer Agency Matching Algorithms.**  
> Interactive AI skills simulating Japanese IT recruitment logic (SPI3, Portable Skills, Skill Ontology).

[**日本語**](#-japanese) | [**한국어**](#-korean) | [**English**](#-english)

---

## 🌏 Overview

This repository provides a set of AI Agent Skills (MCP compatible instructions) designed to help candidates and hiring managers navigate the Japanese IT recruitment ecosystem. It simulates the internal logic of top-tier Japanese agencies.

### Key Features
- **Algorithm Transparency**: Understand how Skill Ontology and SPI3 affect your matching score.
- **Interactive Coaching**: Agents walk you through career reflection step-by-step.
- **Data Synergy**: Seamlessly transfer data between candidate profiling, JD optimization, and matching simulation.

---

## 🇯🇵 Japanese

### このツールについて
日本の大手エージェント（リクルート、パソナ/doda等）の内部ロジックをシミュレーションし、**「書類選考・面談の前に自分を客観視する」**ためのAIツールセットです。

### 構成スキル
- **`job-seeker-agent`**: 候補者担当(CA)の視点で経歴書を数値化。SPI3診断、ポータブルスキル分析。
- **`hiring-manager-agent`**: 企業担当(RA)の視点で求人票(JD)を最適化。ハイパーフォーマー定義。
- **`matching-simulator`**: 両者のデータを統合し、エージェント内部の「マッチングスコア」を算出。

### 導入方法
1. **Claude Code**: `~/.claude/skills/` に各フォルダをコピー。
2. **ブラウザAI**: 各スキルの `SKILL.md` の内容をコピーしてチャットに貼り付けてください。

---

## 🇰🇷 Korean

### 프로젝트 소개
일본 대형 채용 에이전트의 매칭 알고리즘을 역공학하여, **"지원 전 AI로 나를 먼저 평가"**해볼 수 있는 에이전트 스킬셋입니다. 에이전트 담당자에게 연락이 가기 전, 알고리즘 단계에서 필터링되는 리스크를 최소화합니다.

### 주요 기능
- **인터랙티브 대화 모드**: AI가 일방적으로 분석하는 것이 아니라, 대화를 통해 사용자의 강점을 끌어냅니다.
- **증거 기반 채점 (Evidence Grounding)**: 근거 없는 칭찬이 아닌, 이력서의 실제 텍스트에 기반한 객관적 스코어링을 수행합니다.
- **에이전트 시뮬레이션**: 리쿠르트 방식(SPI3 가중치)과 파솔 방식(시맨틱 유사도)의 매칭 점수를 모두 산출합니다.

### 구성 요소
1. **구직자 에이전트**: 이력서 리프레이밍 (SIer → 자사서비스 등 전략 분기)
2. **채용 매니저 에이전트**: 하이퍼포머 모델링 및 구인표 최적화
3. **매칭 시뮬레이터**: 두 에이전트의 결과값(YAML)을 읽어 최종 합격률 시뮬레이션

---

## 🚀 Getting Started

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/younnieCutler/japan-recruit-ai-agent.git
cd japan-recruit-ai-agent
```

### 2. Usage by Environment

#### 🤖 Clause Code (Recommended)
Install as native skills to use short commands (`/job-seeker-agent`).

```bash
# Copy agents to global skill directory
cp -r job-seeker-agent ~/.claude/skills/
cp -r hiring-manager-agent ~/.claude/skills/
cp -r matching-simulator ~/.claude/skills/

# Restart Claude Code and run:
> /job-seeker-agent
```

#### ✨ Gemini CLI
Inject the `SKILL.md` as context for your session.

```bash
# Point to the specific skill you want to use
gemini --context job-seeker-agent/SKILL.md
```

#### 🌐 Browser-based AI (ChatGPT, Gemini, etc.)
1.  Open `${agent_name}/SKILL.md` in a text editor.
2.  Copy the entire content and paste it into the AI chat box.
3.  **Wait for the AI to acknowledge the instructions** before starting your data input (Resume/JD).

---

### 3. Testing with Mocks
Quickly verify the scoring logic using our sample profiles:
```bash
# For Claude Code
> /job-seeker-agent [attached_resume.md]

# For Testing
/job-seeker-agent @job-seeker-agent/mock/chuto-park-minjun.md
```

---

## ⚖️ Disclaimer

이 도구의 스코어는 공개된 정보를 바탕으로 한 **추정값**입니다. 실제 에이전트의 내부 판정과 다를 수 있으니 전략 수립의 참고용으로만 사용해 주세요.  
本ツールのスコアは推定値であり、実際のエージェント判定結果を保証するものではありません。

---

## 📄 License
MIT License. Free to use, modify, and distribute.
