/**
 * Google Maps ↔ Leaflet Compatibility Shim
 * Provides L.* API surface backed by Google Maps JavaScript API.
 * Drop-in replacement for Leaflet in the Smart Supply Chain dashboard.
 */

let _gmap = null;
let _gmapDiv = null;
const _allInfoWindows = [];

// ── Custom HTML Overlay (replaces L.divIcon markers) ─────────────────────────
class HtmlOverlay extends google.maps.OverlayView {
  constructor(pos, html, size, anchor, zIndex, interactive) {
    super();
    this._pos = new google.maps.LatLng(pos[0], pos[1]);
    this._html = html;
    this._size = size || [40, 40];
    this._anchor = anchor || [20, 20];
    this._zIndex = zIndex || 0;
    this._interactive = interactive !== false;
    this._div = null;
  }
  onAdd() {
    this._div = document.createElement('div');
    this._div.style.position = 'absolute';
    this._div.style.zIndex = this._zIndex;
    this._div.innerHTML = this._html;
    if (!this._interactive) this._div.style.pointerEvents = 'none';
    this.getPanes().overlayMouseTarget.appendChild(this._div);
  }
  draw() {
    if (!this._div) return;
    const proj = this.getProjection();
    if (!proj) return;
    const px = proj.fromLatLngToDivPixel(this._pos);
    this._div.style.left = (px.x - this._anchor[0]) + 'px';
    this._div.style.top = (px.y - this._anchor[1]) + 'px';
  }
  onRemove() {
    if (this._div && this._div.parentNode) {
      this._div.parentNode.removeChild(this._div);
    }
    this._div = null;
  }
  setPosition(pos) {
    this._pos = new google.maps.LatLng(pos[0], pos[1]);
    this.draw();
  }
  updateHtml(html) {
    this._html = html;
    if (this._div) this._div.innerHTML = html;
  }
  updateSize(size, anchor) {
    this._size = size;
    this._anchor = anchor;
  }
}

// ── InfoWindow tooltip helper ────────────────────────────────────────────────
function _makeTooltip(anchor, content, opts) {
  const iw = new google.maps.InfoWindow({ content, disableAutoPan: true });
  _allInfoWindows.push(iw);
  return iw;
}

// ── LayerGroup ───────────────────────────────────────────────────────────────
class GLayerGroup {
  constructor() { this.items = []; this._onMap = false; }
  addTo() { this._onMap = true; this.items.forEach(i => i._show && i._show()); return this; }
  clearLayers() { this.items.forEach(i => i._destroy && i._destroy()); this.items = []; }
  remove() { this._onMap = false; this.items.forEach(i => i._hide && i._hide()); }
  _reg(item) { this.items.push(item); if (this._onMap && item._show) item._show(); }
}

// ── Wrapped Google Maps objects ──────────────────────────────────────────────

// Polyline wrapper
function _wrapPolyline(path, opts) {
  const gPath = path.map(p => ({ lat: p[0], lng: p[1] }));
  const isDash = !!opts.dashArray;
  const poly = new google.maps.Polyline({
    path: gPath,
    strokeColor: opts.color || '#000',
    strokeOpacity: isDash ? 0 : (opts.opacity ?? 1),
    strokeWeight: opts.weight || 2,
    icons: isDash ? [{
      icon: { path: 'M 0,-1 0,1', strokeOpacity: opts.opacity ?? 0.6, strokeColor: opts.color || '#000', scale: opts.weight || 2 },
      offset: '0', repeat: (opts.dashArray || '4 4').split(' ').reduce((a, b) => a + parseInt(b), 0) + 'px'
    }] : undefined,
  });
  let iw = null, layer = null;
  const wrapper = {
    addTo(target) {
      if (target instanceof GLayerGroup) { layer = target; target._reg(wrapper); }
      else { poly.setMap(_gmap); }
      return wrapper;
    },
    bindTooltip(content, tOpts) {
      iw = new google.maps.InfoWindow({ content, disableAutoPan: true });
      if (tOpts?.sticky) {
        poly.addListener('mouseover', (e) => { iw.setPosition(e.latLng); iw.open(_gmap); });
        poly.addListener('mouseout', () => iw.close());
      } else {
        poly.addListener('mouseover', (e) => { iw.setPosition(e.latLng); iw.open(_gmap); });
        poly.addListener('mouseout', () => iw.close());
      }
      return wrapper;
    },
    getBounds() {
      const b = new google.maps.LatLngBounds();
      poly.getPath().forEach(p => b.extend(p));
      return b;
    },
    remove() { poly.setMap(null); if (iw) iw.close(); },
    _show() { poly.setMap(_gmap); },
    _hide() { poly.setMap(null); if (iw) iw.close(); },
    _destroy() { poly.setMap(null); if (iw) iw.close(); },
    _gObj: poly,
  };
  return wrapper;
}

