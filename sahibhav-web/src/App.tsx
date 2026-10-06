import { useState, useRef, useEffect } from 'react';
import confetti from 'canvas-confetti';
import {
  Search,
  Sparkles,
  Clock,
  TrendingDown,
  ExternalLink,
  MapPin,
  AlertCircle,
  ArrowRight,
  RefreshCw,
  Zap,
  Info,
  ChevronDown,
  Award,
  Store,
  Globe,
  Compass,
  Layers
} from 'lucide-react';
import type { SahiBhavResponse } from './types';
import { LocationModal } from './components/LocationModal';
import type { UserLocation } from './components/LocationModal';

// Supported Quick-Commerce Platforms
const PLATFORMS_META = [
  { id: 'blinkit', name: 'Blinkit', color: '#F8CB46', textColor: '#000000', glow: 'rgba(248, 203, 70, 0.25)', eta: '10-15m' },
  { id: 'zepto', name: 'Zepto', color: '#8B30EC', textColor: '#FFFFFF', glow: 'rgba(139, 48, 236, 0.25)', eta: '8-12m' },
  { id: 'swiggy', name: 'Swiggy Instamart', color: '#FC8019', textColor: '#FFFFFF', glow: 'rgba(252, 128, 25, 0.25)', eta: '12-18m' },
  { id: 'bigbasket', name: 'BigBasket BBNow', color: '#84C225', textColor: '#FFFFFF', glow: 'rgba(132, 194, 37, 0.25)', eta: '15-25m' },
];

