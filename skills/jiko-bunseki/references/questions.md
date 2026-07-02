# Jiko Bunseki Question Bank

## 1. Strength Tendencies

### Strength Definitions

- `initiative` -> starts motion before conditions feel perfect
- `communication` -> explains ideas clearly and memorably
- `confidence` -> trusts own judgment under uncertainty
- `execution` -> gains energy from making visible progress
- `discipline` -> prefers order, process, and clear structure
- `ownership` -> feels personal responsibility for commitments
- `analysis` -> looks for evidence and logic gaps first
- `learning` -> gains energy from acquiring new knowledge
- `strategy` -> sees multiple possible paths quickly
- `empathy` -> notices emotional cues and interpersonal tension
- `harmony` -> seeks workable agreement and low-friction coordination
- `support` -> invests in helping others grow and stabilize

### Cluster Mapping

- `executing`: `execution`, `discipline`, `ownership`
- `strategic_thinking`: `analysis`, `learning`, `strategy`
- `relationship_building`: `empathy`, `harmony`, `support`
- `influencing`: `initiative`, `communication`, `confidence`

### Response Scale

- `SL` = strongly left
- `L` = slightly left
- `N` = neutral / both similar
- `R` = slightly right
- `SR` = strongly right

### Pair Sheet

| # | Left statement | Left strength | Right statement | Right strength |
|---|---|---|---|---|
| 1 | I would rather start moving than wait for perfect conditions. | initiative | I would rather verify the evidence before moving. | analysis |
| 2 | A good day feels productive when I can point to concrete progress. | execution | Learning something new can feel rewarding even before results appear. | learning |
| 3 | Clear rules and repeatable process help me perform at my best. | discipline | I like discovering a route others have not considered yet. | strategy |
| 4 | I feel responsible for following through once I say I will handle something. | ownership | I quickly pick up when someone is tense, discouraged, or uneasy. | empathy |
| 5 | I try to reduce unnecessary friction before conflict escalates. | harmony | I naturally explain ideas in a way others can follow. | communication |
| 6 | Supporting someone else's growth feels meaningful to me. | support | I can trust my own judgment even without much reassurance. | confidence |
| 7 | I move faster than most people when something needs to begin now. | initiative | A clear deliverable list keeps me energized. | execution |
| 8 | I prefer improving systems with evidence rather than reacting by instinct. | analysis | I like exploring new concepts even if they are not immediately useful. | learning |
| 9 | Order and predictability help me stay calm and effective. | discipline | In a complicated situation, I tend to see several workable routes. | strategy |
| 10 | I carry promises in my head until they are fully resolved. | ownership | I often notice emotional shifts before other people mention them. | empathy |
| 11 | Practical agreement matters more to me than winning an argument. | harmony | When a message matters, I think about how to make it land clearly. | communication |
| 12 | I often step in to make sure another person can succeed. | support | I can make a call even when information is incomplete. | confidence |
| 13 | Action itself often creates clarity. | initiative | Visible completion matters more to me than endless refinement. | execution |
| 14 | My first instinct is to ask what caused the problem. | analysis | I get restless if I am not learning or improving something. | learning |
| 15 | I like routines, checklists, and orderly handoffs. | discipline | I enjoy choosing the best route among several options. | strategy |
| 16 | I do not like leaving shared work in an ambiguous state. | ownership | I often adjust my words after sensing what others are feeling. | empathy |
| 17 | I look for the overlap that lets a group keep moving together. | harmony | I often translate complexity into language people can use. | communication |
| 18 | I am patient when helping someone become capable on their own. | support | I do not need much external validation to keep moving. | confidence |
| 19 | I am comfortable being the person who initiates the next step. | initiative | I enjoy closing loops and checking things off. | execution |
| 20 | I look for data, logic, or patterns before I form a conclusion. | analysis | New skills and frameworks energize me. | learning |
| 21 | I work best when expectations and methods are explicit. | discipline | I like spotting the opening that others missed. | strategy |
| 22 | I feel accountable even for small commitments. | ownership | I can often tell what support someone needs without them saying it directly. | empathy |
| 23 | I usually prefer stable collaboration over open confrontation. | harmony | I enjoy persuading people with a clear explanation. | communication |
| 24 | I am willing to spend time helping another person level up. | support | I stay steady when I have to back my own judgment. | confidence |

### Scoring Rules

- Each strength appears in 4 pairs
- Maximum raw score per strength = `16`
- Rank all 12 strengths by raw score
- Report the top 5 strengths
- If scores tie, prefer the strength with more `SL` / `SR` extremes before neutral-heavy patterns

## 2. Work Style

Ask all 6 items in one batch with a 1 to 5 scale.

- `1` = does not fit me at all
- `3` = neutral
- `5` = fits me very well

| Item | YAML field | Prompt |
|---|---|---|
| W1 | `autonomy` | I prefer deciding how to approach work without detailed instruction. |
| W2 | `structure_preference` | I perform better when process, rules, and expectations are clearly defined. |
| W3 | `speed_preference` | I prefer shipping a workable version quickly and improving it later. |
| W4 | `change_tolerance` | Frequent change and ambiguity usually energize me rather than drain me. |
| W5 | `collaboration_preference` | I prefer solving important problems with others rather than owning them mostly alone. |
| W6 | `feedback_frequency` | I want regular feedback, 1-on-1s, or active manager support. |

## 3. Interpretation Rules

### Preferred Company Type

- `self-developed startup`
  - autonomy >= 4
  - change_tolerance >= 4
  - speed_preference >= 4
- `SIer`
  - structure_preference >= 4
  - change_tolerance <= 3
  - feedback_frequency >= 3
- `large enterprise`
  - balanced profile not strongly pulled to startup or SIer

### Preferred Role Environment

Generate 2 to 4 tags from the strongest style signals:

- autonomy >= 4 -> `high-autonomy`
- structure_preference >= 4 -> `clear-process`
- speed_preference >= 4 -> `fast-iteration`
- change_tolerance >= 4 -> `high-ambiguity`
- collaboration_preference >= 4 -> `team-intensive`
- feedback_frequency >= 4 -> `manager-support-heavy`

### Recommended Role Clusters

- strong `strategic_thinking` + autonomy >= 4 -> `product / service planning`, `data / business analysis`
- strong `executing` + structure_preference >= 4 -> `operations`, `backend / infrastructure`, `PMO / QA`
- strong `relationship_building` + collaboration_preference >= 4 -> `customer success`, `HR / recruiter`, `project coordination`
- strong `influencing` + communication >= 12 -> `sales`, `marketing`, `business development`, `evangelism`

For `shinsotsu`, phrase these as broad starting directions rather than definitive job titles.

### Risk Flags

Add only evidence-based flags. Common examples:

- startup mismatch:
  - preferred company type is `self-developed startup`
  - but structure_preference >= 4 and change_tolerance <= 2
- bureaucracy friction:
  - autonomy >= 4 and preferred company type = `SIer`
- low-manager-support tolerance:
  - feedback_frequency >= 4 and autonomy <= 2
- solo-role friction:
  - collaboration_preference >= 4 but role direction is highly individual

### Self-PR Seeds

Write 2 to 4 short phrases based on:

- top strength
- strongest work style signal
- strongest wellbeing priority

Example patterns:

- `turns complexity into a clear next step`
- `prefers ownership with reliable follow-through`
- `does best in collaborative environments with high mutual respect`
- `learns quickly and applies new methods without waiting for perfect certainty`