// Circle / CircleMarker wrapper
function _wrapCircle(pos, opts, isMarker) {
  const radius = isMarker ? (opts.radius || 6) * 1500 : (opts.radius || 50000);
  const circle = new google.maps.Circle({
    center: { lat: pos[0], lng: pos[1] },
    radius,
    strokeColor: opts.color || '#000',
    strokeWeight: opts.weight ?? 1.5,
    strokeOpacity: 1,
    fillColor: opts.fillColor || opts.color || '#000',
    fillOpacity: opts.fillOpacity ?? 0.3,
    map: null,
  });
  let iw = null, layer = null;
  const wrapper = {
    addTo(target) {
      if (target instanceof GLayerGroup) { layer = target; target._reg(wrapper); }
      else { circle.setMap(_gmap); }
      return wrapper;
    },
    bindTooltip(content, tOpts) {
      iw = new google.maps.InfoWindow({ content, disableAutoPan: true });
      circle.addListener('mouseover', () => { iw.setPosition(circle.getCenter()); iw.open(_gmap); });
      circle.addListener('mouseout', () => iw.close());
      return wrapper;
    },
    setStyle(s) {
      circle.setOptions({
        strokeColor: s.color || circle.get('strokeColor'),
        fillColor: s.fillColor || s.color || circle.get('fillColor'),
        fillOpacity: s.fillOpacity ?? circle.get('fillOpacity'),
        radius: s.radius != null ? (isMarker ? s.radius * 1500 : s.radius) : circle.get('radius'),
      });
    },
    remove() { circle.setMap(null); if (iw) iw.close(); },
    _show() { circle.setMap(_gmap); },
    _hide() { circle.setMap(null); if (iw) iw.close(); },
    _destroy() { circle.setMap(null); if (iw) iw.close(); },
    _gObj: circle,
  };
  return wrapper;
}

// Marker wrapper (supports both SVG icon and HTML divIcon)
function _wrapMarker(pos, opts) {
  const iconData = opts?.icon;
  const isHtml = iconData && iconData._isDivIcon;
  let gMarker = null, overlay = null, iw = null, layer = null;

  if (isHtml) {
    overlay = new HtmlOverlay(
      pos,
      iconData.html,
      iconData.iconSize,
      iconData.iconAnchor,
      opts.zIndexOffset || 0,
      opts.interactive !== false
    );
  } else {
    const svgHtml = iconData?.html || '';
    gMarker = new google.maps.Marker({
      position: { lat: pos[0], lng: pos[1] },
      icon: svgHtml ? {
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svgHtml),
        scaledSize: new google.maps.Size(
          iconData?.iconSize?.[0] || 20,
          iconData?.iconSize?.[1] || 20
        ),
        anchor: new google.maps.Point(
          iconData?.iconAnchor?.[0] || 10,
          iconData?.iconAnchor?.[1] || 10
        ),
      } : undefined,
      zIndex: opts.zIndexOffset || 0,
      clickable: opts.interactive !== false,
    });
  }

  const wrapper = {
    addTo(target) {
      if (target instanceof GLayerGroup) { layer = target; target._reg(wrapper); }
      else {
        if (gMarker) gMarker.setMap(_gmap);
        if (overlay) overlay.setMap(_gmap);
      }
      return wrapper;
    },
    setLatLng(p) {
      if (gMarker) gMarker.setPosition({ lat: p[0], lng: p[1] });
      if (overlay) overlay.setPosition(p);
      return wrapper;
    },
    setIcon(iconData) {
      if (!gMarker) return wrapper;
      const svgHtml = iconData?.html || '';
      gMarker.setIcon(svgHtml ? {
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svgHtml),
        scaledSize: new google.maps.Size(
          iconData?.iconSize?.[0] || 20,
          iconData?.iconSize?.[1] || 20
        ),
        anchor: new google.maps.Point(
          iconData?.iconAnchor?.[0] || 10,
          iconData?.iconAnchor?.[1] || 10
        ),
      } : null);
      return wrapper;
    },
    bindTooltip(content, tOpts) {
      iw = new google.maps.InfoWindow({
        content,
        disableAutoPan: true,
        pixelOffset: tOpts?.offset ? new google.maps.Size(tOpts.offset[0], tOpts.offset[1]) : undefined,
      });
      const anchor = gMarker || null;
      const getPos = () => {
        if (gMarker) return gMarker.getPosition();
        if (overlay) return overlay._pos;
        return null;
      };
      if (gMarker) {
        gMarker.addListener('mouseover', () => iw.open({ map: _gmap, anchor: gMarker }));
        gMarker.addListener('mouseout', () => iw.close());
      } else if (overlay && overlay._div) {
        // Set up after overlay is on map
        const setupHover = () => {
          if (!overlay._div) { setTimeout(setupHover, 200); return; }
          overlay._div.addEventListener('mouseenter', () => { iw.setPosition(overlay._pos); iw.open(_gmap); });
          overlay._div.addEventListener('mouseleave', () => iw.close());
        };
        setTimeout(setupHover, 300);
      }
      return wrapper;
    },
    on(event, fn) {
      if (gMarker) gMarker.addListener(event, fn);
      else if (overlay) {
        const setup = () => {
          if (!overlay._div) { setTimeout(setup, 200); return; }
          overlay._div.addEventListener(event, fn);
        };
        setTimeout(setup, 300);
      }
      return wrapper;
    },
    remove() { wrapper._destroy(); },
    _show() {
      if (gMarker) gMarker.setMap(_gmap);
      if (overlay) overlay.setMap(_gmap);
    },
    _hide() {
      if (gMarker) gMarker.setMap(null);
      if (overlay) overlay.setMap(null);
      if (iw) iw.close();
    },
    _destroy() {
      if (gMarker) { gMarker.setMap(null); }
      if (overlay) { overlay.setMap(null); }
      if (iw) iw.close();
    },
    _gMarker: gMarker,
    _overlay: overlay,
  };
  return wrapper;
}

