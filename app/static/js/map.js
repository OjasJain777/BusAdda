import { drawGeography, MAP_HEIGHT, MAP_WIDTH, project } from "./geography.js";
import { corridorPath } from "./route-geometry.js";
import { icon, svg } from "./ui.js";

export const legColors = ["#24d5b2", "#f3b564", "#a894ef", "#6fa7eb", "#ed8fa0", "#6bc4cd"];
const labelOffsets = {
  "Dwarka": [-10, 15, "end"], "Rohini": [-7, -9, "end"], "Pitampura": [8, 13],
  "Janakpuri": [-8, -8, "end"], "Punjabi Bagh": [-7, -8, "end"], "Rajouri Garden": [8, -9],
  "Karol Bagh": [-8, -9, "end"], "Connaught Place": [-8, 15, "end"], "Kashmiri Gate": [-9, -9, "end"],
  "AIIMS": [-8, 14, "end"], "Lajpat Nagar": [-8, -11, "end"], "Saket": [9, 5], "Vasant Vihar": [-7, -9, "end"],
  "India Gate": [-8, 14, "end"], "Noida Sector 15": [8, -8], "Anand Vihar": [8, -8],
  "Greater Noida": [-8, -9, "end"], "Faridabad": [9, 4],
  "Ghaziabad": [-8, -8, "end"], "Gurugram": [9, 4], "Laxmi Nagar": [8, -8], "Model Town": [-8, -8, "end"],
  "Dhaula Kuan": [-8, -9, "end"], "Hauz Khas": [-8, -9, "end"],
  "Kalkaji": [8, 14],
};

export class TransitMap {
  constructor(root, network, onStop, onBus, onService, onBackground) {
    this.root = root;
    this.points = new Map(network.stops.map((stop) => [stop.id, project(stop.lat, stop.lon)]));
    this.nodes = new Map();
    this.services = new Map();
    this.active = null;
    this.network = network;
    this.mode = "default";
    this.selected = new Set();
    this.selectedStops = new Set();
    this.journeyPoints = null;
    this.servicePoints = null;
    this.routeLinesVisible = true;
    this.home = project(28.618, 77.188);
    this.zoom = 1.12;
    this.center = [...this.home];
    this.fitButton = document.querySelector("#map-fit");
    this.focusToggle = document.querySelector("#journey-focus");

    const geo = svg("g", { class: "map-geography", "aria-hidden": "true" });
    const roadbeds = svg("g", { class: "corridor-roadbeds" });
    this.labelLayer = svg("g", { class: "locality-layer", "aria-hidden": "true" });
    drawGeography(geo, this.labelLayer);
    this.serviceLayer = svg("g", { class: "network-lines", "aria-label": "Bus route lines" });
    const roads = new Set();
    for (const service of network.services) {
      const direction = service.directions[0] || Object.values(service.directions)[0];
      const d = corridorPath(direction.projected);
      for (const [index, segment] of direction.projected.entries()) {
        const stops = [direction.stops[index], direction.stops[index + 1]].sort((a, b) => a - b).join("-");
        if (roads.has(stops)) continue;
        roads.add(stops);
        roadbeds.append(svg("path", { d: corridorPath([segment]), class: "geo-road" }));
      }
      const line = svg("g", { class: "network-service", role: "button", tabindex: "0",
        "aria-label": "Route " + service.number + " · " + service.name, "data-service": service.id });
      const title = svg("title");
      title.textContent = "Route " + service.number + " · " + service.name;
      const all = direction.projected.flatMap((segment) => segment.points);
      const [x, y] = all[Math.floor(all.length / 2)];
      const label = svg("text", { x, y: y - 9, class: "service-caption", "text-anchor": "middle" });
      label.textContent = service.number;
      line.append(title, svg("path", { d, class: "service-stroke", stroke: service.color }),
        svg("path", { d, class: "service-hit" }), label);
      this.activate(line, () => onService(service.id));
      this.services.set(service.id, line);
      this.serviceLayer.append(line);
    }
    this.routeLayer = svg("g", { "aria-hidden": "true" });
    this.stopLayer = svg("g", { class: "network-stops", "aria-label": "Bus stops" });
    const labels = this.labelLayer;
    this.labels = new Map();
    this.busLayer = svg("g", { class: "network-buses", "aria-label": "Simulated buses" });
    this.endpoints = svg("g", { class: "journey-endpoints", "aria-label": "Stops on your journey" });
    this.journeyMarker = svg("circle", { r: 7, class: "journey-vehicle", visibility: "hidden" });
    for (const stop of network.stops) {
      const [x, y] = this.points.get(stop.id);
      const hub = stop.services.length >= 3;
      const marker = svg("g", { transform: "translate(" + x + " " + y + ")", class: "stop-point" + (hub ? " hub" : ""),
        role: "button", tabindex: "0", "aria-label": stop.name + " bus stop" });
      const title = svg("title");
      title.textContent = stop.name + " · " + stop.locality;
      marker.append(title, svg("circle", { r: 8, class: "stop-hit" }), svg("circle", { r: hub ? 3.5 : 2.5, class: "stop-core" }));
      this.activate(marker, () => onStop(stop.id));
      this.stopLayer.append(marker);
      this.nodes.set(stop.id, marker);
      if (labelOffsets[stop.name]) {
        const [dx, dy, align] = labelOffsets[stop.name];
        const label = svg("text", { x: x + dx, y: y + dy, "text-anchor": align || "start", class: "stop-caption" });
        label.textContent = stop.name;
        labels.append(label);
        this.labels.set(stop.id, label);
      }
    }
    root.append(geo, roadbeds, this.serviceLayer, this.stopLayer, labels, this.busLayer, this.routeLayer, this.endpoints, this.journeyMarker);
    this.onStop = onStop;
    this.onBus = onBus;
    this.onBackground = onBackground;
    this.setInteraction();
    this.updateServices();
    this.updateView();
    new ResizeObserver(() => this.updateView()).observe(root);
  }

