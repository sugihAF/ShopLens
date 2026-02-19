// Reviewer card data from backend
export interface ReviewerCard {
  reviewer_name: string
  reviewer_id: number | null
  review_url: string | null
  review_type: 'video' | 'blog' | string
  summary: string
  rating: number | null
  pros: string[]
  cons: string[]
}

// Marketplace listing data from backend
export interface MarketplaceListing {
  title: string
  url: string
  price: string
  description: string
  marketplace: 'amazon' | 'ebay' | string
}

// Attachment types
export interface ReviewerCardsAttachment {
  type: 'reviewer_cards'
  data: {
    product_name: string
    cards: ReviewerCard[]
  }
}

export interface MarketplaceListingsAttachment {
  type: 'marketplace_listings'
  data: {
    product_name: string
    listings: MarketplaceListing[]
  }
}

// Semantic search result from vector search
export interface SemanticSearchResult {
  score: number | null
  product_name: string
  reviewer_name: string
  content: string
  aspect: string | null
  source_url: string | null
}

export interface SemanticSearchAttachment {
  type: 'semantic_search_results'
  data: {
    query: string
    results: SemanticSearchResult[]
    total: number
    search_type: string
  }
}

// Sentiment analysis from opinion extraction
export interface AspectSentiment {
  aspect: string
  average_sentiment: number
  positive_pct: number
  negative_pct: number
  review_count: number
  agreement_score: number
}

export interface SentimentAnalysisAttachment {
  type: 'sentiment_analysis'
  data: {
    product_name: string
    aspects: AspectSentiment[]
  }
}

// Product comparison table
export interface ComparisonProduct {
  name: string
  brand: string
  aspects: Record<string, { sentiment_score: number; agreement_score: number; review_count: number }>
}

export interface ComparisonTableAttachment {
  type: 'comparison_table'
  data: {
    products: ComparisonProduct[]
    aspects_compared: string[]
    aspect_winners: Record<string, { winner: string; score: number }>
    recommendation: string
  }
}

export type Attachment =
  | ReviewerCardsAttachment
  | MarketplaceListingsAttachment
  | SemanticSearchAttachment
  | SentimentAnalysisAttachment
  | ComparisonTableAttachment
  | { type: string; data: unknown }

export interface ProgressStep {
  step: string
  label: string
  status: 'running' | 'done'
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  sources?: SourceReference[]
  attachments?: Attachment[]
}

export interface SourceReference {
  type: string
  id: number
  name: string
  url?: string
  snippet?: string
}

export interface ChatRequest {
  message: string
  conversation_id?: string
}

// Backend API response format
export interface ApiMessageResponse {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: SourceReference[] | null
  attachments: Attachment[] | null
  created_at: string
}

export interface ApiChatResponse {
  message: ApiMessageResponse
  conversation_id: string
  suggested_questions: string[] | null
  products_mentioned: number[] | null
}

// Legacy format (kept for compatibility)
export interface ChatResponse {
  response: string
  conversationId: string
  sources?: string[]
}

export interface Feature {
  icon: React.ReactNode
  title: string
  description: string
  iconColor?: 'violet' | 'cyan' | 'pink' | 'orange' | 'green' | 'blue'
}

export interface Step {
  number: string
  title: string
  description: string
  visual: React.ReactNode
}

export interface Stat {
  value: number
  suffix: string
  label: string
}