// ── Public L.* API ───────────────────────────────────────────────────────────
const L = {
  map(id, opts) {
    _gmapDiv = document.getElementById(id);
    const center = opts?.center ? { lat: opts.center[0], lng: opts.center[1] } : { lat: 20, lng: 80 };
    _gmap = new google.maps.Map(_gmapDiv, {
      center,
      zoom: opts?.zoom || 5,
      disableDefaultUI: !opts?.zoomControl,
      zoomControl: opts?.zoomControl ?? true,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      styles: _darkStyle(),
      backgroundColor: '#0d1117',
    });
    const mapWrapper = {
      setView(latlng, zoom) {
        _gmap.setCenter({ lat: latlng[0], lng: latlng[1] });
        _gmap.setZoom(zoom);
        return mapWrapper;
      },
      panTo(latlng) {
        _gmap.panTo({ lat: latlng[0], lng: latlng[1] });
      },
      fitBounds(bounds, opts) {
        const padding = opts?.padding ? { top: opts.padding[0], right: opts.padding[1], bottom: opts.padding[0], left: opts.padding[1] } : 30;
        _gmap.fitBounds(bounds, padding);
      },
      _gmap,
    };
    return mapWrapper;
  },

  tileLayer(url, opts) {
    return { addTo() { return this; }, remove() {} };
  },

  layerGroup() {
    return new GLayerGroup();
  },

  polyline(path, opts) {
    return _wrapPolyline(path, opts || {});
  },

  circleMarker(pos, opts) {
    return _wrapCircle(pos, opts || {}, true);
  },

  circle(pos, opts) {
    return _wrapCircle(pos, opts || {}, false);
  },

  marker(pos, opts) {
    return _wrapMarker(pos, opts || {});
  },

  divIcon(opts) {
    return { ...opts, _isDivIcon: true };
  },
};

// ── Google Maps Dark Style ───────────────────────────────────────────────────
function _darkStyle() {
  return [
    { elementType: 'geometry', stylers: [{ color: '#0d1117' }] },
    { elementType: 'labels.text.stroke', stylers: [{ color: '#0d1117' }] },
    { elementType: 'labels.text.fill', stylers: [{ color: '#8b949e' }] },
    { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1c2128' }] },
    { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#6e7681' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#161b22' }] },
    { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#30363d' }] },
    { featureType: 'poi', stylers: [{ visibility: 'off' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] },
    { featureType: 'administrative', elementType: 'geometry.stroke', stylers: [{ color: '#30363d' }] },
    { featureType: 'landscape', elementType: 'geometry', stylers: [{ color: '#0d1117' }] },
  ];
}

function _lightStyle() {
  return [
    { elementType: 'geometry', stylers: [{ color: '#f6f8fa' }] },
    { elementType: 'labels.text.fill', stylers: [{ color: '#57606a' }] },
    { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#ffffff' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#d0d7de' }] },
    { featureType: 'poi', stylers: [{ visibility: 'off' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  ];
}

// Theme toggle helper — call from toggleTheme()
function setGMapTheme(isLight) {
  if (_gmap) {
    _gmap.setOptions({ styles: isLight ? _lightStyle() : _darkStyle() });
  }
}
