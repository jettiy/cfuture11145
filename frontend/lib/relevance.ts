export type ImpactLevel = 'low' | 'medium' | 'high' | 'critical'

export type RelevanceResult = {
  assetTags: string[]
  score: number
  impact: ImpactLevel
  oneLiner?: string
  matched: string[]
}

type Rule = {
  tag: string
  keywords: (string | RegExp)[]
  score: number
  impact?: ImpactLevel
  oneLiner?: string
}

const SYMBOL_RULES: Record<string, Rule[]> = {
  'NQ1!': [
    { tag: 'FOMC', keywords: ['fomc', 'fed meeting', 'federal reserve meeting', 'federal open market'], score: 60, impact: 'critical', oneLiner: '연준 이벤트는 성장주/나스닥 변동성에 직접 영향.' },
    { tag: 'CPI', keywords: ['cpi', 'consumer price'], score: 55, impact: 'critical', oneLiner: '인플레 지표는 금리 기대를 바꿔 주가에 즉시 반영.' },
    { tag: 'PPI', keywords: ['ppi', 'producer price'], score: 40, impact: 'high' },
    { tag: 'NFP', keywords: ['nfp', 'nonfarm payroll', 'non-farm payroll'], score: 55, impact: 'critical' },
    { tag: 'ISM', keywords: ['ism'], score: 35, impact: 'high' },
    { tag: 'UST', keywords: ['treasury yield', 'bond yield', 'us yields', '10-year', '2-year'], score: 40, impact: 'high', oneLiner: '국채금리 변화는 밸류에이션/멀티플에 영향.' },
    { tag: 'BIGTECH', keywords: ['apple', 'aapl', 'microsoft', 'msft', 'amazon', 'amzn', 'meta', 'nvda', 'nvidia', 'google', 'googl', 'alphabet', 'tesla', 'tsla', 'semiconductor', 'chip'], score: 35, impact: 'high' },
  ],
  'GOLD': [
    { tag: 'USD', keywords: ['dollar', 'usd', 'dxy'], score: 45, impact: 'high', oneLiner: '달러 강/약은 금 가격과 역상관 경향.' },
    { tag: 'REAL_YIELD', keywords: ['real yield', 'real rates', 'real rate'], score: 55, impact: 'critical' },
    { tag: 'FED', keywords: ['fed', 'federal reserve', 'powell', 'rate cuts', 'rate hike', 'interest rate'], score: 45, impact: 'high' },
    { tag: 'GEO', keywords: ['geopolit', 'war', 'conflict', 'middle east', 'sanction', 'risk-off'], score: 45, impact: 'high' },
    { tag: 'INFLATION', keywords: ['inflation', 'cpi', 'ppi'], score: 35, impact: 'high' },
  ],
  'CL1!': [
    { tag: 'EIA', keywords: ['eia', 'crude inventories', 'oil inventories', 'weekly inventory'], score: 50, impact: 'critical', oneLiner: '재고는 단기 유가 방향성에 직접 영향.' },
    { tag: 'OPEC', keywords: ['opec', 'opec+', 'production cut', 'output'], score: 45, impact: 'high' },
    { tag: 'SUPPLY', keywords: ['supply disruption', 'pipeline', 'strike', 'outage'], score: 35, impact: 'high' },
    { tag: 'MIDEAST', keywords: ['middle east', 'strait of hormuz', 'red sea', 'gulf'], score: 40, impact: 'high' },
    { tag: 'DEMAND', keywords: ['global demand', 'demand outlook', 'recession'], score: 30, impact: 'medium' },
  ],
  'HSI1!': [
    { tag: 'CHINA_PMI', keywords: ['china pmi', 'pmi'], score: 45, impact: 'high' },
    { tag: 'PROPERTY', keywords: ['property', 'real estate', 'developer', 'evergrande'], score: 45, impact: 'high', oneLiner: '중국 부동산 뉴스는 HSI 리스크 프리미엄에 영향.' },
    { tag: 'STIMULUS', keywords: ['stimulus', 'support measures', 'bailout', 'easing', 'rate cut', 'rrr'], score: 40, impact: 'high' },
    { tag: 'CNY', keywords: ['yuan', 'cny', 'renminbi', 'fx'], score: 35, impact: 'high' },
    { tag: 'HKCN_EQ', keywords: ['hang seng', 'hong kong', 'china stocks', 'h-share', 'a-share'], score: 30, impact: 'medium' },
  ],
}

function toText(input?: string | null): string {
  return (input || '').toString().toLowerCase()
}

function matchKeyword(text: string, kw: string | RegExp): boolean {
  if (!text) return false
  if (typeof kw === 'string') return text.includes(kw.toLowerCase())
  return kw.test(text)
}

function maxImpact(a: ImpactLevel, b: ImpactLevel): ImpactLevel {
  const rank: Record<ImpactLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 }
  return rank[b] > rank[a] ? b : a
}

export function calcRelevanceForSymbol(params: {
  symbol: string
  title?: string | null
  summary?: string | null
  source?: string | null
  baseImpact?: ImpactLevel
}): RelevanceResult {
  const { symbol } = params
  const rules = SYMBOL_RULES[symbol] || []
  const text = `${toText(params.title)}\n${toText(params.summary)}\n${toText(params.source)}`

  let score = 0
  let impact: ImpactLevel = params.baseImpact || 'medium'
  const tags: string[] = [symbol]
  const matched: string[] = []
  let oneLiner: string | undefined

  for (const r of rules) {
    const hit = r.keywords.some((kw) => matchKeyword(text, kw))
    if (!hit) continue
    score += r.score
    tags.push(r.tag)
    matched.push(r.tag)
    if (r.impact) impact = maxImpact(impact, r.impact)
    if (!oneLiner && r.oneLiner) oneLiner = r.oneLiner
  }

  // 기본 가중치: breaking/importance 같은 값을 호출자가 baseImpact로 주는 것을 전제로 하되,
  // 룰 매칭이 전혀 없으면 너무 높은 점수/태그를 만들지 않음.
  const uniqueTags = Array.from(new Set(tags))
  return { assetTags: uniqueTags, score, impact, oneLiner, matched }
}