  activate(node, action) {
    node.addEventListener("click", (event) => {
      if (this.suppressClick) return;
      event.stopPropagation();
      action();
    });
    node.addEventListener("keydown", (event) => {
      if (["Enter", " "].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
        action();
      }
    });
  }

  dimensions() {
    const ratio = (this.root.clientWidth || MAP_WIDTH) / (this.root.clientHeight || MAP_HEIGHT);
    const width = Math.max(570, MAP_HEIGHT * ratio);
    return [width / this.zoom, width / ratio / this.zoom];
  }

  updateView() {
    const [w, h] = this.dimensions();
    this.root.setAttribute("viewBox", [this.center[0] - w / 2, this.center[1] - h / 2, w, h].join(" "));
  }

  reset() {
    this.focusPoint(this.home, 1.12);
  }

  fit(points) {
    if (!points?.length) return;
    const xs = points.map(([x]) => x), ys = points.map(([, y]) => y);
    const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    this.zoom = 1;
    const [width, height] = this.dimensions();
    this.focusPoint([(minX + maxX) / 2, (minY + maxY) / 2],
      Math.max(.48, Math.min(2, width / (maxX - minX + 126), height / (maxY - minY + 128))));
  }

  setZoom(factor, x, y) {
    const prior = this.zoom;
    this.zoom = Math.max(.48, Math.min(4, prior * factor));
    if (x !== undefined) {
      this.center = [x + (this.center[0] - x) * prior / this.zoom, y + (this.center[1] - y) * prior / this.zoom];
    }
    this.updateView();
  }

  focusPoint(point, zoom = 1.75) {
    this.center = [...point];
    this.zoom = zoom;
    this.updateView();
  }

