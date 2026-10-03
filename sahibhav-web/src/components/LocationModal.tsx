import React, { useState, useEffect } from 'react';
import {
  MapPin,
  Navigation,
  Search,
  X,
  AlertTriangle,
  RotateCw
} from 'lucide-react';

export interface UserLocation {
  lat: number;
  lng: number;
  area: string;
  city: string;
  formattedAddress: string;
  pincode?: string;
}

interface LocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentLocation: UserLocation | null;
  onSelectLocation: (loc: UserLocation) => void;
  isRequiredBlocker?: boolean;
}

export const LocationModal: React.FC<LocationModalProps> = ({
  isOpen,
  onClose,
  currentLocation,
  onSelectLocation,
  isRequiredBlocker = false
}) => {
  const [detectingGps, setDetectingGps] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  const handleModalClose = () => {
    setSearchQuery('');
    setSearchResults([]);
    setGpsError(null);
    setSearching(false);
    onClose();
  };

  // Reset search state whenever modal opens or closes
  useEffect(() => {
    if (!isOpen) {
      setSearchQuery('');
      setSearchResults([]);
      setGpsError(null);
      setSearching(false);
    }
  }, [isOpen]);

  // Reverse geocode lat/lng via Nominatim
  const reverseGeocode = async (lat: number, lng: number): Promise<UserLocation> => {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`,
        { headers: { 'Accept-Language': 'en' } }
      );
      if (!res.ok) throw new Error('Geocoding service unavailable');
      const data = await res.json();

      const addr = data.address || {};
      const area = addr.suburb || addr.neighbourhood || addr.residential || addr.road || addr.quarter || 'Hyperlocal Area';
      const city = addr.city || addr.town || addr.municipality || addr.state_district || addr.state || 'India';
      const pincode = addr.postcode || '';
      const formattedAddress = data.display_name || `${area}, ${city}`;

      return {
        lat,
        lng,
        area,
        city,
        formattedAddress,
        pincode
      };
    } catch {
      return {
        lat,
        lng,
        area: 'Current Location',
        city: 'India',
        formattedAddress: `Lat: ${lat.toFixed(4)}, Lng: ${lng.toFixed(4)}`
      };
    }
  };

  // Trigger GPS Detection
  const handleDetectGPS = () => {
    if (!navigator.geolocation) {
      setGpsError('Geolocation is not supported by your browser.');
      return;
    }

    setDetectingGps(true);
    setGpsError(null);

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          const loc = await reverseGeocode(latitude, longitude);
          setDetectingGps(false);
          onSelectLocation(loc);
          handleModalClose();
        } catch (err: any) {
          setDetectingGps(false);
          setGpsError(err.message || 'Failed to resolve street address from GPS.');
        }
      },
      (err) => {
        setDetectingGps(false);
        if (err.code === err.PERMISSION_DENIED) {
          setGpsError('Location permission denied. Please allow location access or search your address/pincode below.');
        } else {
          setGpsError('Unable to determine GPS location. Please search your address/pincode.');
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  // Search Address / Pincode
  const handleSearchAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearching(true);
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery + ', India')}&addressdetails=1&limit=5`,
        { headers: { 'Accept-Language': 'en' } }
      );
      const data = await res.json();
      setSearchResults(data);
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  const handleSelectSearchResult = (result: any) => {
    const lat = parseFloat(result.lat);
    const lng = parseFloat(result.lon);
    const addr = result.address || {};
    const area = addr.suburb || addr.neighbourhood || addr.residential || addr.road || addr.quarter || result.name || 'Hyperlocal Area';
    const city = addr.city || addr.town || addr.state_district || addr.state || 'India';
    const pincode = addr.postcode || '';

    const loc: UserLocation = {
      lat,
      lng,
      area,
      city,
      formattedAddress: result.display_name,
      pincode
    };

    onSelectLocation(loc);
    handleModalClose();
  };

  if (!isOpen) return null;

  return (
    <div
      onClick={(e) => {
        if (!isRequiredBlocker && e.target === e.currentTarget) {
          handleModalClose();
        }
      }}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px'
      }}
    >
      <div
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: '24px',
          width: '100%',
          maxWidth: '560px',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          overflow: 'hidden'
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--bg-glass-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '12px',
                background: 'rgba(16, 185, 129, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-emerald)'
              }}
            >
              <MapPin size={22} />
            </div>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                Set Hyperlocal Delivery Location
              </h2>
              {currentLocation ? (
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0' }}>
                  Active: <strong style={{ color: 'var(--accent-emerald)' }}>{currentLocation.area}, {currentLocation.city}</strong>
                </p>
              ) : (
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0' }}>
                  Required for real-time Blinkit, Zepto, Swiggy & BigBasket availability.
                </p>
              )}
            </div>
          </div>

          {!isRequiredBlocker && (
            <button
              onClick={handleModalClose}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: 'none',
                color: 'var(--text-secondary)',
                borderRadius: '50%',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer'
              }}
              title="Close"
            >
              <X size={18} />
            </button>
          )}
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Option 1: Quick GPS Auto-Detect Button */}
          <div
            style={{
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(16, 185, 129, 0.04))',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '16px',
              padding: '14px 18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: 'var(--accent-emerald)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#FFFFFF'
                }}
              >
                <Navigation size={18} />
              </div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Use Current GPS Location
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Auto-detects your exact neighborhood using browser geolocation.
                </div>
              </div>
            </div>

            <button
              onClick={handleDetectGPS}
              disabled={detectingGps}
              style={{
                background: 'var(--accent-emerald)',
                color: '#000000',
                border: 'none',
                borderRadius: '10px',
                padding: '10px 16px',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)'
              }}
            >
              {detectingGps ? (
                <>
                  <RotateCw size={14} className="spin-animation" />
                  <span>Detecting...</span>
                </>
              ) : (
                <>
                  <Navigation size={14} />
                  <span>Detect GPS</span>
                </>
              )}
            </button>
          </div>

          {/* GPS Error Alert */}
          {gpsError && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '12px',
                padding: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '13px',
                color: '#FCA5A5'
              }}
            >
              <AlertTriangle size={18} color="var(--accent-danger)" style={{ flexShrink: 0 }} />
              <span>{gpsError}</span>
            </div>
          )}

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '4px 0' }}>
            <div style={{ flex: 1, height: '1px', background: 'var(--bg-glass-border)' }} />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700 }}>OR SEARCH ADDRESS / PINCODE</span>
            <div style={{ flex: 1, height: '1px', background: 'var(--bg-glass-border)' }} />
          </div>

          {/* Option 2: Search Address / Pincode */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <form onSubmit={handleSearchAddress} style={{ display: 'flex', gap: '10px' }}>
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid var(--bg-glass-border)',
                  borderRadius: '12px',
                  padding: '0 14px'
                }}
              >
                <Search size={16} color="var(--text-muted)" />
                <input
                  type="text"
                  placeholder="Enter area, colony, or pincode (e.g. 752101 or Nayapalli)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    padding: '12px',
                    color: '#FFFFFF',
                    fontSize: '14px'
                  }}
                />
              </div>
              <button
                type="submit"
                disabled={searching || !searchQuery.trim()}
                style={{
                  background: 'var(--accent-emerald)',
                  color: '#000000',
                  border: 'none',
                  borderRadius: '12px',
                  padding: '0 20px',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: 'pointer'
                }}
              >
                {searching ? 'Searching...' : 'Search'}
              </button>
            </form>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '220px', overflowY: 'auto' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>SELECT LOCATION:</div>
                {searchResults.map((res, i) => (
                  <button
                    key={i}
                    onClick={() => handleSelectSearchResult(res)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--bg-glass-border)',
                      borderRadius: '12px',
                      padding: '12px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      cursor: 'pointer',
                      textAlign: 'left'
                    }}
                  >
                    <MapPin size={16} color="var(--accent-emerald)" style={{ flexShrink: 0 }} />
                    <div style={{ overflow: 'hidden' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {res.display_name.split(',')[0]}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {res.display_name}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