export default function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [pipelineStep, setPipelineStep] = useState<number>(0);
  const [result, setResult] = useState<SahiBhavResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Real dynamic user location state
  const [userLocation, setUserLocation] = useState<UserLocation | null>(null);
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);
  const [isRequiredBlocker, setIsRequiredBlocker] = useState(false);

  const [selectedTab, setSelectedTab] = useState<'winner' | 'all_stores'>('winner');
  const timerRef = useRef<number | null>(null);

  // Initial load: check localStorage or request browser geolocation
  useEffect(() => {
    const saved = localStorage.getItem('sahibhav_user_location');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.lat && parsed.lng) {
          console.log(`📍 [SahiBhav Location (Restored from cache)] Lat: ${parsed.lat}, Lng: ${parsed.lng} | ${parsed.formattedAddress}`);
          setUserLocation(parsed);
          return;
        }
      } catch {
        // Continue to geolocation
      }
    }

    // Auto-request location from browser
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const { latitude, longitude } = pos.coords;
            const res = await fetch(
              `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`,
              { headers: { 'Accept-Language': 'en' } }
            );
            const data = await res.json();
            const addr = data.address || {};
            const area = addr.suburb || addr.neighbourhood || addr.residential || addr.road || addr.quarter || 'Hyperlocal Area';
            const city = addr.city || addr.town || addr.state_district || addr.state || 'India';
            const loc: UserLocation = {
              lat: latitude,
              lng: longitude,
              area,
              city,
              formattedAddress: data.display_name || `${area}, ${city}`,
              pincode: addr.postcode
            };
            console.log(`📍 [SahiBhav Location (First Time GPS Added)] Lat: ${loc.lat}, Lng: ${loc.lng} | ${loc.formattedAddress}`);
            setUserLocation(loc);
            localStorage.setItem('sahibhav_user_location', JSON.stringify(loc));
          } catch {
            // Geocoding network blip: set coords
            const loc: UserLocation = {
              lat: pos.coords.latitude,
              lng: pos.coords.longitude,
              area: 'Current Location',
              city: 'Detected',
              formattedAddress: `Lat: ${pos.coords.latitude.toFixed(3)}, Lng: ${pos.coords.longitude.toFixed(3)}`
            };
            console.log(`📍 [SahiBhav Location (First Time GPS Coords Added)] Lat: ${loc.lat}, Lng: ${loc.lng}`);
            setUserLocation(loc);
            localStorage.setItem('sahibhav_user_location', JSON.stringify(loc));
          }
        },
        () => {
          // User blocked or denied location: show modal so they can pick on map
          setIsLocationModalOpen(true);
          setIsRequiredBlocker(true);
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    } else {
      setIsLocationModalOpen(true);
      setIsRequiredBlocker(true);
    }
  }, []);

  const handleSelectLocation = (loc: UserLocation) => {
    console.log(`📍 [SahiBhav Location (Updated)] Lat: ${loc.lat}, Lng: ${loc.lng} | ${loc.formattedAddress}`);
    setUserLocation(loc);
    localStorage.setItem('sahibhav_user_location', JSON.stringify(loc));
    setIsRequiredBlocker(false);
  };

  // Trigger celebration confetti
  const triggerConfetti = () => {
    confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.6 },
      colors: ['#10B981', '#34D399', '#F8CB46', '#FC8019', '#8B30EC']
    });
  };

  const handleSearch = async (overrideQuery?: string) => {
    const searchQuery = (overrideQuery ?? query).trim();
    if (!searchQuery) return;

    // Strict location gate: Quick-commerce prices and inventory require exact GPS coordinates
    if (!userLocation) {
      setIsLocationModalOpen(true);
      setIsRequiredBlocker(true);
      return;
    }

    if (overrideQuery) {
      setQuery(overrideQuery);
    }

    setLoading(true);
    setError(null);
    setPipelineStep(1);

    // Simulate animated pipeline progression
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      setPipelineStep(prev => (prev < 4 ? prev + 1 : prev));
    }, 1200);

    try {
      const response = await fetch('http://localhost:8000/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          lat: userLocation.lat,
          lng: userLocation.lng,
          delivery_mode: 'instant'
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server responded with status ${response.status}`);
      }

      const data: SahiBhavResponse = await response.json();
      setResult(data);
      setPipelineStep(4);
      setSelectedTab('winner');

      // If user saved money, celebrate!
      if (data.optimization?.winning_recommendation?.savings_vs_highest && data.optimization.winning_recommendation.savings_vs_highest > 0) {
        setTimeout(triggerConfetti, 300);
      }
    } catch (err: any) {
      console.error('Optimization error:', err);
      setError(
        err.message || 'Unable to connect to SahiBhav AI backend. Make sure the FastAPI server is running on port 8000.'
      );
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
      setLoading(false);
    }
  };

  const clearSearch = () => {
    setQuery('');
    setResult(null);
    setError(null);
    setPipelineStep(0);
  };

  const getPlatformMeta = (platformName: string) => {
    const lower = platformName.toLowerCase();
    return PLATFORMS_META.find(p => lower.includes(p.id)) || {
      id: lower,
      name: platformName,
      color: '#3B82F6',
      textColor: '#FFFFFF',
      glow: 'rgba(59, 130, 246, 0.25)',
      eta: '15-20m'
    };
  };

  const winner = result?.optimization?.winning_recommendation;

  return (
    <div className="app-container">
      {/* Location Modal (GPS detection + Interactive Leaflet Map + Nominatim search) */}
      <LocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        currentLocation={userLocation}
        onSelectLocation={handleSelectLocation}
        isRequiredBlocker={isRequiredBlocker && !userLocation}
      />

      {/* 1. Header Navigation */}
      <header className="header-nav">
        <div className="brand-badge">
          <div className="brand-icon-wrapper">
            🛒
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="brand-title">SahiBhav AI</span>
              <span className="brand-tag">v1.0 Live</span>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
              India's 4-App Quick-Commerce Optimizer
            </p>
          </div>
        </div>

        <div className="header-meta">
          {/* Quick-Commerce Platforms Indicator */}
          <div className="platform-dots-wrapper">
            {PLATFORMS_META.map(p => (
              <span key={p.id} className={`platform-pill plat-${p.id}`} title={`${p.name} (~${p.eta})`}>
                {p.name.split(' ')[0]}
              </span>
            ))}
          </div>

          {/* Dynamic Real Location Selector / Pin */}
          <button
            className="location-picker"
            onClick={() => {
              setIsRequiredBlocker(false);
              setIsLocationModalOpen(true);
            }}
            aria-label="Set Delivery Location"
            style={{
              borderColor: userLocation ? 'rgba(16, 185, 129, 0.4)' : 'rgba(245, 158, 11, 0.6)',
              background: userLocation ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.12)',
              animation: userLocation ? 'none' : 'pulse-warning 2s infinite ease-in-out'
            }}
          >
            <MapPin
              size={15}
              color={userLocation ? 'var(--accent-emerald)' : 'var(--accent-gold)'}
            />
            <div style={{ textAlign: 'left', lineHeight: 1.2 }}>
              {userLocation ? (
                <>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {userLocation.area}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                    {userLocation.city}
                  </div>
                </>
              ) : (
                <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--accent-gold)' }}>
                  Set Location (Required)
                </div>
              )}
            </div>
            <ChevronDown size={14} color="var(--text-muted)" />
          </button>
        </div>
      </header>

      {/* Location Warning Alert Banner if location not yet selected */}
      {!userLocation && (
        <div
          onClick={() => {
            setIsRequiredBlocker(true);
            setIsLocationModalOpen(true);
          }}
          style={{
            background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.05))',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            borderRadius: '16px',
            padding: '12px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            transition: 'var(--transition-normal)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Compass size={20} color="var(--accent-gold)" />
            <div>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#FCD34D' }}>
                Hyperlocal Delivery Location Not Set
              </span>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0' }}>
                Quick-commerce stores (Blinkit, Zepto, Swiggy, BBNow) depend on your exact location. Click here to auto-detect GPS or pick on map.
              </p>
            </div>
          </div>
          <button
            style={{
              background: 'var(--accent-gold)',
              color: '#000000',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 800,
              cursor: 'pointer'
            }}
          >
            Pick Location
          </button>
        </div>
      )}

      {/* 2. Hero Section */}
      <section className="hero-section">
        <h1 className="hero-headline">
          Sahi Bhav, Har Baar. <span>Save ₹50–₹200</span> on Every Grocery Order.
        </h1>
        <p className="hero-subhead">
          Real-time AI price optimizer across Blinkit, Zepto, Swiggy Instamart & BigBasket. Speak or type naturally in <strong>any language, regional dialect, or mixed vernacular</strong> — from Odia, Bengali, and Hindi to Tamil, Telugu, and Hinglish. We calculate items, delivery fees, and split combos to get you the lowest price in seconds.
        </p>

        {/* 3. Search Box Omnibar */}
        <div className="search-container">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSearch();
            }}
            className="search-box-wrapper"
          >
            <div className="search-icon-prefix">
              <Search size={20} />
            </div>
            <input
              type="text"
              className="search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search grocery items in any language (e.g. 1 packet milk and 1 pack butter)..."
              disabled={loading}
            />
            {query && (
              <button
                type="button"
                onClick={clearSearch}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '8px',
                  display: 'flex',
                  alignItems: 'center'
                }}
                title="Clear"
              >
                ✕
              </button>
            )}
            <button
              type="submit"
              className="search-button"
              disabled={loading || !query.trim()}
            >
              {loading ? (
                <>
                  <div className="spinner" />
                  <span>Optimizing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  <span>Find Sahi Bhav</span>
                </>
              )}
            </button>
          </form>
        </div>
      </section>

      {/* 4. Live Pipeline Tracker (when loading) */}
      {loading && (
        <section className="pipeline-card">
          <div className="pipeline-header">
            <div className="pipeline-status-text">
              <div className="spinner" />
              <span>Analyzing Quick-Commerce Stores at {userLocation?.area || 'Your Location'}</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Step {pipelineStep} of 4
            </span>
          </div>

          <div className="pipeline-steps">
            <div className={`pipeline-step ${pipelineStep >= 1 ? 'active' : ''} ${pipelineStep > 1 ? 'done' : ''}`}>
              <Globe size={16} color={pipelineStep >= 1 ? 'var(--accent-emerald)' : 'var(--text-muted)'} />
              <div>
                <strong>1. Multilingual AI Intent</strong>
                <div style={{ fontSize: '11px' }}>Extracting items & units</div>
              </div>
            </div>

            <div className={`pipeline-step ${pipelineStep >= 2 ? 'active' : ''} ${pipelineStep > 2 ? 'done' : ''}`}>
              <Zap size={16} color={pipelineStep >= 2 ? 'var(--accent-emerald)' : 'var(--text-muted)'} />
              <div>
                <strong>2. 4-App Real-Time Scraper</strong>
                <div style={{ fontSize: '11px' }}>Blinkit, Zepto, Swiggy, BB</div>
              </div>
            </div>

            <div className={`pipeline-step ${pipelineStep >= 3 ? 'active' : ''} ${pipelineStep > 3 ? 'done' : ''}`}>
              <Layers size={16} color={pipelineStep >= 3 ? 'var(--accent-emerald)' : 'var(--text-muted)'} />
              <div>
                <strong>3. Combo Optimizer</strong>
                <div style={{ fontSize: '11px' }}>Calculating delivery fee thresholds</div>
              </div>
            </div>

            <div className={`pipeline-step ${pipelineStep >= 4 ? 'active' : ''}`}>
              <Sparkles size={16} color={pipelineStep >= 4 ? 'var(--accent-emerald)' : 'var(--text-muted)'} />
              <div>
                <strong>4. SahiBhav AI Advice</strong>
                <div style={{ fontSize: '11px' }}>Crafting localized decision</div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 5. Error State */}
      {error && !loading && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '16px',
            padding: '20px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '14px',
            color: '#FCA5A5'
          }}
        >
          <AlertCircle size={24} color="var(--accent-danger)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: '15px', color: '#FFFFFF', marginBottom: '4px' }}>
              Connection or Request Issue
            </div>
            <p style={{ fontSize: '14px', margin: 0, lineHeight: 1.5 }}>{error}</p>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
              <button
                onClick={() => handleSearch()}
                style={{
                  background: 'rgba(239, 68, 68, 0.2)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  color: '#FFFFFF',
                  padding: '6px 12px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <RefreshCw size={12} />
                Retry Search
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Results Presentation */}
      {result && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
          {/* AI Multilingual Natural Language Response Bubble */}
          <div className="ai-speech-bubble">
            <div className="ai-bubble-header">
              <Sparkles size={16} />
              <span>SahiBhav AI Intelligence • Detected Language: {result.detected_language || 'Auto'}</span>
            </div>
            <div className="ai-bubble-content">
              {result.natural_language_response}
            </div>
          </div>

          {/* Navigation Tabs for Views */}
          {result.optimization && (
            <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid var(--bg-glass-border)', paddingBottom: '12px' }}>
              <button
                onClick={() => setSelectedTab('winner')}
                style={{
                  padding: '8px 18px',
                  borderRadius: '10px',
                  fontSize: '14px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  border: selectedTab === 'winner' ? '1px solid var(--accent-emerald)' : '1px solid transparent',
                  background: selectedTab === 'winner' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                  color: selectedTab === 'winner' ? 'var(--accent-emerald)' : 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <Award size={16} />
                Winner Recommendation
              </button>

              <button
                onClick={() => setSelectedTab('all_stores')}
                style={{
                  padding: '8px 18px',
                  borderRadius: '10px',
                  fontSize: '14px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  border: selectedTab === 'all_stores' ? '1px solid var(--accent-blue)' : '1px solid transparent',
                  background: selectedTab === 'all_stores' ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                  color: selectedTab === 'all_stores' ? 'var(--text-highlight)' : 'var(--text-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <Store size={16} />
                Compare Single Stores ({result.optimization.all_single_stores?.filter(c => c.items_subtotal > 0).length || 0})
              </button>
            </div>
          )}

          {/* TAB 1: HERO WINNER CARD */}
          {selectedTab === 'winner' && winner && (
            <div className="winner-card">
              <div className="winner-top-banner">
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <div className="winner-badge-pill">
                    <Award size={16} />
                    <span>BEST VALUE STRATEGY</span>
                  </div>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Single Store Fulfillment (Lowest Total Price)
                  </span>
                </div>

                {winner.savings_vs_highest > 0 && (
                  <div className="savings-highlight">
                    <TrendingDown size={18} />
                    <span>You Save ₹{winner.savings_vs_highest.toFixed(0)}</span>
                  </div>
                )}
              </div>

              {/* Strategy Header Summary */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                    Recommended Cart
                  </div>
                  <div className="winner-strategy-title">
                    {winner.platforms.map((p, idx) => {
                      const meta = getPlatformMeta(p);
                      return (
                        <span key={p}>
                          {idx > 0 && <span style={{ color: 'var(--text-muted)', margin: '0 6px' }}>+</span>}
                          <span style={{ color: meta.color }}>{meta.name}</span>
                        </span>
                      );
                    })}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Total Checkout Price</div>
                  <div style={{ fontSize: '32px', fontWeight: 900, color: 'var(--accent-emerald)', lineHeight: 1.1 }}>
                    ₹{winner.total_price.toFixed(0)}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    Items: ₹{winner.items_subtotal.toFixed(0)} + Delivery: {winner.total_delivery_fees === 0 ? 'FREE' : `₹${winner.total_delivery_fees}`}
                  </div>
                </div>
              </div>

              {/* Delivery Fee Rule Explainer Banner */}
              {winner.fee_explanation && (
                <div
                  style={{
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid var(--bg-glass-border)',
                    borderRadius: '12px',
                    padding: '10px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    fontSize: '13px',
                    color: 'var(--text-secondary)'
                  }}
                >
                  <Info size={16} color="var(--accent-emerald)" style={{ flexShrink: 0 }} />
                  <span>{winner.fee_explanation}</span>
                </div>
              )}

              {/* Platform Orders Grid */}
              <div className="orders-grid">
                {winner.orders.map((order, orderIdx) => {
                  const meta = getPlatformMeta(order.platform);
                  return (
                    <div key={orderIdx} className="platform-order-box">
                      <div className="platform-box-header">
                        <div className="platform-title-group">
                          <span
                            style={{
                              width: '12px',
                              height: '12px',
                              borderRadius: '50%',
                              backgroundColor: meta.color
                            }}
                          />
                          <span style={{ fontSize: '18px', fontWeight: 800, color: meta.color }}>
                            {meta.name}
                          </span>
                        </div>
                        <div className="eta-pill">
                          <Clock size={12} />
                          <span>~{order.eta_mins || meta.eta} mins</span>
                        </div>
                      </div>

                      {/* Items Selected */}
                      <div className="items-list">
                        {order.items.map((item, itemIdx) => (
                          <div key={itemIdx} className="item-row">
                            <div className="item-info-col">
                              <span className="item-prod-name">{item.product.name}</span>
                              <span className="item-subtext">
                                {item.product.raw_quantity} {item.product.brand ? `• ${item.product.brand}` : ''}
                              </span>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              <span className="item-price">₹{item.item_total_price.toFixed(0)}</span>
                              {item.product.mrp > item.product.offer_price && (
                                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textDecoration: 'line-through' }}>
                                  ₹{item.product.mrp}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Pricing Breakdown */}
                      <div className="pricing-breakdown">
                        <div className="breakdown-row">
                          <span>Items Subtotal</span>
                          <span>₹{order.items_subtotal.toFixed(0)}</span>
                        </div>
                        <div className="breakdown-row">
                          <span>Delivery Fee (Orders &lt; ₹200: ₹30)</span>
                          {order.delivery_fee === 0 ? (
                            <span className="fee-free-badge">FREE</span>
                          ) : (
                            <span style={{ color: 'var(--accent-gold)' }}>+₹{order.delivery_fee}</span>
                          )}
                        </div>
                        <div className="breakdown-row total-row">
                          <span>Order Total</span>
                          <span style={{ color: meta.color }}>₹{order.total_order_cost.toFixed(0)}</span>
                        </div>
                      </div>

                      {/* Order Action Button */}
                      <a
                        href={order.items[0]?.product.deeplink || `https://www.google.com/search?q=${encodeURIComponent(order.platform + ' app')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`checkout-btn btn-${meta.id}`}
                      >
                        <span>Open {meta.name}</span>
                        <ExternalLink size={15} />
                      </a>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: STORE BY STORE COMPARISON */}
          {selectedTab === 'all_stores' && result.optimization && (
            <div className="comparison-section">
              <div className="section-title">
                <Store size={20} color="var(--accent-blue)" />
                <span>Single Store Total Comparison</span>
              </div>
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: 0 }}>
                See how much each individual platform costs for this exact basket, including delivery fees.
              </p>

              <div className="stores-comparison-grid">
                {result.optimization.all_single_stores.filter(combo => combo.items_subtotal > 0).map((combo, idx) => {
                  const platName = combo.platforms[0];
                  const meta = getPlatformMeta(platName);
                  const isWinner = winner && winner.combo_type === 'single_platform' && winner.platforms[0] === platName;

                  return (
                    <div
                      key={idx}
                      className="store-card"
                      style={{
                        borderColor: isWinner ? 'var(--accent-emerald)' : 'var(--bg-glass-border)',
                        boxShadow: isWinner ? '0 0 25px rgba(16, 185, 129, 0.2)' : 'none'
                      }}
                    >
                      <div className="store-card-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: meta.color }} />
                          <span className="store-name" style={{ color: meta.color }}>{meta.name}</span>
                        </div>
                        {isWinner && (
                          <span style={{ background: 'var(--accent-emerald)', color: '#000', fontSize: '10px', fontWeight: 800, padding: '2px 8px', borderRadius: '6px' }}>
                            WINNER
                          </span>
                        )}
                      </div>

                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Total Cost</div>
                        <div className="store-price-big">₹{combo.total_price.toFixed(0)}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          Items: ₹{combo.items_subtotal.toFixed(0)} | Delivery: {combo.total_delivery_fees === 0 ? 'FREE' : `₹${combo.total_delivery_fees}`}
                        </div>
                      </div>

                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={12} />
                        <span>ETA: ~{combo.max_eta_mins || meta.eta} mins</span>
                      </div>

                      {/* Items list preview */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingTop: '8px', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
                        {combo.orders[0]?.items.map((item, iIdx) => (
                          <div key={iIdx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                            <span style={{ color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '170px' }}>
                              {item.product.name}
                            </span>
                            <span style={{ fontWeight: 600 }}>₹{item.item_total_price.toFixed(0)}</span>
                          </div>
                        ))}
                      </div>

                      <a
                        href={combo.orders[0]?.items[0]?.product.deeplink || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`checkout-btn btn-${meta.id}`}
                        style={{ marginTop: 'auto', padding: '8px 12px', fontSize: '13px' }}
                      >
                        <span>Select {meta.name}</span>
                        <ArrowRight size={14} />
                      </a>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 7. Footer */}
      <footer
        style={{
          marginTop: 'auto',
          paddingTop: '40px',
          borderTop: '1px solid rgba(255, 255, 255, 0.05)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '8px',
          color: 'var(--text-muted)',
          fontSize: '13px',
          textAlign: 'center'
        }}
      >
        <p>
          <strong>SahiBhav AI</strong> • Real-time Grocery Optimizer for Blinkit, Zepto, Swiggy Instamart & BigBasket BBNow.
        </p>
        <p style={{ fontSize: '12px' }}>
          Delivery rule: ₹30 fee applied on orders &lt; ₹200, FREE delivery for orders ≥ ₹200.
        </p>
      </footer>
    </div>
  );
}