  setInteraction() {
    const node = this.root;
    document.querySelector("#zoom-in").addEventListener("click", () => this.setZoom(1.25));
    document.querySelector("#zoom-out").addEventListener("click", () => this.setZoom(.8));
    document.querySelector("#map-reset").addEventListener("click", () => this.reset());
    this.focusToggle.addEventListener("click", () => this.setJourneyFocus(!this.root.classList.contains("route-focus")));
    this.fitButton.addEventListener("click", () => this.fit(this.journeyPoints || this.servicePoints));
    node.addEventListener("wheel", (event) => {
      event.preventDefault();
      const pt = new DOMPoint(event.clientX, event.clientY).matrixTransform(node.getScreenCTM().inverse());
      this.setZoom(event.deltaY < 0 ? 1.15 : .87, pt.x, pt.y);
    }, { passive: false });
    node.addEventListener("keydown", (event) => {
      const moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      if (moves[event.key]) {
        event.preventDefault();
        this.center = this.center.map((v, i) => v + moves[event.key][i] * 30 / this.zoom);
        this.updateView();
      } else if (["+", "=", "-"].includes(event.key)) {
        event.preventDefault();
        this.setZoom(event.key === "-" ? .8 : 1.25);
      }
    });
    const contacts = new Map();
    node.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      this.suppressClick = false;
      contacts.set(event.pointerId, [event.clientX, event.clientY]);
    });
    node.addEventListener("pointermove", (event) => {
      if (!contacts.has(event.pointerId)) return;
      const [lastX, lastY] = contacts.get(event.pointerId);
      const dx = event.clientX - lastX, dy = event.clientY - lastY;
      if (!this.suppressClick && contacts.size === 1 && Math.hypot(dx, dy) < 4) return;
      contacts.set(event.pointerId, [event.clientX, event.clientY]);
      node.setPointerCapture(event.pointerId);
      this.suppressClick = true;
      const matrix = node.getScreenCTM();
      if (contacts.size === 2) {
        const [otherX, otherY] = [...contacts].find(([id]) => id !== event.pointerId)[1];
        const before = Math.hypot(lastX - otherX, lastY - otherY);
        const after = Math.hypot(event.clientX - otherX, event.clientY - otherY);
        const midpoint = new DOMPoint((event.clientX + otherX) / 2, (event.clientY + otherY) / 2).matrixTransform(matrix.inverse());
        if (before > 0 && after > 0) this.setZoom(after / before, midpoint.x, midpoint.y);
      } else {
        node.classList.add("dragging");
        this.center = [this.center[0] - dx / matrix.a, this.center[1] - dy / matrix.d];
        this.updateView();
      }
    });
    const release = (event) => {
      contacts.delete(event.pointerId);
      if (!contacts.size) node.classList.remove("dragging");
    };
    node.addEventListener("pointerup", release);
    node.addEventListener("pointercancel", release);
    node.addEventListener("pointerleave", (event) => {
      if (!node.hasPointerCapture(event.pointerId)) release(event);
    });
    node.addEventListener("click", () => { if (!this.suppressClick) this.onBackground(); });
  }

  highlightStop(id, focus = false) {
    this.active?.classList.remove("focused");
    this.active = this.endpoints.querySelector('[data-stop="' + id + '"]') || this.nodes.get(id);
    this.active?.classList.add("focused");
    if (focus) this.focusPoint(this.points.get(id));
  }

  serviceSelection(ids, mode = this.mode) {
    this.selected = new Set(ids);
    this.mode = mode;
    this.selectedStops = new Set();
    this.servicePoints = [];
    for (const id of ids) {
      const service = this.network.byService.get(id);
      const direction = service.directions[0] || Object.values(service.directions)[0];
      direction.stops.forEach((stopId) => this.selectedStops.add(stopId));
      this.servicePoints.push(...direction.projected.flatMap((segment) => segment.points));
      this.serviceLayer.append(this.services.get(id));
    }
    this.updateServices();
    this.updateStops();
    this.fitButton.hidden = !this.journeyPoints && (!this.servicePoints.length || this.mode === "none" || !this.routeLinesVisible);
  }

  setLayer(layer, visible) {
    if (layer === "routes") {
      this.routeLinesVisible = visible;
      this.updateServices();
      this.fitButton.hidden = !this.journeyPoints && (!visible || !this.servicePoints?.length || this.mode === "none");
    } else if (layer === "stops") {
      this.stopLayer.classList.toggle("layer-off", !visible);
      this.updateStops();
    } else if (layer === "labels") {
      this.labelLayer.classList.toggle("layer-off", !visible);
    }
  }

  updateServices() {
    this.services.forEach((line, id) => {
      const selected = this.selected.has(id);
      const visible = this.routeLinesVisible && this.mode !== "none" &&
        (this.mode !== "selected" || selected);
      line.classList.toggle("focused", selected);
      line.classList.toggle("subdued", this.selected.size > 0 && !selected);
      line.classList.toggle("show-all", this.mode === "all");
      line.classList.toggle("layer-off", !visible);
      const interactive = visible && !this.root.classList.contains("has-route");
      line.setAttribute("aria-hidden", String(!interactive));
      line.setAttribute("tabindex", interactive ? "0" : "-1");
    });
    for (const marker of this.busLayer.children) {
      marker.classList.toggle("service-focus", this.selected.has(Number(marker.dataset.service)));
    }
  }

  updateStops() {
    const hidden = this.stopLayer.classList.contains("layer-off");
    this.nodes.forEach((marker, id) => {
      const selected = this.selectedStops.has(id);
      marker.classList.toggle("service-stop", selected);
      marker.setAttribute("tabindex", hidden ? "-1" : "0");
    });
  }

  addBus(vehicle, service) {
    const marker = svg("g", { class: "bus-marker", tabindex: "0", role: "button",
      "aria-label": "Simulated bus " + vehicle.label, "data-service": service.id });
    const graphic = icon("bus", 13);
    graphic.setAttribute("x", "-6.5");
    graphic.setAttribute("y", "-6.5");
    graphic.setAttribute("class", "bus-glyph");
    marker.append(svg("rect", { x: -9, y: -9, width: 18, height: 18, class: "bus-ring", fill: service.color }), graphic);
    this.activate(marker, () => this.onBus(vehicle.id));
    this.busLayer.append(marker);
    return marker;
  }

  setJourneyFocus(focus) {
    this.root.classList.toggle("route-focus", focus);
    this.focusToggle.setAttribute("aria-pressed", String(focus));
  }

  drawRoute(journey, network, access = {}) {
    this.routeLayer.replaceChildren();
    this.endpoints.replaceChildren();
    this.root.classList.toggle("has-route", Boolean(journey));
    this.updateServices();
    this.focusToggle.hidden = !journey;
    this.setJourneyFocus(Boolean(journey));
    const endpoints = new Set(journey?.stops || []);
    this.labels.forEach((label, id) => label.setAttribute("visibility", endpoints.has(id) ? "hidden" : "visible"));
    this.journeyPoints = journey ? [] : null;
    this.fitButton.hidden = !journey && !this.servicePoints?.length;
    if (!journey) return;
    for (const endpoint of [access.from, access.to]) {
      if (!endpoint?.coordinates || endpoint.km < .05) continue;
      const point = project(endpoint.coordinates.lat, endpoint.coordinates.lon);
      const [x, y] = point;
      const [stopX, stopY] = this.points.get(endpoint.stop.id);
      this.routeLayer.append(svg("line", { x1: x, y1: y, x2: stopX, y2: stopY, class: "journey-connector" }));
      this.endpoints.append(svg("circle", { cx: x, cy: y, r: 4, class: "journey-place" }));
      this.journeyPoints.push(point);
    }
    const strokes = [];
    for (const [index, leg] of journey.legs.entries()) {
      const direction = network.byService.get(leg.service).directions[leg.direction];
      const begin = direction.stops.indexOf(leg.from);
      const segments = direction.projected.slice(begin, begin + leg.stops.length - 1);
      const d = corridorPath(segments);
      this.journeyPoints.push(...segments.flatMap((segment) => segment.points));
      this.routeLayer.append(svg("path", { d, class: "route-halo" }));
      strokes.push(svg("path", {
        d, class: "journey-leg-line", stroke: legColors[index % legColors.length],
        "data-color": index % legColors.length,
      }));
    }
    this.routeLayer.append(...strokes);
    const transfers = new Set(journey.interchanges);
    for (const id of new Set(journey.stops)) {
      const [cx, cy] = this.points.get(id);
      const kind = id === journey.source ? "from" : id === journey.destination ? "to"
        : transfers.has(id) ? "interchange" : "intermediate";
      const stop = network.byStop.get(id);
      const marker = svg("g", {
        class: "journey-stop-control", tabindex: "0", role: "button",
        "data-stop": id, "aria-label": stop.name + " journey stop",
      });
      const title = svg("title");
      title.textContent = stop.name;
      const hit = svg("circle", { cx, cy, r: 11, class: "journey-stop-hit" });
      const point = kind === "interchange"
        ? svg("rect", { x: cx - 5, y: cy - 5, width: 10, height: 10, rx: 2,
          transform: "rotate(45 " + cx + " " + cy + ")", class: "route-point interchange" })
        : svg("circle", { cx, cy, r: kind === "intermediate" ? 3.5 : 6.5,
          class: kind === "intermediate" ? "journey-stop" : "route-point " + kind });
      marker.append(title, hit, point);
      this.activate(marker, () => this.onStop(id));
      this.endpoints.append(marker);
      if (kind === "intermediate") continue;
      const [dx, dy, anchor] = labelOffsets[stop.name] || [9, -12, "start"];
      const label = svg("text", { x: cx + dx, y: cy + dy, class: "route-caption",
        "text-anchor": anchor || "start" });
      label.textContent = stop.name;
      marker.append(label);
    }
    this.fit(this.journeyPoints);
  }
}
