import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import './App.css'
import heroImg from './assets/hero.png'

type ApiProduct = {
  id: number
  title: string
  description: string
  category: string
  price: number
  rating: number
  stock: number
  brand: string
  sku: string
  thumbnail?: string
  images?: string[]
  availabilityStatus?: string
}

type DisplayProduct = {
  brand: string
  title: string
  price: string
  rating: string
  sku: string
  stock: 'In Stock' | 'Out of Stock' | 'Low Stock'
  note: string
  image: string
  category: string
}

type MatchItem = {
  title: string
  brand: string
  sku: string
  category: string
  price: number
  rating: number
  stock: number
  thumbnail: string
}

type RecommendationItem = {
  brand: string
  title: string
  price: string | number
  rating: string | number
  image?: string
  thumbnail?: string
  sku?: string
  category?: string
  stock?: number
}

type AssistantProduct = {
  title: string
  brand: string
  sku: string
  category: string
  price: number
  rating: number
  stock: number
  thumbnail: string
  availabilityStatus?: string
  description?: string
  shippingInformation?: string
  returnPolicy?: string
  tags?: string[]
}

type ChatItem =
  | {
      type: 'user'
      text: string
    }
  | {
      type: 'assistant'
      text: string
      matches?: MatchItem[]
      recommendations?: RecommendationItem[]
      product?: AssistantProduct
      followUpQuestion?: string
    }

const chat: ChatItem[] = [
  {
    type: 'user',
    text: 'Find affordable skincare with good reviews',
  },
  {
    type: 'assistant',
    text: 'I found several highly-rated affordable skincare options for you. Based on customer reviews and price points, here are my top recommendations:',
    recommendations: [
      {
        brand: 'PureBalance',
        title: 'Gentle Cleansing Oil',
        price: '$38.00',
        rating: '4.6',
        image:
          'https://images.unsplash.com/photo-1556228578-8c89e6adf883?auto=format&fit=crop&w=400&q=80',
      },
      {
        brand: 'GlowLab',
        title: 'Hydrating Face Serum',
        price: '$45.00',
        rating: '4.8',
        image: heroImg,
      },
    ],
  },
  {
    type: 'user',
    text: 'Show me premium beauty products under $100',
  },
  {
    type: 'assistant',
    text: 'Here are the best premium beauty products under $100 with excellent customer satisfaction:',
    recommendations: [
      {
        brand: 'DermaScience',
        title: 'Retinol Night Treatment',
        price: '$78.00',
        rating: '4.7',
        image:
          'https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=400&q=80',
      },
    ],
  },
]

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const moneyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
})

function formatPrice(price: number) {
  return moneyFormatter.format(price)
}

function formatDisplayPrice(price: string | number) {
  return typeof price === 'number' ? formatPrice(price) : price
}

function formatDisplayRating(rating: string | number) {
  return typeof rating === 'number' ? rating.toFixed(1) : rating
}

function toTitleCase(value: string) {
  return value
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

function summarizeProduct(product: ApiProduct) {
  const firstSentence = product.description.split('.').find(Boolean)?.trim()
  return firstSentence || `${product.brand} ${product.title}`
}

function mapProduct(product: ApiProduct): DisplayProduct {
  const status = product.availabilityStatus ?? (product.stock > 0 ? 'In Stock' : 'Out of Stock')

  return {
    brand: product.brand,
    title: product.title,
    price: formatPrice(product.price),
    rating: Number(product.rating).toFixed(1),
    sku: product.sku,
    stock:
      status === 'Low Stock'
        ? 'Low Stock'
        : status === 'Out of Stock'
          ? 'Out of Stock'
          : 'In Stock',
    note: summarizeProduct(product),
    image: product.thumbnail || product.images?.[0] || heroImg,
    category: product.category,
  }
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16.2 16.2 20 20" />
    </svg>
  )
}

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 12.2a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z" />
      <path d="M5 20.2a7 7 0 0 1 14 0" />
    </svg>
  )
}

function FilterIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5h16l-6 7v5l-4 2v-7Z" />
    </svg>
  )
}

function SparkleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8Z" />
      <path d="m19 14 1 2.8L22 18l-2 .6L19 21l-1-2.4-2-.6 2-.2Z" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 20 16-8L4 4v6l10 2-10 2Z" />
    </svg>
  )
}

function StarIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 4 2.6 5.3 5.9.9-4.3 4.2 1 5.9-5.2-2.7-5.2 2.7 1-5.9-4.3-4.2 5.9-.9Z" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12" />
      <path d="m18 6-12 12" />
    </svg>
  )
}

function AssistantContent() {
  const [messages, setMessages] = useState<ChatItem[]>(chat)
  const [message, setMessage] = useState('')
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [messages.length])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = message.trim()
    if (!trimmed) return

    setMessages((current) => [...current, { type: 'user', text: trimmed }])
    setMessage('')

    try {
      const response = await fetch(`${apiBaseUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: trimmed,
          sku: null,
          category: null,
          brand: null,
          price_max: null,
          in_stock_only: false,
        }),
      })

      if (!response.ok) {
        throw new Error(`Chat request failed (${response.status})`)
      }

      const data = await response.json()

      setMessages((current) => [
        ...current,
        {
          type: 'assistant',
          text: data.answer ?? 'No answer returned.',
          matches: data.matches ?? [],
          recommendations: data.recommendations ?? [],
          product: data.product ?? data.matches?.[0],
          followUpQuestion: data.follow_up_question ?? data.followUpQuestion,
        },
      ])
    } catch {
      setMessages((current) => [
        ...current,
        { type: 'assistant', text: 'Sorry, I could not reach the assistant.' },
      ])
    }
  }

  return (
    <>
      <div className="assistant-header">
        <div className="assistant-icon">
          <SparkleIcon />
        </div>
        <div>
          <h2>Shopping Assistant</h2>
          <p>Ask me anything about our products</p>
        </div>
      </div>

      <div className="chat-stream">
        {messages.map((item, index) =>
          item.type === 'user' ? (
            <div className="chat-bubble user" key={`${item.type}-${index}`}>
              {item.text}
            </div>
          ) : (
            <div className="assistant-block" key={`${item.type}-${index}`}>
              <div className="chat-bubble assistant">{item.text}</div>

              {item.product ? (
                <article className="assistant-product-card">
                  <img src={item.product.thumbnail || heroImg} alt={item.product.title} loading="lazy" />
                  <div className="assistant-product-copy">
                    <p className="assistant-product-brand">{item.product.brand}</p>
                    <h4>{item.product.title}</h4>
                    <div className="assistant-product-meta">
                      <span>{formatDisplayRating(item.product.rating)}</span>
                      <strong>{formatDisplayPrice(item.product.price)}</strong>
                      <span className={`status ${item.product.stock > 0 ? 'ok' : 'bad'}`}>
                        {item.product.availabilityStatus ?? (item.product.stock > 0 ? 'In Stock' : 'Out of Stock')}
                      </span>
                    </div>
                    {item.product.description ? <p>{item.product.description}</p> : null}
                    <div className="assistant-product-facts">
                      <span>SKU: {item.product.sku}</span>
                      <span>Category: {item.product.category}</span>
                      {item.product.shippingInformation ? <span>{item.product.shippingInformation}</span> : null}
                    </div>
                    {item.product.returnPolicy ? (
                      <p className="assistant-product-secondary">Return policy: {item.product.returnPolicy}</p>
                    ) : null}
                  </div>
                </article>
              ) : (
                <div className="recommendation-list">
                  {(item.matches ?? item.recommendations ?? []).map((rec) => {
                    const image = rec.thumbnail || ('image' in rec ? rec.image : undefined) || heroImg
                    const stockLabel =
                      typeof rec.stock === 'number'
                        ? rec.stock > 0
                          ? `In stock: ${rec.stock}`
                          : 'Out of stock'
                        : null

                    return (
                      <article className="mini-card" key={`${rec.brand}-${rec.sku ?? rec.title}`}>
                        <img src={image} alt={rec.title} loading="lazy" />
                        <div className="mini-copy">
                          <p>{rec.brand}</p>
                          <h4>{rec.title}</h4>
                          <div className="mini-meta">
                            <span className="mini-star" aria-hidden="true">
                              <StarIcon />
                            </span>
                            <span>{formatDisplayRating(rec.rating)}</span>
                            <strong>{formatDisplayPrice(rec.price)}</strong>
                          </div>
                          {rec.category || rec.sku || stockLabel ? (
                            <p className="mini-details">
                              {[rec.category, rec.sku, stockLabel].filter(Boolean).join(' | ')}
                            </p>
                          ) : null}
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}

              {item.followUpQuestion ? <div className="chat-bubble assistant follow-up">{item.followUpQuestion}</div> : null}
            </div>
          ),
        )}
        <div ref={endRef} />
      </div>

      <form className="assistant-input" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Ask about products..."
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <button type="submit" aria-label="Send message">
          <SendIcon />
        </button>
      </form>
    </>
  )
}

function App() {
  const [mobileAssistantOpen, setMobileAssistantOpen] = useState(false)
  const [products, setProducts] = useState<DisplayProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [skuSearch, setSkuSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All Categories')
  const [selectedBrand, setSelectedBrand] = useState('All Brands')
  const [selectedRating, setSelectedRating] = useState('All Ratings')
  const [priceCap, setPriceCap] = useState(100)
  const [inStockOnly, setInStockOnly] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadProducts() {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch(`${apiBaseUrl}/products`, {
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`Failed to load products (${response.status})`)
        }

        const data = (await response.json()) as ApiProduct[]
        setProducts(data.map(mapProduct))
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === 'AbortError') {
          return
        }

        setError(loadError instanceof Error ? loadError.message : 'Unable to load products.')
      } finally {
        setLoading(false)
      }
    }

    loadProducts()

    return () => controller.abort()
  }, [])

  const availableCategories = useMemo(() => {
    const categories = [...new Set(products.map((product) => product.category))].sort((left, right) =>
      left.localeCompare(right),
    )

    return ['All Categories', ...categories]
  }, [products])

  const availableBrands = useMemo(
    () => ['All Brands', ...new Set(products.map((product) => product.brand))],
    [products],
  )

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const combinedText = `${product.title} ${product.brand} ${product.sku} ${product.note}`.toLowerCase()
      const searchValue = searchTerm.trim().toLowerCase()
      const skuValue = skuSearch.trim().toLowerCase()
      const priceValue = Number(product.price.replace(/[^0-9.]/g, ''))
      const ratingValue = Number(product.rating)

      const matchesSearch = searchValue.length === 0 || combinedText.includes(searchValue)
      const matchesSku = skuValue.length === 0 || product.sku.toLowerCase().includes(skuValue)
      const matchesCategory = selectedCategory === 'All Categories' || product.category === selectedCategory
      const matchesBrand = selectedBrand === 'All Brands' || product.brand === selectedBrand
      const matchesRating =
        selectedRating === 'All Ratings' || ratingValue >= Number.parseFloat(selectedRating.replace('+', ''))
      const matchesPrice = priceValue <= priceCap
      const matchesStock = !inStockOnly || product.stock === 'In Stock'

      return (
        matchesSearch &&
        matchesSku &&
        matchesCategory &&
        matchesBrand &&
        matchesRating &&
        matchesPrice &&
        matchesStock
      )
    })
  }, [products, searchTerm, skuSearch, selectedCategory, selectedBrand, selectedRating, priceCap, inStockOnly])

  const visibleProducts = filteredProducts.slice(0, 6)

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">SF</span>
          <span className="brand-name">Smart Product Finder</span>
        </div>

        <label className="searchbar" htmlFor="search">
          <span className="search-icon">
            <SearchIcon />
          </span>
          <input
            id="search"
            type="text"
            placeholder="Search products by name, brand, or SKU..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
        </label>

        <button className="icon-button" type="button" aria-label="Profile">
          <UserIcon />
        </button>
      </header>

      <main className="workspace">
        <aside className="sidebar sidebar-left">
          <div className="sidebar-title">
            <span className="sidebar-icon">
              <FilterIcon />
            </span>
            <h2>Filters</h2>
          </div>

          <div className="filter-group">
            <label htmlFor="category">Category</label>
            <select
              id="category"
              value={selectedCategory}
              onChange={(event) => setSelectedCategory(event.target.value)}
            >
              {availableCategories.map((category) => (
                <option key={category} value={category}>
                  {category === 'All Categories' ? category : toTitleCase(category)}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="brand">Brand</label>
            <select
              id="brand"
              value={selectedBrand}
              onChange={(event) => setSelectedBrand(event.target.value)}
            >
              {availableBrands.map((brand) => (
                <option key={brand} value={brand}>
                  {brand}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="sku">SKU Search</label>
            <input
              id="sku"
              type="text"
              placeholder="Enter SKU..."
              value={skuSearch}
              onChange={(event) => setSkuSearch(event.target.value)}
            />
          </div>

          <div className="filter-group">
            <div className="label-row">
              <label htmlFor="price">Price Range</label>
              <span>$0</span>
              <span>${priceCap}</span>
            </div>
            <input
              id="price"
              type="range"
              min="0"
              max="2000"
              value={priceCap}
              onChange={(event) => setPriceCap(Number(event.target.value))}
            />
          </div>

          <div className="filter-group">
            <label htmlFor="rating">Rating</label>
            <select
              id="rating"
              value={selectedRating}
              onChange={(event) => setSelectedRating(event.target.value)}
            >
              <option>All Ratings</option>
              <option>4.5+</option>
              <option>4.0+</option>
              <option>3.5+</option>
            </select>
          </div>

          <div className="toggle-row">
            <span>In Stock Only</span>
            <button
              className={`toggle ${inStockOnly ? 'on' : ''}`}
              type="button"
              aria-label="In stock only"
              onClick={() => setInStockOnly((value) => !value)}
            >
              <span />
            </button>
          </div>

          <button className="primary-button" type="button">
            Apply Filters
          </button>
        </aside>

        <section className="content">
          {error ? (
            <div className="empty-state">
              <h3>Unable to load products</h3>
              <p>{error}</p>
            </div>
          ) : loading ? (
            <div className="product-grid">
              {Array.from({ length: 6 }).map((_, index) => (
                <article className="product-card skeleton" key={index}>
                  <div className="product-image-wrap" />
                  <div className="product-body">
                    <div className="skeleton-line short" />
                    <div className="skeleton-line title" />
                    <div className="skeleton-line medium" />
                    <div className="skeleton-line long" />
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <>
              <div className="product-grid">
                {visibleProducts.map((product) => (
                  <article className="product-card" key={product.sku}>
                    <div className="product-image-wrap">
                      <img src={product.image} alt={product.title} loading="lazy" />
                    </div>

                    <div className="product-body">
                      <p className="brand-label">{product.brand}</p>
                      <h3>{product.title}</h3>

                      <div className="meta-row">
                        <div className="rating">
                          <span className="stars" aria-hidden="true">
                            <StarIcon />
                          </span>
                          <span>{product.rating}</span>
                        </div>
                        <div className="price">{product.price}</div>
                      </div>

                      <div className="availability-row">
                        <span className="sku-label">SKU: {product.sku}</span>
                        <span className={`status ${product.stock === 'In Stock' ? 'ok' : 'bad'}`}>
                          {product.stock}
                        </span>
                      </div>

                      <div className="insight-box">
                        <span className="sparkle">
                          <SparkleIcon />
                        </span>
                        <p>{product.note}</p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>

              {filteredProducts.length === 0 ? (
                <div className="empty-state empty-state-grid">
                  <h3>No products match your filters</h3>
                  <p>Try widening the price range or clearing the SKU search.</p>
                </div>
              ) : null}
            </>
          )}
        </section>

        <aside className="sidebar sidebar-right">
          <AssistantContent />
        </aside>
      </main>

      <button
        className="assistant-fab"
        type="button"
        aria-label="Open shopping assistant"
        onClick={() => setMobileAssistantOpen(true)}
      >
        <SparkleIcon />
      </button>

      <div
        className={`assistant-mobile-backdrop ${mobileAssistantOpen ? 'open' : ''}`}
        onClick={() => setMobileAssistantOpen(false)}
        aria-hidden="true"
      />

      <section
        className={`assistant-mobile-sheet ${mobileAssistantOpen ? 'open' : ''}`}
        aria-label="Shopping assistant"
      >
        <div className="assistant-mobile-sheet-header">
          <button
            className="assistant-mobile-close"
            type="button"
            aria-label="Close shopping assistant"
            onClick={() => setMobileAssistantOpen(false)}
          >
            <CloseIcon />
          </button>
        </div>

        <div className="assistant-mobile-content">
          <AssistantContent />
        </div>
      </section>
    </div>
  )
}

export default App
