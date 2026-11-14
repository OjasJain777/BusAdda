function normalize(value) {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase()
    .replace(/[’']/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}

export function haversineKm(latA, lonA, latB, lonB) {
  const radians = Math.PI / 180;
  const a = Math.sin((latB - latA) * radians / 2) ** 2 +
    Math.cos(latA * radians) * Math.cos(latB * radians) *
    Math.sin((lonB - lonA) * radians / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))));
}

function nearestStop(lat, lon, stops) {
  let best = null;
  for (const stop of stops) {
    const km = haversineKm(lat, lon, stop.lat, stop.lon);
    if (best === null || km < best.km) best = { stop, km };
  }
  return best;
}

function matchScore(name, query, words) {
  if (name === query) return 0;
  if (name.startsWith(query)) return 2;
  if (words.every((word) => name.split(" ").some((part) => part.startsWith(word)))) return 4;
  return name.includes(query) ? 6 : Infinity;
}

export function createPlaceSearch(stops, catalog) {
  const active = stops.filter((stop) => stop.services.length);
  const stopNames = new Set(active.map((stop) => normalize(stop.name)));
  const places = catalog.filter(([name]) => !stopNames.has(normalize(name)))
    .map(([name, lat, lon, aliases]) => ({ name, lat, lon, terms: [name, ...aliases].map(normalize) }));

  return (input) => {
    const coordinates = input.trim().match(/^(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)$/);
    if (coordinates) {
      const [, latitude, longitude] = coordinates;
      const lat = Number(latitude), lon = Number(longitude);
      if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return [];
      const near = nearestStop(lat, lon, active);
      return near && near.km <= 25 ? [{ ...near, place: lat + ", " + lon, coordinates: { lat, lon }, exact: true }] : [];
    }
    const query = normalize(input);
    if (!query) return active.slice(0, 7).map((stop) => ({ stop }));
    const words = query.split(" ");
    const candidates = [];
    for (const stop of active) {
      const score = Math.min(matchScore(normalize(stop.name), query, words),
        matchScore(normalize(stop.locality), query, words) + 7);
      if (Number.isFinite(score)) candidates.push({ stop, score, exact: score === 0 });
    }
    if (query.length >= 2) {
      for (const place of places) {
        const score = Math.min(...place.terms.map((term) => matchScore(term, query, words))) + 1;
        if (Number.isFinite(score)) candidates.push({ place: place.name, coordinates: place, score });
      }
    }
    const label = (result) => result.place || result.stop.name;
    candidates.sort((a, b) => a.score - b.score || label(a).localeCompare(label(b)));
    const seen = new Set();
    const results = [];
    for (const candidate of candidates) {
      const place = candidate.coordinates;
      const result = place ? { ...nearestStop(place.lat, place.lon, active), place: place.name, coordinates: place, exact: candidate.score === 1 } : candidate;
      if (!result.stop) continue;
      const key = normalize(label(result)) + ":" + result.stop.id;
      if (seen.has(key)) continue;
      seen.add(key);
      results.push(result);
      if (results.length === 8) break;
    }
    return results;
  };
}

export function stopDistance(km) {
  return km < 1 ? Math.round(km * 1000) + " m" : km.toFixed(1) + " km";
}
